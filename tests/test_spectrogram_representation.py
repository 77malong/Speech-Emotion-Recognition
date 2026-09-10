from __future__ import annotations

from pathlib import Path

import torch
import torchaudio.transforms as T

from ser_lib.data.representations.spectral import SpectrogramRepresentation
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
