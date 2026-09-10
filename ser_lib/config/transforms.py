"""内置 waveform/feature transform 的用户配置 schema。"""

from __future__ import annotations

from pydantic import Field, model_validator

from ser_lib.config.base import StrictConfig


class NormalizeConfig(StrictConfig):
    """Normalize 无参数。"""


class GaussianNoiseConfig(StrictConfig):
    """高斯噪声参数。"""

    snr_db: float = Field(default=15.0, gt=0.0, le=120.0, description="信噪比 (dB)")


class TimeShiftConfig(StrictConfig):
    """时间平移参数。"""

    max_ratio: float = Field(default=0.2, ge=0.0, le=1.0, description="最大平移比例")


class VolumeScaleConfig(StrictConfig):
    """音量缩放参数。"""

    gain_min: float = Field(default=0.5, gt=0.0)
    gain_max: float = Field(default=1.5, gt=0.0)

    @model_validator(mode="after")
    def _validate_range(self) -> "VolumeScaleConfig":
        if self.gain_min >= self.gain_max:
            raise ValueError(f"gain_min ({self.gain_min}) 必须小于 gain_max ({self.gain_max})")
        return self


class PitchShiftConfig(StrictConfig):
    """音高偏移参数。sample_rate 由 pipeline 构建时按 AudioLoader 配置注入。"""

    sample_rate: int = Field(default=16000, ge=1000, le=192000)
    n_steps: int = Field(default=4, ge=-24, le=24)


class TimeStretchConfig(StrictConfig):
    """时间拉伸参数。"""

    rate: float = Field(default=1.2, gt=0.1, le=4.0)


class SpecMaskingConfig(StrictConfig):
    """SpecAugment 掩码参数。"""

    time_mask_param: int = Field(default=30, ge=1, description="时间掩码最大宽度")
    freq_mask_param: int = Field(default=15, ge=1, description="频率掩码最大宽度")


__all__ = [
    "NormalizeConfig",
    "GaussianNoiseConfig",
    "TimeShiftConfig",
    "VolumeScaleConfig",
    "PitchShiftConfig",
    "TimeStretchConfig",
    "SpecMaskingConfig",
]
