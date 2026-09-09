"""白名单优化器和学习率调度器的 Torch 构建逻辑。"""

from __future__ import annotations

import torch

from ser_lib.config.optimizer import (
    AdamConfig,
    AdamWConfig,
    OptimizerConfig,
    SGDConfig,
    parse_optimizer_config,
)
from ser_lib.config.scheduler import (
    CosineSchedulerConfig,
    SchedulerConfig,
    StepSchedulerConfig,
    parse_scheduler_config,
)


def build_optimizer(
    parameters,
    config: OptimizerConfig,
) -> torch.optim.Optimizer:
    common = {"lr": config.learning_rate, "weight_decay": config.weight_decay}
    if isinstance(config, AdamWConfig):
        return torch.optim.AdamW(
            parameters, **common, betas=(config.beta1, config.beta2), eps=config.eps
        )
    if isinstance(config, AdamConfig):
        return torch.optim.Adam(
            parameters, **common, betas=(config.beta1, config.beta2), eps=config.eps
        )
    if isinstance(config, SGDConfig):
        return torch.optim.SGD(
            parameters, **common, momentum=config.momentum, nesterov=config.nesterov
        )
    raise TypeError(f"不支持的优化器配置: {type(config)!r}")


def build_scheduler(
    optimizer: torch.optim.Optimizer,
    config: SchedulerConfig | None,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    if config is None:
        return None
    if isinstance(config, StepSchedulerConfig):
        return torch.optim.lr_scheduler.StepLR(
            optimizer, step_size=config.step_size, gamma=config.gamma
        )
    if isinstance(config, CosineSchedulerConfig):
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=config.t_max, eta_min=config.eta_min
        )
    raise TypeError(f"不支持的调度器配置: {type(config)!r}")


__all__ = [
    "AdamWConfig",
    "AdamConfig",
    "SGDConfig",
    "OptimizerConfig",
    "StepSchedulerConfig",
    "CosineSchedulerConfig",
    "SchedulerConfig",
    "parse_optimizer_config",
    "build_optimizer",
    "parse_scheduler_config",
    "build_scheduler",
]
