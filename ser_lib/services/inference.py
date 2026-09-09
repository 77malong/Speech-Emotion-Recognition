"""离线、批量与流式推理应用服务。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.types import AudioRecord
from ser_lib.inference.batch import (
    BatchEmotionPredictor,
    BatchPredictionResult,
    BatchPredictionSink,
)
from ser_lib.inference.offline import EmotionPredictor, PredictionResult
from ser_lib.inference.streaming import StreamingConfig, StreamingEmotionRecognizer


class InferenceService:
    """保持 Predictor 为领域对象，只统一常用应用级调用方式。"""

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
    def create_stream(
        predictor: EmotionPredictor,
        config: StreamingConfig | None = None,
    ) -> StreamingEmotionRecognizer:
        return StreamingEmotionRecognizer(predictor, config or StreamingConfig())


__all__ = ["InferenceService"]
