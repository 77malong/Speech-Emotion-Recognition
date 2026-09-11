from __future__ import annotations

import torch

from ser_lib.data.transforms.waveform import Normalize


def test_normalize_single_sample_is_finite_zero():
    output = Normalize()(torch.tensor([[0.5]], dtype=torch.float32))

    assert torch.isfinite(output).all()
    assert torch.equal(output, torch.zeros_like(output))


def test_normalize_constant_waveform_is_finite_zero():
    waveform = torch.full((1, 8), 0.5, dtype=torch.float32)

    output = Normalize()(waveform)

    assert torch.isfinite(output).all()
    assert torch.equal(output, torch.zeros_like(output))


def test_normalize_multichannel_uses_existing_global_statistics_contract():
    waveform = torch.tensor(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        dtype=torch.float32,
    )

    output = Normalize()(waveform)
    expected = (waveform - waveform.mean()) / (waveform.std(correction=0) + 1e-8)

    assert torch.isfinite(output).all()
    assert torch.allclose(output, expected)
