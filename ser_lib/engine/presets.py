"""稳定实验预设目录；所有预设最终都构造现有 ExperimentConfig。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from ser_lib.engine.config import ExperimentConfig

PresetStatus = Literal["stable", "experimental"]

_DEFAULT_LABELS: dict[int, dict[str, str]] = {
    0: {"en": "neutral", "zh": "中性"},
    1: {"en": "happy", "zh": "高兴"},
    2: {"en": "sad", "zh": "悲伤"},
    3: {"en": "angry", "zh": "愤怒"},
    4: {"en": "fearful", "zh": "恐惧"},
    5: {"en": "surprised", "zh": "惊讶"},
}

_COMMON_TRAINER: dict[str, Any] = {
    "epochs": 30,
    "device": "cpu",
    "seed": 42,
    "deterministic": True,
    "amp": False,
    "gradient_clip_norm": 5.0,
    "monitor": "val_uar",
    "early_stopping_patience": 7,
    "early_stopping_min_delta": 0.001,
    "save_best": True,
    "save_last": True,
}

_PRESET_PAYLOADS: dict[str, dict[str, Any]] = {
    "cnn_logmel_baseline": {
        "schema_version": 1,
        "data": {
            "schema_version": 1,
            "manifest": "data/standard/dataset.yaml",
            "labels": _DEFAULT_LABELS,
            "audio": {
                "target_sample_rate": 16000,
                "mono": True,
                "normalize_peak": False,
            },
            "representation": {
                "type": "log_mel",
                "params": {
                    "sample_rate": 16000,
                    "n_fft": 400,
                    "win_length": 400,
                    "hop_length": 160,
                    "n_mels": 64,
                },
            },
            "waveform_transforms": [
                {
                    "type": "volume_scale",
                    "params": {"gain_min": 0.8, "gain_max": 1.2},
                    "probability": 0.5,
                }
            ],
            "feature_transforms": [
                {
                    "type": "spec_masking",
                    "params": {"time_mask_param": 20, "freq_mask_param": 8},
                    "probability": 0.5,
                }
            ],
            "batching": {"type": "dynamic"},
        },
        "model": {
            "type": "cnn_baseline",
            "params": {
                "feature_dim": 64,
                "num_classes": 6,
                "hidden_dim": 128,
                "dropout": 0.2,
            },
        },
        "trainer": {**_COMMON_TRAINER, "gradient_accumulation_steps": 1},
        "optimizer": {
            "type": "adamw",
            "params": {"learning_rate": 0.001, "weight_decay": 0.0001},
        },
        "scheduler": {
            "type": "cosine",
            "params": {"t_max": 30, "eta_min": 0.00001},
        },
        "loss": {"type": "cross_entropy", "label_smoothing": 0.05},
        "sampling": {"type": "weighted"},
        "output_dir": "runs/cnn-logmel",
    },
    "gru_mfcc_baseline": {
        "schema_version": 1,
        "data": {
            "schema_version": 1,
            "manifest": "data/standard/dataset.yaml",
            "labels": _DEFAULT_LABELS,
            "audio": {
                "target_sample_rate": 16000,
                "mono": True,
                "normalize_peak": False,
            },
            "representation": {
                "type": "mfcc",
                "params": {
                    "sample_rate": 16000,
                    "n_fft": 400,
                    "win_length": 400,
                    "hop_length": 160,
                    "n_mels": 64,
                    "n_mfcc": 40,
                },
            },
            "waveform_transforms": [
                {
                    "type": "gaussian_noise",
                    "params": {"snr_db": 20.0},
                    "probability": 0.3,
                }
            ],
            "batching": {"type": "dynamic"},
        },
        "model": {
            "type": "gru_baseline",
            "params": {
                "feature_dim": 40,
                "num_classes": 6,
                "hidden_dim": 128,
                "num_layers": 2,
                "bidirectional": True,
                "dropout": 0.2,
            },
        },
        "trainer": dict(_COMMON_TRAINER),
        "optimizer": {
            "type": "adamw",
            "params": {"learning_rate": 0.001, "weight_decay": 0.0001},
        },
        "scheduler": {"type": "cosine", "params": {"t_max": 30}},
        "loss": {"type": "focal", "focal_gamma": 2.0},
        "sampling": {"type": "weighted"},
        "output_dir": "runs/gru-mfcc",
    },
    "transformer_logmel_baseline": {
        "schema_version": 1,
        "data": {
            "schema_version": 1,
            "manifest": "data/standard/dataset.yaml",
            "labels": _DEFAULT_LABELS,
            "audio": {
                "target_sample_rate": 16000,
                "mono": True,
                "normalize_peak": False,
            },
            "representation": {
                "type": "log_mel",
                "params": {
                    "sample_rate": 16000,
                    "n_fft": 400,
                    "win_length": 400,
                    "hop_length": 160,
                    "n_mels": 64,
                },
            },
            "feature_transforms": [
                {
                    "type": "spec_masking",
                    "params": {"time_mask_param": 20, "freq_mask_param": 8},
                    "probability": 0.5,
                }
            ],
            "batching": {"type": "dynamic"},
        },
        "model": {
            "type": "transformer_baseline",
            "params": {
                "feature_dim": 64,
                "num_classes": 6,
                "d_model": 128,
                "num_heads": 4,
                "num_layers": 2,
                "feedforward_dim": 256,
                "dropout": 0.1,
            },
        },
        "trainer": dict(_COMMON_TRAINER),
        "optimizer": {
            "type": "adamw",
            "params": {"learning_rate": 0.0005, "weight_decay": 0.0001},
        },
        "scheduler": {"type": "cosine", "params": {"t_max": 30}},
        "loss": {"type": "cross_entropy", "label_smoothing": 0.05},
        "sampling": {"type": "weighted"},
        "output_dir": "runs/transformer-logmel",
    },
}

_PRESET_METADATA: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "cnn_logmel_baseline": (
        "CNN + LogMel Baseline",
        "与 configs/cnn_logmel.yaml 对齐的 CNN/LogMel 稳定基线。",
        ("cnn", "log_mel", "baseline"),
    ),
    "gru_mfcc_baseline": (
        "GRU + MFCC Baseline",
        "与 configs/gru_mfcc.yaml 对齐的 GRU/MFCC 稳定基线。",
        ("gru", "mfcc", "baseline"),
    ),
    "transformer_logmel_baseline": (
        "Transformer + LogMel Baseline",
        "与 configs/transformer_logmel.yaml 对齐的 Transformer/LogMel 稳定基线。",
        ("transformer", "log_mel", "baseline"),
    ),
}


@dataclass(frozen=True, slots=True)
class ExperimentPresetInfo:
    preset_id: str
    display_name: str
    description: str
    status: PresetStatus
    tags: tuple[str, ...]
    default_config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "display_name": self.display_name,
            "description": self.description,
            "status": self.status,
            "tags": list(self.tags),
            "default_config": deepcopy(self.default_config),
        }


@dataclass(frozen=True, slots=True)
class ExperimentPresetCatalog:
    presets: tuple[ExperimentPresetInfo, ...]

    @property
    def total(self) -> int:
        return len(self.presets)

    def get(self, preset_id: str) -> ExperimentPresetInfo:
        for preset in self.presets:
            if preset.preset_id == preset_id:
                return preset
        raise KeyError(f"未知 experiment preset: {preset_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "presets": [preset.to_dict() for preset in self.presets],
        }


def list_experiment_presets() -> ExperimentPresetCatalog:
    """枚举稳定 preset；只做配置模型校验，不创建模型或分配设备。"""
    presets: list[ExperimentPresetInfo] = []
    for preset_id in sorted(_PRESET_PAYLOADS):
        config = ExperimentConfig.model_validate(deepcopy(_PRESET_PAYLOADS[preset_id]))
        display_name, description, tags = _PRESET_METADATA[preset_id]
        presets.append(
            ExperimentPresetInfo(
                preset_id=preset_id,
                display_name=display_name,
                description=description,
                status="stable",
                tags=tags,
                default_config=config.model_dump(mode="json"),
            )
        )
    return ExperimentPresetCatalog(tuple(presets))


def get_experiment_preset(preset_id: str) -> ExperimentPresetInfo:
    return list_experiment_presets().get(preset_id)


def build_experiment_config(
    preset_id: str,
    overrides: Mapping[str, Any] | None = None,
) -> ExperimentConfig:
    """从 preset 构造唯一的 ExperimentConfig；override 后重新执行严格校验。"""
    try:
        payload = deepcopy(_PRESET_PAYLOADS[preset_id])
    except KeyError as exc:
        raise KeyError(f"未知 experiment preset: {preset_id}") from exc
    if overrides is not None:
        _deep_merge(payload, overrides)
    return ExperimentConfig.model_validate(payload)


def _deep_merge(target: dict[str, Any], updates: Mapping[str, Any]) -> None:
    for key, value in updates.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge(current, value)
        else:
            target[key] = deepcopy(value)


__all__ = [
    "PresetStatus",
    "ExperimentPresetInfo",
    "ExperimentPresetCatalog",
    "list_experiment_presets",
    "get_experiment_preset",
    "build_experiment_config",
]
