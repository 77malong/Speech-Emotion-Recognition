"""训练 checkpoint 的轻量文件系统检查与 Catalog 扫描。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ser_lib.foundation.events import CancellationCheck, EventCallback, ProgressEvent

CheckpointKind = Literal["best", "last", "epoch", "other"]
_EPOCH_NAME = re.compile(r"^epoch-(\d+)\.pt$")


@dataclass(frozen=True, slots=True)
class CheckpointInfo:
    """不反序列化 `.pt` 内容即可获得的 checkpoint 文件信息。"""

    path: str
    name: str
    kind: CheckpointKind
    epoch: int | None
    size_bytes: int
    modified_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "epoch": self.epoch,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CheckpointScanFailure:
    path: str
    error_type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class CheckpointCatalog:
    """Checkpoint 列表；扫描不会调用 `torch.load()`。"""

    root: str
    checkpoints: tuple[CheckpointInfo, ...]
    failures: tuple[CheckpointScanFailure, ...]

    @property
    def total(self) -> int:
        return len(self.checkpoints) + len(self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total": self.total,
            "checkpoints": [item.to_dict() for item in self.checkpoints],
            "failures": [failure.to_dict() for failure in self.failures],
        }


def inspect_checkpoint_file(path: Path | str) -> CheckpointInfo:
    """只读取一个 `.pt` 文件的 stat 信息，不解析 pickle payload。"""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"checkpoint 文件不存在: {source}")
    if source.suffix.lower() != ".pt":
        raise ValueError(f"checkpoint 文件必须使用 .pt 后缀: {source}")
    stat = source.stat()
    kind, epoch = _classify_checkpoint_name(source.name)
    return CheckpointInfo(
        path=source.as_posix(),
        name=source.name,
        kind=kind,
        epoch=epoch,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )


def scan_checkpoints(
    root: Path | str,
    *,
    recursive: bool = False,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> CheckpointCatalog:
    """扫描 `.pt` checkpoint；不读取模型、optimizer 或 RNG state。"""
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"checkpoint 根目录不存在或不是目录: {root_path}")
    candidates = _candidate_files(root_path, recursive=recursive)
    checkpoints: list[CheckpointInfo] = []
    failures: list[CheckpointScanFailure] = []
    total = len(candidates)

    for index, path in enumerate(candidates, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            checkpoints.append(inspect_checkpoint_file(path))
        except Exception as exc:
            if fail_fast:
                raise
            failures.append(
                CheckpointScanFailure(
                    path=path.as_posix(),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
        if event_callback is not None:
            event_callback(
                ProgressEvent(
                    stage="checkpoint_catalog_scan",
                    completed=index,
                    total=total,
                    details={
                        "valid": len(checkpoints),
                        "failed": len(failures),
                        "path": path,
                    },
                )
            )

    checkpoints.sort(
        key=lambda item: (item.modified_at, item.name.casefold()),
        reverse=True,
    )
    return CheckpointCatalog(
        root=root_path.as_posix(),
        checkpoints=tuple(checkpoints),
        failures=tuple(failures),
    )


def _classify_checkpoint_name(name: str) -> tuple[CheckpointKind, int | None]:
    if name == "best.pt":
        return "best", None
    if name == "last.pt":
        return "last", None
    match = _EPOCH_NAME.fullmatch(name)
    if match is not None:
        return "epoch", int(match.group(1))
    return "other", None


def _candidate_files(root: Path, *, recursive: bool) -> list[Path]:
    iterator = root.rglob("*.pt") if recursive else root.glob("*.pt")
    return sorted(
        (path for path in iterator if path.is_file()),
        key=lambda path: path.as_posix().casefold(),
    )


__all__ = [
    "CheckpointKind",
    "CheckpointInfo",
    "CheckpointScanFailure",
    "CheckpointCatalog",
    "inspect_checkpoint_file",
    "scan_checkpoints",
]
