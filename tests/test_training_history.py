from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.engine import TrainingHistoryInfo, load_training_history


def _epoch(epoch: int, *, validation: dict[str, float] | None = None) -> dict:
    return {
        "epoch": epoch,
        "loss": 1.0 / epoch,
        "accuracy": min(0.4 + epoch * 0.1, 1.0),
        "sample_count": 32,
        "optimizer_steps": epoch * 4,
        "validation": validation,
    }


def test_training_history_inspection_returns_json_safe_curve_data(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "history.json").write_text(
        json.dumps([
            _epoch(1, validation={"loss": 0.8, "accuracy": 0.6, "uar": 0.55}),
            _epoch(2, validation={"loss": 0.6, "accuracy": 0.7, "uar": 0.65}),
        ]),
        encoding="utf-8",
    )

    history = load_training_history(run)

    assert isinstance(history, TrainingHistoryInfo)
    assert history.directory == run.as_posix()
    assert history.history_file == (run / "history.json").as_posix()
    assert history.epoch_count == 2
    assert [item.epoch for item in history.epochs] == [1, 2]
    assert history.epochs[1].validation["uar"] == pytest.approx(0.65)
    json.dumps(history.to_dict())

    direct = load_training_history(run / "history.json")
    assert direct == history


def test_training_history_rejects_missing_invalid_or_non_monotonic_data(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_training_history(tmp_path / "missing")

    history_path = tmp_path / "history.json"
    history_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="顶层"):
        load_training_history(history_path)

    invalid = _epoch(1)
    invalid["unexpected"] = True
    history_path.write_text(json.dumps([invalid]), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_training_history(history_path)

    history_path.write_text(
        json.dumps([_epoch(2), _epoch(1)]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="严格递增"):
        load_training_history(history_path)

    history_path.write_text(
        json.dumps([_epoch(1), _epoch(1)]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="不能重复"):
        load_training_history(history_path)
