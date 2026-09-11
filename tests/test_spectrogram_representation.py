from __future__ import annotations

from pathlib import Path

import pytest
import torch
import torchaudio.transforms as T

from ser_lib.data.representations.spectral import (
    LogMelRepresentation,
    SpectrogramRepresentation,
)
from ser_lib.data.types import AudioData


def _audio(waveform: torch.Tensor, sample_rate: int = 16000) -> AudioData:
    return AudioData(
        waveform=waveform,
        sample_rate=sample_rate,
        source_path=Path("synthetic.wav"),
        original_sample_rate=sample_rate,
        num_frames=int(waveform.shape[-1]),
    )


def test_default_spectrogram_representation_constructs_and_runs():
    representation = SpectrogramRepresentation()
    waveform = torch.linspace(-1.0, 1.0, 4096).unsqueeze(0)

    output = representation(_audio(waveform))

    assert output.inputs["features"].shape[0] == representation.output_specs["features"].feature_dim
    assert output.lengths["features"] == output.inputs["features"].shape[1]
    assert torch.isfinite(output.inputs["features"]).all()


def test_linear_spectrogram_matches_direct_torchaudio_transform():
    params = {
        "sample_rate": 16000,
        "n_fft": 256,
        "win_length": 200,
        "hop_length": 80,
        "power": 2.0,
        "center": True,
        "pad_mode": "reflect",
    }
    representation = SpectrogramRepresentation(**params)
    torch.manual_seed(73)
    waveform = torch.randn(1, 3200)

    actual = representation(_audio(waveform)).inputs["features"]
    expected = T.Spectrogram(
        n_fft=params["n_fft"],
        win_length=params["win_length"],
        hop_length=params["hop_length"],
        power=params["power"],
        center=params["center"],
        pad_mode=params["pad_mode"],
    )(waveform)[0]

    assert torch.equal(actual, expected)



@pytest.mark.parametrize(
    ("power", "expected_db"),
    [(1.0, 20.0 * torch.log10(torch.tensor(2.0)).item()),
     (2.0, 10.0 * torch.log10(torch.tensor(4.0)).item())],
)
def test_log_mel_db_scaling_matches_power_semantics(power: float, expected_db: float):
    representation = LogMelRepresentation(
        sample_rate=16000,
        n_fft=256,
        win_length=200,
        hop_length=80,
        n_mels=32,
        power=power,
        top_db=120.0,
    )
    time = torch.arange(0, 3200, dtype=torch.float32) / 16000.0
    waveform = (0.4 * torch.sin(2.0 * torch.pi * 440.0 * time)).unsqueeze(0)

    base = representation(_audio(waveform)).inputs["features"]
    doubled = representation(_audio(waveform * 2.0)).inputs["features"]
    delta = doubled - base

    assert torch.allclose(
        delta,
        torch.full_like(delta, expected_db),
        atol=1e-4,
        rtol=0.0,
    )


def test_log_mel_rejects_unsupported_power_semantics():
    with pytest.raises(ValueError):
        LogMelRepresentation(power=1.5)
