"""面向 CLI/Web 的结构化诊断协议。

Diagnostic 表示“发现了一个需要展示给调用方的问题”，但不意味着操作必须
终止。不可继续的领域错误仍使用 :class:`ser_lib.core.exceptions.SERError`。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

DiagnosticSeverity = Literal["info", "warning", "error"]
_DIAGNOSTIC_SEVERITIES = frozenset({"info", "warning", "error"})


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    raise TypeError(f"Diagnostic.details 包含不可 JSON 序列化的类型: {type(value).__name__}")


def _validate_code(code: str) -> None:
    if not code or not code.replace("_", "").isalnum():
        raise ValueError(f"Diagnostic.code 非法: {code!r}")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """一个稳定、可 JSON 序列化、可由 UI 直接展示的诊断项。"""

    severity: DiagnosticSeverity
    code: str
    message: str
    stage: str | None = None
    field: str | None = None
    path: str | Path | None = None
    uid: str | None = None
    suggestion: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in _DIAGNOSTIC_SEVERITIES:
            allowed = ", ".join(sorted(_DIAGNOSTIC_SEVERITIES))
            raise ValueError(f"Diagnostic.severity 非法: {self.severity!r}; 支持: {allowed}")
        _validate_code(self.code)
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("Diagnostic.message 必须是非空字符串")
        if self.path is not None:
            object.__setattr__(self, "path", str(self.path))
        # 构造时即验证，避免错误等到 HTTP/JSON 序列化阶段才暴露。
        _json_safe(self.details)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "field": self.field,
            "path": self.path,
            "uid": self.uid,
            "suggestion": self.suggestion,
            "details": _json_safe(self.details),
        }

    @classmethod
    def from_error(
        cls,
        error: Exception,
        *,
        severity: DiagnosticSeverity = "error",
        suggestion: str | None = None,
    ) -> "Diagnostic":
        """把异常转换为展示用 Diagnostic，不改变原异常的控制流语义。"""
        from ser_lib.core.exceptions import SERError

        if isinstance(error, SERError):
            raw_details = dict(error.details)
            return cls(
                severity=severity,
                code=error.code,
                message=str(error),
                stage=_optional_string(raw_details.get("stage")),
                field=_optional_string(raw_details.get("field")),
                path=_optional_string(raw_details.get("path")),
                uid=_optional_string(raw_details.get("uid")),
                suggestion=suggestion,
                details=raw_details,
            )
        return cls(
            severity=severity,
            code="unexpected_error",
            message=str(error) or type(error).__name__,
            suggestion=suggestion,
            details={"error_type": type(error).__name__},
        )


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


__all__ = ["Diagnostic", "DiagnosticSeverity"]
