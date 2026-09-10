from __future__ import annotations

import torch

from ser_lib.data.types import SERBatch
from ser_lib.models.cnn_models import CNNBaseline


def _batch(features: torch.Tensor, lengths: list[int]) -> SERBatch:
    batch_size, _, time = features.shape
    mask = torch.arange(time).unsqueeze(0) < torch.tensor(lengths).unsqueeze(1)
    return SERBatch(
        {"features": features},
        {"features": torch.tensor(lengths)},
        {"features": mask},
        torch.zeros(batch_size, dtype=torch.long),
        [f"sample-{index}" for index in range(batch_size)],
        [{} for _ in range(batch_size)],
    )


def test_cnn_eval_output_is_invariant_to_extra_right_padding():
    torch.manual_seed(101)
    model = CNNBaseline(2, 2, hidden_dim=4, dropout=0.0).eval()
    valid = torch.randn(1, 2, 7)

    with torch.no_grad():
        short = model(_batch(valid, [7])).logits
        padded = model(
            _batch(torch.nn.functional.pad(valid, (0, 15)), [7])
        ).logits

    assert torch.allclose(short, padded, atol=1e-7, rtol=1e-6)


def test_cnn_train_output_is_invariant_to_other_samples_padding_extent():
    torch.manual_seed(102)
    base = CNNBaseline(2, 2, hidden_dim=4, dropout=0.0)
    state = base.state_dict()
    sample = torch.randn(1, 2, 7)
    peer_valid = torch.randn(1, 2, 5)

    model_a = CNNBaseline(2, 2, hidden_dim=4, dropout=0.0)
    model_a.load_state_dict(state)
    model_a.train()
    batch_a = torch.cat(
        [
            sample,
            torch.nn.functional.pad(peer_valid, (0, 2)),
        ],
        dim=0,
    )
    logits_a = model_a(_batch(batch_a, [7, 5])).logits[0]

    model_b = CNNBaseline(2, 2, hidden_dim=4, dropout=0.0)
    model_b.load_state_dict(state)
    model_b.train()
    batch_b = torch.cat(
        [
            torch.nn.functional.pad(sample, (0, 12)),
            torch.nn.functional.pad(peer_valid, (0, 14)),
        ],
        dim=0,
    )
    logits_b = model_b(_batch(batch_b, [7, 5])).logits[0]

    assert torch.allclose(logits_a, logits_b, atol=1e-6, rtol=1e-5)


def test_cnn_masked_batchnorm_keeps_legacy_state_dict_surface():
    model = CNNBaseline(3, 2, hidden_dim=5, dropout=0.0)
    keys = set(model.state_dict())

    assert "encoder.1.weight" in keys
    assert "encoder.1.bias" in keys
    assert "encoder.1.running_mean" in keys
    assert "encoder.1.running_var" in keys
    assert "encoder.1.num_batches_tracked" in keys
