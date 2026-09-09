from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from ser_lib.engine import TrainingRunDetail, TrainingRunInfo
from ser_lib.services import TrainingService


def _write_run(run_dir: Path, checkpoint_dir: Path) -> TrainingRunInfo:
    now = datetime(2026, 9, 9, 2, 0, tzinfo=timezone.utc)
    info = TrainingRunInfo(
        run_id="run-detail-demo",
        directory=run_dir.as_posix(),
        status="completed",
        created_at=now,
        started_at=now,
        finished_at=now,
        duration_seconds=12.5,
        dataset_id="dataset-demo",
        dataset_fingerprint="d" * 64,
        model_id="cnn_baseline",
        seed=42,
        device="cpu",
        library_version="0.2.0",
        config={
            "trainer": {"checkpoint_dir": checkpoint_dir.as_posix()},
            "output_dir": run_dir.as_posix(),
        },
        epochs_completed=2,
        last_epoch=2,
        best_epoch=2,
        best_metric=0.8,
        monitored_metric="accuracy",
        last_checkpoint=(checkpoint_dir / "epoch-0002.pt").as_posix(),
        best_checkpoint=(checkpoint_dir / "best.pt").as_posix(),
        stop_reason=None,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(info.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return info


def _write_history(run_dir: Path) -> None:
    (run_dir / "history.json").write_text(
        json.dumps(
            [
                {
                    "epoch": 1,
                    "loss": 0.8,
                    "accuracy": 0.6,
                    "sample_count": 10,
                    "optimizer_steps": 2,
                    "validation": {"accuracy": 0.65},
                },
                {
                    "epoch": 2,
                    "loss": 0.4,
                    "accuracy": 0.8,
                    "sample_count": 10,
                    "optimizer_steps": 2,
                    "validation": {"accuracy": 0.8},
                },
            ]
        ),
        encoding="utf-8",
    )


def test_training_run_detail_aggregates_lightweight_sources(
    tmp_path: Path,
    monkeypatch,
):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(run_dir, checkpoint_dir)
    _write_history(run_dir)
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "best.pt").write_bytes(b"not-a-pytorch-checkpoint")
    (checkpoint_dir / "last.pt").write_bytes(b"still-not-a-checkpoint")
    (checkpoint_dir / "epoch-0002.pt").write_bytes(b"opaque")

    def fail_torch_load(*args, **kwargs):
        raise AssertionError("TrainingRunDetail must not call torch.load")

    monkeypatch.setattr(torch, "load", fail_torch_load)

    detail = TrainingService.inspect_run_detail(run_dir)

    assert isinstance(detail, TrainingRunDetail)
    assert detail.run.run_id == "run-detail-demo"
    assert detail.history is not None
    assert detail.history.epoch_count == 2
    assert {item.name for item in detail.checkpoints.checkpoints} == {
        "best.pt",
        "last.pt",
        "epoch-0002.pt",
    }
    assert detail.diagnostics == ()
    json.dumps(detail.to_dict())


def test_training_run_detail_tolerates_missing_history_and_checkpoints(tmp_path: Path):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "missing-checkpoints"
    _write_run(run_dir, checkpoint_dir)

    detail = TrainingService.inspect_run_detail(run_dir)

    assert detail.history is None
    assert detail.checkpoints.checkpoints == ()
    assert detail.checkpoints.failures == ()
    assert detail.checkpoints.root == checkpoint_dir.as_posix()
    assert [item.code for item in detail.diagnostics] == [
        "training_history_unavailable",
        "training_checkpoint_directory_missing",
    ]
    json.dumps(detail.to_dict())


def test_training_run_detail_uses_run_directory_after_move(tmp_path: Path):
    original = tmp_path / "original"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(original, checkpoint_dir)
    _write_history(original)
    checkpoint_dir.mkdir(parents=True)

    moved = tmp_path / "moved"
    original.rename(moved)

    detail = TrainingService.inspect_run_detail(moved)

    assert detail.run.directory == moved.as_posix()
    assert detail.history is not None
    assert detail.history.directory == moved.as_posix()


def test_training_run_detail_keeps_corrupt_history_nonfatal(tmp_path: Path):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(run_dir, checkpoint_dir)
    checkpoint_dir.mkdir(parents=True)
    (run_dir / "history.json").write_text("{broken", encoding="utf-8")

    detail = TrainingService.inspect_run_detail(run_dir)

    assert detail.history is None
    assert [item.code for item in detail.diagnostics] == ["training_history_unavailable"]
    assert detail.diagnostics[0].details["error_type"] == "JSONDecodeError"


def test_training_run_detail_keeps_history_validation_error_nonfatal(tmp_path: Path):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(run_dir, checkpoint_dir)
    checkpoint_dir.mkdir(parents=True)
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
