from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ser_lib.engine._trainer_core import EpochResult, TrainingResult
from ser_lib.engine.experiment import _write_training_history


def _result(*epochs: EpochResult) -> TrainingResult:
    now = datetime.now(timezone.utc)
    return TrainingResult(
        run_id="run",
        status="completed",
        epochs=tuple(epochs),
        best_epoch=None,
        best_metric=None,
        monitored_metric="val_loss",
        started_at=now,
        finished_at=now,
        duration_seconds=0.0,
        last_checkpoint=None,
        best_checkpoint=None,
        stop_reason=None,
    )


def test_history_merges_resume_segments_by_epoch(tmp_path: Path):
    path = tmp_path / "history.json"
    first = EpochResult(epoch=1, loss=1.0, accuracy=0.5, sample_count=2)
    second = EpochResult(epoch=2, loss=0.8, accuracy=0.75, sample_count=2)

    _write_training_history(path, _result(first))
    _write_training_history(path, _result(second))

    history = json.loads(path.read_text(encoding="utf-8"))
    assert [item["epoch"] for item in history] == [1, 2]
    assert history[0]["loss"] == 1.0
    assert history[1]["loss"] == 0.8


def test_history_is_preserved_when_resume_runs_no_new_epoch(tmp_path: Path):
    path = tmp_path / "history.json"
    first = EpochResult(epoch=1, loss=1.0, accuracy=0.5, sample_count=2)
    _write_training_history(path, _result(first))
    before = path.read_text(encoding="utf-8")

    _write_training_history(path, _result())

    assert path.read_text(encoding="utf-8") == before


def test_history_replaces_duplicate_epoch_instead_of_duplicating_it(tmp_path: Path):
    path = tmp_path / "history.json"
    original = EpochResult(epoch=1, loss=1.0, accuracy=0.5, sample_count=2)
    revised = EpochResult(epoch=1, loss=0.9, accuracy=0.6, sample_count=2)

    _write_training_history(path, _result(original))
    _write_training_history(path, _result(revised))

    history = json.loads(path.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["epoch"] == 1
    assert history[0]["loss"] == 0.9
