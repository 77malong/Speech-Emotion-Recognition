"""学习率调度器 schema 与不依赖 Torch 的白名单解析。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ser_lib.config.base import StrictConfig


class StepSchedulerConfig(StrictConfig):
    type: Literal["step"] = "step"
    step_size: int = Field(default=10, ge=1)
    gamma: float = Field(default=0.1, gt=0, le=1)


class CosineSchedulerConfig(StrictConfig):
    type: Literal["cosine"] = "cosine"
    t_max: int = Field(ge=1)
    eta_min: float = Field(default=0.0, ge=0)


SchedulerConfig = StepSchedulerConfig | CosineSchedulerConfig


def parse_scheduler_config(raw: dict[str, Any] | None) -> SchedulerConfig | None:
    if raw is None:
        return None
    kind = raw.get("type")
    params = raw.get("params", {})
    if set(raw) - {"type", "params"}:
        raise ValueError(f"scheduler 包含未知字段: {sorted(set(raw) - {'type', 'params'})}")
    if not isinstance(params, dict):
        raise ValueError("scheduler.params 必须是映射")
    models = {"step": StepSchedulerConfig, "cosine": CosineSchedulerConfig}
    if kind not in models:
        raise ValueError(f"未知 scheduler.type={kind!r}，可用: {sorted(models)}")
    return models[kind](type=kind, **params)


__all__ = [
    "StepSchedulerConfig",
    "CosineSchedulerConfig",
    "SchedulerConfig",
    "parse_scheduler_config",
]
