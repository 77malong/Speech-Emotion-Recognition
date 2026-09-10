"""与设备和 UI 无关的纯 PCM 流式 SER 核心。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import torch
import torchaudio

from ser_lib.config.inference import StreamingConfig
from ser_lib.data.types import AudioData
from ser_lib.inference.offline import EmotionPredictor, PredictionResult


@dataclass(frozen=True, slots=True)
class StreamingPrediction:
    sequence: int
    start_ms: float
    end_ms: float
    silent: bool
    rms: float
    prediction: PredictionResult | None


@dataclass(frozen=True, slots=True)
class StreamingLatency:
    window_ms: float
    hop_ms: float
    resampler_lookahead_ms: float
    first_result_ms: float


class _LinearResampler:
    """历史私有名称下的有状态带限 sinc 重采样器。

    实际滤波由 ``torchaudio.functional.resample`` 完成。流式状态只保留有限左右
    上下文，并把可丢弃 buffer 起点对齐到源/目标采样率的有理相位周期，因此不同
    chunk 切分得到相同的全局输出相位，同时避免逐输出采样点的 Python 插值循环。

    非 final push 会保留一个保守的右侧滤波 lookahead；flush 时再输出尾部。这个
    lookahead 同时是流式重采样相对纯采样窗口增加的算法延迟。
    """

    _FILTER_WIDTH = 6
    _ROLLOFF = 0.99

    def __init__(self, source_rate: int, target_rate: int) -> None:
        if source_rate <= 0 or target_rate <= 0:
            raise ValueError("source_rate/target_rate 必须为正")
        self.source_rate = int(source_rate)
        self.target_rate = int(target_rate)
        divisor = math.gcd(self.source_rate, self.target_rate)
        self._phase_period = self.source_rate // divisor
        if self.source_rate == self.target_rate:
            self.lookahead_samples = 0
        else:
            base_rate = min(self.source_rate, self.target_rate) * self._ROLLOFF
            self.lookahead_samples = max(
                1,
                math.ceil(self._FILTER_WIDTH * self.source_rate / base_rate),
            )
        self._buffer = torch.empty(0, dtype=torch.float32)
        self._buffer_start = 0
        self._input_count = 0
        self._output_count = 0

    @property
    def buffered_input_samples(self) -> int:
        return int(self._buffer.numel())

    def _target_output_count(self, source_count: int) -> int:
        if source_count <= 0:
            return 0
        return math.ceil(source_count * self.target_rate / self.source_rate)

    def _stable_output_count(self, *, final: bool) -> int:
        if final:
            return self._target_output_count(self._input_count)
        stable_source = max(self._input_count - self.lookahead_samples, 0)
        return self._target_output_count(stable_source)

    def _resample_buffer(self) -> torch.Tensor:
        if not self._buffer.numel():
            return torch.empty(0, dtype=torch.float32)
        if self.source_rate == self.target_rate:
            return self._buffer
        return torchaudio.functional.resample(
            self._buffer,
            self.source_rate,
            self.target_rate,
            lowpass_filter_width=self._FILTER_WIDTH,
            rolloff=self._ROLLOFF,
        )

    def _discard_consumed_left_context(self) -> None:
        if self.source_rate == self.target_rate:
            discard_until = self._input_count
        else:
            next_source = (
                self._output_count * self.source_rate // self.target_rate
            )
            desired_start = max(next_source - self.lookahead_samples, 0)
            discard_until = (
                desired_start // self._phase_period
            ) * self._phase_period
        discard_until = min(discard_until, self._input_count)
        discard = discard_until - self._buffer_start
        if discard > 0:
            self._buffer = self._buffer[discard:]
            self._buffer_start = discard_until

    def push(self, samples: torch.Tensor, *, final: bool = False) -> torch.Tensor:
        values = torch.as_tensor(samples, dtype=torch.float32).reshape(-1).cpu()
        if values.numel():
            self._buffer = torch.cat((self._buffer, values))
            self._input_count += int(values.numel())

        if self.source_rate == self.target_rate:
            if not self._buffer.numel():
                return torch.empty(0, dtype=torch.float32)
            output = self._buffer.clone()
            self._output_count += int(output.numel())
            self._buffer = torch.empty(0, dtype=torch.float32)
            self._buffer_start = self._input_count
            return output

        stop = self._stable_output_count(final=final)
        start = self._output_count
        if stop <= start:
            return torch.empty(0, dtype=torch.float32)

        if self._buffer_start % self._phase_period != 0:
            raise RuntimeError("streaming resampler buffer 相位未对齐")
        output_offset = self._buffer_start * self.target_rate // self.source_rate
        local_start = start - output_offset
        local_stop = stop - output_offset
        if local_start < 0:
            raise RuntimeError("streaming resampler 丢失了必要的左侧滤波上下文")

        local_output = self._resample_buffer()
        if local_stop > int(local_output.numel()):
            raise RuntimeError("streaming resampler 右侧滤波上下文不足")
        output = local_output[local_start:local_stop].clone()
        self._output_count = stop
        if final:
            self._buffer = torch.empty(0, dtype=torch.float32)
            self._buffer_start = self._input_count
        else:
            self._discard_consumed_left_context()
        return output

    def reset(self) -> None:
        self._buffer = torch.empty(0, dtype=torch.float32)
        self._buffer_start = 0
        self._input_count = 0
        self._output_count = 0


class StreamingEmotionRecognizer:
    """同步消费 PCM，并为每个完整窗口返回一次预测。"""

    def __init__(self, predictor: EmotionPredictor, config: StreamingConfig) -> None:
        self.predictor = predictor
        self.config = config
        self.target_rate = predictor.audio_loader.config.target_sample_rate
        self.window_samples = round(config.window_ms * self.target_rate / 1000)
        self.hop_samples = round(config.hop_ms * self.target_rate / 1000)
        if self.window_samples < 1 or self.hop_samples < 1:
            raise ValueError("window_ms/hop_ms 在目标采样率下不足一个采样点")
        self._resampler = _LinearResampler(
            config.input_sample_rate, self.target_rate
        )
        self._buffer = torch.empty(0, dtype=torch.float32)
        self._consumed = 0
        self._sequence = 0
        self._smoothed: torch.Tensor | None = None
        self._closed = False
        self._flushed = False

    @property
    def buffered_samples(self) -> int:
        return int(self._buffer.numel())

    @property
    def latency(self) -> StreamingLatency:
        lookahead = (
            self._resampler.lookahead_samples
            * 1000.0
            / self.config.input_sample_rate
        )
        return StreamingLatency(
            float(self.config.window_ms),
            float(self.config.hop_ms),
            lookahead,
            float(self.config.window_ms) + lookahead,
        )

    def push_pcm(
        self, pcm: torch.Tensor | Sequence[float]
    ) -> list[StreamingPrediction]:
        if self._closed:
            raise RuntimeError("流式会话已关闭")
        if self._flushed:
            raise RuntimeError("流式会话已 flush；请 reset 后再输入")
        samples = torch.as_tensor(pcm, dtype=torch.float32)
        if samples.dim() == 2:
            samples = samples.mean(dim=0)
        if samples.dim() != 1:
            raise ValueError("PCM 必须是 [T] 或 [C,T]")
        if not torch.isfinite(samples).all():
            raise ValueError("PCM 包含 NaN/Inf")
        maximum = round(
            self.config.max_chunk_ms * self.config.input_sample_rate / 1000
        )
        if samples.numel() > maximum:
            raise BufferError(
                f"PCM chunk 超过 max_chunk_ms={self.config.max_chunk_ms}"
            )
        converted = self._resampler.push(samples.contiguous())
        if converted.numel():
            self._buffer = torch.cat((self._buffer, converted))
        return self._drain()

    def flush(self, *, pad_final: bool = False) -> list[StreamingPrediction]:
        if self._closed or self._flushed:
            return []
        self._flushed = True
        tail = self._resampler.push(torch.empty(0), final=True)
        if tail.numel():
            self._buffer = torch.cat((self._buffer, tail))
        results = self._drain()
        if pad_final and self._buffer.numel():
            self._buffer = torch.nn.functional.pad(
                self._buffer, (0, self.window_samples - self._buffer.numel())
            )
            results.extend(self._drain())
            self._buffer = torch.empty(0, dtype=torch.float32)
        return results

    def _drain(self) -> list[StreamingPrediction]:
        results = []
        while self._buffer.numel() >= self.window_samples:
            window = self._buffer[: self.window_samples]
            results.append(self._predict_window(window))
            self._buffer = self._buffer[self.hop_samples :]
            self._consumed += self.hop_samples
        return results

    def _predict_window(self, window: torch.Tensor) -> StreamingPrediction:
        rms = float(window.square().mean().sqrt())
        silent = rms <= self.config.silence_rms_threshold
        prediction = None
        uid = f"stream-{self._sequence:08d}"
        if not (silent and self.config.suppress_silence):
            audio = AudioData(
                waveform=window.unsqueeze(0),
                sample_rate=self.target_rate,
                source_path=Path("<stream>"),
                original_sample_rate=self.target_rate,
                num_frames=self.window_samples,
            )
            raw = self.predictor.predict_audio(audio, uid=uid)
            probabilities = torch.tensor(raw.probabilities)
            alpha = self.config.smoothing_alpha
            self._smoothed = (
                probabilities
                if self._smoothed is None
                else alpha * probabilities + (1 - alpha) * self._smoothed
            )
            label_id = int(self._smoothed.argmax())
            prediction = PredictionResult(
                uid,
                label_id,
                self.predictor.labels.get(label_id, str(label_id)),
                float(self._smoothed[label_id]),
                self._smoothed.tolist(),
            )
        result = StreamingPrediction(
            sequence=self._sequence,
            start_ms=self._consumed * 1000.0 / self.target_rate,
            end_ms=(self._consumed + self.window_samples) * 1000.0 / self.target_rate,
            silent=silent,
            rms=rms,
            prediction=prediction,
        )
        self._sequence += 1
        return result

    def reset(self) -> None:
        if self._closed:
            raise RuntimeError("流式会话已关闭")
        self._resampler.reset()
        self._buffer = torch.empty(0, dtype=torch.float32)
        self._consumed = 0
        self._sequence = 0
        self._smoothed = None
        self._flushed = False

    def close(self) -> None:
        self._buffer = torch.empty(0, dtype=torch.float32)
        self._smoothed = None
        self._closed = True


__all__ = [
    "StreamingConfig",
    "StreamingPrediction",
    "StreamingLatency",
    "StreamingEmotionRecognizer",
]
