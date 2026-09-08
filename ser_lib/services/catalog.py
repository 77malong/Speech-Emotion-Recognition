"""统一组件 Catalog 的应用服务。"""

from __future__ import annotations

from ser_lib.catalog import (
    ComponentCatalog,
    ComponentDescriptor,
    get_component_catalog,
    list_component_descriptors,
)


class CatalogService:
    """为动态表单和组件选择器提供只读 Catalog facade。"""

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


__all__ = ["CatalogService"]
