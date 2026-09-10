from __future__ import annotations

import json
from itertools import islice
from pathlib import Path

import pytest

from ser_lib.engine import iter_evaluation_predictions
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken


def _row(
    uid: str,
    target: int,
    predicted: int,
    confidence: float,
    probabilities: list[float],
) -> str:
    return json.dumps(
        {
            "uid": uid,
            "target": target,
            "predicted": predicted,
            "confidence": confidence,
            "probabilities": probabilities,
        }
    )


def _predictions(tmp_path: Path) -> Path:
    directory = tmp_path / "evaluation"
    directory.mkdir()
    rows = [
        _row("a", 0, 0, 0.90, [0.90, 0.05, 0.05]),
        _row("b", 1, 0, 0.70, [0.70, 0.20, 0.10]),
        _row("c", 1, 1, 0.80, [0.10, 0.80, 0.10]),
        _row("d", 2, 1, 0.60, [0.10, 0.60, 0.30]),
        _row("e", 2, 2, 0.85, [0.05, 0.10, 0.85]),
        _row("f", 1, 2, 0.55, [0.15, 0.30, 0.55]),
    ]
    (directory / "predictions.jsonl").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return directory


def test_iter_predictions_filters_and_supports_caller_side_pagination(tmp_path: Path):
    directory = _predictions(tmp_path)
    records = iter_evaluation_predictions(directory, incorrect_only=True)

    first = list(islice(records, 2))
    second = list(islice(records, 2))

    assert [record.uid for record in first] == ["b", "d"]
    assert [record.uid for record in second] == ["f"]


def test_iter_predictions_supports_confusion_cell_filters(tmp_path: Path):
    directory = _predictions(tmp_path)

    target_one = list(iter_evaluation_predictions(directory, target=1))
    predicted_two = list(iter_evaluation_predictions(directory, predicted=2))
    cell = list(iter_evaluation_predictions(directory, target=1, predicted=0))

    assert [record.uid for record in target_one] == ["b", "c", "f"]
    assert [record.uid for record in predicted_two] == ["e", "f"]
    assert [record.uid for record in cell] == ["b"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"target": -1}, "target"),
        ({"predicted": -1}, "predicted"),
    ],
)
def test_iter_predictions_rejects_invalid_filters(
    tmp_path: Path,
    kwargs: dict,
    message: str,
):
    directory = _predictions(tmp_path)
    with pytest.raises(ValueError, match=message):
        iter_evaluation_predictions(directory, **kwargs)


def test_iter_predictions_reports_missing_or_corrupt_jsonl_with_line_number(tmp_path: Path):
    directory = tmp_path / "evaluation"
    directory.mkdir()

    with pytest.raises(FileNotFoundError, match="predictions.jsonl"):
        iter_evaluation_predictions(directory)

    (directory / "predictions.jsonl").write_text(
        _row("good", 0, 0, 0.9, [0.9, 0.1])
        + "\n"
        + '{"uid":"broken","target":1}\n',
        encoding="utf-8",
    )
    records = iter_evaluation_predictions(directory)
    assert next(records).uid == "good"
    with pytest.raises(ValueError, match="第 2 行"):
        next(records)


def test_iter_predictions_does_not_scan_tail_before_first_yield(tmp_path: Path):
    directory = tmp_path / "evaluation"
    directory.mkdir()
    (directory / "predictions.jsonl").write_text(
        _row("first", 0, 0, 0.9, [0.9, 0.1]) + "\n" + "{broken\n",
        encoding="utf-8",
    )

    records = iter_evaluation_predictions(directory)

    assert next(records).uid == "first"


def test_iter_predictions_honors_cancellation(tmp_path: Path):
    directory = _predictions(tmp_path)
    token = CancellationToken()
    token.cancel()

    with pytest.raises(OperationCancelled):
        next(iter_evaluation_predictions(directory, cancellation=token))
