"""数据领域异常。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ser_lib.foundation.errors.base import SERError


class SERDataError(SERError):
    """数据模块所有业务异常的基类。"""

    default_code = "data_error"

    def __init__(
        self,
        message: str,
        *,
        uid: str | None = None,
        path: Path | str | None = None,
        component: str | None = None,
        stage: str | None = None,
    ) -> None:
        parts: list[str] = []
        if uid is not None:
            parts.append(f"uid={uid}")
        if path is not None:
            parts.append(f"path={Path(path)}")
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
                    "path": str(path) if path is not None else None,
                    "component": component,
                    "stage": stage,
                }.items()
                if value is not None
            },
        )
        self.uid = uid
        self.path = Path(path) if path is not None else None
        self.component = component
        self.stage = stage


class ManifestError(SERDataError):
    """Manifest 读取、校验或路径解析失败。"""

    default_code = "manifest_error"


class AudioNotFoundError(SERDataError):
    """音频文件不存在。"""

    default_code = "audio_not_found"


class AudioDecodeError(SERDataError):
    """音频解码失败或内容损坏。"""

    default_code = "audio_decode_error"


class InvalidAudioSegmentError(SERDataError):
    """音频片段定义非法（越界、零长度或解码结果为空）。"""

    default_code = "audio_invalid_segment"


class RepresentationError(SERDataError):
    """表示（Representation）计算失败或输出违反契约。"""

    default_code = "representation_error"


class TransformError(SERDataError):
    """Transform 构建或执行失败。"""

    default_code = "transform_error"


class CollationError(SERDataError):
    """批处理失败：key、layout 或标签契约不一致。"""

    default_code = "collation_error"


def wrap_error(
    exc: Exception,
    target: type[SERDataError],
    message: str,
    *,
    uid: str | None = None,
    path: Any = None,
    component: str | None = None,
    stage: str | None = None,
) -> SERDataError:
    """把底层异常包装为业务异常并保留异常链。"""
    if isinstance(exc, target):
        return exc
    wrapped = target(
        message,
        uid=uid,
        path=path,
        component=component,
        stage=stage,
    )
    wrapped.__cause__ = exc
    return wrapped


__all__ = [
    "SERDataError",
    "ManifestError",
    "AudioNotFoundError",
    "AudioDecodeError",
    "InvalidAudioSegmentError",
    "RepresentationError",
    "TransformError",
    "CollationError",
    "wrap_error",
]
