"""声学帧级特征表示：F0、RMS、ZCR 与谱特征。

输出协议：

- 帧级特征堆叠为 ``inputs["features"]`` ``[T, D]``（layout ``TD``），
  仅当各帧级特征时间长度一致时堆叠；不一致时抛出
  ``RepresentationError``，禁止在 Dataset 中无条件插值或裁剪“凑齐”长度
  （设计文档 §2.4）。需要不等长时间轴时，请用多个独立的
  ``AcousticFeatures`` 子表示通过 :class:`CompositeRepresentation` 组合。
- ``delta`` 暂不提供：历史实现直接对原始 waveform 计算采样点级差分，不能
  冒充 MFCC/Log-Mel 等帧级声学特征的 delta。
- ``jitter_shimmer_hnr`` 暂不提供：历史实现只真实计算 jitter，却把 shimmer/HNR
  返回为 0。公共配置显式拒绝这些未经数值参考验证的输出。
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio

from ser_lib.config.representations import AcousticFeaturesConfig
from ser_lib.foundation.errors import RepresentationError
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.representations.base import Representation
from ser_lib.data.types import (
    LAYOUT_TD,
    AudioData,
    RepresentationOutput,
    TensorSpec,
)

_FRAME_FEATURE_DIMS: dict[str, int] = {
    "f0": 1,
    "rms": 1,
    "zcr": 1,
    "spectral_centroid": 1,
    "spectral_rolloff": 1,
    "spectral_flatness": 1,
    "spectral_flux": 1,
}


class _FrameFeature(nn.Module):
    """帧级特征基类：输入 [1, T]，输出 [T_f] 或 [T_f, D]。"""

    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError


class _PitchF0(_FrameFeature):
    """基于 torchaudio NCCF 的 F0；0 表示 unvoiced。

    ``detect_pitch_frequency.win_length`` 的单位是中值平滑的帧数，不是音频
    采样点。这里使用 3 帧窗口。静音直接返回全 0；不足两个分析帧的极短输入
    返回单个 unvoiced frame，避免底层中值窗口无法展开导致运行时异常。
    """

    _SMOOTHING_FRAMES = 3

    def __init__(self, sample_rate: int, hop_length: int) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.hop_length = hop_length

    def _analysis_frame_count(self, sample_count: int) -> int:
        return max(math.ceil(sample_count / self.hop_length), 1)

    def _unvoiced_output(self, waveform: torch.Tensor, frame_count: int) -> torch.Tensor:
        output_frames = max(frame_count - self._SMOOTHING_FRAMES // 2, 1)
        return torch.zeros(
            output_frames,
            dtype=waveform.dtype,
            device=waveform.device,
        )

    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        sample_count = int(waveform.shape[-1])
        if sample_count == 0:
            raise ValueError("F0 输入 waveform 不能为空")
        frame_count = self._analysis_frame_count(sample_count)
        if frame_count < 2 or not bool(torch.any(waveform != 0)):
            return self._unvoiced_output(waveform, frame_count)

        pitch = torchaudio.functional.detect_pitch_frequency(
            waveform,
            sample_rate=self.sample_rate,
            frame_time=self.hop_length / self.sample_rate,
            win_length=self._SMOOTHING_FRAMES,
            freq_low=50,
            freq_high=800,
        )
        return pitch[0]


class _RMS(_FrameFeature):
    def __init__(self, win_length: int, hop_length: int) -> None:
        super().__init__()
        self.pool = nn.AvgPool1d(
            kernel_size=win_length, stride=hop_length, padding=win_length // 2
        )

    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        x = waveform.unsqueeze(1)
        rms = torch.sqrt(self.pool(x ** 2) + 1e-8)
        return rms[0, 0]


class _ZeroCrossingRate(_FrameFeature):
    def __init__(self, win_length: int, hop_length: int) -> None:
        super().__init__()
        self.pool = nn.AvgPool1d(
            kernel_size=win_length, stride=hop_length, padding=win_length // 2
        )

    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        signs = torch.sign(waveform)
        diffs = torch.abs(signs[:, 1:] - signs[:, :-1])
        diffs = F.pad(diffs, (1, 0)).unsqueeze(1)
        zcr = 0.5 * self.pool(diffs)
        return zcr[0, 0]


class _StftFeature(_FrameFeature):
    """基于 STFT 幅度谱的帧级特征公共基类。"""

    _window: torch.Tensor
    _freqs: torch.Tensor

    def __init__(self, sample_rate: int, n_fft: int, hop_length: int) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.register_buffer("_window", torch.hann_window(n_fft), persistent=False)
        freqs = torch.linspace(0, sample_rate / 2, n_fft // 2 + 1)
        self.register_buffer("_freqs", freqs, persistent=False)

    def _magnitude(self, waveform: torch.Tensor) -> torch.Tensor:
        return torch.stft(
            waveform,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window=self._window.to(waveform.device),
            return_complex=True,
        ).abs()

    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError


class _SpectralCentroid(_StftFeature):
    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        S = self._magnitude(waveform)
        freqs = self._freqs.to(waveform.device).unsqueeze(-1)
        centroid = torch.sum(S * freqs, dim=-2) / (torch.sum(S, dim=-2) + 1e-8)
        return centroid[0]


class _SpectralRolloff(_StftFeature):
    def __init__(
        self,
        sample_rate: int,
        n_fft: int,
        hop_length: int,
        roll_percent: float,
    ) -> None:
        super().__init__(sample_rate, n_fft, hop_length)
        self.roll_percent = roll_percent

    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        S = self._magnitude(waveform)
        total = torch.sum(S, dim=-2, keepdim=True)
        threshold = total * self.roll_percent
        mask = torch.cumsum(S, dim=-2) >= threshold
        idx = torch.argmax(mask.to(torch.int8), dim=-2)
        freqs = self._freqs.to(waveform.device)
        return freqs[idx][0]


class _SpectralFlatness(_StftFeature):
    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        S = self._magnitude(waveform)
        power = S ** 2 + 1e-10
        gmean = torch.exp(torch.mean(torch.log(power), dim=-2))
        amean = torch.mean(power, dim=-2)
        return (gmean / (amean + 1e-10))[0]


class _SpectralFlux(_StftFeature):
    def compute(self, waveform: torch.Tensor) -> torch.Tensor:
        S = self._magnitude(waveform)
        diff = F.relu(S[..., 1:] - S[..., :-1])
        flux = torch.sum(diff ** 2, dim=-2)
        return F.pad(flux, (1, 0))[0]


class _JitterShimmerHNR(nn.Module):
    """退役的历史 helper；禁止继续返回未实现的 shimmer/HNR 占位值。"""

    def compute(self, waveform: torch.Tensor, pitch: torch.Tensor) -> torch.Tensor:
        _ = waveform, pitch
        raise NotImplementedError(
            "jitter_shimmer_hnr 暂不可用：shimmer 与 HNR 尚无经过数值参考验证的实现"
        )


class AcousticFeatures(Representation):
    """声学帧级特征表示（详见模块 docstring 的输出协议）。"""

    descriptor = ComponentDescriptor(
        id="acoustic_features",
        display_name="声学特征",
        category="representation",
        description="帧级声学特征 (f0/rms/zcr/spectral_*) 堆叠为 [T, D]；"
        "delta 与未经验证的 jitter/shimmer/HNR 暂不开放。",
        config_schema=AcousticFeaturesConfig.model_json_schema(),
    )

    def __init__(self, **params) -> None:
        config = AcousticFeaturesConfig(**params)
        super().__init__()
        self.config = config
        self._expected_sample_rate = config.sample_rate

        self._frame_modules: dict[str, _FrameFeature] = {}
        for name in config.features:
            if name == "f0":
                self._frame_modules[name] = _PitchF0(config.sample_rate, config.hop_length)
            elif name == "rms":
                self._frame_modules[name] = _RMS(config.win_length, config.hop_length)
            elif name == "zcr":
                self._frame_modules[name] = _ZeroCrossingRate(config.win_length, config.hop_length)
            elif name == "spectral_centroid":
                self._frame_modules[name] = _SpectralCentroid(
                    config.sample_rate, config.n_fft, config.hop_length
                )
            elif name == "spectral_rolloff":
                self._frame_modules[name] = _SpectralRolloff(
                    config.sample_rate,
                    config.n_fft,
                    config.hop_length,
                    config.roll_percent,
                )
            elif name == "spectral_flatness":
                self._frame_modules[name] = _SpectralFlatness(
                    config.sample_rate, config.n_fft, config.hop_length
                )
            elif name == "spectral_flux":
                self._frame_modules[name] = _SpectralFlux(
                    config.sample_rate, config.n_fft, config.hop_length
                )

        self._feature_modules = nn.ModuleDict(
            {f"feat_{key}": value for key, value in self._frame_modules.items()}
        )

    @property
    def output_specs(self) -> dict[str, TensorSpec]:
        specs: dict[str, TensorSpec] = {}
        if self._frame_names:
            feature_dim = sum(_FRAME_FEATURE_DIMS[name] for name in self._frame_names)
            specs["features"] = TensorSpec(layout=LAYOUT_TD, feature_dim=feature_dim)
        return specs

    @property
    def _frame_names(self) -> list[str]:
        return [name for name in self.config.features if name in _FRAME_FEATURE_DIMS]

    def forward(self, audio: AudioData) -> RepresentationOutput:
        self._require_mono(audio)
        self._require_sample_rate(audio)
        waveform = audio.waveform

        inputs: dict[str, torch.Tensor] = {}
        lengths: dict[str, int] = {}

        frame_tensors: list[torch.Tensor] = []
        if self._frame_names:
            computed: dict[str, torch.Tensor] = {}
            for name in self._frame_names:
                value = self._frame_modules[name].compute(waveform)
                if value.dim() == 1:
                    value = value.unsqueeze(-1)
                computed[name] = value
                frame_tensors.append(value)

            ref = frame_tensors[0].shape[0]
            mismatched = {
                name: value.shape[0]
                for name, value in computed.items()
                if value.shape[0] != ref
            }
            if mismatched:
                raise RepresentationError(
                    f"帧级特征时间长度不一致: {mismatched}（参考帧数 {ref}）。"
                    "禁止自动插值或裁剪对齐；如需不等长时间轴，请将各特征拆分为"
                    "独立的 AcousticFeatures 子表示并通过 CompositeRepresentation 组合",
                    path=audio.source_path,
                    component=self.descriptor.id,
                    stage="representation",
                )
            features = torch.cat(frame_tensors, dim=-1)
            inputs["features"] = features
            lengths["features"] = int(features.shape[0])

        return RepresentationOutput(inputs=inputs, lengths=lengths)
