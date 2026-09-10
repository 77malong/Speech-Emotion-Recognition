"""训练应用服务：稳定 dry-run、Trainer 构造、lineage、历史记录和终态结果入口。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from ser_lib.data.types import SERBatch
from ser_lib.engine.checkpoint_catalog import (
    CheckpointCatalog,
    CheckpointInfo,
    inspect_checkpoint_file,
    scan_checkpoints as scan_checkpoint_files,
)
from ser_lib.engine.config import ExperimentConfig, ObservabilityConfig
from ser_lib.engine.lineage import TrainingRunMetadata
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
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.foundation.events import CancellationCheck, EventCallback
from ser_lib.models.base import SERModel


class TrainingService:
    """训练兼容 facade；可复用训练能力以 engine API 为正式入口。"""

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
        """兼容入口；正式构造与 lineage 由 ``Trainer.from_experiment`` 负责。"""
        return Trainer.from_experiment(
            model,
            experiment,
            event_callback=event_callback,
            cancellation=cancellation,
            observability=observability,
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_fingerprint=dataset_fingerprint,
        )

    @staticmethod
    def get_run_metadata(trainer: Trainer) -> TrainingRunMetadata | None:
        return trainer.run_metadata

    @staticmethod
    def run(
        trainer: Trainer,
        train_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]],
        *,
        val_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]] | None = None,
        on_epoch_end: Callable[[EpochResult], None] | None = None,
        start_epoch: int | None = None,
    ) -> TrainingResult:
        """兼容入口；直接返回公开 ``Trainer.fit`` 的 ``TrainingResult``。"""
        return trainer.fit(
            train_batches,
            val_batches=val_batches,
            on_epoch_end=on_epoch_end,
            start_epoch=start_epoch,
        )

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
