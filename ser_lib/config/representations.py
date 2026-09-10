"""内置 representation 的用户配置 schema；不依赖 torch/torchaudio 执行实现。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RawWaveformConfig(BaseModel):
    """RawWaveform 无参数；保留空模型用于 schema 生成与未知参数报错。"""

    model_config = ConfigDict(extra="forbid")


class SpectralConfigBase(BaseModel):
    """谱图类表示的公共参数（对齐 torchaudio 默认值）。"""

    model_config = ConfigDict(extra="forbid")

    sample_rate: int = Field(default=16000, ge=1000, le=192000)
    n_fft: int = Field(default=400, ge=32, le=8192)
    win_length: int | None = Field(default=None, ge=32, le=8192)
    hop_length: int = Field(default=200, ge=1, le=4096)
    f_min: float = Field(default=0.0, ge=0.0)
    f_max: float | None = Field(default=None, ge=0.0)
    center: bool = True
    pad_mode: str = "reflect"

    @model_validator(mode="after")
    def _validate_params(self) -> "SpectralConfigBase":
        win = self.win_length if self.win_length is not None else self.n_fft
        if win > self.n_fft:
            raise ValueError(f"win_length ({win}) 不能大于 n_fft ({self.n_fft})")
        if self.f_max is not None and self.f_max <= self.f_min:
            raise ValueError(f"f_max ({self.f_max}) 必须大于 f_min ({self.f_min})")
        return self


class SpectrogramConfig(SpectralConfigBase):
    """线性谱图参数。"""

    power: float = Field(default=2.0, ge=0.0, le=3.0)


class MelConfig(SpectralConfigBase):
    """Mel 谱公共参数。"""

    n_mels: int = Field(default=80, ge=16, le=512)
    power: float = Field(default=2.0, ge=1.0, le=3.0)


class LogMelConfig(MelConfig):
    """Log-Mel 参数。"""

    top_db: float = Field(default=80.0, ge=10.0, le=120.0)


class MFCCConfig(SpectralConfigBase):
    """MFCC 参数；Mel 参数封装在组件内部。"""

    n_mels: int = Field(default=80, ge=16, le=512)
    n_mfcc: int = Field(default=40, ge=10, le=128)
    dct_norm: Literal["ortho"] | None = "ortho"
    mel_norm: Literal["slaney"] | None = "slaney"
    mel_scale: Literal["htk", "slaney"] = "htk"

    @model_validator(mode="after")
    def _validate_mfcc(self) -> "MFCCConfig":
        if self.n_mfcc > self.n_mels:
            raise ValueError(f"n_mfcc ({self.n_mfcc}) 不能大于 n_mels ({self.n_mels})")
        return self


AcousticFeatureName = Literal[
    "f0",
    "rms",
    "zcr",
    "spectral_centroid",
    "spectral_rolloff",
    "spectral_flatness",
    "spectral_flux",
    "delta",
    "jitter_shimmer_hnr",
]


class AcousticFeaturesConfig(BaseModel):
    """AcousticFeatures 参数。"""

    model_config = ConfigDict(extra="forbid")

    features: list[AcousticFeatureName] = Field(..., min_length=1)
    sample_rate: int = Field(default=16000, ge=1000, le=192000)
    hop_length: int = Field(default=256, ge=1, le=4096)
    win_length: int = Field(default=400, ge=2, le=8192)
    n_fft: int = Field(default=1024, ge=32, le=8192)
    roll_percent: float = Field(default=0.85, gt=0.0, lt=1.0)
    delta_win_length: int = Field(default=5, ge=3, le=21)

    @model_validator(mode="after")
    def _validate(self) -> "AcousticFeaturesConfig":
        if len(set(self.features)) != len(self.features):
            raise ValueError(f"features 存在重复项: {self.features}")
        if self.delta_win_length % 2 == 0:
            raise ValueError(f"delta_win_length 必须是奇数，实际: {self.delta_win_length}")
        if "jitter_shimmer_hnr" in self.features:
            raise ValueError(
                "jitter_shimmer_hnr 暂不可用：当前库尚未提供经过数值参考验证的 "
                "shimmer 与 HNR 实现，拒绝返回占位测量值"
            )
        return self


class CompositeConfig(BaseModel):
    """组合表示参数：``{key: 组件配置}``。"""

    model_config = ConfigDict(extra="forbid")

    outputs: dict[str, dict[str, Any]] = Field(..., min_length=1)


__all__ = [
    "RawWaveformConfig",
    "SpectralConfigBase",
    "SpectrogramConfig",
    "MelConfig",
    "LogMelConfig",
    "MFCCConfig",
    "AcousticFeatureName",
    "AcousticFeaturesConfig",
    "CompositeConfig",
]
