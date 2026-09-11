"""波形级 transform（设计文档 §8.1、T3.3）。

stable：normalize、gaussian_noise、time_shift、volume_scale。
experimental：pitch_shift、time_stretch（实现存在但语义需注意，见 descriptor）。

所有 transform 接收 ``[C, T]`` 波形并返回新张量，不原地修改输入；
随机数使用 torch 全局 RNG（受 seed 与 DataLoader worker seed 控制）。
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio.transforms as T
from pydantic import BaseModel

from ser_lib.config.transforms import (
    GaussianNoiseConfig,
    NormalizeConfig,
    PitchShiftConfig,
    TimeShiftConfig,
    TimeStretchConfig,
    VolumeScaleConfig,
)
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.transforms.base import RandomApply


class Normalize(nn.Module):
    """逐条 waveform 归一化（确定性，零均值单位方差）。"""

    compatible_layouts = ("T",)
    is_random = False

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        std = waveform.std(correction=0)
        return (waveform - waveform.mean()) / (std + 1e-8)


class AddGaussianNoise(nn.Module):
    """按目标信噪比注入高斯白噪声。"""

    def __init__(self, snr_db: float = 15.0) -> None:
        super().__init__()
        self.snr_db = float(snr_db)

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        noise = torch.randn_like(waveform)
        signal_power = torch.mean(waveform ** 2)
        if signal_power == 0:
            return waveform
        noise_power = torch.mean(noise ** 2)
        target_noise_power = signal_power / (10 ** (self.snr_db / 10))
        scale = torch.sqrt(target_noise_power / (noise_power + 1e-8))
        return waveform + scale * noise


class TimeShift(nn.Module):
    """时间平移，越界部分用零填充（输出长度不变）。"""

    def __init__(self, max_ratio: float = 0.2) -> None:
        super().__init__()
        self.max_ratio = float(max_ratio)

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        length = waveform.shape[-1]
        max_shift = int(length * self.max_ratio)
        if max_shift == 0:
            return waveform
        shift = int(torch.randint(-max_shift, max_shift + 1, ()).item())
        if shift == 0:
            return waveform
        if shift > 0:
            return F.pad(waveform[..., :-shift], (shift, 0), value=0.0)
        return F.pad(waveform[..., -shift:], (0, -shift), value=0.0)


class VolumeScale(nn.Module):
    """随机音量缩放，模拟麦克风远近波动。"""

    def __init__(self, gain_min: float = 0.5, gain_max: float = 1.5) -> None:
        super().__init__()
        self.gain_min = float(gain_min)
        self.gain_max = float(gain_max)

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        gain = float(torch.empty(()).uniform_(self.gain_min, self.gain_max).item())
        return waveform * gain


class PitchShift(nn.Module):
    """音高偏移（半音）。"""

    def __init__(self, sample_rate: int = 16000, n_steps: int = 4) -> None:
        super().__init__()
        self.sample_rate = int(sample_rate)
        self.n_steps = int(n_steps)
        self.transform = T.PitchShift(self.sample_rate, self.n_steps)

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        return self.transform(waveform)


class TimeStretch(nn.Module):
    """时间拉伸（相位声码器；输出长度随 rate 变化）。"""

    def __init__(self, rate: float = 1.2, n_fft: int = 1024, hop_length: int = 256) -> None:
        super().__init__()
        self.rate = float(rate)
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.stretch = T.TimeStretch(
            n_freq=(n_fft // 2) + 1, hop_length=hop_length, fixed_rate=rate
        )

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        window = torch.hann_window(self.n_fft).to(waveform.device)
        stft_complex = torch.stft(
            waveform,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window=window,
            return_complex=True,
        )
        stretched = self.stretch(stft_complex)
        return torch.istft(
            stretched,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window=window,
        )


WAVEFORM_TRANSFORM_SPECS: dict[
    str, tuple[type[nn.Module], type[BaseModel], ComponentDescriptor]
] = {
    "normalize": (
        Normalize,
        NormalizeConfig,
        ComponentDescriptor(
            id="normalize",
            display_name="波形归一化",
            category="waveform_transform",
            description="零均值单位方差归一化（确定性）。",
            config_schema=NormalizeConfig.model_json_schema(),
        ),
    ),
    "gaussian_noise": (
        AddGaussianNoise,
        GaussianNoiseConfig,
        ComponentDescriptor(
            id="gaussian_noise",
            display_name="高斯噪声",
            category="waveform_transform",
            description="按目标信噪比 (dB) 注入高斯白噪声。",
            config_schema=GaussianNoiseConfig.model_json_schema(),
        ),
    ),
    "time_shift": (
        TimeShift,
        TimeShiftConfig,
        ComponentDescriptor(
            id="time_shift",
            display_name="时间平移",
            category="waveform_transform",
            description="随机左右平移波形，零填充，输出长度不变。",
            config_schema=TimeShiftConfig.model_json_schema(),
        ),
    ),
    "volume_scale": (
        VolumeScale,
        VolumeScaleConfig,
        ComponentDescriptor(
            id="volume_scale",
            display_name="音量缩放",
            category="waveform_transform",
            description="在 [gain_min, gain_max] 内随机缩放音量。",
            config_schema=VolumeScaleConfig.model_json_schema(),
        ),
    ),
    "pitch_shift": (
        PitchShift,
        PitchShiftConfig,
        ComponentDescriptor(
            id="pitch_shift",
            display_name="音高偏移",
            category="waveform_transform",
            status="experimental",
            description="按半音数偏移音高（experimental）。",
            config_schema=PitchShiftConfig.model_json_schema(),
        ),
    ),
    "time_stretch": (
        TimeStretch,
        TimeStretchConfig,
        ComponentDescriptor(
            id="time_stretch",
            display_name="时间拉伸",
            category="waveform_transform",
            status="experimental",
            description="相位声码器时间拉伸，输出长度随 rate 变化（experimental）。",
            config_schema=TimeStretchConfig.model_json_schema(),
        ),
    ),
}

__all__ = [
    "Normalize",
    "NormalizeConfig",
    "AddGaussianNoise",
    "GaussianNoiseConfig",
    "TimeShift",
    "TimeShiftConfig",
    "VolumeScale",
    "VolumeScaleConfig",
    "PitchShift",
    "PitchShiftConfig",
    "TimeStretch",
    "TimeStretchConfig",
    "RandomApply",
    "WAVEFORM_TRANSFORM_SPECS",
]
