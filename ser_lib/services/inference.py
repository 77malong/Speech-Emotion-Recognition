"""离线、批量与流式推理应用服务。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.events import CancellationCheck, EventCallback
from ser_lib.inference.batch import (
    BatchEmotionPredictor,
    BatchPredictionResult,
    BatchPredictionSink,
    write_batch_predictions as _write_batch_predictions,
)
from ser_lib.inference.offline import EmotionPredictor, PredictionResult
from ser_lib.inference.streaming import StreamingConfig, StreamingEmotionRecognizer

if TYPE_CHECKING:
    from ser_lib.artifacts import LoadedArtifact

WindowAggregation = Literal[
    "mean_logits",
    "mean_probabilities",
    "max_confidence",
]


class InferenceService:
    """统一应用层的 predictor 构造、批量来源选择、结果写盘和流式入口。"""

    @staticmethod
    def create_predictor(
        artifact: "LoadedArtifact",
        *,
        device: str = "cpu",
        window_aggregation: WindowAggregation | None = None,
    ) -> EmotionPredictor:
        return EmotionPredictor(
            artifact.model,
            artifact.audio_loader,
            artifact.pipeline,
            artifact.collator,
            artifact.manifest.labels,
            device=device,
            window_aggregation=window_aggregation,
        )

    @staticmethod
    def predict_file(
        predictor: EmotionPredictor,
        path: Path | str,
        *,
        uid: str | None = None,
    ) -> PredictionResult:
        return predictor.predict_file(path, uid=uid)

    @staticmethod
    def predict_record(
        predictor: EmotionPredictor,
        record: AudioRecord,
    ) -> PredictionResult:
        return predictor.predict_record(record)

    @staticmethod
    def predict_records(
        predictor: EmotionPredictor,
        records: Iterable[AudioRecord],
        *,
        fail_fast: bool = True,
        batch_size: int = 16,
        total: int | None = None,
        result_sink: BatchPredictionSink | None = None,
        retain_results: bool = True,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> BatchPredictionResult:
        return BatchEmotionPredictor(predictor).predict_records(
            records,
            fail_fast=fail_fast,
            batch_size=batch_size,
            total=total,
            result_sink=result_sink,
            retain_results=retain_results,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def predict_files(
        predictor: EmotionPredictor,
        paths: Iterable[Path | str],
        *,
        fail_fast: bool = True,
        batch_size: int = 16,
        result_sink: BatchPredictionSink | None = None,
        retain_results: bool = True,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> BatchPredictionResult:
        return BatchEmotionPredictor(predictor).predict_files(
            paths,
            fail_fast=fail_fast,
            batch_size=batch_size,
            result_sink=result_sink,
            retain_results=retain_results,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def predict_directory(
        predictor: EmotionPredictor,
        directory: Path | str,
        *,
        recursive: bool = True,
        extensions: Sequence[str] | None = None,
        fail_fast: bool = True,
        batch_size: int = 16,
        result_sink: BatchPredictionSink | None = None,
        retain_results: bool = True,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> BatchPredictionResult:
        return BatchEmotionPredictor(predictor).predict_directory(
            directory,
            recursive=recursive,
            extensions=extensions,
            fail_fast=fail_fast,
            batch_size=batch_size,
            result_sink=result_sink,
            retain_results=retain_results,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def predict_manifest(
        predictor: EmotionPredictor,
        manifest: DatasetManifest | Path | str,
        *,
        split: str | None = None,
        fail_fast: bool = True,
        batch_size: int = 16,
        result_sink: BatchPredictionSink | None = None,
        retain_results: bool = True,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> BatchPredictionResult:
        return BatchEmotionPredictor(predictor).predict_manifest(
            manifest,
            split=split,
            fail_fast=fail_fast,
            batch_size=batch_size,
            result_sink=result_sink,
            retain_results=retain_results,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def write_predictions(
        path: Path | str,
        result: BatchPredictionResult,
        *,
        format: Literal["jsonl", "csv"] | None = None,
    ) -> Path:
        return _write_batch_predictions(path, result, format=format)

    @staticmethod
    def create_stream(
        predictor: EmotionPredictor,
        config: StreamingConfig | None = None,
    ) -> StreamingEmotionRecognizer:
        return StreamingEmotionRecognizer(predictor, config or StreamingConfig())


__all__ = ["InferenceService", "WindowAggregation"]
