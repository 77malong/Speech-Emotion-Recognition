"""模型注册表。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel
from torch import nn

from ser_lib.foundation.errors import RegistryError
from ser_lib.models.base import SERModel
from ser_lib.models.specs import ModelSpec

ModelSpecFactory = Callable[[dict[str, Any]], ModelSpec]
ReconstructibilityCheck = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    display_name: str
    description: str
    config_schema: dict[str, Any]
    input_layouts: dict[str, str]
    version: str = "1.0"
    status: str = "stable"

    def to_json_safe(self) -> dict[str, Any]:
        return {
            "id": self.id, "display_name": self.display_name,
            "description": self.description, "config_schema": self.config_schema,
            "input_layouts": self.input_layouts, "version": self.version,
            "status": self.status,
        }


@dataclass(frozen=True)
class _ModelEntry:
    factory: Callable[..., SERModel]
    config_model: type[BaseModel] | None
    descriptor: ModelDescriptor
    spec_factory: ModelSpecFactory | None = None
    reconstructibility_check: ReconstructibilityCheck | None = None


@dataclass(frozen=True)
class _TorchFactoryEntry:
    factory: Callable[..., nn.Module]
    config_model: type[BaseModel] | None


class ModelRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, _ModelEntry] = {}
        # 普通 nn.Module factory 与 SERModel 共用同一个 registry owner；这里只是
        # adapter 重建所需的私有子表，不创建第二套 Registry 类型或全局实例。
        self._torch_factories: dict[str, _TorchFactoryEntry] = {}

    def register(
        self,
        name: str,
        factory: Callable[..., SERModel],
        *,
        config_model: type[BaseModel] | None = None,
        descriptor: ModelDescriptor | None = None,
        spec_factory: ModelSpecFactory | None = None,
        reconstructibility_check: ReconstructibilityCheck | None = None,
        replace: bool = False,
    ) -> None:
        if not name:
            raise RegistryError("模型名称不能为空")
        if name in self._entries and not replace:
            raise RegistryError(f"模型重复注册: {name!r}")
        descriptor = descriptor or ModelDescriptor(name, name, "", {}, {})
        if descriptor.id != name:
            raise RegistryError("模型 descriptor.id 必须与注册名称一致")
        self._entries[name] = _ModelEntry(
            factory,
            config_model,
            descriptor,
            spec_factory,
            reconstructibility_check,
        )

    def create(self, name: str, **params: Any) -> SERModel:
        if name not in self._entries:
            raise RegistryError(f"未知模型 {name!r}，可用模型: {sorted(self._entries)}")
        entry = self._entries[name]
        try:
            if entry.config_model is not None:
                params = entry.config_model(**params).model_dump()
            model = entry.factory(**params)
        except Exception as exc:
            raise RegistryError(f"模型 {name!r} 构建失败: {exc}") from exc
        if not isinstance(model, SERModel):
            raise RegistryError(f"模型工厂 {name!r} 返回了非 SERModel: {type(model)!r}")
        return model

    def validate_config(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """严格校验模型配置，并返回带默认值的 JSON-safe 参数。"""
        if name not in self._entries:
            raise RegistryError(f"未知模型 {name!r}，可用模型: {sorted(self._entries)}")
        entry = self._entries[name]
        if entry.config_model is None:
            return dict(params)
        try:
            return entry.config_model(**params).model_dump(mode="json")
        except Exception as exc:
            raise RegistryError(f"模型 {name!r} 配置校验失败: {exc}") from exc

    def validate_reconstructible(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """验证模型配置可由注册 ID 重建，但不实例化模型或加载权重。"""
        normalized = self.validate_config(name, params)
        entry = self._entries[name]
        if entry.reconstructibility_check is None:
            return normalized
        try:
            entry.reconstructibility_check(normalized)
        except Exception as exc:
            raise RegistryError(f"模型 {name!r} 不可重建: {exc}") from exc
        return normalized

    def inspect_spec(self, name: str, params: dict[str, Any]) -> ModelSpec:
        """仅根据配置生成 ModelSpec，不实例化模型、不加载权重。"""
        if name not in self._entries:
            raise RegistryError(f"未知模型 {name!r}，可用模型: {sorted(self._entries)}")
        entry = self._entries[name]
        if entry.spec_factory is None:
            raise RegistryError(
                f"模型 {name!r} 未声明静态 ModelSpec，无法执行无实例化 dry-run"
            )
        normalized = self.validate_config(name, params)
        try:
            spec = entry.spec_factory(normalized)
        except Exception as exc:
            raise RegistryError(f"模型 {name!r} ModelSpec 生成失败: {exc}") from exc
        if not isinstance(spec, ModelSpec):
            raise RegistryError(
                f"模型 {name!r} spec_factory 返回了非 ModelSpec: {type(spec)!r}"
            )
        return spec

    def supports_static_spec(self, name: str) -> bool:
        """模型是否支持不实例化模型的静态 ModelSpec 查询。"""
        if name not in self._entries:
            raise RegistryError(f"未知模型 {name!r}，可用模型: {sorted(self._entries)}")
        return self._entries[name].spec_factory is not None

    def register_torch_factory(
        self,
        factory_id: str,
        factory: Callable[..., nn.Module],
        *,
        config_model: type[BaseModel] | None = None,
        replace: bool = False,
    ) -> None:
        """登记普通 nn.Module 的可重建 factory。

        callable 只存在于当前 Python 进程的 registry；artifact 永远只持久化
        ``factory_id`` 与 JSON-safe 参数，不序列化或动态导入 callable。
        """
        if not factory_id:
            raise RegistryError("Torch factory ID 不能为空")
        if factory_id in self._torch_factories and not replace:
            raise RegistryError(f"Torch factory 重复注册: {factory_id!r}")
        if not callable(factory):
            raise RegistryError("Torch factory 必须可调用")
        self._torch_factories[factory_id] = _TorchFactoryEntry(factory, config_model)

    def has_torch_factory(self, factory_id: str) -> bool:
        return factory_id in self._torch_factories

    def torch_factory_names(self) -> list[str]:
        return sorted(self._torch_factories)

    def validate_torch_factory_config(
        self,
        factory_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if factory_id not in self._torch_factories:
            raise RegistryError(
                f"未知 Torch factory {factory_id!r}，可用: {sorted(self._torch_factories)}"
            )
        entry = self._torch_factories[factory_id]
        if entry.config_model is not None:
            try:
                return entry.config_model(**params).model_dump(mode="json")
            except Exception as exc:
                raise RegistryError(
                    f"Torch factory {factory_id!r} 配置校验失败: {exc}"
                ) from exc
        try:
            json.dumps(params, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise RegistryError(
                f"Torch factory {factory_id!r} 参数必须是 JSON-safe 数据"
            ) from exc
        return dict(params)

    def create_torch_module(self, factory_id: str, **params: Any) -> nn.Module:
        """由已注册 ID 重建普通 nn.Module。"""
        normalized = self.validate_torch_factory_config(factory_id, dict(params))
        entry = self._torch_factories[factory_id]
        try:
            module = entry.factory(**normalized)
        except Exception as exc:
            raise RegistryError(f"Torch factory {factory_id!r} 构建失败: {exc}") from exc
        if not isinstance(module, nn.Module):
            raise RegistryError(
                f"Torch factory {factory_id!r} 返回了非 nn.Module: {type(module)!r}"
            )
        return module

    def descriptor(self, name: str) -> dict[str, Any]:
        if name not in self._entries:
            raise RegistryError(f"未知模型 {name!r}，可用模型: {sorted(self._entries)}")
        return self._entries[name].descriptor.to_json_safe()

    def names(self) -> list[str]:
        return sorted(self._entries)

    def descriptors(self) -> list[dict[str, Any]]:
        return [self._entries[name].descriptor.to_json_safe() for name in self.names()]


model_registry = ModelRegistry()
