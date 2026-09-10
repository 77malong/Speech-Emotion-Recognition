from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ser_lib.engine import EvaluationRunDetail, EvaluationRunInfo, inspect_evaluation_run_detail


def _aggregate_metrics() -> dict[str, float]:
    return {
        "loss": 0.25,
        "accuracy": 0.75,
        "war": 0.75,
        "uar": 0.8,
        "macro_f1": 0.77,
        "weighted_precision": 0.81,
        "weighted_recall": 0.75,
        "weighted_f1": 0.76,
        "balanced_accuracy": 0.8,
        "matthews_correlation_coefficient": 0.7,
        "cohen_kappa": 0.63,
    }


def _metrics_report() -> dict:
    return {
        **_aggregate_metrics(),
        "sample_count": 4,
        "confusion_matrix": [[1, 0, 0], [1, 1, 0], [0, 0, 1]],
        "per_class": [
            {
                "label_id": 0,
                "label_name": "neutral",
                "precision": 0.5,
                "recall": 1.0,
                "f1": 2 / 3,
                "support": 1,
            },
            {
                "label_id": 1,
                "label_name": "happy",
                "precision": 1.0,
                "recall": 0.5,
                "f1": 2 / 3,
                "support": 2,
            },
            {
                "label_id": 2,
                "label_name": "sad",
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "support": 1,
            },
        ],
    }


def _write_run(directory: Path, *, predictions_file: str | None = "predictions.jsonl") -> None:
    now = datetime(2026, 9, 9, 2, 30, tzinfo=timezone.utc)
    info = EvaluationRunInfo(
        evaluation_id="eval-detail-demo",
        directory=directory.as_posix(),
        created_at=now,
        started_at=now,
        finished_at=now,
        duration_seconds=1.0,
        source_artifact="artifacts/model",
        source_run_id="run-demo",
        dataset_id="dataset-demo",
        dataset_fingerprint="d" * 64,
        model_name="cnn_baseline",
        split="test",
        device="cpu",
        library_version="0.2.0",
        sample_count=4,
        metrics=_aggregate_metrics(),
        metrics_file="metrics.json",
        predictions_file=predictions_file,
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "evaluation.json").write_text(
        json.dumps(info.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_evaluation_run_detail_does_not_read_prediction_contents(tmp_path: Path, monkeypatch):
    directory = tmp_path / "evaluation"
    _write_run(directory)
    (directory / "metrics.json").write_text(json.dumps(_metrics_report()), encoding="utf-8")
    predictions = directory / "predictions.jsonl"
    predictions.write_text("this content is intentionally invalid jsonl\n", encoding="utf-8")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args, **kwargs):
        if self.name == "predictions.jsonl":
            raise AssertionError("run detail must not read predictions.jsonl")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    detail = inspect_evaluation_run_detail(directory)

    assert isinstance(detail, EvaluationRunDetail)
    assert detail.run.evaluation_id == "eval-detail-demo"
    assert detail.report is not None
    assert detail.report.sample_count == 4
    assert detail.predictions.exists is True
    assert detail.predictions.path == predictions.as_posix()
    assert detail.predictions.size_bytes == predictions.stat().st_size
    assert detail.diagnostics == ()
    json.dumps(detail.to_dict())


def test_evaluation_run_detail_keeps_prediction_metadata_when_metrics_missing(tmp_path: Path):
    directory = tmp_path / "evaluation"
    _write_run(directory)
    predictions = directory / "predictions.jsonl"
    predictions.write_bytes(b"opaque-predictions")

    detail = inspect_evaluation_run_detail(directory)

    assert detail.report is None
    assert detail.predictions.exists is True
    assert detail.predictions.size_bytes == len(b"opaque-predictions")
    assert [item.code for item in detail.diagnostics] == ["evaluation_report_unavailable"]
    json.dumps(detail.to_dict())


def test_evaluation_run_detail_reports_missing_predictions(tmp_path: Path):
    directory = tmp_path / "evaluation"
    _write_run(directory)
    (directory / "metrics.json").write_text(json.dumps(_metrics_report()), encoding="utf-8")

    detail = inspect_evaluation_run_detail(directory)

    assert detail.report is not None
    assert detail.predictions.exists is False
    assert detail.predictions.size_bytes is None
    assert [item.code for item in detail.diagnostics] == [
        "evaluation_predictions_unavailable"
    ]


def test_evaluation_run_detail_allows_run_without_prediction_sink(tmp_path: Path):
    directory = tmp_path / "evaluation"
    _write_run(directory, predictions_file=None)
    (directory / "metrics.json").write_text(json.dumps(_metrics_report()), encoding="utf-8")

    detail = inspect_evaluation_run_detail(directory)

    assert detail.report is not None
    assert detail.predictions.path is None
    assert detail.predictions.exists is False
    assert detail.diagnostics == ()


def test_evaluation_run_detail_keeps_report_validation_error_nonfatal(tmp_path: Path):
    directory = tmp_path / "evaluation"
    _write_run(directory, predictions_file=None)
    invalid_report = {
        **_aggregate_metrics(),
        "sample_count": 4,
        "confusion_matrix": [[1, 0], [0, 1]],
        "per_class": _metrics_report()["per_class"],
    }
    (directory / "metrics.json").write_text(json.dumps(invalid_report), encoding="utf-8")

    detail = inspect_evaluation_run_detail(directory)

    assert detail.report is None
    assert detail.predictions.path is None
    assert [item.code for item in detail.diagnostics] == ["evaluation_report_unavailable"]
    assert detail.diagnostics[0].details["error_type"] == "ValidationError"
