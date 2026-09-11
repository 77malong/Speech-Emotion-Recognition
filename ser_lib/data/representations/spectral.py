"""谱图类表示：Spectrogram、MelSpectrogram、LogMel、MFCC（设计文档 §9.2）。

统一输出 key ``features``，layout ``FT``（``[F, Tm]``）；Mel 参数转换逻辑
封装在组件内部，不暴露给 Dataset。
"""

from __future__ import annotations

import torchaudio.transforms as T

from ser_lib.config.representations import (
    LogMelConfig,
    MelConfig,
    MFCCConfig,
    SpectralConfigBase,
    SpectrogramConfig,
)
from ser_lib.foundation.errors import RepresentationError
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.representations.base import Representation
from ser_lib.data.types import (
    LAYOUT_FT,
    AudioData,
    RepresentationOutput,
    TensorSpec,
)


class _SpectralRepresentationBase(Representation):
    """谱图类表示公共实现：单声道输入 + 采样率校验 + ``features`` 输出。"""

    def __init__(self, config: SpectralConfigBase) -> None:
        super().__init__()
        self.config = config
        self._expected_sample_rate = config.sample_rate

    @property
    def output_specs(self) -> dict[str, TensorSpec]:
        return {
            "features": TensorSpec(
                layout=LAYOUT_FT,
                feature_dim=self._feature_dim,
            )
        }

    @property
    def _feature_dim(self) -> int:
        raise NotImplementedError

    def _to_output(self, features: "T.Tensor", audio: AudioData) -> RepresentationOutput:
        if features.dim() != 3:
            raise RepresentationError(
                f"谱图提取输出维度错误: 期望 3D [C, F, T]，实际 "
                f"{features.dim()}D {tuple(features.shape)}",
                path=audio.source_path,
                component=self.descriptor.id,
                stage="representation",
            )
        features = features[0]
        return RepresentationOutput(
            inputs={"features": features},
            lengths={"features": int(features.shape[1])},
        )


class SpectrogramRepresentation(_SpectralRepresentationBase):
    """线性幅度谱（power 谱）。"""

    descriptor = ComponentDescriptor(
        id="spectrogram",
        display_name="线性谱图",
        category="representation",
        description="输出 [F, T] 幂谱/幅度谱。",
        config_schema=SpectrogramConfig.model_json_schema(),
    )

    def __init__(self, **params) -> None:
        config = SpectrogramConfig(**params)
        super().__init__(config)
        # ``torchaudio.transforms.Spectrogram`` operates directly on waveform
        # samples and does not accept Mel-only frequency-range/sample-rate args.
        self.transform = T.Spectrogram(
            n_fft=config.n_fft,
            win_length=config.win_length,
            hop_length=config.hop_length,
            power=config.power,
            center=config.center,
            pad_mode=config.pad_mode,
        )

    @property
    def _feature_dim(self) -> int:
        return self.config.n_fft // 2 + 1

    def forward(self, audio: AudioData) -> RepresentationOutput:
        self._require_mono(audio)
        self._require_sample_rate(audio)
        return self._to_output(self.transform(audio.waveform), audio)


class MelSpectrogramRepresentation(_SpectralRepresentationBase):
    """Mel 谱。"""

    config: MelConfig

    descriptor = ComponentDescriptor(
        id="mel_spectrogram",
        display_name="Mel 谱",
        category="representation",
        description="输出 [F, T] Mel 谱。",
        config_schema=MelConfig.model_json_schema(),
    )

    def __init__(self, **params) -> None:
        config = MelConfig(**params)
        super().__init__(config)
        self.transform = T.MelSpectrogram(
            sample_rate=config.sample_rate,
            n_fft=config.n_fft,
            win_length=config.win_length,
            hop_length=config.hop_length,
            f_min=config.f_min,
            f_max=config.f_max,
            n_mels=config.n_mels,
            power=config.power,
            center=config.center,
            pad_mode=config.pad_mode,
        )

    @property
    def _feature_dim(self) -> int:
        return self.config.n_mels

    def forward(self, audio: AudioData) -> RepresentationOutput:
        self._require_mono(audio)
        self._require_sample_rate(audio)
        return self._to_output(self.transform(audio.waveform), audio)


class LogMelRepresentation(_SpectralRepresentationBase):
    """Log-Mel 谱：Mel 谱后接 AmplitudeToDB。"""

    config: LogMelConfig

    descriptor = ComponentDescriptor(
        id="log_mel",
        display_name="Log-Mel 谱",
        category="representation",
        description="输出 [F, T] Log-Mel 谱（AmplitudeToDB, top_db 可配）。",
        config_schema=LogMelConfig.model_json_schema(),
    )

    def __init__(self, **params) -> None:
        config = LogMelConfig(**params)
        super().__init__(config)
        self.mel_transform = T.MelSpectrogram(
            sample_rate=config.sample_rate,
            n_fft=config.n_fft,
            win_length=config.win_length,
            hop_length=config.hop_length,
            f_min=config.f_min,
            f_max=config.f_max,
            n_mels=config.n_mels,
            power=config.power,
            center=config.center,
            pad_mode=config.pad_mode,
        )
        self.db_transform = T.AmplitudeToDB(
            stype="magnitude" if config.power == 1.0 else "power",
            top_db=config.top_db,
        )

    @property
    def _feature_dim(self) -> int:
        return self.config.n_mels

    def forward(self, audio: AudioData) -> RepresentationOutput:
        self._require_mono(audio)
        self._require_sample_rate(audio)
        mel = self.mel_transform(audio.waveform)
        return self._to_output(self.db_transform(mel), audio)


class MFCCRepresentation(_SpectralRepresentationBase):
    """MFCC：Mel 参数转换逻辑封装在组件内部。"""

    config: MFCCConfig

    descriptor = ComponentDescriptor(
        id="mfcc",
        display_name="MFCC",
        category="representation",
        description="输出 [n_mfcc, T] MFCC 特征。",
        config_schema=MFCCConfig.model_json_schema(),
    )

    def __init__(self, **params) -> None:
        config = MFCCConfig(**params)
        super().__init__(config)
        self.transform = T.MFCC(
            sample_rate=config.sample_rate,
            n_mfcc=config.n_mfcc,
            norm=config.dct_norm,
            melkwargs={
                "n_fft": config.n_fft,
                "win_length": config.win_length,
                "hop_length": config.hop_length,
                "f_min": config.f_min,
                "f_max": config.f_max,
                "n_mels": config.n_mels,
                "center": config.center,
                "pad_mode": config.pad_mode,
                "norm": config.mel_norm,
                "mel_scale": config.mel_scale,
            },
        )

    @property
    def _feature_dim(self) -> int:
        return self.config.n_mfcc

    def forward(self, audio: AudioData) -> RepresentationOutput:
        self._require_mono(audio)
        self._require_sample_rate(audio)
        return self._to_output(self.transform(audio.waveform), audio)


__all__ = [
    "SpectrogramConfig",
    "MelConfig",
    "LogMelConfig",
    "MFCCConfig",
    "SpectrogramRepresentation",
    "MelSpectrogramRepresentation",
    "LogMelRepresentation",
    "MFCCRepresentation",
]
