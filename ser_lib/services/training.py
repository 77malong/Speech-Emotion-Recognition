"""训练应用服务：稳定 dry-run、Trainer 构造和终态结果入口。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.data.types import SERBatch
from ser_lib.engine.config import ExperimentConfig, ObservabilityConfig
from ser_lib.engine.trainer import EpochResult, Trainer, TrainingResult
from ser_lib.engine.validation import ExperimentValidationResult, validate_experiment
from ser_lib.models.base import SERModel


class TrainingService:
    """隐藏 Trainer 兼容层细节，同时保留底层对象的可组合性。"""

    @staticmethod
    def validate(
        config: ExperimentConfig | Path | str,
    ) -> ExperimentValidationResult:
        return validate_experiment(config)

    @staticmethod
    def create_trainer(
        model: SERModel,
        experiment: ExperimentConfig,
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        observability: ObservabilityConfig | None = None,
        run_id: str | None = None,
    ) -> Trainer:
        return Trainer.from_experiment(
            model,
            experiment,
            event_callback=event_callback,
            cancellation=cancellation,
            observability=observability,
            run_id=run_id,
        )

    @staticmethod
    def run(
        trainer: Trainer,
        train_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]],
        *,
        val_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]] | None = None,
        on_epoch_end: Callable[[EpochResult], None] | None = None,
        start_epoch: int | None = None,
    ) -> TrainingResult:
        """执行 Trainer.fit，并直接返回 Web 需要的 TrainingResult。"""
        trainer.fit(
            train_batches,
            val_batches=val_batches,
            on_epoch_end=on_epoch_end,
            start_epoch=start_epoch,
        )
        if trainer.last_result is None:
            raise RuntimeError("Trainer.fit 完成后未生成 TrainingResult")
        return trainer.last_result


__all__ = ["TrainingService"]
