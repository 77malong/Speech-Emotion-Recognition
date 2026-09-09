from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.core import CancellationToken, OperationCancelled, ProgressEvent
from ser_lib.engine import EvaluationRunCatalog, scan_evaluation_runs
from ser_lib.services import EvaluationService


def _record(evaluation_id: str, created_at: datetime) -> dict:
    started = created_at + timedelta(seconds=1)
    finished = started + timedelta(seconds=2)
    return {
        "schema_version": 1,
        "evaluation_id": evaluation_id,
        "directory": "stale/path",
        "created_at": created_at.isoformat(),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": 2.0,
        "source_artifact": "artifacts/demo",
        "source_run_id": None,
        "dataset_id": "demo",
        "dataset_fingerprint": "a" * 64,
        "model_name": "cnn_baseline",
        "split": "test",
        "device": "cpu",
        "library_version": "0.2.0",
        "sample_count": 2,
        "metrics": {
            "loss": 0.5,
            "accuracy": 0.5,
            "war": 0.5,
            "uar": 0.5,
            "macro_f1": 0.5,
            "weighted_precision": 0.5,
            "weighted_recall": 0.5,
            "weighted_f1": 0.5,
            "balanced_accuracy": 0.5,
            "matthews_correlation_coefficient": 0.0,
            "cohen_kappa": 0.0,
        },
        "metrics_file": "metrics.json",
        "predictions_file": "predictions.jsonl",
    }


def _write(directory: Path, evaluation_id: str, created_at: datetime) -> None:
    directory.mkdir(parents=True)
    (directory / "evaluation.json").write_text(
        json.dumps(_record(evaluation_id, created_at)),
        encoding="utf-8",
    )


def test_evaluation_catalog_scans_shallow_sorts_and_isolates_failures(tmp_path: Path):
    root = tmp_path / "evaluations"
    base = datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)
    _write(root / "older", "eval_old", base)
    _write(root / "newer", "eval_new", base + timedelta(minutes=1))
    _write(root / "nested" / "deep", "eval_deep", base + timedelta(minutes=2))
    bad = root / "broken"
    bad.mkdir(parents=True)
    (bad / "evaluation.json").write_text("{}", encoding="utf-8")
    events = []

    catalog = EvaluationService.scan_runs(root, event_callback=events.append)

    assert isinstance(catalog, EvaluationRunCatalog)
    assert [run.evaluation_id for run in catalog.runs] == ["eval_new", "eval_old"]
    assert all(run.directory != "stale/path" for run in catalog.runs)
    assert len(catalog.failures) == 1
    assert catalog.failures[0].directory == bad.as_posix()
    assert catalog.total == 3
    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert [event.completed for event in progress] == [1, 2, 3]
    assert all(event.total == 3 for event in progress)
    json.dumps(catalog.to_dict())

    recursive = scan_evaluation_runs(root, recursive=True)
    assert [run.evaluation_id for run in recursive.runs] == [
        "eval_deep",
        "eval_new",
        "eval_old",
    ]
    assert len(recursive.failures) == 1


def test_evaluation_catalog_supports_fail_fast_and_cancellation(tmp_path: Path):
    root = tmp_path / "evaluations"
    base = datetime.now(timezone.utc)
    _write(root / "valid", "eval_valid", base)
    bad = root / "broken"
    bad.mkdir(parents=True)
    (bad / "evaluation.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValidationError):
        scan_evaluation_runs(root, fail_fast=True)

    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationCancelled):
        scan_evaluation_runs(root, cancellation=token)


def test_evaluation_catalog_rejects_missing_root(tmp_path: Path):
    with pytest.raises(NotADirectoryError):
        scan_evaluation_runs(tmp_path / "missing")
