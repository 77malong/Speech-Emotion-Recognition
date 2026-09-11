from __future__ import annotations

import torch

from ser_lib.data.collate import SERCollator
from ser_lib.config import BatchingConfig, FixedBatching, SlidingBatching
from ser_lib.data.types import SERBatch, SERSample, TensorSpec
from ser_lib.models.cnn_models import CNNBaseline


_FEATURE_SPEC = {"features": TensorSpec(layout="FT", feature_dim=2)}


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


def _sample(uid: str, features: torch.Tensor, length: int) -> SERSample:
    return SERSample(
        uid=uid,
        inputs={"features": features},
        lengths={"features": length},
        label=0,
        metadata={},
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


def test_cnn_fixed_collator_uses_lengths_when_masks_are_absent():
    torch.manual_seed(103)
    model = CNNBaseline(2, 2, hidden_dim=4, dropout=0.0).eval()
    features = torch.randn(2, 7)
    sample = _sample("fixed", features, 7)

    short = SERCollator(
        _FEATURE_SPEC,
        BatchingConfig(
            type="fixed",
            fixed=FixedBatching(max_lengths={"features": 7}),
        ),
    )([sample])
    padded = SERCollator(
        _FEATURE_SPEC,
        BatchingConfig(
            type="fixed",
            fixed=FixedBatching(max_lengths={"features": 22}),
        ),
    )([sample])

    assert short.masks == {}
    assert padded.masks == {}
    with torch.no_grad():
        short_logits = model(short).logits
        padded_logits = model(padded).logits
    assert torch.allclose(short_logits, padded_logits, atol=1e-7, rtol=1e-6)


def test_cnn_sliding_tail_window_uses_true_window_length():
    torch.manual_seed(104)
    model = CNNBaseline(2, 2, hidden_dim=4, dropout=0.0).eval()
    features = torch.randn(2, 7)
    sample = _sample("sliding", features, 7)
    sliding = SERCollator(
        _FEATURE_SPEC,
        BatchingConfig(
            type="sliding",
            sliding=SlidingBatching(window_size=5, stride=5),
            primary_key="features",
        ),
    )([sample])
    tail = SERBatch(
        inputs={"features": features[:, 5:].unsqueeze(0)},
        lengths={"features": torch.tensor([2], dtype=torch.long)},
        masks={},
        labels=torch.tensor([0], dtype=torch.long),
        uids=["tail"],
        metadata=[{}],
    )

    assert sliding.masks == {}
    assert sliding.lengths["features"].tolist() == [5, 2]
    with torch.no_grad():
        sliding_tail = model(sliding).logits[1]
        direct_tail = model(tail).logits[0]
    assert torch.allclose(sliding_tail, direct_tail, atol=1e-7, rtol=1e-6)


def test_cnn_masked_batchnorm_keeps_legacy_state_dict_surface():
    model = CNNBaseline(3, 2, hidden_dim=5, dropout=0.0)
    keys = set(model.state_dict())

    assert "encoder.1.weight" in keys
    assert "encoder.1.bias" in keys
    assert "encoder.1.running_mean" in keys
    assert "encoder.1.running_var" in keys
    assert "encoder.1.num_batches_tracked" in keys