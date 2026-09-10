"""标准 Dataset 的轻量 manifest 版本快照、历史扫描与安全恢复。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ser_lib.data.errors import DatasetEditConflictError, DatasetTransactionError
from ser_lib.data.fingerprint import fingerprint_manifest
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.migrations import migrate_data_payload
from ser_lib.foundation.events import CancellationCheck, EventCallback, ProgressEvent

DATASET_REVISION_SCHEMA_VERSION = 1
_DEFAULT_HISTORY_DIR = ".ser_history"
_REVISION_RECORD = "revision.json"
_CHUNK_SIZE = 1024 * 1024
_REVISION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower()
    )


class _RevisionFileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_file: str
    target_path: str = Field(min_length=1)
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("snapshot_file")
    @classmethod
    def _safe_snapshot_file(cls, value: str) -> str:
        path = PurePath(value)
        if (
            not value
            or path.is_absolute()
            or len(path.parts) != 1
            or value in {".", ".."}
        ):
            raise ValueError("snapshot_file 必须是 revision 目录内的普通文件名")
        return value

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _valid_sha256(value):
            raise ValueError("sha256 必须是 64 位十六进制摘要")
        return value.lower()


class _RevisionRecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    revision_id: str
    dataset_id: str = Field(min_length=1)
    created_at: datetime
    fingerprint: str
    source_manifest: str = Field(min_length=1)
    note: str = ""
    files: dict[str, _RevisionFileModel] = Field(min_length=1)

    @field_validator("revision_id")
    @classmethod
    def _revision_id(cls, value: str) -> str:
        if not _REVISION_ID.fullmatch(value):
            raise ValueError("revision_id 仅允许字母、数字、点、下划线和连字符")
        return value

    @field_validator("fingerprint")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if not _valid_sha256(value):
            raise ValueError("fingerprint 必须是 64 位十六进制 SHA256")
        return value.lower()

    @field_validator("created_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at 必须包含时区")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_files(self) -> "_RevisionRecordModel":
        if "dataset.yaml" not in self.files:
            raise ValueError("revision files 必须包含 dataset.yaml")
        names = [item.snapshot_file for item in self.files.values()]
        if len(names) != len(set(names)):
            raise ValueError("revision snapshot_file 不能重复")
        targets = [item.target_path for item in self.files.values()]
        if len(targets) != len(set(targets)):
            raise ValueError("revision target_path 不能重复")
        if _combined_digest(self.files) != self.fingerprint:
            raise ValueError("revision fingerprint 与 files 摘要不一致")
        return self


@dataclass(frozen=True, slots=True)
class DatasetRevisionInfo:
    revision_id: str
    dataset_id: str
    created_at: datetime
    fingerprint: str
    directory: str
    source_manifest: str
    note: str
    file_count: int
    total_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "dataset_id": self.dataset_id,
            "created_at": self.created_at.isoformat(),
            "fingerprint": self.fingerprint,
            "directory": self.directory,
            "source_manifest": self.source_manifest,
            "note": self.note,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
        }


@dataclass(frozen=True, slots=True)
class DatasetRevisionScanFailure:
    directory: str
    error_type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "directory": self.directory,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class DatasetRevisionCatalog:
    dataset_id: str
    root: str
    revisions: tuple[DatasetRevisionInfo, ...]
    failures: tuple[DatasetRevisionScanFailure, ...]

    @property
    def total(self) -> int:
        return len(self.revisions) + len(self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "root": self.root,
            "total": self.total,
            "revisions": [item.to_dict() for item in self.revisions],
            "failures": [item.to_dict() for item in self.failures],
        }


def create_dataset_revision(
    manifest: DatasetManifest | Path | str,
    *,
    history_root: Path | str | None = None,
    revision_id: str | None = None,
    note: str = "",
    created_at: datetime | None = None,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetRevisionInfo:
    """快照 dataset.yaml 与 split JSONL；音频文件永远不会被复制。"""
    dataset = _load_dataset(manifest)
    if created_at is not None and (
        created_at.tzinfo is None or created_at.utcoffset() is None
    ):
        raise ValueError("created_at 必须包含时区")
    timestamp = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    base_fingerprint = fingerprint_manifest(dataset, cancellation=cancellation)
    resolved_id = revision_id or (
        f"rev_{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}_{base_fingerprint.digest[:8]}"
    )
    if not _REVISION_ID.fullmatch(resolved_id):
        raise ValueError("revision_id 仅允许字母、数字、点、下划线和连字符")

    root = _history_root(dataset, history_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / resolved_id
    if target.exists():
        raise FileExistsError(f"Dataset revision 已存在: {target}")
    temporary = root / f".{resolved_id}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir()

    sources = [("dataset.yaml", dataset.meta.yaml_path)]
    sources.extend(
        (f"split:{split}", path)
        for split, path in sorted(dataset.meta.splits.items())
    )
    total_bytes = sum(path.stat().st_size for _, path in sources)
    copied_bytes = 0
    files: dict[str, _RevisionFileModel] = {}
    _emit_progress(
        event_callback,
        "dataset_revision_snapshot",
        0,
        total_bytes,
        {"revision_id": resolved_id, "files_total": len(sources)},
    )

    try:
        for index, (logical_name, source) in enumerate(sources):
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            snapshot_name = (
                "dataset.yaml" if index == 0 else f"split-{index:04d}.jsonl"
            )
            snapshot_path = temporary / snapshot_name
            expected_digest = base_fingerprint.files[logical_name]

            def on_chunk(amount: int) -> None:
                nonlocal copied_bytes
                copied_bytes += amount
                _emit_progress(
                    event_callback,
                    "dataset_revision_snapshot",
                    copied_bytes,
                    total_bytes,
                    {
                        "revision_id": resolved_id,
                        "file": logical_name,
                        "files_completed": index,
                        "files_total": len(sources),
                    },
                )

            digest, size = _copy_hash(
                source,
                snapshot_path,
                cancellation=cancellation,
                on_chunk=on_chunk,
            )
            if digest != expected_digest:
                raise DatasetEditConflictError(
                    "创建历史版本期间 Dataset 被外部修改",
                    path=source,
                    stage="snapshot",
                )
            files[logical_name] = _RevisionFileModel(
                snapshot_file=snapshot_name,
                target_path=source.resolve().as_posix(),
                sha256=digest,
                size_bytes=size,
            )

        latest = fingerprint_manifest(dataset, cancellation=cancellation)
        if latest.digest != base_fingerprint.digest:
            raise DatasetEditConflictError(
                "创建历史版本期间 Dataset 被外部修改",
                path=dataset.meta.yaml_path,
                stage="snapshot",
            )
        record = _RevisionRecordModel(
            revision_id=resolved_id,
            dataset_id=dataset.meta.dataset_id,
            created_at=timestamp,
            fingerprint=base_fingerprint.digest,
            source_manifest=dataset.meta.yaml_path.resolve().as_posix(),
            note=note,
            files=files,
        )
        (temporary / _REVISION_RECORD).write_text(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return inspect_dataset_revision(target)


def inspect_dataset_revision(
    path: Path | str,
    *,
    verify: bool = False,
    cancellation: CancellationCheck | None = None,
) -> DatasetRevisionInfo:
    """读取一个 revision；``verify=True`` 时重新 hash 所有快照文件。"""
    directory, record = _load_revision(path)
    total_bytes = 0
    for logical_name in _ordered_logical_names(record.files):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        file_info = record.files[logical_name]
        snapshot = directory / file_info.snapshot_file
        if not snapshot.is_file():
            raise FileNotFoundError(f"Dataset revision 文件缺失: {snapshot}")
        size = snapshot.stat().st_size
        if size != file_info.size_bytes:
            raise ValueError(f"Dataset revision 文件大小不一致: {snapshot}")
        total_bytes += size
        if verify and _sha256(snapshot, cancellation=cancellation) != file_info.sha256:
            raise ValueError(f"Dataset revision 文件 SHA256 不一致: {snapshot}")
    return DatasetRevisionInfo(
        revision_id=record.revision_id,
        dataset_id=record.dataset_id,
        created_at=record.created_at,
        fingerprint=record.fingerprint,
        directory=directory.as_posix(),
        source_manifest=record.source_manifest,
        note=record.note,
        file_count=len(record.files),
        total_bytes=total_bytes,
    )


def scan_dataset_revisions(
    manifest: DatasetManifest | Path | str,
    *,
    history_root: Path | str | None = None,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetRevisionCatalog:
    """扫描当前 Dataset 的 revision 目录，不做内容 hash。"""
    dataset = _load_dataset(manifest)
    root = _history_root(dataset, history_root)
    if not root.exists():
        return DatasetRevisionCatalog(dataset.meta.dataset_id, root.as_posix(), (), ())
    if not root.is_dir():
        raise NotADirectoryError(f"Dataset history_root 不是目录: {root}")
    candidates = sorted(
        (
            child
            for child in root.iterdir()
            if child.is_dir()
            and not child.name.startswith(".")
            and (child / _REVISION_RECORD).is_file()
        ),
        key=lambda item: item.name.casefold(),
    )

    def inspect_candidate(directory: Path) -> DatasetRevisionInfo | None:
        item = inspect_dataset_revision(directory, cancellation=cancellation)
        return item if item.dataset_id == dataset.meta.dataset_id else None

    revisions: list[DatasetRevisionInfo] = []
    failures: list[DatasetRevisionScanFailure] = []
    total = len(candidates)
    for index, directory in enumerate(candidates, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            item = inspect_candidate(directory)
            if item is not None:
                revisions.append(item)
        except Exception as exc:
            if fail_fast:
                raise
            failures.append(
                DatasetRevisionScanFailure(
                    directory=directory.as_posix(),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
        if event_callback is not None:
            event_callback(
                ProgressEvent(
                    stage="dataset_revision_catalog_scan",
                    completed=index,
                    total=total,
                    details={"valid": len(revisions), "failed": len(failures)},
                )
            )

    revisions.sort(key=lambda item: (item.created_at, item.revision_id), reverse=True)
    return DatasetRevisionCatalog(
        dataset_id=dataset.meta.dataset_id,
        root=root.as_posix(),
        revisions=tuple(revisions),
        failures=tuple(failures),
    )


def restore_dataset_revision(
    manifest: DatasetManifest | Path | str,
    revision: Path | str,
    *,
    expected_current_fingerprint: str,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetManifest:
    """在乐观锁保护下，把 Dataset manifest 文件事务化恢复到指定 revision。"""
    if not _valid_sha256(expected_current_fingerprint):
        raise ValueError("expected_current_fingerprint 必须是 64 位 SHA256")
    dataset = _load_dataset(manifest)
    current = fingerprint_manifest(dataset, cancellation=cancellation).digest
    if current != expected_current_fingerprint.lower():
        raise DatasetEditConflictError(
            "Dataset 当前版本与 expected_current_fingerprint 不一致",
            path=dataset.meta.yaml_path,
            stage="restore",
        )

    directory, record = _load_revision(revision)
    if record.dataset_id != dataset.meta.dataset_id:
        raise ValueError(
            f"revision dataset_id={record.dataset_id!r} 与当前 Dataset 不一致"
        )
    if Path(record.source_manifest).resolve() != dataset.meta.yaml_path.resolve():
        raise ValueError("revision 不属于当前 manifest 路径")
    inspect_dataset_revision(directory, verify=True, cancellation=cancellation)

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    ordered = _ordered_logical_names(record.files)
    total_bytes = sum(record.files[name].size_bytes for name in ordered)
    staged_bytes = 0
    _emit_progress(
        event_callback,
        "dataset_revision_restore",
        0,
        total_bytes,
        {"revision_id": record.revision_id},
    )
    try:
        for logical_name in ordered:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            file_info = record.files[logical_name]
            source = directory / file_info.snapshot_file
            target = Path(file_info.target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged[target] = _stage_file(source, target)
            staged_bytes += file_info.size_bytes
            _emit_progress(
                event_callback,
                "dataset_revision_restore",
                staged_bytes,
                total_bytes,
                {"revision_id": record.revision_id, "file": logical_name},
            )

        if fingerprint_manifest(dataset, cancellation=cancellation).digest != current:
            raise DatasetEditConflictError(
                "准备恢复期间 Dataset 被外部修改",
                path=dataset.meta.yaml_path,
                stage="restore",
            )
        if cancellation is not None:
            cancellation.raise_if_cancelled()

        for target in staged:
            backups[target] = _backup_file(target)
        yaml_path = dataset.meta.yaml_path.resolve()
        targets = [Path(record.files[name].target_path) for name in ordered]
        targets.sort(key=lambda item: item.resolve() == yaml_path)
        try:
            for target in targets:
                os.replace(staged[target], target)
            restored = DatasetManifest.load(dataset.meta.yaml_path)
            if fingerprint_manifest(restored).digest != record.fingerprint:
                raise DatasetTransactionError(
                    "恢复后的 Dataset fingerprint 与 revision 不一致",
                    path=dataset.meta.yaml_path,
                    stage="restore_verify",
                )
        except Exception as exc:
            restore_errors = _restore_backups(backups)
            if restore_errors:
                raise DatasetTransactionError(
                    "Dataset revision 恢复失败，且回滚不完整: "
                    + "; ".join(restore_errors),
                    path=dataset.meta.yaml_path,
                    stage="restore_rollback",
                ) from exc
            if isinstance(exc, (DatasetEditConflictError, DatasetTransactionError)):
                raise
            raise DatasetTransactionError(
                "Dataset revision 恢复失败，已恢复原文件",
                path=dataset.meta.yaml_path,
                stage="restore",
            ) from exc
    finally:
        for staged_path in staged.values():
            staged_path.unlink(missing_ok=True)
        for backup_path in backups.values():
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)
    return restored


def _load_dataset(manifest: DatasetManifest | Path | str) -> DatasetManifest:
    return (
        manifest
        if isinstance(manifest, DatasetManifest)
        else DatasetManifest.load(manifest)
    )


def _history_root(dataset: DatasetManifest, history_root: Path | str | None) -> Path:
    return (
        Path(history_root)
        if history_root is not None
        else dataset.meta.yaml_path.parent / _DEFAULT_HISTORY_DIR
    )


def _ordered_logical_names(files: dict[str, _RevisionFileModel]) -> list[str]:
    return ["dataset.yaml", *sorted(name for name in files if name != "dataset.yaml")]


def _combined_digest(files: dict[str, _RevisionFileModel]) -> str:
    digest = hashlib.sha256()
    for logical_name in _ordered_logical_names(files):
        digest.update(logical_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[logical_name].sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_revision(path: Path | str) -> tuple[Path, _RevisionRecordModel]:
    source = Path(path)
    record_path = source if source.name == _REVISION_RECORD else source / _REVISION_RECORD
    if not record_path.is_file():
        raise FileNotFoundError(f"Dataset revision.json 不存在: {record_path}")
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("revision.json 顶层必须是映射")
    payload = dict(raw)
    payload.setdefault("schema_version", DATASET_REVISION_SCHEMA_VERSION)
    payload = migrate_data_payload(
        "dataset_revision",
        payload,
        target_version=DATASET_REVISION_SCHEMA_VERSION,
    )
    return record_path.parent, _RevisionRecordModel.model_validate(payload)


def _copy_hash(
    source: Path,
    destination: Path,
    *,
    cancellation: CancellationCheck | None,
    on_chunk: Callable[[int], None] | None = None,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_stream, destination.open("wb") as output_stream:
        while True:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            chunk = input_stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            output_stream.write(chunk)
            digest.update(chunk)
            size += len(chunk)
            if on_chunk is not None:
                on_chunk(len(chunk))
    shutil.copystat(source, destination)
    return digest.hexdigest(), size


def _sha256(path: Path, *, cancellation: CancellationCheck | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            digest.update(chunk)
    return digest.hexdigest()


def _stage_file(source: Path, target: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.restore-",
        dir=target.parent,
    )
    os.close(descriptor)
    staged = Path(name)
    shutil.copy2(source, staged)
    return staged


def _backup_file(target: Path) -> Path | None:
    if not target.exists():
        return None
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.backup-",
        dir=target.parent,
    )
    os.close(descriptor)
    backup = Path(name)
    shutil.copy2(target, backup)
    return backup


def _restore_backups(backups: dict[Path, Path | None]) -> list[str]:
    errors: list[str] = []
    for target, backup in reversed(list(backups.items())):
        try:
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                os.replace(backup, target)
        except OSError as exc:
            errors.append(f"{target}: {exc}")
    return errors


def _emit_progress(
    callback: EventCallback | None,
    stage: str,
    completed: int,
    total: int,
    details: dict[str, Any],
) -> None:
    if callback is not None:
        callback(
            ProgressEvent(
                stage=stage,
                completed=completed,
                total=total,
                details=details,
            )
        )


__all__ = [
    "DATASET_REVISION_SCHEMA_VERSION",
    "DatasetRevisionInfo",
    "DatasetRevisionScanFailure",
    "DatasetRevisionCatalog",
    "create_dataset_revision",
    "inspect_dataset_revision",
    "scan_dataset_revisions",
    "restore_dataset_revision",
]
