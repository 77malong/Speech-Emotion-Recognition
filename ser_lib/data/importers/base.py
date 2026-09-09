"""Importer 公共协议、预览结构与长任务可观察性工具。

Importer 把外部数据格式转换为标准 manifest，必须区分 ``scan()``（预览，
不写盘）与 ``convert()``（确认后写入目标目录）。扫描按条目收集结构化
Diagnostic，不因单个损坏文件终止全部扫描，也不把音频内容加载进内存。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from ser_lib.core.diagnostics import Diagnostic
from ser_lib.core.events import (
    CancellationCheck,
    EventCallback,
    EventContext,
    LifecycleEvent,
    ProgressEvent,
)
from ser_lib.core.exceptions import OperationCancelled
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord

ImportOperation = Literal["scan", "convert"]


@dataclass
class ImportPreview:
    """``scan()`` 结果；所有问题只通过统一 Diagnostic 表达。"""

    importer_id: str
    records: list[AudioRecord] = field(default_factory=list)
    label_mapping: dict[str, int] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "error" for item in self.diagnostics)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.diagnostics)

    @property
    def info_count(self) -> int:
        return sum(item.severity == "info" for item in self.diagnostics)

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def format_errors(self, *, limit: int = 10) -> str:
        """为异常消息生成紧凑的人类可读错误摘要。"""
        errors = [item for item in self.diagnostics if item.severity == "error"]
        rendered: list[str] = []
        for item in errors[:limit]:
            prefix = f"{item.stage}: " if item.stage else ""
            location = f" [{item.path}]" if item.path else ""
            rendered.append(f"{prefix}{item.message}{location}")
        return "; ".join(rendered)

    def summary(self) -> dict[str, Any]:
        """返回单轨、JSON-safe 的预览摘要。"""
        return {
            "importer": self.importer_id,
            "num_records": len(self.records),
            "label_mapping": dict(self.label_mapping),
            "num_errors": self.error_count,
            "num_warnings": self.warning_count,
            "num_info": self.info_count,
            "num_diagnostics": len(self.diagnostics),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


class ImportTask:
    """Importer ``scan``/``convert`` 的共享生命周期、进度和取消适配器。"""

    def __init__(
        self,
        importer_id: str,
        operation: ImportOperation,
        *,
        source: Path,
        destination: Path | None = None,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> None:
        self.importer_id = importer_id
        self.operation = operation
        self.source = Path(source)
        self.destination = Path(destination) if destination is not None else None
        self.event_callback = event_callback
        self.cancellation = cancellation
        self.context = event_context or EventContext()
        self.started_at = 0.0
        self._details: dict[str, Any] = {}

    @property
    def stage(self) -> str:
        return f"import_{self.operation}"

    def _emit(self, event: LifecycleEvent | ProgressEvent) -> None:
        if self.event_callback is not None:
            self.event_callback(event)

    def _base_details(self) -> dict[str, Any]:
        return {
            "importer_id": self.importer_id,
            "duration_seconds": max(time.perf_counter() - self.started_at, 0.0),
            **self._details,
        }

    def __enter__(self) -> "ImportTask":
        self.started_at = time.perf_counter()
        details: dict[str, Any] = {"importer_id": self.importer_id, "source": self.source}
        if self.destination is not None:
            details["destination"] = self.destination
        self._emit(LifecycleEvent(self.stage, "started", details=details, context=self.context))
        try:
            self.check()
        except OperationCancelled:
            self._emit(
                LifecycleEvent(
                    self.stage,
                    "cancelled",
                    details=self._base_details(),
                    context=self.context,
                )
            )
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> Literal[False]:
        details = self._base_details()
        if exc is None:
            self._emit(LifecycleEvent(self.stage, "completed", details=details, context=self.context))
        elif isinstance(exc, OperationCancelled):
            self._emit(LifecycleEvent(self.stage, "cancelled", details=details, context=self.context))
        else:
            self._emit(
                LifecycleEvent(
                    self.stage,
                    "failed",
                    message=str(exc),
                    details={"error_type": type(exc).__name__, **details},
                    context=self.context,
                )
            )
        return False

    def check(self) -> None:
        if self.cancellation is not None:
            self.cancellation.raise_if_cancelled()

    def update_details(self, **details: Any) -> None:
        self._details.update(details)

    def progress(
        self,
        completed: int,
        total: int | None,
        *,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.check()
        payload = {
            "importer_id": self.importer_id,
            "elapsed_seconds": max(time.perf_counter() - self.started_at, 0.0),
        }
        if details:
            payload.update(details)
        self._emit(
            ProgressEvent(
                self.stage,
                completed=completed,
                total=total,
                message=message,
                details=payload,
                context=self.context,
            )
        )


class DatasetImporter(Protocol):
    descriptor: ComponentDescriptor

    def scan(
        self,
        source: Path,
        config: Mapping[str, Any],
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> ImportPreview:
        ...

    def convert(
        self,
        source: Path,
        destination: Path,
        config: Mapping[str, Any],
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> DatasetManifest:
        ...


__all__ = ["DatasetImporter", "ImportPreview", "ImportTask", "ImportOperation"]
