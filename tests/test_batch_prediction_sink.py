from __future__ import annotations

import json
from pathlib import Path

import pytest

from ser_lib.data import AudioRecord
from ser_lib.inference import (
    BatchEmotionPredictor,
    JsonlBatchPredictionSink,
    PredictionResult,
    write_batch_predictions,
)


class FakePredictor:
    def __init__(self) -> None:
        self.records: list[AudioRecord] = []

    def predict_record(self, record: AudioRecord) -> PredictionResult:
        self.records.append(record)
        if not record.audio_path.is_file():
            raise FileNotFoundError(f"missing: {record.audio_path}")
        return PredictionResult(record.uid, 1, "happy", 0.8, [0.2, 0.8])


def test_batch_sink_can_stream_without_retaining_result_details(tmp_path: Path):
    valid = tmp_path / "valid.wav"
    valid.write_bytes(b"audio")
    records = (
        record
        for record in (
            AudioRecord("ok", valid),
            AudioRecord("bad", tmp_path / "missing.wav"),
        )
    )
    output = tmp_path / "streamed.jsonl"

    with JsonlBatchPredictionSink(output, flush_each=True) as sink:
        result = BatchEmotionPredictor(FakePredictor()).predict_records(
            records,
            fail_fast=False,
            total=2,
            result_sink=sink,
            retain_results=False,
        )

    assert result.total == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.retained_results == 0
    assert result.predictions == ()
    assert result.failures == ()
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [row["status"] for row in rows] == ["succeeded", "failed"]
    assert rows[0]["uid"] == "ok"
    assert rows[1]["uid"] == "bad"
    json.dumps(result.to_dict())


def test_unknown_length_iterable_is_consumed_chunk_by_chunk(tmp_path: Path):
    paths = []
    for index in range(5):
        path = tmp_path / f"{index}.wav"
        path.write_bytes(b"audio")
        paths.append(path)
    predictor = FakePredictor()

    def record_stream():
        for index, path in enumerate(paths):
            if index >= 2 and not predictor.records:
                raise AssertionError("records iterable was materialized before first batch ran")
            yield AudioRecord(f"item-{index}", path)

    events = []
    result = BatchEmotionPredictor(predictor).predict_records(
        record_stream(),
        batch_size=2,
        event_callback=events.append,
    )

    assert result.succeeded == 5
    assert result.failed == 0
    assert len(predictor.records) == 5
    progress = [event for event in events if getattr(event, "stage", None) == "batch_predict"]
    assert progress
    assert all(event.total is None for event in progress)


def test_batch_predictor_forwards_sink_and_retention_options(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    output = tmp_path / "direct.jsonl"

    with JsonlBatchPredictionSink(output) as sink:
        result = BatchEmotionPredictor(FakePredictor()).predict_records(
            [AudioRecord("direct", audio)],
            result_sink=sink,
            retain_results=False,
        )

    assert result.total == 1
    assert result.succeeded == 1
    assert result.retained_results == 0
    assert json.loads(output.read_text(encoding="utf-8"))["uid"] == "direct"


def test_declared_total_mismatch_is_rejected(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")

    with pytest.raises(ValueError, match="声明 total"):
        BatchEmotionPredictor(FakePredictor()).predict_records(
            (AudioRecord("only", audio) for _ in range(1)),
            total=2,
        )


def test_legacy_writer_rejects_nonretained_result(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    result = BatchEmotionPredictor(FakePredictor()).predict_records(
        [AudioRecord("only", audio)],
        retain_results=False,
    )

    with pytest.raises(ValueError, match="未保留完整明细"):
        write_batch_predictions(tmp_path / "result.jsonl", result)
