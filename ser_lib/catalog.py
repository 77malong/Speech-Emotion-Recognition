"""供 Web/CLI 查询的统一组件目录。

Catalog 是纯只读适配层：不创建模型、不构建 optimizer、不加载数据，只把现有
Data Registry、Model Registry 与训练侧白名单配置统一暴露为 ComponentDescriptor。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Iterable

from pydantic import BaseModel

# 导入公开包以确保内置 data/model 组件完成轻量注册。
from ser_lib import data as _data_package  # noqa: F401
from ser_lib import models as _models_package  # noqa: F401
from ser_lib.data.registry import ComponentDescriptor, default_registry
from ser_lib.engine.objectives import LossConfig, SamplingConfig
from ser_lib.engine.optim import (
    AdamConfig,
    AdamWConfig,
    CosineSchedulerConfig,
    SGDConfig,
    StepSchedulerConfig,
)
from ser_lib.foundation.errors import RegistryError
from ser_lib.models.registry import model_registry

CATALOG_SCHEMA_VERSION = 1
CATALOG_CATEGORIES: tuple[str, ...] = (
    "model",
    "representation",
    "waveform_transform",
    "feature_transform",
    "importer",
    "optimizer",
    "scheduler",
    "loss",
    "sampler",
)

_DATA_NAMESPACES: tuple[str, ...] = (
    "representation",
    "waveform_transform",
    "feature_transform",
    "importer",
)


def _parameter_schema(
    model: type[BaseModel],
    *,
    fields: Iterable[str] | None = None,
) -> dict[str, Any]:
    """把完整 Pydantic 配置 Schema 裁剪为组件 ``params`` Schema。"""
    schema = deepcopy(model.model_json_schema())
    properties = dict(schema.get("properties", {}))
    properties.pop("type", None)
    allowed = set(fields) if fields is not None else set(properties)
    properties = {key: value for key, value in properties.items() if key in allowed}
    required = [
        key for key in schema.get("required", [])
        if key != "type" and key in properties
    ]
    schema["properties"] = properties
    if required:
        schema["required"] = required
    else:
        schema.pop("required", None)
    schema["type"] = "object"
    schema["additionalProperties"] = False
    return schema


def _descriptor(
    component_id: str,
    display_name: str,
    category: str,
    description: str,
    config_model: type[BaseModel],
    *,
    fields: Iterable[str] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> ComponentDescriptor:
    return ComponentDescriptor(
        id=component_id,
        display_name=display_name,
        category=category,
        description=description,
        config_schema=_parameter_schema(config_model, fields=fields),
        capabilities=capabilities or {},
    )


def _data_descriptors() -> list[ComponentDescriptor]:
    result: list[ComponentDescriptor] = []
    category_capabilities: dict[str, dict[str, Any]] = {
        "representation": {"pipeline_stage": "representation"},
        "waveform_transform": {"pipeline_stage": "waveform"},
        "feature_transform": {"pipeline_stage": "feature"},
        "importer": {"supports_scan": True, "supports_convert": True},
    }
    for namespace in _DATA_NAMESPACES:
        for descriptor in default_registry.descriptors(namespace, statuses=None):
            capabilities = {
                **category_capabilities[namespace],
                **descriptor.capabilities,
            }
            # Catalog 对外 category 以 Registry namespace 为准，避免第三方 descriptor
            # 写错 category 后迫使前端猜测组件所属分组。
            result.append(
                replace(
                    descriptor,
                    category=namespace,
                    capabilities=capabilities,
                )
            )
    return result


def _model_descriptors() -> list[ComponentDescriptor]:
    result: list[ComponentDescriptor] = []
    for name in model_registry.names():
        raw = model_registry.descriptor(name)
        result.append(
            ComponentDescriptor(
                id=raw["id"],
                display_name=raw["display_name"],
                category="model",
                version=raw["version"],
                status=raw["status"],
                description=raw["description"],
                config_schema=raw["config_schema"],
                capabilities={
                    "input_layouts": dict(raw["input_layouts"]),
                    "supports_static_spec": model_registry.supports_static_spec(name),
                },
            )
        )
    return result


def _training_descriptors() -> list[ComponentDescriptor]:
    return [
        _descriptor(
            "adamw", "AdamW", "optimizer", "AdamW 优化器。", AdamWConfig,
            capabilities={"decoupled_weight_decay": True},
        ),
        _descriptor(
            "adam", "Adam", "optimizer", "Adam 优化器。", AdamConfig,
            capabilities={"decoupled_weight_decay": False},
        ),
        _descriptor(
            "sgd", "SGD", "optimizer", "支持 momentum / Nesterov 的 SGD 优化器。",
            SGDConfig,
            capabilities={"supports_momentum": True, "supports_nesterov": True},
        ),
        _descriptor(
            "step", "StepLR", "scheduler", "按固定 epoch 间隔衰减学习率。",
            StepSchedulerConfig,
        ),
        _descriptor(
            "cosine", "Cosine Annealing", "scheduler", "余弦退火学习率调度器。",
            CosineSchedulerConfig,
        ),
        _descriptor(
            "cross_entropy", "Cross Entropy", "loss", "交叉熵分类损失。",
            LossConfig,
            fields=("class_weights", "label_smoothing"),
            capabilities={
                "supports_class_weights": True,
                "supports_label_smoothing": True,
            },
        ),
        _descriptor(
            "focal", "Focal Loss", "loss", "用于类别不均衡的 Focal Loss。",
            LossConfig,
            fields=("class_weights", "label_smoothing", "focal_gamma"),
            capabilities={
                "supports_class_weights": True,
                "supports_label_smoothing": True,
                "supports_focal_gamma": True,
            },
        ),
        _descriptor(
            "shuffle", "Shuffle", "sampler", "普通随机打乱采样。",
            SamplingConfig,
            fields=(),
            capabilities={"weighted": False},
        ),
        _descriptor(
            "weighted", "Weighted", "sampler", "按类别权重或类别频次进行加权采样。",
            SamplingConfig,
            fields=("class_weights", "replacement", "num_samples"),
            capabilities={
                "weighted": True,
                "auto_class_weights": True,
            },
        ),
    ]


@dataclass(frozen=True, slots=True)
class ComponentCatalog:
    """稳定、JSON-safe 的组件目录快照。"""

    components: tuple[ComponentDescriptor, ...]

    def __post_init__(self) -> None:
        seen: set[tuple[str, str]] = set()
        for component in self.components:
            if component.category not in CATALOG_CATEGORIES:
                raise RegistryError(f"Catalog 包含未知 category: {component.category!r}")
            key = (component.category, component.id)
            if key in seen:
                raise RegistryError(
                    f"Catalog 组件重复: category={component.category!r}, id={component.id!r}"
                )
            seen.add(key)

    @property
    def categories(self) -> tuple[str, ...]:
        return CATALOG_CATEGORIES

    def list(
        self,
        category: str | None = None,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> tuple[ComponentDescriptor, ...]:
        if category is not None and category not in CATALOG_CATEGORIES:
            raise RegistryError(
                f"未知 Catalog category {category!r}，可用: {list(CATALOG_CATEGORIES)}"
            )
        return tuple(
            component for component in self.components
            if (category is None or component.category == category)
            and (statuses is None or component.status in statuses)
        )

    def get(self, category: str, component_id: str) -> ComponentDescriptor:
        for component in self.list(category):
            if component.id == component_id:
                return component
        available = [item.id for item in self.list(category)]
        raise RegistryError(
            f"未知 Catalog 组件 {category}.{component_id}；可用: {available}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "categories": list(CATALOG_CATEGORIES),
            "components": [component.to_json_safe() for component in self.components],
        }


def get_component_catalog() -> ComponentCatalog:
    """创建当前进程已注册组件的只读 Catalog 快照。"""
    components = [
        *_model_descriptors(),
        *_data_descriptors(),
        *_training_descriptors(),
    ]
    category_order = {category: index for index, category in enumerate(CATALOG_CATEGORIES)}
    components.sort(key=lambda item: (category_order[item.category], item.id))
    return ComponentCatalog(tuple(components))


def list_component_descriptors(
    category: str | None = None,
    *,
    statuses: tuple[str, ...] | None = None,
) -> tuple[ComponentDescriptor, ...]:
    """便捷查询函数；等价于 ``get_component_catalog().list(...)``。"""
    return get_component_catalog().list(category, statuses=statuses)


__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "CATALOG_CATEGORIES",
    "ComponentDescriptor",
    "ComponentCatalog",
    "get_component_catalog",
    "list_component_descriptors",
]
