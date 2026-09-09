"""稳定实验预设目录；配置模板与构造由中央 config 层提供。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from ser_lib.config.presets import build_experiment_config, list_experiment_preset_ids

PresetStatus = Literal["stable", "experimental"]

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
    for preset_id in list_experiment_preset_ids():
        config = build_experiment_config(preset_id)
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


__all__ = [
    "PresetStatus",
    "ExperimentPresetInfo",
    "ExperimentPresetCatalog",
    "list_experiment_presets",
    "get_experiment_preset",
    "build_experiment_config",
]
