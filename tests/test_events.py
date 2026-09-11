from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ser_lib.engine.events import CheckpointEvent
from ser_lib.foundation.events import (
    EventContext,
    LifecycleEvent,
    LogEvent,
    MetricEvent,
    ProgressEvent,
)


def test_event_context_has_stable_json_shape():
    context = EventContext(
        run_id="run-001",
        epoch=2,
        total_epochs=10,
        batch=4,
        total_batches=20,
        global_step=24,
        split="train",
    )
    assert context.to_dict() == {
        "run_id": "run-001",
        "epoch": 2,
        "total_epochs": 10,
        "batch": 4,
        "total_batches": 20,
        "global_step": 24,
        "split": "train",
    }


def test_progress_event_v2_is_json_safe_and_preserves_legacy_constructor():
    event = ProgressEvent(
        "decode",
        completed=2,
        total=4,
        context=EventContext(run_id="run-001", batch=2, total_batches=4),
        details={"path": Path("audio.wav"), "rate": 12.5},
    )
    payload = event.to_dict()
    assert "schema_version" not in payload
    assert payload["event_type"] == "progress"
    assert payload["stage"] == "decode"
    assert payload["completed"] == 2
    assert payload["total"] == 4
    assert payload["context"]["run_id"] == "run-001"
    assert payload["details"] == {"path": "audio.wav", "rate": 12.5}
    assert payload["sequence"] > 0
    assert event.fraction == 0.5
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def test_event_sequences_are_monotonic_across_event_types():
    progress = ProgressEvent("scan", completed=0)
    metric = MetricEvent("loss", 0.5)

    assert metric.sequence > progress.sequence


def test_metric_legacy_split_is_mirrored_into_event_context():
    event = MetricEvent("loss", 0.5, step=3, split="train")

    assert event.context.split == "train"
    assert event.to_dict()["context"]["split"] == "train"
    assert event.to_dict()["split"] == "train"


def test_metric_rejects_conflicting_legacy_and_context_split():
    with pytest.raises(ValueError, match="context.split"):
        MetricEvent(
            "loss",
            0.5,
            split="train",
            context=EventContext(split="validation"),
        )


def test_metric_event_rejects_non_finite_value_during_serialization():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="非有限浮点值"):
            MetricEvent("loss", value).to_dict()


def test_log_event_converts_common_metadata_to_json_safe_values():
    event = LogEvent(
        "INFO",
        "saved",
        details={
            "path": Path("artifacts/model"),
            "at": datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
            "items": ("a", "b"),
        },
    )
    payload = event.to_dict()

    assert payload["details"]["path"] == "artifacts/model"
    assert payload["details"]["at"].endswith("+00:00")
    assert payload["details"]["items"] == ["a", "b"]
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def test_event_details_reject_non_finite_nested_float():
    with pytest.raises(ValueError, match="非有限浮点值"):
        LogEvent("INFO", "bad", details={"nested": [1.0, float("nan")]}).to_dict()


def test_lifecycle_event_serializes_status_and_context():
    event = LifecycleEvent(
        "training",
        "started",
        context=EventContext(run_id="run-001"),
        details={"device": "cpu"},
    )
    payload = event.to_dict()

    assert payload["event_type"] == "lifecycle"
    assert payload["stage"] == "training"
    assert payload["status"] == "started"
    assert payload["context"]["run_id"] == "run-001"
    assert payload["details"] == {"device": "cpu"}
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def test_lifecycle_event_rejects_unknown_status():
    with pytest.raises(ValueError, match="status"):
        LifecycleEvent("training", "unknown")


def test_checkpoint_event_is_json_safe():
    event = CheckpointEvent(
        "saved",
        "best",
        Path("checkpoints/best.pt"),
        3,
        metric_name="val_uar",
        metric_value=0.72,
        context=EventContext(run_id="run-001", epoch=3),
    )
    payload = event.to_dict()

    assert payload["event_type"] == "checkpoint"
    assert payload["action"] == "saved"
    assert payload["kind"] == "best"
    assert payload["path"] == "checkpoints/best.pt"
    assert payload["metric_name"] == "val_uar"
    assert payload["metric_value"] == 0.72
    json.dumps(payload, ensure_ascii=False, allow_nan=False)


def test_checkpoint_event_rejects_non_finite_metric_value():
    with pytest.raises(ValueError, match="非有限浮点值"):
        CheckpointEvent("saved", "best", "best.pt", 1, metric_value=float("nan")).to_dict()


def test_checkpoint_event_rejects_unknown_action():
    with pytest.raises(ValueError, match="action"):
        CheckpointEvent("unknown", "best", "best.pt", 1)
