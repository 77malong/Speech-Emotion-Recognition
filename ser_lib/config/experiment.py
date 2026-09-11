"""一次可复现实验的纯用户配置 schema。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from ser_lib.config.base import StrictConfig
from ser_lib.config.data import DataConfig
from ser_lib.config.model import ModelConfig
from ser_lib.config.optimizer import parse_optimizer_config
from ser_lib.config.scheduler import parse_scheduler_config
from ser_lib.config.training import LossConfig, SamplingConfig, TrainerConfig


class ExperimentConfig(StrictConfig):
    """一次可复现实验的完整、可序列化配置快照。"""

    data: DataConfig
    model: ModelConfig
    trainer: TrainerConfig = Field(default_factory=TrainerConfig)
    optimizer: dict[str, Any] = Field(
        default_factory=lambda: {"type": "adamw", "params": {}}
    )
    scheduler: dict[str, Any] | None = None
    loss: LossConfig = Field(default_factory=LossConfig)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    output_dir: Path = Path("runs/default")

    @field_validator("optimizer")
    @classmethod
    def _validate_optimizer(cls, value: dict[str, Any]) -> dict[str, Any]:
        parse_optimizer_config(value)
        return value

    @field_validator("scheduler")
    @classmethod
    def _validate_scheduler(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        parse_scheduler_config(value)
        return value


__all__ = ["ExperimentConfig"]
