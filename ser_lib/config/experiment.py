"""一次可复现实验的纯用户配置 schema。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError, field_validator

from ser_lib.config.base import StrictConfig
from ser_lib.config.loader import load_yaml_mapping, resolve_config_path
from ser_lib.foundation.errors import ConfigurationError
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


def load_experiment_config(path: Path | str) -> ExperimentConfig:
    """严格读取当前实验配置，并基于配置文件目录解析所有相对路径。"""
    raw, source = load_yaml_mapping(path)
    try:
        config = ExperimentConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"配置内容校验失败: {source}: {exc}") from exc

    updates: dict[str, Any] = {}
    if not config.output_dir.is_absolute():
        updates["output_dir"] = resolve_config_path(
            config.output_dir,
            base_dir=source.parent,
        )
    if (
        config.trainer.checkpoint_dir is not None
        and not config.trainer.checkpoint_dir.is_absolute()
    ):
        updates["trainer"] = config.trainer.model_copy(
            update={
                "checkpoint_dir": resolve_config_path(
                    config.trainer.checkpoint_dir,
                    base_dir=source.parent,
                )
            }
        )

    data_updates: dict[str, Any] = {}
    if not config.data.manifest.is_absolute():
        data_updates["manifest"] = resolve_config_path(
            config.data.manifest,
            base_dir=source.parent,
        )
    if not config.data.cache.directory.is_absolute():
        data_updates["cache"] = config.data.cache.model_copy(
            update={
                "directory": resolve_config_path(
                    config.data.cache.directory,
                    base_dir=source.parent,
                )
            }
        )
    if data_updates:
        updates["data"] = config.data.model_copy(update=data_updates)

    return config.model_copy(update=updates)


__all__ = ["ExperimentConfig", "load_experiment_config"]
