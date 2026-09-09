from __future__ import annotations

import pytest

from ser_lib.engine.eta import EtaEstimator


def test_eta_warmup_then_converges():
    estimator = EtaEstimator(window_size=4, warmup_batches=2)
    estimator.record_batch(2.0, 4, phase="train")
    cold = estimator.snapshot(
        phase="train", completed_batches=1, total_batches=5, future_batches=5
    )
    assert not cold.ready
    assert cold.phase_remaining_seconds is None

    estimator.record_batch(2.0, 4, phase="train")
    warm = estimator.snapshot(
        phase="train", completed_batches=2, total_batches=5, future_batches=5
    )
    assert warm.ready
    assert warm.average_batch_seconds == pytest.approx(2.0)
    assert warm.batches_per_second == pytest.approx(0.5)
    assert warm.samples_per_second == pytest.approx(2.0)
    assert warm.phase_remaining_seconds == pytest.approx(6.0)
    assert warm.global_remaining_seconds == pytest.approx(16.0)


def test_eta_recent_window_forgets_old_slow_batch():
    estimator = EtaEstimator(window_size=3, warmup_batches=1)
    estimator.record_batch(30.0, 1)
    for _ in range(3):
        estimator.record_batch(1.0, 1)

    snapshot = estimator.snapshot(completed_batches=4, total_batches=10)
    assert snapshot.average_batch_seconds == pytest.approx(1.0)
    assert snapshot.phase_remaining_seconds == pytest.approx(6.0)


def test_eta_tracks_phases_independently():
    estimator = EtaEstimator(window_size=4, warmup_batches=1)
    estimator.record_batch(1.0, 2, phase="train")
    estimator.record_batch(4.0, 2, phase="validation")

    train = estimator.snapshot(phase="train", completed_batches=1, total_batches=3)
    validation = estimator.snapshot(
        phase="validation", completed_batches=1, total_batches=2
    )

    assert train.phase_remaining_seconds == pytest.approx(2.0)
    assert validation.phase_remaining_seconds == pytest.approx(4.0)
    assert train.samples_seen == validation.samples_seen == 2


def test_eta_reset_and_validation():
    estimator = EtaEstimator(window_size=2, warmup_batches=1)
    estimator.record_batch(1.0, phase="train")
    estimator.reset("train")
    snapshot = estimator.snapshot(phase="train", completed_batches=0, total_batches=1)
    assert not snapshot.ready

    with pytest.raises(ValueError):
        EtaEstimator(window_size=1, warmup_batches=2)
    with pytest.raises(ValueError):
        estimator.record_batch(-1.0)
    with pytest.raises(ValueError):
        estimator.snapshot(completed_batches=2, total_batches=1)
