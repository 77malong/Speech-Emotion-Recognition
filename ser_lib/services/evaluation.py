"""评估应用服务。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

import torch

from ser_lib.data.types import SERBatch
from ser_lib.engine.evaluation_catalog import EvaluationRunCatalog, scan_evaluation_runs
from ser_lib.engine.evaluation_detail import (
    EvaluationRunDetail,
    inspect_evaluation_prediction_file,
)
from ser_lib.engine.evaluation_reports import (
    EvaluationPredictionPage,
    EvaluationReportInfo,
    inspect_evaluation_report,
    query_evaluation_predictions,
)
from ser_lib.engine.evaluation_runs import (
    EvaluationRunInfo,
    EvaluationRunMetadata,
    build_evaluation_run_metadata,
    load_evaluation_run_info,
    write_evaluation_run_info,
)
from ser_lib.engine.evaluator import (
    EvaluationResult,
    PredictionSink,
    evaluate,
    write_evaluation_report,
)
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.foundation.events import CancellationCheck, EventCallback, EventContext
from ser_lib.models.base import SERModel


class EvaluationService:
    """统一 standalone/Web evaluation 的运行、lineage、落盘与查询入口。"""

    @staticmethod
    def create_run_metadata(
        *,
        source_artifact: Path | str,
        dataset_id: str,
        model_name: str,
        split: str,
        device: str,
        source_run_id: str | None = None,
        dataset_fingerprint: str | None = None,
        evaluation_id: str | None = None,
        created_at: datetime | None = None,
    ) -> EvaluationRunMetadata:
        from ser_lib import __version__

        return build_evaluation_run_metadata(
            source_artifact=source_artifact,
            source_run_id=source_run_id,
            dataset_id=dataset_id,
            dataset_fingerprint=dataset_fingerprint,
            model_name=model_name,
            split=split,
            device=device,
            library_version=__version__,
            evaluation_id=evaluation_id,
            created_at=created_at,
        )

    @staticmethod
    def run(
        model: SERModel,
        batches: Iterable[SERBatch],
        *,
        num_classes: int,
        device: str | torch.device = "cpu",
        labels: Mapping[int, str] | None = None,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        loss_fn: torch.nn.Module | None = None,
        event_context: EventContext | None = None,
        split: str | None = None,
        prediction_sink: PredictionSink | None = None,
        retain_predictions: bool = True,
    ) -> EvaluationResult:
        return evaluate(
            model,
            batches,
            num_classes=num_classes,
            device=device,
            labels=labels,
            event_callback=event_callback,
            cancellation=cancellation,
            loss_fn=loss_fn,
            event_context=event_context,
            split=split,
            prediction_sink=prediction_sink,
            retain_predictions=retain_predictions,
        )

    @staticmethod
    def write_report(directory: Path | str, result: EvaluationResult) -> Path:
        return write_evaluation_report(directory, result)

    @staticmethod
    def save_run(
        directory: Path | str,
        metadata: EvaluationRunMetadata,
        result: EvaluationResult,
        *,
        started_at: datetime,
        finished_at: datetime,
        predictions_file: str | None = "predictions.jsonl",
    ) -> EvaluationRunInfo:
        path = write_evaluation_run_info(
            directory,
            metadata,
            result,
            started_at=started_at,
            finished_at=finished_at,
            predictions_file=predictions_file,
        )
        return load_evaluation_run_info(path)

    @staticmethod
    def inspect_run(path: Path | str) -> EvaluationRunInfo:
        return load_evaluation_run_info(path)

    @staticmethod
    def inspect_run_detail(path: Path | str) -> EvaluationRunDetail:
        """聚合 evaluation metadata、metrics 与 prediction stat，不读预测明细。"""
        run = load_evaluation_run_info(path)
        run_dir = Path(run.directory)
        predictions = inspect_evaluation_prediction_file(run)
        diagnostics: list[Diagnostic] = []

        try:
            report = inspect_evaluation_report(run_dir)
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            report = None
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="evaluation_report_unavailable",
                    message=str(exc),
                    stage="evaluation_run_detail",
                    path=(run_dir / run.metrics_file).as_posix(),
                    details={"error_type": type(exc).__name__},
                )
            )

        if run.predictions_file is not None and not predictions.exists:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="evaluation_predictions_unavailable",
                    message=f"评估 predictions 文件不存在: {predictions.path}",
                    stage="evaluation_run_detail",
                    path=predictions.path,
                )
            )

        return EvaluationRunDetail(
            run=run,
            report=report,
            predictions=predictions,
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
    ) -> EvaluationRunCatalog:
        return scan_evaluation_runs(
            root,
            recursive=recursive,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def inspect_report(directory: Path | str) -> EvaluationReportInfo:
        return inspect_evaluation_report(directory)

    @staticmethod
    def query_predictions(
        directory: Path | str,
        *,
        offset: int = 0,
        limit: int = 100,
        incorrect_only: bool = False,
        target: int | None = None,
        predicted: int | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> EvaluationPredictionPage:
        return query_evaluation_predictions(
            directory,
            offset=offset,
            limit=limit,
            incorrect_only=incorrect_only,
            target=target,
            predicted=predicted,
            cancellation=cancellation,
        )


__all__ = ["EvaluationService"]
