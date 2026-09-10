"""ser_lib: Speech Emotion Recognition core SDK.

The package root intentionally exposes only a small set of high-level conveniences.
Domain APIs live in ``ser_lib.config``, ``ser_lib.data``, ``ser_lib.models``,
``ser_lib.engine``, ``ser_lib.inference`` and ``ser_lib.artifacts``.  Root exports are
resolved lazily so ``import ser_lib`` stays lightweight.
"""

from __future__ import annotations

import importlib
from typing import Any

from ser_lib._version import __version__ as __version__

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "SERDataset": ("ser_lib.data", "SERDataset"),
    "SERBatch": ("ser_lib.data", "SERBatch"),
    "SERModel": ("ser_lib.models", "SERModel"),
    "Trainer": ("ser_lib.engine", "Trainer"),
    "TrainingResult": ("ser_lib.engine", "TrainingResult"),
    "evaluate": ("ser_lib.engine", "evaluate"),
    "train_experiment": ("ser_lib.engine", "train_experiment"),
    "evaluate_artifact": ("ser_lib.engine", "evaluate_artifact"),
    "EmotionPredictor": ("ser_lib.inference", "EmotionPredictor"),
    "PredictionResult": ("ser_lib.inference", "PredictionResult"),
    "export_model_artifact": ("ser_lib.artifacts", "export_model_artifact"),
    "load_model_artifact": ("ser_lib.artifacts", "load_model_artifact"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "SERDataset",
    "SERBatch",
    "SERModel",
    "Trainer",
    "TrainingResult",
    "evaluate",
    "train_experiment",
    "evaluate_artifact",
    "EmotionPredictor",
    "PredictionResult",
    "export_model_artifact",
    "load_model_artifact",
]
