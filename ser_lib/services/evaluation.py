"""评估应用服务。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import torch

from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.types import SERBatch
from ser_lib.engine.evaluation_reports import (
    EvaluationPredictionPage,
    EvaluationReportInfo,
    inspect_evaluation_report,
    query_evaluation_predictions,
)
from ser_lib.engine.evaluator import (
    EvaluationResult,
    PredictionSink,
    evaluate,
    write_evaluation_report,
)
from ser_lib.models.base import SERModel


class EvaluationService:
    """统一 standalone/Web evaluation 的运行、落盘与查询入口。"""

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
