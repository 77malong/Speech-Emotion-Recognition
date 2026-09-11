"""内置实验 preset 的配置模板与严格构造。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ser_lib.config.experiment import ExperimentConfig

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

        "data": {

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

        "data": {

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

        "data": {

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


def list_experiment_preset_ids() -> tuple[str, ...]:
    """返回稳定、排序后的内置 preset ID，不构造运行时组件。"""
    return tuple(sorted(_PRESET_PAYLOADS))


def get_experiment_preset_payload(preset_id: str) -> dict[str, Any]:
    """返回 preset payload 的深拷贝，调用方修改不会污染内置模板。"""
    try:
        return deepcopy(_PRESET_PAYLOADS[preset_id])
    except KeyError as exc:
        raise KeyError(f"未知 experiment preset: {preset_id}") from exc


def build_experiment_config(
    preset_id: str,
    overrides: Mapping[str, Any] | None = None,
) -> ExperimentConfig:
    """从 preset 构造 ExperimentConfig；override 后重新执行严格校验。"""
    payload = get_experiment_preset_payload(preset_id)
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
    "list_experiment_preset_ids",
    "get_experiment_preset_payload",
    "build_experiment_config",
]
