from __future__ import annotations

from pathlib import Path

import pytest
import torch
from pydantic import ValidationError

from ser_lib.config import BatchingConfig
from ser_lib.data import SERCollator, SERSample, TensorSpec
from ser_lib.engine import ObservabilityConfig, Trainer, TrainerConfig
from ser_lib.foundation.events import CheckpointEvent
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken, LifecycleEvent, MetricEvent, ProgressEvent
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


def test_observability_config_validates_intervals():
    with pytest.raises(ValidationError):
        ObservabilityConfig(progress_interval_batches=0)
    with pytest.raises(ValidationError):
        ObservabilityConfig(metric_interval_batches=0)


def test_trainer_exposes_detailed_progress_context_and_live_metrics():
    events = []
    trainer = Trainer(
        _model(),
        TrainerConfig(epochs=1),
        event_callback=events.append,
        observability=ObservabilityConfig(
            progress_interval_batches=1,
            metric_interval_batches=2,
        ),
        run_id="run-test",
    )

    training_result = trainer.fit([_batch(1), _batch(2), _batch(3)])

    assert len(training_result.epochs) == 1
    progress = [
        event for event in events
        if isinstance(event, ProgressEvent) and event.stage == "train_batch"
    ]
    assert [event.completed for event in progress] == [1, 2, 3]
    assert all(event.total == 3 for event in progress)
    assert [event.context.batch for event in progress] == [1, 2, 3]
    assert [event.context.global_step for event in progress] == [1, 2, 3]
    assert all(event.context.run_id == "run-test" for event in progress)
    assert all(event.context.epoch == 1 for event in progress)
    assert all(event.context.total_epochs == 1 for event in progress)
    assert all(event.context.total_batches == 3 for event in progress)
    assert all(event.context.split == "train" for event in progress)

    last_details = progress[-1].details
    assert last_details["samples_processed"] == 6
    assert last_details["samples_total"] == 6
    assert last_details["optimizer_steps"] == 3
    assert last_details["running_loss"] > 0
    assert 0 <= last_details["running_accuracy"] <= 1
    assert last_details["learning_rate"] > 0
    assert last_details["elapsed_seconds"] >= 0
    assert last_details["epoch_elapsed_seconds"] >= 0
    assert last_details["estimated_epoch_remaining_seconds"] == pytest.approx(0.0)
    assert last_details["estimated_remaining_seconds"] == pytest.approx(0.0)
    assert last_details["samples_per_second"] >= 0
    assert last_details["batches_per_second"] >= 0

    live_metrics = [
        event for event in events
        if isinstance(event, MetricEvent) and event.step == 2
    ]
    assert {event.name for event in live_metrics} == {
        "batch_loss",
        "running_loss",
        "running_accuracy",
        "learning_rate",
        "samples_per_second",
    }
    assert all(event.context.global_step == 2 for event in live_metrics)
    assert all(event.context.split == "train" for event in live_metrics)

    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert ("training", "started") in {(event.stage, event.status) for event in lifecycle}
    assert ("train", "phase_started") in {(event.stage, event.status) for event in lifecycle}
    assert ("train", "phase_completed") in {(event.stage, event.status) for event in lifecycle}
    assert ("epoch", "completed") in {(event.stage, event.status) for event in lifecycle}
    assert ("training", "completed") in {(event.stage, event.status) for event in lifecycle}


def test_validation_progress_is_enriched_with_training_run_context():
    events = []
    trainer = Trainer(
        _model(),
        TrainerConfig(epochs=1),
        event_callback=events.append,
        run_id="run-validation",
    )

    trainer.fit([_batch(1)], val_batches=[_batch(2), _batch(3)])

    validation_progress = [
        event for event in events
        if isinstance(event, ProgressEvent) and event.stage == "evaluate_batch"
    ]
    assert [event.completed for event in validation_progress] == [1, 2]
    assert all(event.total == 2 for event in validation_progress)
    assert all(event.context.run_id == "run-validation" for event in validation_progress)
    assert all(event.context.epoch == 1 for event in validation_progress)
    assert all(event.context.total_batches == 2 for event in validation_progress)
    assert all(event.context.split == "val" for event in validation_progress)


def test_checkpoint_events_describe_epoch_last_and_best_files(tmp_path: Path):
    events = []
    trainer = Trainer(
        _model(),
        TrainerConfig(
            epochs=1,
            checkpoint_dir=tmp_path / "checkpoints",
            monitor="val_accuracy",
        ),
        event_callback=events.append,
        run_id="run-checkpoint",
    )

    trainer.fit([_batch(1)], val_batches=[_batch(2)])

    checkpoint_events = [event for event in events if isinstance(event, CheckpointEvent)]
    assert [(event.action, event.kind) for event in checkpoint_events] == [
        ("started", "epoch"),
        ("saved", "epoch"),
        ("started", "last"),
        ("saved", "last"),
        ("started", "best"),
        ("saved", "best"),
        ("best_model_updated", "best"),
    ]
    assert all(event.context.run_id == "run-checkpoint" for event in checkpoint_events)
    best = checkpoint_events[-1]
    assert Path(best.path).name == "best.pt"
    assert best.metric_name == "val_accuracy"
    assert best.metric_value == pytest.approx(trainer.best_metric)


def test_cancelled_training_emits_cancelled_lifecycle_event():
    events = []
    token = CancellationToken()
    token.cancel()
    trainer = Trainer(
        _model(),
        TrainerConfig(epochs=1),
        event_callback=events.append,
        cancellation=token,
        run_id="run-cancel",
    )

    with pytest.raises(OperationCancelled):
        trainer.fit([_batch(1)])

    statuses = [
        event.status
        for event in events
        if isinstance(event, LifecycleEvent) and event.stage == "training"
    ]
    assert statuses == ["started", "cancelled"]


def test_event_callback_does_not_change_training_results_or_weights():
    torch.manual_seed(123)
    source = _model()
    initial_state = {
        name: parameter.detach().clone()
        for name, parameter in source.state_dict().items()
    }
    batches = [_batch(10), _batch(11)]

    plain_model = _model()
    plain_model.load_state_dict(initial_state)
    plain = Trainer(plain_model, TrainerConfig(epochs=1, seed=7))
    plain_result = plain.fit(batches)

    observed_model = _model()
    observed_model.load_state_dict(initial_state)
    observed_events = []
    observed = Trainer(
        observed_model,
        TrainerConfig(epochs=1, seed=7),
        event_callback=observed_events.append,
        observability=ObservabilityConfig(metric_interval_batches=1),
    )
    observed_result = observed.fit(batches)

    assert observed_events
    assert observed_result.epochs[0].loss == pytest.approx(
        plain_result.epochs[0].loss, abs=1e-12
    )
    assert observed_result.epochs[0].accuracy == pytest.approx(
        plain_result.epochs[0].accuracy, abs=1e-12
    )
    for name, parameter in plain_model.state_dict().items():
        assert torch.allclose(parameter, observed_model.state_dict()[name], atol=1e-8)


def test_resume_restores_run_and_progress_counters(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    trainer = Trainer(
        _model(),
        TrainerConfig(epochs=1, checkpoint_dir=checkpoint_dir),
        run_id="run-resume",
    )
    trainer.fit([_batch(1), _batch(2)])

    resumed = Trainer(_model(), trainer.config)
    resumed.resume_from(checkpoint_dir / "last.pt")

    assert resumed.run_id == "run-resume"
    assert resumed.global_step == trainer.global_step == 2
    assert resumed.optimizer_step == trainer.optimizer_step == 2
