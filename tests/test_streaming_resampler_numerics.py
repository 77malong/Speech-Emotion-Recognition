from __future__ import annotations

import torch
import torchaudio

from ser_lib.inference.streaming import _LinearResampler


def _run_chunked(
    waveform: torch.Tensor,
    *,
    source_rate: int,
    target_rate: int,
    cuts: tuple[int, ...],
) -> torch.Tensor:
    resampler = _LinearResampler(source_rate, target_rate)
    outputs: list[torch.Tensor] = []
    start = 0
    for stop in cuts:
        outputs.append(resampler.push(waveform[start:stop]))
        start = stop
    outputs.append(resampler.push(waveform[start:]))
    outputs.append(resampler.push(torch.empty(0), final=True))
    nonempty = [item for item in outputs if item.numel()]
    return torch.cat(nonempty) if nonempty else torch.empty(0)


def test_streaming_resampler_matches_offline_torchaudio_across_chunk_boundaries():
    torch.manual_seed(201)
    waveform = torch.randn(4800)

    streamed = _run_chunked(
        waveform,
        source_rate=48000,
        target_rate=16000,
        cuts=(137, 1024, 2049, 3777),
    )
    offline = torchaudio.functional.resample(waveform, 48000, 16000)

    assert streamed.shape == offline.shape
    assert torch.allclose(streamed, offline, atol=2e-6, rtol=2e-5)


def test_streaming_downsampling_attenuates_frequency_above_target_nyquist():
    source_rate = 48000
    target_rate = 16000
    samples = torch.arange(source_rate, dtype=torch.float32)
    waveform = torch.sin(2 * torch.pi * 12000 * samples / source_rate)

    streamed = _run_chunked(
        waveform,
        source_rate=source_rate,
        target_rate=target_rate,
        cuts=(503, 4097, 12000, 30001),
    )
    rms = streamed.square().mean().sqrt()

    assert float(rms) < 0.05


def test_resampler_reports_finite_filter_lookahead_and_bounds_buffer():
    resampler = _LinearResampler(48000, 16000)
    assert 0 < resampler.lookahead_samples < 256

    for _ in range(100):
        resampler.push(torch.ones(480))
        assert resampler.buffered_input_samples < 2048
