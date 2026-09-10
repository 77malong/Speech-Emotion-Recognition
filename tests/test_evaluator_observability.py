from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from ser_lib.data import BatchingConfig, SERCollator, SERSample, TensorSpec
from ser_lib.engine import evaluate, write_evaluation_report
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken, EventContext, LifecycleEvent, ProgressEvent
from ser_lib.models import CNNBaseline


def _batch(seed: int = 1):
    generator = torch.Generator().manual_seed(seed)
    samples = [
        SERSample(
            "a",
            {"features": torch.randn(4, 5, generator=generator)},
            {"features": 5},
            0,
            {},
        ),
        SERSample(
            "b",
            {"features": torch.randn(4, 3, generator=generator)},
            {"features": 3},
            1,
            {},
        ),
    ]
    return SERCollator(
        {"features": TensorSpec(layout="FT", feature_dim=4)},
        BatchingConfig(type="dynamic"),
    )(samples)


def _model() -> CNNBaseline:
    return CNNBaseline(feature_dim=4, num_classes=2, hidden_dim=6, dropout=0)


def test_evaluator_exposes_total_progress_lifecycle_and_native_context():
    events = []
    context = EventContext(
        run_id="eval-run",
        epoch=3,
        total_epochs=10,
        global_step=17,
        split="test",
    )

    result = evaluate(
        _model(),
        [_batch(1), _batch(2)],
        num_classes=2,
        event_callback=events.append,
        event_context=context,
    )

    assert result.sample_count == 4
    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert [(event.stage, event.status) for event in lifecycle] == [
        ("evaluation", "started"),
        ("evaluation", "completed"),
    ]
    assert lifecycle[0].context.run_id == "eval-run"
    assert lifecycle[0].context.total_batches == 2
    assert lifecycle[-1].details["sample_count"] == 4
    assert lifecycle[-1].details["duration_seconds"] >= 0

    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert [event.completed for event in progress] == [1, 2]
    assert [event.total for event in progress] == [2, 2]
    assert [event.context.batch for event in progress] == [1, 2]
    assert all(event.context.run_id == "eval-run" for event in progress)
    assert all(event.context.epoch == 3 for event in progress)
    assert all(event.context.total_epochs == 10 for event in progress)
    assert all(event.context.global_step == 17 for event in progress)
    assert all(event.context.total_batches == 2 for event in progress)
    assert all(event.context.split == "test" for event in progress)
    assert progress[-1].details["samples_processed"] == 4
    assert progress[-1].details["running_loss"] > 0
    assert progress[-1].details["elapsed_seconds"] >= 0
    assert progress[-1].details["samples_per_second"] >= 0


def test_evaluator_keeps_total_unknown_for_unsized_iterable():
    events = []

    def batches():
        yield _batch(1)
        yield _batch(2)

    evaluate(
        _model(),
        batches(),
        num_classes=2,
        event_callback=events.append,
        split="validation",
    )

    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert [event.total for event in progress] == [None, None]
    assert all(event.context.total_batches is None for event in progress)
    assert all(event.context.split == "validation" for event in progress)


def test_evaluation_result_and_prediction_records_are_json_safe(tmp_path: Path):
    result = evaluate(
        _model(),
        [_batch(3)],
        num_classes=2,
        labels={0: "neutral", 1: "happy"},
    )

    payload = result.to_dict()
    summary = result.summary_dict()
    json.dumps(payload, ensure_ascii=False)
    json.dumps(summary, ensure_ascii=False)

    assert payload["sample_count"] == 2
    assert isinstance(payload["confusion_matrix"], list)
    assert isinstance(payload["per_class"], list)
    assert isinstance(payload["predictions"], list)
    assert len(payload["predictions"]) == 2
    assert isinstance(payload["predictions"][0]["probabilities"], list)
    assert "predictions" not in summary
    assert result.per_class[0].to_dict()["label_name"] == "neutral"
    assert result.predictions[0].to_dict()["uid"] == "a"

    directory = write_evaluation_report(tmp_path / "report", result)
    metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    predictions = [
        json.loads(line)
        for line in (directory / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "predictions" not in metrics
    assert metrics["sample_count"] == 2
    assert len(predictions) == 2
    assert predictions[0]["uid"] == "a"


def test_evaluator_emits_cancelled_lifecycle_event_and_restores_model_mode():
    events = []
    token = CancellationToken()
    token.cancel()
    model = _model()
    model.train()

    with pytest.raises(OperationCancelled):
        evaluate(
            model,
            [_batch(1)],
            num_classes=2,
            event_callback=events.append,
            cancellation=token,
            event_context=EventContext(run_id="cancel-eval"),
        )

    statuses = [
        event.status
        for event in events
        if isinstance(event, LifecycleEvent) and event.stage == "evaluation"
    ]
    assert statuses == ["started", "cancelled"]
    cancelled = [
        event
        for event in events
        if isinstance(event, LifecycleEvent) and event.status == "cancelled"
    ][0]
    assert cancelled.context.run_id == "cancel-eval"
    assert cancelled.details["samples_processed"] == 0
    assert model.training


def test_evaluator_emits_failed_lifecycle_event_and_restores_model_mode():
    events = []
    model = _model()
    model.train()
    invalid = replace(_batch(1), labels=None)

    with pytest.raises(ValueError, match="labels"):
        evaluate(
            model,
            [invalid],
            num_classes=2,
            event_callback=events.append,
            event_context=EventContext(run_id="failed-eval", split="test"),
        )

    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert [(event.stage, event.status) for event in lifecycle] == [
        ("evaluation", "started"),
        ("evaluation", "failed"),
    ]
    assert lifecycle[-1].context.run_id == "failed-eval"
    assert lifecycle[-1].details["error_type"] == "ValueError"
    assert lifecycle[-1].details["samples_processed"] == 0
    assert model.training


def test_evaluator_rejects_conflicting_split_and_context_total():
    with pytest.raises(ValueError, match="split"):
        evaluate(
            _model(),
            [_batch(1)],
            num_classes=2,
            event_context=EventContext(split="test"),
            split="val",
        )

    with pytest.raises(ValueError, match="total_batches"):
        evaluate(
            _model(),
            [_batch(1)],
            num_classes=2,
            event_context=EventContext(total_batches=2),
        )
