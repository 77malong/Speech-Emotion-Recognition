from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from ser_lib.config.presets import (
    build_experiment_config as central_build_experiment_config,
)
from ser_lib.config.presets import get_experiment_preset_payload
from ser_lib.config.representations import (
    AcousticFeaturesConfig,
    CompositeConfig,
    LogMelConfig,
    MelConfig,
    MFCCConfig,
    RawWaveformConfig,
    SpectralConfigBase,
    SpectrogramConfig,
)
from ser_lib.config.transforms import (
    GaussianNoiseConfig,
    NormalizeConfig,
    PitchShiftConfig,
    SpecMaskingConfig,
    TimeShiftConfig,
    TimeStretchConfig,
    VolumeScaleConfig,
)
from ser_lib.data.representations.acoustic import (
    AcousticFeaturesConfig as LegacyAcousticFeaturesConfig,
)
from ser_lib.data.representations.composite import CompositeConfig as LegacyCompositeConfig
from ser_lib.data.representations.spectral import (
    LogMelConfig as LegacyLogMelConfig,
)
from ser_lib.data.representations.spectral import MFCCConfig as LegacyMFCCConfig
from ser_lib.data.representations.spectral import MelConfig as LegacyMelConfig
from ser_lib.data.representations.spectral import (
    SpectralConfigBase as LegacySpectralConfigBase,
)
from ser_lib.data.representations.spectral import (
    SpectrogramConfig as LegacySpectrogramConfig,
)
from ser_lib.data.representations.waveform import (
    RawWaveformConfig as LegacyRawWaveformConfig,
)
from ser_lib.data.transforms.feature import SpecMaskingConfig as LegacySpecMaskingConfig
from ser_lib.data.transforms.waveform import (
    GaussianNoiseConfig as LegacyGaussianNoiseConfig,
)
from ser_lib.data.transforms.waveform import NormalizeConfig as LegacyNormalizeConfig
from ser_lib.data.transforms.waveform import PitchShiftConfig as LegacyPitchShiftConfig
from ser_lib.data.transforms.waveform import TimeShiftConfig as LegacyTimeShiftConfig
from ser_lib.data.transforms.waveform import TimeStretchConfig as LegacyTimeStretchConfig
from ser_lib.data.transforms.waveform import VolumeScaleConfig as LegacyVolumeScaleConfig
from ser_lib.engine.presets import build_experiment_config as legacy_build_experiment_config


def test_representation_config_legacy_paths_are_identity_aliases():
    pairs = [
        (RawWaveformConfig, LegacyRawWaveformConfig),
        (SpectralConfigBase, LegacySpectralConfigBase),
        (SpectrogramConfig, LegacySpectrogramConfig),
        (MelConfig, LegacyMelConfig),
        (LogMelConfig, LegacyLogMelConfig),
        (MFCCConfig, LegacyMFCCConfig),
        (AcousticFeaturesConfig, LegacyAcousticFeaturesConfig),
        (CompositeConfig, LegacyCompositeConfig),
    ]
    assert all(current is legacy for current, legacy in pairs)


def test_transform_config_legacy_paths_are_identity_aliases():
    pairs = [
        (NormalizeConfig, LegacyNormalizeConfig),
        (GaussianNoiseConfig, LegacyGaussianNoiseConfig),
        (TimeShiftConfig, LegacyTimeShiftConfig),
        (VolumeScaleConfig, LegacyVolumeScaleConfig),
        (PitchShiftConfig, LegacyPitchShiftConfig),
        (TimeStretchConfig, LegacyTimeStretchConfig),
        (SpecMaskingConfig, LegacySpecMaskingConfig),
    ]
    assert all(current is legacy for current, legacy in pairs)


def test_migrated_component_configs_preserve_mutability_and_strict_fields():
    config = LogMelConfig()
    config.n_mels = 96
    assert config.n_mels == 96
    with pytest.raises(ValidationError):
        RawWaveformConfig(unknown=True)
    with pytest.raises(ValidationError):
        NormalizeConfig(unknown=True)


def test_representation_validators_are_preserved():
    with pytest.raises(ValidationError, match="win_length"):
        SpectrogramConfig(n_fft=400, win_length=800)
    with pytest.raises(ValidationError, match="f_max"):
        MelConfig(f_min=100.0, f_max=50.0)
    with pytest.raises(ValidationError, match="n_mfcc"):
        MFCCConfig(n_mels=20, n_mfcc=40)
    with pytest.raises(ValidationError, match="重复"):
        AcousticFeaturesConfig(features=["rms", "rms"])
    with pytest.raises(ValidationError, match="奇数"):
        AcousticFeaturesConfig(features=["delta"], delta_win_length=4)
    with pytest.raises(ValidationError):
        CompositeConfig(outputs={})


def test_transform_validators_and_defaults_are_preserved():
    assert GaussianNoiseConfig().snr_db == 15.0
    assert TimeShiftConfig().max_ratio == 0.2
    assert PitchShiftConfig().sample_rate == 16000
    assert TimeStretchConfig().rate == 1.2
    assert SpecMaskingConfig().model_dump() == {
        "time_mask_param": 30,
        "freq_mask_param": 15,
    }
    with pytest.raises(ValidationError, match="gain_min"):
        VolumeScaleConfig(gain_min=2.0, gain_max=1.0)


def test_config_schema_modules_do_not_load_torch_execution_dependencies():
    code = (
        "import sys; "
        "import ser_lib.config.representations, ser_lib.config.transforms; "
        "assert 'torch' not in sys.modules; "
        "assert 'torchaudio' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_preset_build_is_central_and_payload_isolated():
    assert central_build_experiment_config is legacy_build_experiment_config
    payload = get_experiment_preset_payload("cnn_logmel_baseline")
    payload["trainer"]["epochs"] = 999
    fresh = get_experiment_preset_payload("cnn_logmel_baseline")
    assert fresh["trainer"]["epochs"] == 30
    config = central_build_experiment_config(
        "cnn_logmel_baseline",
        {"trainer": {"epochs": 2}},
    )
    assert config.trainer.epochs == 2
    assert config.data.representation.type == "log_mel"
