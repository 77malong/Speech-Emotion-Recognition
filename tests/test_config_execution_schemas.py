from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from ser_lib.config import (
    AcousticFeaturesConfig,
    AdamWConfig,
    CNNBaselineConfig,
    CompositeConfig,
    CosineSchedulerConfig,
    ExperimentConfig,
    GaussianNoiseConfig,
    GRUBaselineConfig,
    HFAudioClassifierConfig,
    LogMelConfig,
    LossConfig,
    MFCCConfig,
    ModelConfig,
    NormalizeConfig,
    ObservabilityConfig,
    RawWaveformConfig,
    SGDConfig,
    SamplingConfig,
    SpecMaskingConfig,
    SpectrogramConfig,
    StepSchedulerConfig,
    StreamingConfig,
    StrictConfig,
    TimeShiftConfig,
    TimeStretchConfig,
    TrainerConfig,
    TransformerBaselineConfig,
    VolumeScaleConfig,
    PitchShiftConfig,
    parse_optimizer_config,
    parse_scheduler_config,
)
from ser_lib.engine import (
    AdamWConfig as LegacyAdamWConfig,
    ExperimentConfig as LegacyExperimentConfig,
    LossConfig as LegacyLossConfig,
    ModelConfig as LegacyModelConfig,
    ObservabilityConfig as LegacyObservabilityConfig,
    SamplingConfig as LegacySamplingConfig,
    TrainerConfig as LegacyTrainerConfig,
    parse_optimizer_config as legacy_parse_optimizer_config,
    parse_scheduler_config as legacy_parse_scheduler_config,
)
from ser_lib.inference.streaming import StreamingConfig as LegacyStreamingConfig
from ser_lib.models.cnn_models import CNNBaselineConfig as LegacyCNNBaselineConfig
from ser_lib.models.rnn_models import GRUBaselineConfig as LegacyGRUBaselineConfig
from ser_lib.models.transformer_models import (
    TransformerBaselineConfig as LegacyTransformerBaselineConfig,
)


def test_central_execution_config_import_does_not_load_torch_or_transformers():
    code = """
import sys
import ser_lib.config
assert "torch" not in sys.modules
assert "transformers" not in sys.modules
assert "ser_lib.models" not in sys.modules
assert "ser_lib.engine" not in sys.modules
assert "ser_lib.inference" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_old_execution_config_paths_are_identity_aliases():
    assert LegacyModelConfig is ModelConfig
    assert LegacyObservabilityConfig is ObservabilityConfig
    assert LegacyTrainerConfig is TrainerConfig
    assert LegacyExperimentConfig is ExperimentConfig
    assert LegacyLossConfig is LossConfig
    assert LegacySamplingConfig is SamplingConfig
    assert LegacyAdamWConfig is AdamWConfig
    assert LegacyCNNBaselineConfig is CNNBaselineConfig
    assert LegacyGRUBaselineConfig is GRUBaselineConfig
    assert LegacyTransformerBaselineConfig is TransformerBaselineConfig
    assert LegacyStreamingConfig is StreamingConfig
    assert legacy_parse_optimizer_config is parse_optimizer_config
    assert legacy_parse_scheduler_config is parse_scheduler_config


def test_optimizer_and_scheduler_union_order_and_defaults_are_preserved():
    assert isinstance(parse_optimizer_config({"type": "adamw", "params": {}}), AdamWConfig)
    assert isinstance(
        parse_optimizer_config({"type": "sgd", "params": {"learning_rate": 0.2}}),
        SGDConfig,
    )
    assert isinstance(
        parse_scheduler_config({"type": "step", "params": {}}),
        StepSchedulerConfig,
    )
    cosine = parse_scheduler_config({"type": "cosine", "params": {"t_max": 4}})
    assert isinstance(cosine, CosineSchedulerConfig)
    assert AdamWConfig().learning_rate == 1e-3


def test_model_and_training_config_payload_defaults_are_preserved():
    assert CNNBaselineConfig(feature_dim=4, num_classes=2).hidden_dim == 128
    assert GRUBaselineConfig(feature_dim=4, num_classes=2).bidirectional is True
    assert TransformerBaselineConfig(feature_dim=4, num_classes=2).activation == "gelu"
    assert TrainerConfig().epochs == 10
    assert ObservabilityConfig().metric_interval_batches == 10
    assert LossConfig().type == "cross_entropy"
    assert SamplingConfig().type == "shuffle"
    hf = HFAudioClassifierConfig(
        num_classes=2,
        encoder_config={"model_type": "fake_audio", "hidden_size": 4},
    )
    assert hf.local_files_only is True


def test_representation_and_transform_configs_share_strict_contract():
    config_types = (
        RawWaveformConfig,
        SpectrogramConfig,
        LogMelConfig,
        MFCCConfig,
        AcousticFeaturesConfig,
        CompositeConfig,
        NormalizeConfig,
        GaussianNoiseConfig,
        TimeShiftConfig,
        VolumeScaleConfig,
        PitchShiftConfig,
        TimeStretchConfig,
        SpecMaskingConfig,
    )
    assert all(issubclass(config_type, StrictConfig) for config_type in config_types)

    config = GaussianNoiseConfig()
    with pytest.raises(ValidationError):
        config.snr_db = 20.0
    with pytest.raises(ValidationError):
        GaussianNoiseConfig(unknown_field=True)


def test_streaming_config_keeps_dataclass_defaults_and_validation():
    config = StreamingConfig()
    assert config.input_sample_rate == 16000
    assert config.window_ms == 2000
    assert config.hop_ms == 500
    try:
        StreamingConfig(window_ms=100, hop_ms=200)
    except ValueError as exc:
        assert "hop_ms" in str(exc)
    else:
        raise AssertionError("hop_ms > window_ms must fail")
