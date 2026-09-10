from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from ser_lib import TrainingResult as RootTrainingResult
from ser_lib.data import BatchingConfig, SERCollator, SERSample, TensorSpec
from ser_lib.engine import Trainer, TrainerConfig, TrainingResult, TrainingStatus
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken
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


def test_training_result_is_public_and_fit_returns_it_directly():
    assert RootTrainingResult is TrainingResult
    status: TrainingStatus = "completed"
    assert status == "completed"

    trainer = Trainer(_model(), TrainerConfig(epochs=1), run_id="result-completed")
    result = trainer.fit([_batch(1), _batch(2)])

    assert isinstance(result, TrainingResult)
    assert trainer.last_result is result
    assert result.run_id == "result-completed"
    assert result.status == "completed"
    assert len(result.epochs) == 1
    assert result.monitored_metric == trainer.config.monitor
    assert result.stop_reason is None
    assert result.started_at.tzinfo is not None
    assert result.finished_at.tzinfo is not None
    assert result.finished_at >= result.started_at
    assert result.duration_seconds >= 0
    assert result.last_checkpoint is None
    assert result.best_checkpoint is None

    payload = result.to_dict()
    assert payload["epochs"] == [result.epochs[0].to_dict()]
    assert payload["started_at"].endswith("+00:00")
    assert payload["finished_at"].endswith("+00:00")
    json.dumps(payload)


def test_training_result_tracks_last_and_best_checkpoint(tmp_path: Path):
    trainer = Trainer(
        _model(),
        TrainerConfig(
            epochs=1,
            checkpoint_dir=tmp_path / "checkpoints",
            monitor="val_accuracy",
        ),
        run_id="result-checkpoint",
    )

    result = trainer.fit([_batch(1)], val_batches=[_batch(2)])

    assert trainer.last_result is result
    assert result.status == "completed"
    assert result.best_epoch == 1
    assert result.best_metric == pytest.approx(trainer.best_metric)
    assert result.last_checkpoint is not None
    assert result.last_checkpoint.name == "last.pt"
    assert result.best_checkpoint is not None
    assert result.best_checkpoint.name == "best.pt"
    assert result.last_checkpoint.is_file()
    assert result.best_checkpoint.is_file()
    payload = result.to_dict()
    assert payload["last_checkpoint"].endswith("last.pt")
    assert payload["best_checkpoint"].endswith("best.pt")


def test_early_stopping_has_distinct_training_result_status():
    trainer = Trainer(
        _model(),
        TrainerConfig(
            epochs=4,
            monitor="val_accuracy",
            early_stopping_patience=1,
            early_stopping_min_delta=2.0,
        ),
        run_id="result-early-stop",
    )

    result = trainer.fit(lambda: [_batch(1)], val_batches=lambda: [_batch(2)])

    assert trainer.last_result is result
    assert len(result.epochs) == 2
    assert result.status == "early_stopped"
    assert result.stop_reason == "early_stopped"
    assert result.best_epoch == 1


def test_cancelled_training_records_result_before_reraising():
    token = CancellationToken()
    token.cancel()
    trainer = Trainer(
        _model(),
        TrainerConfig(epochs=2),
        cancellation=token,
        run_id="result-cancelled",
    )

    with pytest.raises(OperationCancelled):
        trainer.fit([_batch(1)])

    result = trainer.last_result
    assert result is not None
    assert result.status == "cancelled"
    assert result.stop_reason == "cancelled"
    assert result.epochs == ()
    assert result.run_id == "result-cancelled"
    json.dumps(result.to_dict())


def test_failed_training_records_result_before_reraising():
    trainer = Trainer(
        _model(),
        TrainerConfig(epochs=1),
        run_id="result-failed",
    )

    with pytest.raises(ValueError, match="训练数据为空"):
        trainer.fit([])

    result = trainer.last_result
    assert result is not None
    assert result.status == "failed"
    assert result.epochs == ()
    assert result.stop_reason is not None
    assert result.stop_reason.startswith("ValueError:")
    assert "训练数据为空" in result.stop_reason
    json.dumps(result.to_dict())


def test_resume_source_is_exposed_as_last_checkpoint(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    source = Trainer(
        _model(),
        TrainerConfig(epochs=1, checkpoint_dir=checkpoint_dir),
        run_id="result-resume",
    )
    source.fit([_batch(1)])

    resumed = Trainer(_model(), source.config)
    resumed.resume_from(checkpoint_dir / "last.pt")

    assert resumed.last_result is None
    result = resumed.fit([], start_epoch=2)
    assert resumed.last_result is result
    assert result.status == "completed"
    assert result.last_checkpoint == checkpoint_dir / "last.pt"
