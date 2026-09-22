import pytest

from scripts.audit_latest_only_review import config
from ser_lib.config import ObservabilityConfig
from ser_lib.engine import train_experiment
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken, ProgressEvent


def test_train_experiment_forwards_batch_observability(tmp_path):
    events = []
    cfg = config(tmp_path / "dataset")

    result = train_experiment(
        cfg,
        event_callback=events.append,
        observability=ObservabilityConfig(
            progress_interval_batches=1,
            metric_interval_batches=1,
        ),
    )

    progress = [
        event
        for event in events
        if isinstance(event, ProgressEvent) and event.stage == "train_batch"
    ]
    assert result.training.epochs
    assert len(progress) == cfg.trainer.epochs
    assert [event.completed for event in progress] == [1] * cfg.trainer.epochs
    assert all(event.total == 1 for event in progress)
    assert [event.context.epoch for event in progress] == list(range(1, cfg.trainer.epochs + 1))
    assert all("batch_loss" in event.details for event in progress)


def test_train_experiment_forwards_cancellation(tmp_path):
    cfg = config(tmp_path / "dataset")
    token = CancellationToken()
    token.cancel()

    with pytest.raises(OperationCancelled, match="取消"):
        train_experiment(cfg, cancellation=token)
