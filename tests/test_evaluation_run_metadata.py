from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import torch
from pydantic import ValidationError

from ser_lib._version import __version__
from ser_lib.engine import (
    ClassMetrics,
    EvaluationResult,
    EvaluationRecord,
    build_evaluation_metadata,
    load_evaluation_record,
    write_evaluation_record,
)


def _result() -> EvaluationResult:
    return EvaluationResult(
        accuracy=0.5,
        macro_f1=0.4,
        uar=0.5,
        confusion_matrix=torch.tensor([[1, 0], [1, 0]], dtype=torch.long),
        sample_count=2,
        loss=0.7,
        war=0.5,
        per_class=(
            ClassMetrics(0, "low", 0.5, 1.0, 2 / 3, 1),
            ClassMetrics(1, "high", 0.0, 0.0, 0.0, 1),
        ),
        predictions=(),
        weighted_precision=0.25,
        weighted_recall=0.5,
        weighted_f1=1 / 3,
        balanced_accuracy=0.5,
        matthews_correlation_coefficient=0.0,
        cohen_kappa=0.0,
    )


def _metadata(created_at: datetime):
    return build_evaluation_metadata(
        source_artifact="artifacts/demo",
        source_run_id="run_source",
        dataset_id="demo-data",
        dataset_fingerprint="a" * 64,
        model_name="cnn_baseline",
        split="test",
        device="cpu",
        library_version="0.2.0",
        evaluation_id="eval_demo",
        created_at=created_at,
    )


def test_evaluation_run_record_round_trip_and_directory_relocation(tmp_path: Path):
    created = datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)
    started = created + timedelta(seconds=1)
    finished = started + timedelta(seconds=2.5)
    directory = tmp_path / "evaluation"

    path = write_evaluation_record(
        directory,
        _metadata(created),
        _result(),
        started_at=started,
        finished_at=finished,
    )
    assert path == directory / "evaluation.json"
    assert not (directory / ".evaluation.json.tmp").exists()

    loaded = load_evaluation_record(directory)
    assert isinstance(loaded, EvaluationRecord)
    assert loaded.evaluation_id == "eval_demo"
    assert loaded.source_run_id == "run_source"
    assert loaded.dataset_id == "demo-data"
    assert loaded.dataset_fingerprint == "a" * 64
    assert loaded.duration_seconds == pytest.approx(2.5)
    assert loaded.sample_count == 2
    assert loaded.metrics["accuracy"] == pytest.approx(0.5)
    assert loaded.metrics_file == "metrics.json"
    assert loaded.predictions_file == "predictions.jsonl"
    payload = loaded.to_dict()
    assert "schema_version" not in payload
    json.dumps(payload)

    moved = tmp_path / "moved"
    directory.rename(moved)
    relocated = load_evaluation_record(moved)
    assert relocated.directory == moved.as_posix()
    assert relocated.evaluation_id == loaded.evaluation_id


def test_evaluation_metadata_defaults_library_version_and_run_can_be_saved(tmp_path: Path):
    created = datetime.now(timezone.utc)
    metadata = build_evaluation_metadata(
        source_artifact=tmp_path / "artifact",
        source_run_id="run_123",
        dataset_id="dataset",
        dataset_fingerprint="b" * 64,
        model_name="cnn_baseline",
        split="val",
        device="cpu",
        created_at=created,
    )
    assert metadata.evaluation_id.startswith("eval_")
    assert metadata.library_version == __version__

    started = created + timedelta(milliseconds=1)
    finished = started + timedelta(milliseconds=5)
    path = write_evaluation_record(
        tmp_path / "evaluation",
        metadata,
        _result(),
        started_at=started,
        finished_at=finished,
    )
    saved = load_evaluation_record(path)
    assert load_evaluation_record(tmp_path / "evaluation") == saved


def test_evaluation_run_record_rejects_invalid_timeline_and_schema(tmp_path: Path):
    created = datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="finished_at"):
        write_evaluation_record(
            tmp_path / "bad-time",
            _metadata(created),
            _result(),
            started_at=created + timedelta(seconds=2),
            finished_at=created + timedelta(seconds=1),
        )

    directory = tmp_path / "invalid"
    directory.mkdir()
    payload = EvaluationRecord.from_evaluation(
        directory,
        _metadata(created),
        _result(),
        started_at=created,
        finished_at=created + timedelta(seconds=1),
    ).to_dict()
    payload["unexpected"] = True
    (directory / "evaluation.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_evaluation_record(directory)


def test_evaluation_run_metadata_rejects_blank_optional_lineage():
    created = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="source_run_id"):
        build_evaluation_metadata(
            source_artifact="artifact",
            source_run_id=" ",
            dataset_id="dataset",
            model_name="model",
            split="test",
            device="cpu",
            library_version="0.2.0",
            created_at=created,
        )
