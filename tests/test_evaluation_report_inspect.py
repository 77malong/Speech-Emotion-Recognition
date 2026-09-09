from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.engine import EvaluationReportInfo, inspect_evaluation_report
from ser_lib.services import EvaluationService


def _metrics() -> dict:
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


def _report(tmp_path: Path, *, predictions: bool = True) -> Path:
    directory = tmp_path / "evaluation"
    directory.mkdir()
    (directory / "metrics.json").write_text(
        json.dumps(_metrics()),
        encoding="utf-8",
    )
    if predictions:
        (directory / "predictions.jsonl").write_text(
            '{"uid":"a","target":0,"predicted":0,"confidence":0.9,"probabilities":[0.9,0.05,0.05]}\n',
            encoding="utf-8",
        )
    return directory


def test_evaluation_service_inspects_metrics_without_loading_predictions(tmp_path: Path):
    directory = _report(tmp_path)

    info = EvaluationService.inspect_report(directory)

    assert isinstance(info, EvaluationReportInfo)
    assert info.directory == directory.as_posix()
    assert info.sample_count == 4
    assert info.accuracy == pytest.approx(0.75)
    assert info.confusion_matrix == ((1, 0, 0), (1, 1, 0), (0, 0, 1))
    assert [item.label_name for item in info.per_class] == ["neutral", "happy", "sad"]
    assert info.predictions_file == (directory / "predictions.jsonl").as_posix()
    assert info.predictions_bytes == (directory / "predictions.jsonl").stat().st_size
    json.dumps(info.to_dict())


def test_evaluation_report_inspection_allows_missing_prediction_file(tmp_path: Path):
    directory = _report(tmp_path, predictions=False)

    info = inspect_evaluation_report(directory)

    assert info.predictions_file is None
    assert info.predictions_bytes is None
    assert info.sample_count == 4


def test_evaluation_report_inspection_rejects_invalid_report(tmp_path: Path):
    with pytest.raises(NotADirectoryError):
        inspect_evaluation_report(tmp_path / "missing")

    directory = tmp_path / "evaluation"
    directory.mkdir()
    with pytest.raises(FileNotFoundError):
        inspect_evaluation_report(directory)

    (directory / "metrics.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="顶层"):
        inspect_evaluation_report(directory)

    invalid = _metrics()
    invalid["confusion_matrix"] = [[1, 0], [0, 3]]
    (directory / "metrics.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValidationError, match="维度"):
        inspect_evaluation_report(directory)

    invalid = _metrics()
    invalid["confusion_matrix"] = [[1, 0, 0], [1, 0, 0], [0, 0, 1]]
    (directory / "metrics.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValidationError, match="sample_count"):
        inspect_evaluation_report(directory)
