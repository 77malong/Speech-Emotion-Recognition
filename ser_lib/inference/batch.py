"""批量离线推理、增量结果 sink 与 JSONL/CSV 结果导出。"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator, Sequence, Sized
from dataclasses import asdict, dataclass
from itertools import islice
from pathlib import Path
from typing import Literal, Protocol

from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import (
    CancellationCheck,
    EventCallback,
    EventContext,
    ProgressEvent,
)
from ser_lib.inference.events import PredictionEvent
from ser_lib.inference.offline import EmotionPredictor, PredictionResult


DEFAULT_AUDIO_EXTENSIONS = frozenset({".wav", ".flac", ".mp3", ".ogg", ".m4a"})


@dataclass(frozen=True, slots=True)
class PredictionFailure:
    uid: str
    audio_path: str
    error_type: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class BatchPredictionSink(Protocol):
    """批量推理逐条结果消费者；生命周期由调用方管理。"""

    def write_prediction(self, result: PredictionResult) -> None:
        ...

    def write_failure(self, failure: PredictionFailure) -> None:
        ...


class JsonlBatchPredictionSink:
    """把批量推理结果增量写入 JSONL，避免完整结果常驻内存。"""

    def __init__(
        self,
        path: Path | str,
        *,
        append: bool = False,
        flush_each: bool = False,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush_each = flush_each
        self._stream = self.path.open(
            "a" if append else "w",
            encoding="utf-8",
            newline="\n",
        )

    def _write(self, row: dict[str, object]) -> None:
        if self._stream.closed:
            raise ValueError("JsonlBatchPredictionSink 已关闭")
        self._stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        if self._flush_each:
            self._stream.flush()

    def write_prediction(self, result: PredictionResult) -> None:
        self._write({"status": "succeeded", **asdict(result)})

    def write_failure(self, failure: PredictionFailure) -> None:
        self._write({"status": "failed", **failure.to_dict()})

    def flush(self) -> None:
        if not self._stream.closed:
            self._stream.flush()

    def close(self) -> None:
        if not self._stream.closed:
            self._stream.close()

    def __enter__(self) -> "JsonlBatchPredictionSink":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class BatchPredictionResult:
    predictions: tuple[PredictionResult, ...]
    failures: tuple[PredictionFailure, ...]
    total: int
    succeeded_count: int | None = None
    failed_count: int | None = None

    def __post_init__(self) -> None:
        if self.total < 0:
            raise ValueError("BatchPredictionResult.total 不能为负数")
        if self.succeeded < len(self.predictions):
            raise ValueError("succeeded_count 不能小于已保留 predictions 数量")
        if self.failed < len(self.failures):
            raise ValueError("failed_count 不能小于已保留 failures 数量")
        if self.total != self.succeeded + self.failed:
            raise ValueError("BatchPredictionResult.total 与成功/失败数量不一致")

    @property
    def succeeded(self) -> int:
        return len(self.predictions) if self.succeeded_count is None else self.succeeded_count

    @property
    def failed(self) -> int:
        return len(self.failures) if self.failed_count is None else self.failed_count

    @property
    def retained_results(self) -> int:
        return len(self.predictions) + len(self.failures)

    def to_dict(self) -> dict[str, object]:
        return {
            "predictions": [asdict(prediction) for prediction in self.predictions],
            "failures": [failure.to_dict() for failure in self.failures],
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "retained_results": self.retained_results,
        }


def _safe_len(value: object) -> int | None:
    if not isinstance(value, Sized):
        return None
    try:
        return len(value)
    except TypeError:
        return None


def _iter_chunks(records: Iterable[AudioRecord], batch_size: int) -> Iterator[list[AudioRecord]]:
    iterator = iter(records)
    while True:
        chunk = list(islice(iterator, batch_size))
        if not chunk:
            return
        yield chunk


class BatchEmotionPredictor:
    """在单文件预测器之上提供来源枚举、增量事件和逐条失败策略。"""

    def __init__(self, predictor: EmotionPredictor) -> None:
        self.predictor = predictor

    def predict_records(
        self,
        records: Iterable[AudioRecord],
        *,
        fail_fast: bool = True,
        batch_size: int = 16,
        total: int | None = None,
        result_sink: BatchPredictionSink | None = None,
        retain_results: bool = True,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> BatchPredictionResult:
        """批量预测，并支持流式 Iterable 与增量结果 sink。

        默认 ``retain_results=True`` 保持历史行为：完整成功/失败明细都放进返回值。
        超大任务可传 ``result_sink`` 并设置 ``retain_results=False``，此时返回值仅保留
        总计数，逐条明细由 sink 消费。未知长度 Iterable 不会被强制 ``list()``；
        progress 的 ``total`` 为 ``None``，除非调用方显式提供 ``total``。
        """
        if batch_size < 1:
            raise ValueError("batch_size 必须 >= 1")
        if total is not None and total < 0:
            raise ValueError("total 必须 >= 0")
        known_total = total if total is not None else _safe_len(records)
        predictions: list[PredictionResult] = []
        failures: list[PredictionFailure] = []
        completed = 0
        succeeded_count = 0
        failed_count = 0
        base_context = event_context or EventContext()

        def report() -> None:
            if event_callback is not None:
                event_callback(
                    ProgressEvent(
                        stage="batch_predict",
                        completed=completed,
                        total=known_total,
                        message=(
                            f"succeeded={succeeded_count}, failed={failed_count}"
                        ),
                        context=base_context,
                    )
                )

        def accept_prediction(result: PredictionResult) -> None:
            nonlocal completed, succeeded_count
            if result_sink is not None:
                result_sink.write_prediction(result)
            if retain_results:
                predictions.append(result)
            completed += 1
            succeeded_count += 1
            if event_callback is not None:
                event_callback(
                    PredictionEvent(
                        uid=result.uid,
                        label_id=result.label_id,
                        emotion=result.emotion,
                        confidence=result.confidence,
                        probabilities=tuple(result.probabilities),
                        context=base_context,
                        details={
                            "completed": completed,
                            "total": known_total,
                        },
                    )
                )
            report()

        def accept_failure(record: AudioRecord, exc: Exception) -> None:
            nonlocal completed, failed_count
            failure = PredictionFailure(
                uid=record.uid,
                audio_path=str(record.audio_path),
                error_type=type(exc).__name__,
                message=str(exc),
            )
            if result_sink is not None:
                result_sink.write_failure(failure)
            if retain_results:
                failures.append(failure)
            completed += 1
            failed_count += 1
            report()

        def predict_one(record: AudioRecord) -> None:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            try:
                result = self.predictor.predict_record(record)
            except OperationCancelled:
                raise
            except Exception as exc:
                if fail_fast:
                    raise
                accept_failure(record, exc)
            else:
                accept_prediction(result)

        batch_method = getattr(self.predictor, "predict_records", None)
        for chunk in _iter_chunks(records, batch_size):
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            if batch_method is None or len(chunk) == 1:
                for record in chunk:
                    predict_one(record)
                continue
            try:
                chunk_results = list(batch_method(chunk))
                if len(chunk_results) != len(chunk):
                    raise ValueError("批量预测返回数量与输入记录数不一致")
            except OperationCancelled:
                raise
            except Exception:
                if fail_fast:
                    raise
                # 逐条重试以隔离坏文件；有效项可能被重新预处理，但结果不会重复写入。
                for record in chunk:
                    predict_one(record)
            else:
                for result in chunk_results:
                    accept_prediction(result)

        if known_total is not None and completed != known_total:
            raise ValueError(
                f"批量推理实际处理 {completed} 条，与声明 total={known_total} 不一致"
            )
        return BatchPredictionResult(
            tuple(predictions),
            tuple(failures),
            completed,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
        )

    def predict_files(
        self,
        paths: Iterable[Path | str],
        **kwargs,
    ) -> BatchPredictionResult:
        known_total = _safe_len(paths)
        if "total" not in kwargs and known_total is not None:
            kwargs["total"] = known_total
        records = (
            AudioRecord(
                uid=f"{Path(path).stem or 'audio'}-{index:06d}",
                audio_path=Path(path),
            )
            for index, path in enumerate(paths, start=1)
        )
        return self.predict_records(records, **kwargs)

    def predict_directory(
        self,
        directory: Path | str,
        *,
        recursive: bool = True,
        extensions: Sequence[str] | None = None,
        **kwargs,
    ) -> BatchPredictionResult:
        root = Path(directory)
        if not root.is_dir():
            raise NotADirectoryError(f"批量推理目录不存在或不是目录: {root}")
        normalized = {
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            for extension in (extensions or DEFAULT_AUDIO_EXTENSIONS)
        }
        iterator = root.rglob("*") if recursive else root.glob("*")
        paths = sorted(
            (
                path
                for path in iterator
                if path.is_file() and path.suffix.lower() in normalized
            ),
            key=lambda path: path.as_posix().casefold(),
        )
        return self.predict_files(paths, **kwargs)

    def predict_manifest(
        self,
        manifest: DatasetManifest | Path | str,
        *,
        split: str | None = None,
        **kwargs,
    ) -> BatchPredictionResult:
        dataset = (
            manifest
            if isinstance(manifest, DatasetManifest)
            else DatasetManifest.load(manifest)
        )
        return self.predict_records(dataset.resolved_records(split), **kwargs)


def write_batch_predictions(
    path: Path | str,
    result: BatchPredictionResult,
    *,
    format: Literal["jsonl", "csv"] | None = None,
) -> Path:
    """原子写入内存中保留的完整批量结果。"""
    if result.succeeded != len(result.predictions) or result.failed != len(result.failures):
        raise ValueError(
            "BatchPredictionResult 未保留完整明细；请在推理时使用 result_sink 直接写出"
        )
    target = Path(path)
    output_format = format or target.suffix.lower().lstrip(".")
    if output_format not in {"jsonl", "csv"}:
        raise ValueError("批量预测输出格式必须是 jsonl 或 csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        if output_format == "jsonl":
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                for prediction in result.predictions:
                    row = {"status": "succeeded", **asdict(prediction)}
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                for failure in result.failures:
                    row = {"status": "failed", **failure.to_dict()}
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            columns = [
                "status",
                "uid",
                "label_id",
                "emotion",
                "confidence",
                "probabilities",
                "audio_path",
                "error_type",
                "message",
            ]
            with temporary.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                for prediction in result.predictions:
                    writer.writerow(
                        {
                            "status": "succeeded",
                            "uid": prediction.uid,
                            "label_id": prediction.label_id,
                            "emotion": prediction.emotion,
                            "confidence": prediction.confidence,
                            "probabilities": json.dumps(prediction.probabilities),
                        }
                    )
                for failure in result.failures:
                    writer.writerow({"status": "failed", **failure.to_dict()})
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "PredictionFailure",
    "BatchPredictionSink",
    "JsonlBatchPredictionSink",
    "BatchPredictionResult",
    "BatchEmotionPredictor",
    "write_batch_predictions",
]