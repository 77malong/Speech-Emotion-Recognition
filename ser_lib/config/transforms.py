"""内置 waveform/feature transform 的用户配置 schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NormalizeConfig(BaseModel):
    """Normalize 无参数。"""

    model_config = ConfigDict(extra="forbid")


class GaussianNoiseConfig(BaseModel):
    """高斯噪声参数。"""

    model_config = ConfigDict(extra="forbid")

    snr_db: float = Field(default=15.0, gt=0.0, le=120.0, description="信噪比 (dB)")


class TimeShiftConfig(BaseModel):
    """时间平移参数。"""

    model_config = ConfigDict(extra="forbid")

    max_ratio: float = Field(default=0.2, ge=0.0, le=1.0, description="最大平移比例")


class VolumeScaleConfig(BaseModel):
    """音量缩放参数。"""

    model_config = ConfigDict(extra="forbid")

    gain_min: float = Field(default=0.5, gt=0.0)
    gain_max: float = Field(default=1.5, gt=0.0)

    @model_validator(mode="after")
    def _validate_range(self) -> "VolumeScaleConfig":
        if self.gain_min >= self.gain_max:
            raise ValueError(f"gain_min ({self.gain_min}) 必须小于 gain_max ({self.gain_max})")
        return self


class PitchShiftConfig(BaseModel):
    """音高偏移参数。sample_rate 由 pipeline 构建时按 AudioLoader 配置注入。"""

    model_config = ConfigDict(extra="forbid")

    sample_rate: int = Field(default=16000, ge=1000, le=192000)
    n_steps: int = Field(default=4, ge=-24, le=24)


class TimeStretchConfig(BaseModel):
    """时间拉伸参数。"""

    model_config = ConfigDict(extra="forbid")

    rate: float = Field(default=1.2, gt=0.1, le=4.0)


class SpecMaskingConfig(BaseModel):
    """SpecAugment 掩码参数。"""

    model_config = ConfigDict(extra="forbid")

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
