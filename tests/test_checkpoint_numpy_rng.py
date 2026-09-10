from __future__ import annotations

from pathlib import Path

import numpy as np

from ser_lib.engine.checkpoint import load_checkpoint, save_checkpoint
from ser_lib.models import CNNBaseline


def test_checkpoint_restores_numpy_rng_sequence(tmp_path: Path):
    model = CNNBaseline(feature_dim=4, num_classes=2, hidden_dim=6, dropout=0.0)
    checkpoint = tmp_path / "checkpoint.pt"

    np.random.seed(7)
    save_checkpoint(checkpoint, model, None, epoch=1)
    expected_next = float(np.random.random())

    np.random.seed(999)
    assert float(np.random.random()) != expected_next

    load_checkpoint(checkpoint, model, restore_rng=True)

    assert float(np.random.random()) == expected_next


def test_checkpoint_can_leave_numpy_rng_untouched(tmp_path: Path):
    model = CNNBaseline(feature_dim=4, num_classes=2, hidden_dim=6, dropout=0.0)
    checkpoint = tmp_path / "checkpoint.pt"

    np.random.seed(7)
    save_checkpoint(checkpoint, model, None, epoch=1)

    np.random.seed(999)
    expected_next = float(np.random.random())
    np.random.seed(999)
    load_checkpoint(checkpoint, model, restore_rng=False)

    assert float(np.random.random()) == expected_next
