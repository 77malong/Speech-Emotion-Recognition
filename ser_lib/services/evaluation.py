"""评估应用服务。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import torch

from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.types import SERBatch
from ser_lib.engine.evaluator import (
    EvaluationResult,
    PredictionSink,
    evaluate,
    write_evaluation_report,
)
from ser_lib.models.base import SERModel


class EvaluationService:
    """统一 standalone/Web evaluation 的运行与报告写入入口。"""

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


__all__ = ["EvaluationService"]
