from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ser_lib.engine import EvaluationRunInfo, TrainingRunInfo
from ser_lib.services import EvaluationService, TrainingService


def _write_training_run(run_dir: Path, checkpoint_dir: Path) -> None:
    now = datetime(2026, 9, 9, 4, 30, tzinfo=timezone.utc)
    info = TrainingRunInfo(
        run_id="run-validation-error",
        directory=run_dir.as_posix(),
        status="completed",
        created_at=now,
        started_at=now,
        finished_at=now,
        duration_seconds=1.0,
        dataset_id="dataset-demo",
        dataset_fingerprint=None,
        model_id="cnn_baseline",
        seed=42,
        device="cpu",
        library_version="0.2.0",
        config={
            "trainer": {"checkpoint_dir": checkpoint_dir.as_posix()},
            "output_dir": run_dir.as_posix(),
        },
        epochs_completed=1,
        last_epoch=1,
        best_epoch=1,
        best_metric=0.8,
        monitored_metric="accuracy",
        last_checkpoint=None,
        best_checkpoint=None,
        stop_reason=None,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(info.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def _write_evaluation_run(directory: Path) -> None:
    now = datetime(2026, 9, 9, 4, 30, tzinfo=timezone.utc)
    info = EvaluationRunInfo(
        evaluation_id="eval-validation-error",
        directory=directory.as_posix(),
        created_at=now,
        started_at=now,
        finished_at=now,
        duration_seconds=1.0,
        source_artifact="artifacts/model",
        source_run_id="run-demo",
        dataset_id="dataset-demo",
        dataset_fingerprint=None,
        model_name="cnn_baseline",
        split="test",
        device="cpu",
        library_version="0.2.0",
        sample_count=4,
        metrics=_aggregate_metrics(),
        metrics_file="metrics.json",
        predictions_file=None,
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "evaluation.json").write_text(
        json.dumps(info.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_training_run_detail_treats_history_validation_error_as_nonfatal(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_training_run(run_dir, checkpoint_dir)
    (run_dir / "history.json").write_text(
        json.dumps(
            [
                {
                    "epoch": 1,
                    "loss": 0.2,
                    "accuracy": 1.5,
                    "sample_count": 4,
                    "optimizer_steps": 1,
                    "validation": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    detail = TrainingService.inspect_run_detail(run_dir)

    assert detail.history is None
    assert detail.checkpoints.checkpoints == ()
    assert [item.code for item in detail.diagnostics] == ["training_history_unavailable"]
    assert detail.diagnostics[0].details["error_type"] == "ValidationError"


def test_evaluation_run_detail_treats_report_validation_error_as_nonfatal(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evaluation"
    _write_evaluation_run(directory)
    report = {
        **_aggregate_metrics(),
        "sample_count": 4,
        "confusion_matrix": [[1, 0], [0, 1]],
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
    (directory / "metrics.json").write_text(json.dumps(report), encoding="utf-8")

    detail = EvaluationService.inspect_run_detail(directory)

    assert detail.report is None
    assert detail.predictions.path is None
    assert [item.code for item in detail.diagnostics] == ["evaluation_report_unavailable"]
    assert detail.diagnostics[0].details["error_type"] == "ValidationError"
