from __future__ import annotations

import json
from pathlib import Path

import pytest

from ser_lib.engine import EvaluationPredictionPage, query_evaluation_predictions
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


def test_query_predictions_filters_and_pages_without_materializing_all_rows(tmp_path: Path):
    directory = _predictions(tmp_path)

    first = query_evaluation_predictions(
        directory,
        incorrect_only=True,
        offset=0,
        limit=2,
    )

    assert isinstance(first, EvaluationPredictionPage)
    assert first.matched_count == 3
    assert first.returned_count == 2
    assert [record.uid for record in first.records] == ["b", "d"]
    assert first.has_more is True
    assert first.next_offset == 2

    second = query_evaluation_predictions(
        directory,
        incorrect_only=True,
        offset=2,
        limit=2,
    )
    assert [record.uid for record in second.records] == ["f"]
    assert second.matched_count == 3
    assert second.has_more is False
    assert second.next_offset is None
    json.dumps(second.to_dict())


def test_query_predictions_supports_confusion_cell_filters(tmp_path: Path):
    directory = _predictions(tmp_path)

    target_one = query_evaluation_predictions(directory, target=1, limit=10)
    predicted_two = query_evaluation_predictions(directory, predicted=2, limit=10)
    cell = query_evaluation_predictions(directory, target=1, predicted=0, limit=10)

    assert [record.uid for record in target_one.records] == ["b", "c", "f"]
    assert [record.uid for record in predicted_two.records] == ["e", "f"]
    assert [record.uid for record in cell.records] == ["b"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"offset": -1}, "offset"),
        ({"limit": 0}, "limit"),
        ({"limit": 1001}, "limit"),
        ({"target": -1}, "target"),
        ({"predicted": -1}, "predicted"),
    ],
)
def test_query_predictions_rejects_invalid_page_parameters(
    tmp_path: Path,
    kwargs: dict,
    message: str,
):
    directory = _predictions(tmp_path)
    with pytest.raises(ValueError, match=message):
        query_evaluation_predictions(directory, **kwargs)


def test_query_predictions_reports_missing_or_corrupt_jsonl_with_line_number(tmp_path: Path):
    directory = tmp_path / "evaluation"
    directory.mkdir()

    with pytest.raises(FileNotFoundError, match="predictions.jsonl"):
        query_evaluation_predictions(directory)

    (directory / "predictions.jsonl").write_text(
        _row("good", 0, 0, 0.9, [0.9, 0.1])
        + "\n"
        + '{"uid":"broken","target":1}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="第 2 行"):
        query_evaluation_predictions(directory)


def test_query_predictions_honors_cancellation(tmp_path: Path):
    directory = _predictions(tmp_path)
    token = CancellationToken()
    token.cancel()

    with pytest.raises(OperationCancelled):
        query_evaluation_predictions(directory, cancellation=token)
