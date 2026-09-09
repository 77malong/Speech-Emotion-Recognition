"""统一组件 Catalog 与实验 Preset 的应用服务。"""

from __future__ import annotations

from typing import Any, Mapping

from ser_lib.catalog import (
    ComponentCatalog,
    ComponentDescriptor,
    get_component_catalog,
    list_component_descriptors,
)
from ser_lib.engine.config import ExperimentConfig
from ser_lib.engine.presets import (
    ExperimentPresetCatalog,
    ExperimentPresetInfo,
    build_experiment_config,
    get_experiment_preset,
    list_experiment_presets,
)


class CatalogService:
    """为动态表单、组件选择器与实验向导提供只读 facade。"""

    @staticmethod
    def snapshot() -> ComponentCatalog:
        return get_component_catalog()

    @staticmethod
    def list(
        category: str | None = None,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> tuple[ComponentDescriptor, ...]:
        return list_component_descriptors(category, statuses=statuses)

    @staticmethod
    def get(category: str, component_id: str) -> ComponentDescriptor:
        return get_component_catalog().get(category, component_id)

    @staticmethod
    def presets() -> ExperimentPresetCatalog:
        """返回稳定、JSON-safe 的实验 preset catalog。"""
        return list_experiment_presets()

    @staticmethod
    def get_preset(preset_id: str) -> ExperimentPresetInfo:
        return get_experiment_preset(preset_id)

    @staticmethod
    def build_experiment(
        preset_id: str,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> ExperimentConfig:
        """基于 preset 构建唯一的 ``ExperimentConfig``，不引入第二套配置模型。"""
        return build_experiment_config(preset_id, overrides=overrides)


__all__ = ["CatalogService"]
