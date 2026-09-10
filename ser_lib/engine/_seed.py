"""Experiment-level reproducibility helpers.

This module is intentionally internal: callers should configure reproducibility through
``ExperimentConfig.trainer`` rather than invoking RNG setup directly.
"""

from __future__ import annotations

import random

import numpy as np
import torch


def seed_experiment_rng(seed: int, *, deterministic: bool = True) -> None:
    """Seed Python, NumPy and Torch before any experiment component is constructed."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = deterministic
    torch.backends.cudnn.benchmark = not deterministic


__all__ = ["seed_experiment_rng"]
