"""跨数据与模型契约的 engine 异常。"""

from __future__ import annotations

from pathlib import Path

from ser_lib.foundation.errors.base import SERError


class CompatibilityError(SERError):
    """跨数据与模型契约的兼容性校验失败。"""

    default_code = "compatibility_error"

    def __init__(
        self,
        message: str,
        *,
        uid: str | None = None,
        path: Path | str | None = None,
        component: str | None = None,
        stage: str | None = None,
    ) -> None:
        resolved_path = Path(path) if path is not None else None
        parts: list[str] = []
        if uid is not None:
            parts.append(f"uid={uid}")
        if resolved_path is not None:
            parts.append(f"path={resolved_path}")
        if component is not None:
            parts.append(f"component={component}")
        if stage is not None:
            parts.append(f"stage={stage}")
        if parts:
            message = f"{message} [{'; '.join(parts)}]"
        super().__init__(
            message,
            code=self.default_code,
            details={
                key: value
                for key, value in {
                    "uid": uid,
                    "path": str(resolved_path) if resolved_path is not None else None,
                    "component": component,
                    "stage": stage,
                }.items()
                if value is not None
            },
        )
        self.uid = uid
        self.path = resolved_path
        self.component = component
        self.stage = stage


__all__ = ["CompatibilityError"]
