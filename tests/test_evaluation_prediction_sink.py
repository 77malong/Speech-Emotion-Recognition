import json
from pathlib import Path

import pytest
import torch

from ser_lib.data import SERBatch, TensorSpec
from ser_lib.data.validation import ModelSpec
from ser_lib.engine import JsonlPredictionSink, PredictionRecord, evaluate
from ser_lib.models import ModelOutput, SERModel


class ScoreModel(SERModel):
    @property
    def model_spec(self):
        return ModelSpec(
            model_id="prediction_sink_test",
            required_inputs={"scores": TensorSpec(layout="D", feature_dim=3)},
            supports_masks=False,
            supports_variable_length=False,
            num_classes=3,
        )

    @property
    def model_config(self):
        return {}

    def forward(self, batch):
        return ModelOutput(logits=batch.inputs["scores"])


def _batch() -> SERBatch:
    return SERBatch(
        inputs={
            "scores": torch.tensor(
                [
                    [4.0, 1.0, 0.0],
                    [3.0, 2.0, 0.0],
                    [0.0, 4.0, 1.0],
                    [0.0, 1.0, 4.0],
                ]
            )
        },
        lengths={},
        masks={},
        labels=torch.tensor([0, 1, 1, 2], dtype=torch.long),
        uids=["a", "b", "c", "d"],
        metadata=[{}, {}, {}, {}],
    )


class CollectSink:
    def __init__(self) -> None:
        self.records: list[PredictionRecord] = []

    def write(self, record: PredictionRecord) -> None:
        self.records.append(record)


def test_evaluate_can_stream_without_retaining_predictions():
    sink = CollectSink()

    result = evaluate(
        ScoreModel(),
        [_batch()],
        num_classes=3,
        prediction_sink=sink,
        retain_predictions=False,
    )

    assert result.sample_count == 4
    assert result.accuracy == pytest.approx(0.75)
    assert result.predictions == ()
    assert [record.uid for record in sink.records] == ["a", "b", "c", "d"]
    assert sink.records[1].predicted == 0
    assert sum(sink.records[0].probabilities) == pytest.approx(1.0)


def test_evaluate_sink_and_retention_can_be_enabled_together():
    sink = CollectSink()

    result = evaluate(
        ScoreModel(),
        [_batch()],
        num_classes=3,
        prediction_sink=sink,
    )

    assert len(result.predictions) == 4
    assert tuple(sink.records) == result.predictions


def test_jsonl_prediction_sink_writes_json_safe_rows(tmp_path: Path):
    path = tmp_path / "predictions.jsonl"

    with JsonlPredictionSink(path) as sink:
        result = evaluate(
            ScoreModel(),
            [_batch()],
            num_classes=3,
            prediction_sink=sink,
            retain_predictions=False,
        )
        sink.flush()

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert result.predictions == ()
    assert len(rows) == 4
    assert rows[0]["uid"] == "a"
    assert rows[0]["target"] == 0
    assert isinstance(rows[0]["probabilities"], list)


def test_prediction_sink_failure_fails_evaluation_and_restores_model_mode():
    class FailingSink:
        def write(self, record: PredictionRecord) -> None:
            raise OSError(f"cannot write {record.uid}")

    model = ScoreModel()
    model.train()

    with pytest.raises(OSError, match="cannot write a"):
        evaluate(
            model,
            [_batch()],
            num_classes=3,
            prediction_sink=FailingSink(),
            retain_predictions=False,
        )

    assert model.training is True
