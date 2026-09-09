"""AudioLoader：音频解码、片段读取、声道转换与重采样（设计文档 §7）。

执行顺序（§7.2）::

    解析并验证最终路径 → 读取音频元信息 → 毫秒片段转 frame offset
    → 只读取目标片段 → 校验非空且有限值 → 声道转换 → 重采样
    → 可选确定性归一化 → 返回 [C, T] float32

文件 I/O 默认使用 SoundFile。旧配置中的 ``backend='torchaudio'`` 仍然受支持，
并在 TorchAudio I/O backend 不可用时自动回退到 SoundFile。重采样继续使用
TorchAudio，不依赖其文件解码 backend。
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf
import torch
import torchaudio
import torchaudio.transforms as T

from ser_lib.config.data import AudioBackend, AudioConfig
from ser_lib.data.errors import (
    AudioDecodeError,
    AudioNotFoundError,
    InvalidAudioSegmentError,
    SERDataError,
)
from ser_lib.data.types import AudioData, AudioRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AudioFileInfo:
    """与具体解码库无关的稳定音频 header 信息。"""

    sample_rate: int
    num_frames: int
    num_channels: int
    backend: AudioBackend


def _probe_soundfile(path: Path) -> AudioFileInfo:
    info = sf.info(str(path))
    return AudioFileInfo(
        sample_rate=int(info.samplerate),
        num_frames=int(info.frames),
        num_channels=int(info.channels),
        backend="soundfile",
    )


def _probe_torchaudio(path: Path) -> AudioFileInfo:
    info = torchaudio.info(str(path))
    return AudioFileInfo(
        sample_rate=int(info.sample_rate),
        num_frames=int(info.num_frames),
        num_channels=int(info.num_channels),
        backend="torchaudio",
    )


def probe_audio(
    path: Path | str,
    *,
    preferred_backend: AudioBackend = "soundfile",
) -> AudioFileInfo:
    """读取音频 header；TorchAudio 不可用时透明回退到 SoundFile。

    该函数只读取元信息，不解码整段音频，可供数据扫描和 profiling 共用。
    """
    resolved = Path(path)
    if preferred_backend == "soundfile":
        return _probe_soundfile(resolved)
    if preferred_backend != "torchaudio":
        raise ValueError(f"不支持的音频后端: {preferred_backend!r}")
    try:
        return _probe_torchaudio(resolved)
    except Exception as torchaudio_exc:  # noqa: BLE001 - backend 异常类型不稳定
        try:
            return _probe_soundfile(resolved)
        except Exception as soundfile_exc:  # noqa: BLE001
            raise RuntimeError(
                "TorchAudio 与 SoundFile 均无法读取音频元信息；"
                f"torchaudio={torchaudio_exc}; soundfile={soundfile_exc}"
            ) from soundfile_exc


def _decode_soundfile(
    path: Path,
    *,
    frame_offset: int,
    num_frames: int,
) -> tuple[torch.Tensor, int]:
    frames = -1 if num_frames < 0 else num_frames
    data, sample_rate = sf.read(
        str(path),
        start=frame_offset,
        frames=frames,
        dtype="float32",
        always_2d=True,
    )
    waveform = torch.from_numpy(data.T.copy())
    return waveform, int(sample_rate)


def _decode_torchaudio(
    path: Path,
    *,
    frame_offset: int,
    num_frames: int,
) -> tuple[torch.Tensor, int]:
    waveform, sample_rate = torchaudio.load(
        str(path), frame_offset=frame_offset, num_frames=num_frames
    )
    return waveform, int(sample_rate)


def decode_audio(
    path: Path | str,
    *,
    frame_offset: int = 0,
    num_frames: int = -1,
    preferred_backend: AudioBackend = "soundfile",
) -> tuple[torch.Tensor, int]:
    """按 frame 范围解码音频并返回 ``([C,T], sample_rate)``。"""
    resolved = Path(path)
    if preferred_backend == "soundfile":
        return _decode_soundfile(
            resolved, frame_offset=frame_offset, num_frames=num_frames
        )
    if preferred_backend != "torchaudio":
        raise ValueError(f"不支持的音频后端: {preferred_backend!r}")
    try:
        return _decode_torchaudio(
            resolved, frame_offset=frame_offset, num_frames=num_frames
        )
    except Exception as torchaudio_exc:  # noqa: BLE001
        try:
            return _decode_soundfile(
                resolved, frame_offset=frame_offset, num_frames=num_frames
            )
        except Exception as soundfile_exc:  # noqa: BLE001
            raise RuntimeError(
                "TorchAudio 与 SoundFile 均无法解码音频；"
                f"torchaudio={torchaudio_exc}; soundfile={soundfile_exc}"
            ) from soundfile_exc


# 0.2.x 读兼容：运行时 loader 与 YAML 现在共享唯一 AudioConfig schema。
AudioLoaderConfig = AudioConfig


class AudioLoader:
    """从 :class:`AudioRecord` 加载音频并输出标准化的 :class:`AudioData`。"""

    def __init__(self, config: AudioConfig | None = None) -> None:
        config = config or AudioConfig()
        if config.backend not in ("soundfile", "torchaudio"):
            raise SERDataError(
                f"不支持的音频后端: {config.backend!r}，"
                "当前支持 'soundfile' 与 'torchaudio'"
            )
        if config.target_sample_rate <= 0:
            raise SERDataError(
                f"target_sample_rate 必须为正，实际: {config.target_sample_rate}"
            )
        self.config = config
        self._resamplers: dict[tuple[int, int, torch.dtype, torch.device], T.Resample] = {}

    def load(self, record: AudioRecord, *, base_dir: Path | None = None) -> AudioData:
        """加载一条记录对应的音频。"""
        path = self.resolve_path(record.audio_path, base_dir)
        uid = record.uid

        if not path.exists():
            raise AudioNotFoundError(
                "音频文件不存在", uid=uid, path=path, component="audio_loader",
                stage="resolve",
            )
        if not path.is_file():
            raise AudioDecodeError(
                "音频路径不是文件", uid=uid, path=path, component="audio_loader",
                stage="resolve",
            )

        try:
            info = probe_audio(path, preferred_backend=self.config.backend)
        except Exception as exc:  # noqa: BLE001 - 解码库异常类型因格式而异
            raise AudioDecodeError(
                "读取音频元信息失败", uid=uid, path=path,
                component="audio_loader", stage="probe",
            ) from exc

        original_sr = info.sample_rate
        total_frames = info.num_frames

        frame_offset, num_frames = self._segment_to_frames(
            record, original_sr=original_sr, total_frames=total_frames, uid=uid, path=path,
        )

        try:
            waveform, sr = decode_audio(
                path,
                frame_offset=frame_offset,
                num_frames=num_frames,
                preferred_backend=self.config.backend,
            )
        except Exception as exc:  # noqa: BLE001
            raise AudioDecodeError(
                "音频解码失败", uid=uid, path=path, component="audio_loader",
                stage="decode",
            ) from exc

        if waveform.numel() == 0 or waveform.shape[-1] == 0:
            raise InvalidAudioSegmentError(
                "解码结果为空音频（0 帧）", uid=uid, path=path,
                component="audio_loader", stage="decode",
            )
        if sr != original_sr:
            logger.warning(
                "音频实际采样率 (%s) 与元信息 (%s) 不一致: uid=%s, path=%s",
                sr, original_sr, uid, path,
            )
            original_sr = int(sr)

        if not torch.isfinite(waveform).all():
            raise AudioDecodeError(
                "音频包含 NaN/Inf，拒绝加载（不做自动替换）", uid=uid, path=path,
                component="audio_loader", stage="validate",
            )

        if self.config.mono and waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        if sr != self.config.target_sample_rate:
            waveform = self._resample(waveform, sr)

        if self.config.normalize_peak:
            peak = waveform.abs().max()
            if peak > 0:
                waveform = waveform / peak

        waveform = waveform.to(torch.float32)

        if waveform.shape[-1] == 0:
            raise InvalidAudioSegmentError(
                "重采样后音频为空", uid=uid, path=path,
                component="audio_loader", stage="resample",
            )

        return AudioData(
            waveform=waveform,
            sample_rate=self.config.target_sample_rate,
            source_path=path,
            original_sample_rate=original_sr,
            num_frames=int(waveform.shape[-1]),
        )

    @staticmethod
    def resolve_path(audio_path: Path, base_dir: Path | None) -> Path:
        """解析音频路径：绝对路径直接规范化，相对路径基于 base_dir。"""
        path = Path(audio_path)
        if not path.is_absolute() and base_dir is not None:
            path = Path(base_dir) / path
        return path.resolve()

    def _segment_to_frames(
        self,
        record: AudioRecord,
        *,
        original_sr: int,
        total_frames: int,
        uid: str,
        path: Path,
    ) -> tuple[int, int]:
        """把毫秒片段转换为 frame offset / num_frames。"""
        start_ms = record.start_ms
        end_ms = record.end_ms
        if start_ms is None and end_ms is None:
            return 0, -1

        if start_ms is None:
            start_ms = 0

        frame_offset = int(round(start_ms / 1000.0 * original_sr))
        if frame_offset >= total_frames > 0:
            raise InvalidAudioSegmentError(
                f"片段起点超出音频长度: start_ms={start_ms} 对应帧 {frame_offset}，"
                f"音频总帧数 {total_frames}",
                uid=uid, path=path, component="audio_loader", stage="segment",
            )

        if end_ms is None:
            return frame_offset, -1

        end_frame = int(round(end_ms / 1000.0 * original_sr))
        if end_frame > total_frames > 0:
            warnings.warn(
                f"片段 end_ms={end_ms} 超出音频长度（总帧数 {total_frames}），"
                f"将截断到文件结尾: uid={uid}, path={path}",
                UserWarning,
                stacklevel=2,
            )
        num_frames = max(end_frame - frame_offset, 0)
        return frame_offset, num_frames

    def _resample(self, waveform: torch.Tensor, orig_sr: int) -> torch.Tensor:
        """用缓存的 resampler 重采样。key 含 (orig, target, dtype, device)。"""
        key = (orig_sr, self.config.target_sample_rate, waveform.dtype, waveform.device)
        resampler = self._resamplers.get(key)
        if resampler is None:
            resampler = T.Resample(orig_freq=orig_sr, new_freq=self.config.target_sample_rate)
            self._resamplers[key] = resampler
        return resampler(waveform)


__all__ = [
    "AudioBackend", "AudioFileInfo", "AudioLoaderConfig", "AudioLoader",
    "probe_audio", "decode_audio",
]
