"""训练应用服务：稳定 dry-run、Trainer 构造、lineage、历史记录和终态结果入口。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import cast

from ser_lib.core.diagnostics import Diagnostic
from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.data.types import SERBatch
from ser_lib.engine.checkpoint_catalog import (
    CheckpointCatalog,
    CheckpointInfo,
    inspect_checkpoint_file,
    scan_checkpoints as scan_checkpoint_files,
)
from ser_lib.engine.config import ExperimentConfig, ObservabilityConfig
from ser_lib.engine.lineage import TrainingRunMetadata, build_training_run_metadata
from ser_lib.engine.runs import (
    TrainingRunCatalog,
    TrainingRunDetail,
    TrainingRunInfo,
    load_training_run_info,
    scan_training_runs,
    write_training_run_info,
)
from ser_lib.engine.training_history import TrainingHistoryInfo, load_training_history
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
        dataset_id: str | None = None,
        dataset_fingerprint: str | None = None,
    ) -> Trainer:
        """构造可追踪 Trainer，不读取 manifest 或隐式计算 fingerprint。

        ``dataset_id`` 可以由已经加载 manifest 的 CLI/Web 显式传入；未提供时
        使用 ``ExperimentConfig.data.dataset_id``。这避免 Trainer 为补 lineage
        偷偷执行文件系统 I/O。
        """
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
            dataset_id=dataset_id if dataset_id is not None else experiment.data.dataset_id,
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

    @staticmethod
    def save_run(
        directory: Path | str,
        trainer: Trainer,
        result: TrainingResult,
    ) -> TrainingRunInfo:
        """原子持久化终态 run.json，并返回重新读取后的规范记录。"""
        metadata = TrainingService.get_run_metadata(trainer)
        if metadata is None:
            raise ValueError("Trainer 没有 TrainingRunMetadata，无法保存训练运行记录")
        path = write_training_run_info(directory, metadata, result)
        return load_training_run_info(path)

    @staticmethod
    def inspect_run(path: Path | str) -> TrainingRunInfo:
        return load_training_run_info(path)

    @staticmethod
    def inspect_history(path: Path | str) -> TrainingHistoryInfo:
        return load_training_history(path)

    @staticmethod
    def inspect_run_detail(path: Path | str) -> TrainingRunDetail:
        """聚合训练元数据、曲线与 checkpoint stat，不加载任何 checkpoint 内容。"""
        run = load_training_run_info(path)
        run_dir = Path(run.directory)
        diagnostics: list[Diagnostic] = []

        try:
            history = load_training_history(run_dir)
        except (FileNotFoundError, ValueError) as exc:
            history = None
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="training_history_unavailable",
                    message=str(exc),
                    stage="training_run_detail",
                    path=(run_dir / "history.json").as_posix(),
                    details={"error_type": type(exc).__name__},
                )
            )

        checkpoint_root = _checkpoint_root_for_run(run)
        if checkpoint_root.is_dir():
            checkpoints = scan_checkpoint_files(checkpoint_root)
        else:
            checkpoints = CheckpointCatalog(
                root=checkpoint_root.as_posix(),
                checkpoints=(),
                failures=(),
            )
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="training_checkpoint_directory_missing",
                    message=f"checkpoint 目录不存在: {checkpoint_root}",
                    stage="training_run_detail",
                    path=checkpoint_root.as_posix(),
                )
            )

        return TrainingRunDetail(
            run=run,
            history=history,
            checkpoints=checkpoints,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def scan_runs(
        root: Path | str,
        *,
        recursive: bool = False,
        fail_fast: bool = False,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> TrainingRunCatalog:
        return scan_training_runs(
            root,
            recursive=recursive,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def inspect_checkpoint(path: Path | str) -> CheckpointInfo:
        return inspect_checkpoint_file(path)

    @staticmethod
    def scan_checkpoints(
        root: Path | str,
        *,
        recursive: bool = False,
        fail_fast: bool = False,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> CheckpointCatalog:
        return scan_checkpoint_files(
            root,
            recursive=recursive,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )


def _checkpoint_root_for_run(run: TrainingRunInfo) -> Path:
    raw_trainer = run.config.get("trainer")
    if isinstance(raw_trainer, Mapping):
        raw_checkpoint_dir = raw_trainer.get("checkpoint_dir")
        if isinstance(raw_checkpoint_dir, str) and raw_checkpoint_dir.strip():
            checkpoint_root = Path(raw_checkpoint_dir)
            if not checkpoint_root.is_absolute():
                checkpoint_root = Path(run.directory) / checkpoint_root
            return checkpoint_root

    for raw_checkpoint in (run.last_checkpoint, run.best_checkpoint):
        if isinstance(raw_checkpoint, str) and raw_checkpoint.strip():
            return Path(raw_checkpoint).parent

    return Path(run.directory) / "checkpoints"


__all__ = ["TrainingService"]
