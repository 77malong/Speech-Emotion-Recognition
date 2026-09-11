"""优化器 schema 与不依赖 Torch 的白名单解析。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from ser_lib.config.base import StrictConfig


class AdamWConfig(StrictConfig):
    type: Literal["adamw"] = "adamw"
    learning_rate: float = Field(default=1e-3, gt=0, allow_inf_nan=False)
    weight_decay: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    beta1: float = Field(default=0.9, ge=0, lt=1, allow_inf_nan=False)
    beta2: float = Field(default=0.999, ge=0, lt=1, allow_inf_nan=False)
    eps: float = Field(default=1e-8, gt=0, allow_inf_nan=False)


class AdamConfig(StrictConfig):
    type: Literal["adam"] = "adam"
    learning_rate: float = Field(default=1e-3, gt=0, allow_inf_nan=False)
    weight_decay: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    beta1: float = Field(default=0.9, ge=0, lt=1, allow_inf_nan=False)
    beta2: float = Field(default=0.999, ge=0, lt=1, allow_inf_nan=False)
    eps: float = Field(default=1e-8, gt=0, allow_inf_nan=False)


class SGDConfig(StrictConfig):
    type: Literal["sgd"] = "sgd"
    learning_rate: float = Field(default=1e-2, gt=0, allow_inf_nan=False)
    weight_decay: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    momentum: float = Field(default=0.0, ge=0, lt=1)
    nesterov: bool = False

    @model_validator(mode="after")
    def _validate_nesterov(self) -> "SGDConfig":
        if self.nesterov and self.momentum <= 0:
            raise ValueError("SGD nesterov=True 时 momentum 必须 > 0")
        return self


OptimizerConfig = AdamWConfig | AdamConfig | SGDConfig


def parse_optimizer_config(raw: dict[str, Any]) -> OptimizerConfig:
    """解析白名单 optimizer payload；这是 schema 解析，不构建 Torch optimizer。"""
    kind = raw.get("type", "adamw")
    params = raw.get("params", {})
    if set(raw) - {"type", "params"}:
        raise ValueError(f"optimizer 包含未知字段: {sorted(set(raw) - {'type', 'params'})}")
    if not isinstance(params, dict):
        raise ValueError("optimizer.params 必须是映射")
    models = {"adamw": AdamWConfig, "adam": AdamConfig, "sgd": SGDConfig}
    if kind not in models:
        raise ValueError(f"未知 optimizer.type={kind!r}，可用: {sorted(models)}")
    return models[kind](type=kind, **params)


__all__ = [
    "AdamWConfig",
    "AdamConfig",
    "SGDConfig",
    "OptimizerConfig",
    "parse_optimizer_config",
]
