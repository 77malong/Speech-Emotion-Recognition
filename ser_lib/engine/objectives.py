"""Classification losses and imbalance-aware sampling."""

from __future__ import annotations

from typing import Sequence

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import WeightedRandomSampler

from ser_lib.config.training import LossConfig, SamplingConfig


class ClassificationLoss(nn.Module):
    def __init__(self, config: LossConfig, num_classes: int) -> None:
        super().__init__()
        if config.class_weights is not None and len(config.class_weights) != num_classes:
            raise ValueError(
                f"loss.class_weights 长度必须等于 num_classes={num_classes}"
            )
        weights = (
            torch.tensor(config.class_weights, dtype=torch.float32)
            if config.class_weights is not None
            else None
        )
        self.register_buffer("class_weights", weights)
        self.config = config

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        if self.config.type == "cross_entropy":
            return F.cross_entropy(
                logits,
                targets,
                weight=self.class_weights,
                label_smoothing=self.config.label_smoothing,
            )
        per_sample = F.cross_entropy(
            logits,
            targets,
            weight=self.class_weights,
            label_smoothing=self.config.label_smoothing,
            reduction="none",
        )
        target_probability = logits.softmax(dim=-1).gather(
            1, targets.unsqueeze(1)
        ).squeeze(1)
        return (
            ((1.0 - target_probability) ** self.config.focal_gamma) * per_sample
        ).mean()


def build_weighted_sampler(
    labels: Sequence[int | None],
    *,
    num_classes: int,
    config: SamplingConfig,
    seed: int,
) -> WeightedRandomSampler | None:
    if config.type == "shuffle":
        return None
    if not labels or any(label is None for label in labels):
        raise ValueError("weighted sampling 要求所有训练样本都有标签")
    integer_labels = [int(label) for label in labels if label is not None]
    if any(label < 0 or label >= num_classes for label in integer_labels):
        raise ValueError("训练标签超出 [0, num_classes) 范围")
    counts = torch.bincount(torch.tensor(integer_labels), minlength=num_classes)
    if config.class_weights is None:
        class_weights = torch.where(
            counts > 0,
            counts.sum().to(torch.float64)
            / counts.clamp_min(1).to(torch.float64),
            torch.zeros(num_classes, dtype=torch.float64),
        )
    else:
        if len(config.class_weights) != num_classes:
            raise ValueError(
                f"sampling.class_weights 长度必须等于 num_classes={num_classes}"
            )
        class_weights = torch.tensor(config.class_weights, dtype=torch.float64)
    sample_weights = class_weights[torch.tensor(integer_labels)]
    sample_count = config.num_samples or len(integer_labels)
    if not config.replacement and sample_count > len(integer_labels):
        raise ValueError("replacement=False 时 num_samples 不能超过训练样本数")
    generator = torch.Generator().manual_seed(seed)
    return WeightedRandomSampler(
        sample_weights,
        num_samples=sample_count,
        replacement=config.replacement,
        generator=generator,
    )


__all__ = [
    "LossConfig",
    "SamplingConfig",
    "ClassificationLoss",
    "build_weighted_sampler",
]
