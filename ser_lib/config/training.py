"""训练、目标函数和采样的用户配置 schema；不包含 Torch 执行逻辑。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ser_lib.config.base import StrictConfig


class ObservabilityConfig(StrictConfig):
    """训练运行时事件频率与轻量 ETA 参数。"""

    progress_interval_batches: int = Field(default=1, ge=1)
    metric_interval_batches: int = Field(default=10, ge=1)
    eta_window_batches: int = Field(default=20, ge=1)
    eta_warmup_batches: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _validate_eta_window(self) -> "ObservabilityConfig":
        if self.eta_warmup_batches > self.eta_window_batches:
            raise ValueError("eta_warmup_batches 不能大于 eta_window_batches")
        return self


class TrainerConfig(StrictConfig):
    """表示无关的训练循环配置；optimizer 参数不属于本节点。"""

    epochs: int = Field(default=10, ge=1)
    device: str = "cpu"
    seed: int = Field(default=42, ge=0)
    deterministic: bool = True
    amp: bool = False
    gradient_clip_norm: float | None = Field(default=None, gt=0)
    gradient_accumulation_steps: int = Field(default=1, ge=1)
    checkpoint_dir: Path | None = None
    validation_interval: int = Field(default=1, ge=1)
    monitor: Literal[
        "val_loss", "val_accuracy", "val_uar", "val_macro_f1"
    ] = "val_loss"
    early_stopping_patience: int | None = Field(default=None, ge=1)
    early_stopping_min_delta: float = Field(default=0.0, ge=0.0)
    save_best: bool = True
    save_last: bool = True


class LossConfig(StrictConfig):
    type: Literal["cross_entropy", "focal"] = "cross_entropy"
    class_weights: list[float] | None = None
    label_smoothing: float = Field(default=0.0, ge=0.0, lt=1.0)
    focal_gamma: float = Field(default=2.0, ge=0.0)

    @model_validator(mode="after")
    def _validate_weights(self) -> "LossConfig":
        if self.class_weights is not None and any(value <= 0 for value in self.class_weights):
            raise ValueError("loss.class_weights 必须全部大于 0")
        if self.type != "focal" and self.focal_gamma != 2.0:
            raise ValueError("focal_gamma 仅用于 focal loss")
        return self


class SamplingConfig(StrictConfig):
    type: Literal["shuffle", "weighted"] = "shuffle"
    class_weights: list[float] | None = None
    replacement: bool = True
    num_samples: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_options(self) -> "SamplingConfig":
        if self.class_weights is not None and any(value <= 0 for value in self.class_weights):
            raise ValueError("sampling.class_weights 必须全部大于 0")
        if self.type == "shuffle" and (
            self.class_weights is not None
            or self.num_samples is not None
            or not self.replacement
        ):
            raise ValueError("class_weights/replacement/num_samples 仅用于 weighted sampling")
        return self


__all__ = [
    "ObservabilityConfig",
    "TrainerConfig",
    "LossConfig",
    "SamplingConfig",
]
