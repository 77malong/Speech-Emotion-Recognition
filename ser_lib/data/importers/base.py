"""Importer 公共协议、预览结构与长任务可观察性工具。

Importer 把外部数据格式转换为标准 manifest，必须区分 ``scan()``（预览，
不写盘）与 ``convert()``（确认后写入目标目录）。扫描按条目收集错误，
不因单个损坏文件终止全部扫描，也不把音频内容加载进内存。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from ser_lib.core.diagnostics import Diagnostic, DiagnosticSeverity
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


@dataclass(frozen=True)
class ImportIssue:
    """旧 importer issue 结构；保留兼容并可转换为统一 Diagnostic。"""

    entry_index: int | None
    path: Path | None
    stage: str
    message: str
    detail: str | None = None
    severity: DiagnosticSeverity = "error"
    code: str = "import_issue"
    suggestion: str | None = None

    def __str__(self) -> str:  # pragma: no cover - 展示用途
        location = f" [{self.path}]" if self.path is not None else ""
        index = f" #{self.entry_index}" if self.entry_index is not None else ""
        detail = f" ({self.detail})" if self.detail else ""
        return f"{self.stage}{index}{location}: {self.message}{detail}"

    def to_diagnostic(self) -> Diagnostic:
        details: dict[str, Any] = {}
        if self.entry_index is not None:
            details["entry_index"] = self.entry_index
        if self.detail is not None:
            details["detail"] = self.detail
        return Diagnostic(
            severity=self.severity,
            code=self.code,
            message=self.message,
            stage=self.stage,
            path=self.path,
            suggestion=self.suggestion,
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        """保留旧 issue 字段，同时增加稳定 severity/code。"""
        return {
            "entry_index": self.entry_index,
            "path": str(self.path) if self.path else None,
            "stage": self.stage,
            "message": self.message,
            "detail": self.detail,
            "severity": self.severity,
            "code": self.code,
            "suggestion": self.suggestion,
        }


@dataclass
class ImportPreview:
    """``scan()`` 的结果：预览记录、标签映射与错误汇总。"""

    importer_id: str
    records: list[AudioRecord] = field(default_factory=list)
    label_mapping: dict[str, int] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    structured_diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """统一视图；自动桥接旧 ``issues``/``warnings``，供新调用方消费。"""
        legacy_issues = [issue.to_diagnostic() for issue in self.issues]
        legacy_warnings = [
            Diagnostic(
                severity="warning",
                code="import_warning",
                message=warning,
                stage="scan",
            )
            for warning in self.warnings
        ]
        return tuple([*legacy_issues, *legacy_warnings, *self.structured_diagnostics])

    @property
    def ok(self) -> bool:
        """是否不存在 error severity 的诊断。"""
        return not any(item.severity == "error" for item in self.diagnostics)

    def summary(self) -> dict[str, Any]:
        """返回可序列化的预览摘要，兼容旧字段并增加统一 diagnostics。"""
        return {
            "importer": self.importer_id,
            "num_records": len(self.records),
            "label_mapping": dict(self.label_mapping),
            "num_issues": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
            "warnings": list(self.warnings),
            "num_diagnostics": len(self.diagnostics),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


class ImportTask:
    """Importer ``scan``/``convert`` 的共享生命周期、进度和取消适配器。

    该类不包含数据集格式知识，只负责把同步 Python 循环转换成稳定的 Event v2
    事件流。具体 importer 在每个可取消边界调用 :meth:`check`，并在已知工作量
    的循环中调用 :meth:`progress`。
    """

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

    def __enter__(self) -> ImportTask:
        self.started_at = time.perf_counter()
        details: dict[str, Any] = {
            "importer_id": self.importer_id,
            "source": self.source,
        }
        if self.destination is not None:
            details["destination"] = self.destination
        self._emit(
            LifecycleEvent(
                self.stage,
                "started",
                details=details,
                context=self.context,
            )
        )
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
            self._emit(
                LifecycleEvent(
                    self.stage,
                    "completed",
                    details=details,
                    context=self.context,
                )
            )
        elif isinstance(exc, OperationCancelled):
            self._emit(
                LifecycleEvent(
                    self.stage,
                    "cancelled",
                    details=details,
                    context=self.context,
                )
            )
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
        """在 importer 的安全边界进行协作式取消检查。"""
        if self.cancellation is not None:
            self.cancellation.raise_if_cancelled()

    def update_details(self, **details: Any) -> None:
        """补充最终 lifecycle 事件中的紧凑摘要。"""
        self._details.update(details)

    def progress(
        self,
        completed: int,
        total: int | None,
        *,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        """发出一条 importer 进度事件，并在发出前检查取消。"""
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
    """Importer 协议（设计文档 §6.3）。"""

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
        """解析外部数据源并返回预览；不写入任何文件。"""
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
        """把外部数据源转换为标准 manifest 并写入 destination 目录。"""
        ...


__all__ = [
    "DatasetImporter",
    "ImportIssue",
    "ImportPreview",
    "ImportTask",
    "ImportOperation",
]
