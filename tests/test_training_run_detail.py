from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import torch
from pydantic import ValidationError

from ser_lib.engine import (
    TrainingRunInfo,
    load_training_history,
    load_training_run_info,
    scan_checkpoints,
)


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


def test_run_history_and_checkpoint_scan_are_independent_lightweight_sources(
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
        raise AssertionError("checkpoint catalog must not call torch.load")

    monkeypatch.setattr(torch, "load", fail_torch_load)

    run = load_training_run_info(run_dir)
    history = load_training_history(run_dir)
    checkpoints = scan_checkpoints(checkpoint_dir)

    assert run.run_id == "run-detail-demo"
    assert history.epoch_count == 2
    assert {item.name for item in checkpoints.checkpoints} == {
        "best.pt",
        "last.pt",
        "epoch-0002.pt",
    }


def test_missing_history_and_checkpoint_directory_are_explicit_errors(tmp_path: Path):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "missing-checkpoints"
    _write_run(run_dir, checkpoint_dir)

    assert load_training_run_info(run_dir).run_id == "run-detail-demo"
    with pytest.raises(FileNotFoundError, match="history.json"):
        load_training_history(run_dir)
    with pytest.raises(NotADirectoryError, match="checkpoint"):
        scan_checkpoints(checkpoint_dir)


def test_run_and_history_use_actual_directory_after_move(tmp_path: Path):
    original = tmp_path / "original"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(original, checkpoint_dir)
    _write_history(original)

    moved = tmp_path / "moved"
    original.rename(moved)

    run = load_training_run_info(moved)
    history = load_training_history(moved)

    assert run.directory == moved.as_posix()
    assert history.directory == moved.as_posix()


def test_corrupt_history_error_is_not_hidden_by_detail_wrapper(tmp_path: Path):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(run_dir, checkpoint_dir)
    (run_dir / "history.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_training_history(run_dir)


def test_history_validation_error_is_not_hidden_by_detail_wrapper(tmp_path: Path):
    run_dir = tmp_path / "run"
    checkpoint_dir = tmp_path / "checkpoints"
    _write_run(run_dir, checkpoint_dir)
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

    with pytest.raises(ValidationError):
        load_training_history(run_dir)
