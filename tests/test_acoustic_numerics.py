from __future__ import annotations

import pytest
import torch
from pydantic import ValidationError

from ser_lib.config.representations import AcousticFeaturesConfig
from ser_lib.data.representations.acoustic import _JitterShimmerHNR, _PitchF0


def test_pitch_f0_tracks_200hz_sine_without_window_unit_failure():
    sample_rate = 16000
    samples = torch.arange(sample_rate, dtype=torch.float32)
    waveform = torch.sin(2 * torch.pi * 200 * samples / sample_rate).unsqueeze(0)

    pitch = _PitchF0(sample_rate, 256).compute(waveform)

    assert pitch.ndim == 1
    assert pitch.numel() > 10
    assert torch.isfinite(pitch).all()
    voiced = pitch[pitch > 0]
    assert voiced.numel() > 0
    assert float(voiced.median()) == pytest.approx(200.0, abs=8.0)


def test_pitch_f0_defines_silence_as_unvoiced():
    pitch = _PitchF0(16000, 256).compute(torch.zeros(1, 16000))

    assert pitch.ndim == 1
    assert pitch.numel() > 0
    assert torch.count_nonzero(pitch) == 0


def test_pitch_f0_defines_too_short_input_as_single_unvoiced_frame():
    pitch = _PitchF0(16000, 256).compute(torch.ones(1, 100))

    assert torch.equal(pitch, torch.zeros(1))


def test_waveform_delta_is_rejected_as_misleading_acoustic_feature():
    with pytest.raises(ValidationError, match="delta.*waveform.*帧级"):
        AcousticFeaturesConfig(features=["delta"])


def test_unvalidated_quality_vector_is_rejected_by_public_config():
    with pytest.raises(ValidationError, match="jitter_shimmer_hnr"):
        AcousticFeaturesConfig(features=["jitter_shimmer_hnr"])


def test_private_quality_helper_cannot_return_placeholder_measurements():
    with pytest.raises(NotImplementedError, match="shimmer.*HNR"):
        _JitterShimmerHNR().compute(
            torch.ones(1, 16000),
            torch.tensor([190.0, 200.0, 210.0]),
        )
