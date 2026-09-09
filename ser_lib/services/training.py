"""训练应用服务：稳定 dry-run、Trainer 构造、lineage 和终态结果入口。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import cast

from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.data.types import SERBatch
from ser_lib.engine.config import ExperimentConfig, ObservabilityConfig
from ser_lib.engine.lineage import TrainingRunMetadata, build_training_run_metadata
from ser_lib.engine.trainer import EpochResult, Trainer, TrainingResult
from ser_lib.engine.validation import ExperimentValidationResult, validate_experiment
from ser_lib.models.base import SERModel


class _LineageTrainer(Trainer):
    """仅为 Service 路径补 lineage；保持 ``Trainer`` 的公共 API 兼容。"""

    run_metadata: TrainingRunMetadata | None = None

    def _save_checkpoint_with_event(
        self,
        path: Path,
        *,
        kind: str,
        epoch: int,
        metrics: dict[str, float],
        metadata: dict[str, object],
    ) -> Path:
        resolved_metadata = dict(metadata)
        if self.run_metadata is not None:
            resolved_metadata["run_metadata"] = self.run_metadata.to_dict()
        return super()._save_checkpoint_with_event(
            path,
            kind=kind,
            epoch=epoch,
            metrics=metrics,
            metadata=resolved_metadata,
        )

    def resume_from(self, path, *, restore_rng: bool = True) -> dict:
        payload = super().resume_from(path, restore_rng=restore_rng)
        raw_checkpoint_metadata = payload.get("metadata")
        saved_run_metadata: TrainingRunMetadata | None = None
        if isinstance(raw_checkpoint_metadata, Mapping):
            raw_lineage = raw_checkpoint_metadata.get("run_metadata")
            if isinstance(raw_lineage, Mapping):
                saved_run_metadata = TrainingRunMetadata.from_dict(raw_lineage)

        if not self._run_id_explicit and saved_run_metadata is not None:
            self.run_metadata = saved_run_metadata.with_run_id(self.run_id)
        elif self.run_metadata is not None:
            self.run_metadata = self.run_metadata.with_run_id(self.run_id)
        elif saved_run_metadata is not None:
            self.run_metadata = saved_run_metadata.with_run_id(self.run_id)
        return payload


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
        dataset_fingerprint: str | None = None,
    ) -> Trainer:
        """构造可追踪 Trainer，不读取 manifest 或隐式计算 fingerprint。"""
        trainer = cast(
            _LineageTrainer,
            _LineageTrainer.from_experiment(
                model,
                experiment,
                event_callback=event_callback,
                cancellation=cancellation,
                observability=observability,
                run_id=run_id,
            ),
        )
        from ser_lib import __version__

        trainer.run_metadata = build_training_run_metadata(
            run_id=trainer.run_id,
            dataset_id=experiment.data.dataset_id,
            dataset_fingerprint=dataset_fingerprint,
            model_id=model.model_spec.model_id,
            config=experiment.model_dump(mode="json"),
            seed=experiment.trainer.seed,
            device=str(trainer.device),
            library_version=__version__,
        )
        return trainer

    @staticmethod
    def get_run_metadata(trainer: Trainer) -> TrainingRunMetadata | None:
        metadata = getattr(trainer, "run_metadata", None)
        return metadata if isinstance(metadata, TrainingRunMetadata) else None

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
