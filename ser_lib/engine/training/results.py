"""训练结果类型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

TrainingStatus = Literal["completed", "early_stopped", "cancelled", "failed"]


@dataclass(frozen=True, slots=True)
class EpochResult:
    epoch: int
    loss: float
    accuracy: float
    sample_count: int
    optimizer_steps: int = 0
    validation: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "loss": self.loss,
            "accuracy": self.accuracy,
            "sample_count": self.sample_count,
            "optimizer_steps": self.optimizer_steps,
            "validation": dict(self.validation) if self.validation is not None else None,
        }


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """一次 Trainer.fit 调用的稳定、JSON-safe 终态结果。"""

    run_id: str
    status: TrainingStatus
    epochs: tuple[EpochResult, ...]
    best_epoch: int | None
    best_metric: float | None
    monitored_metric: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    last_checkpoint: Path | None
    best_checkpoint: Path | None
    stop_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "epochs": [epoch.to_dict() for epoch in self.epochs],
            "best_epoch": self.best_epoch,
            "best_metric": self.best_metric,
            "monitored_metric": self.monitored_metric,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "last_checkpoint": (
                str(self.last_checkpoint) if self.last_checkpoint is not None else None
            ),
            "best_checkpoint": (
                str(self.best_checkpoint) if self.best_checkpoint is not None else None
            ),
            "stop_reason": self.stop_reason,
        }


__all__ = ["TrainingStatus", "EpochResult", "TrainingResult"]
