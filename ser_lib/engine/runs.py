"""训练运行记录的原子持久化、轻量 Catalog 扫描与详情聚合 DTO。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ser_lib.core._catalog_scan import scan_catalog_candidates
from ser_lib.core.diagnostics import Diagnostic
from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.core.migrations import migrate_schema_payload
from ser_lib.engine.checkpoint_catalog import CheckpointCatalog
from ser_lib.engine.lineage import TrainingRunMetadata
from ser_lib.engine.training_history import TrainingHistoryInfo
from ser_lib.engine.trainer import TrainingResult, TrainingStatus

RUN_RECORD_SCHEMA_VERSION = 1
_RUN_RECORD_NAME = "run.json"


class _RunRecordModel(BaseModel):
    """run.json 的严格磁盘 schema；额外字段会被拒绝。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=RUN_RECORD_SCHEMA_VERSION, ge=1, le=1)
    run_id: str = Field(min_length=1)
    directory: str = Field(min_length=1)
    status: TrainingStatus
    created_at: datetime
    started_at: datetime
    finished_at: datetime
    duration_seconds: float = Field(ge=0)
    dataset_id: str | None = None
    dataset_fingerprint: str | None = None
    model_id: str = Field(min_length=1)
    seed: int = Field(ge=0)
    device: str = Field(min_length=1)
    library_version: str = Field(min_length=1)
    config: dict[str, Any]
    epochs_completed: int = Field(ge=0)
    last_epoch: int | None = Field(default=None, ge=0)
    best_epoch: int | None = Field(default=None, ge=0)
    best_metric: float | None = None
    monitored_metric: str = Field(min_length=1)
    last_checkpoint: str | None = None
    best_checkpoint: str | None = None
    stop_reason: str | None = None

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("run record 时间字段必须包含时区")
        return value


@dataclass(frozen=True, slots=True)
class TrainingRunInfo:
    """Web 历史列表/详情共用的轻量、JSON-safe 训练记录。"""

    run_id: str
    directory: str
    status: TrainingStatus
    created_at: datetime
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    dataset_id: str | None
    dataset_fingerprint: str | None
    model_id: str
    seed: int
    device: str
    library_version: str
    config: dict[str, Any]
    epochs_completed: int
    last_epoch: int | None
    best_epoch: int | None
    best_metric: float | None
    monitored_metric: str
    last_checkpoint: str | None
    best_checkpoint: str | None
    stop_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return _RunRecordModel(
            schema_version=RUN_RECORD_SCHEMA_VERSION,
            **asdict(self),
        ).model_dump(mode="json")

    @classmethod
    def from_training(
        cls,
        directory: Path | str,
        metadata: TrainingRunMetadata,
        result: TrainingResult,
    ) -> "TrainingRunInfo":
        if metadata.run_id != result.run_id:
            raise ValueError("TrainingRunMetadata.run_id 与 TrainingResult.run_id 不一致")
        return cls(
            run_id=result.run_id,
            directory=Path(directory).as_posix(),
            status=result.status,
            created_at=metadata.created_at,
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_seconds=result.duration_seconds,
            dataset_id=metadata.dataset_id,
            dataset_fingerprint=metadata.dataset_fingerprint,
            model_id=metadata.model_id,
            seed=metadata.seed,
            device=metadata.device,
            library_version=metadata.library_version,
            config=dict(metadata.config),
            epochs_completed=len(result.epochs),
            last_epoch=result.epochs[-1].epoch if result.epochs else None,
            best_epoch=result.best_epoch,
            best_metric=result.best_metric,
            monitored_metric=result.monitored_metric,
            last_checkpoint=(
                str(result.last_checkpoint) if result.last_checkpoint is not None else None
            ),
            best_checkpoint=(
                str(result.best_checkpoint) if result.best_checkpoint is not None else None
            ),
            stop_reason=result.stop_reason,
        )

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        directory: Path | str | None = None,
    ) -> "TrainingRunInfo":
        payload = dict(value)
        payload.setdefault("schema_version", RUN_RECORD_SCHEMA_VERSION)
        version = payload.get("schema_version")
        if (
            isinstance(version, int)
            and not isinstance(version, bool)
            and version <= RUN_RECORD_SCHEMA_VERSION
        ):
            payload = migrate_schema_payload(
                "training_run",
                payload,
                target_version=RUN_RECORD_SCHEMA_VERSION,
            )
        if directory is not None:
            payload["directory"] = Path(directory).as_posix()
        record = _RunRecordModel.model_validate(payload)
        fields = record.model_dump()
        fields.pop("schema_version", None)
        return cls(**fields)


@dataclass(frozen=True, slots=True)
class TrainingRunDetail:
    """训练详情页/Worker 可直接消费的轻量聚合结果。

    该 DTO 只组合 ``run.json``、``history.json`` 与 checkpoint 文件 stat，
    不包含模型/optimizer payload，也不会要求调用方反序列化 checkpoint。
    """

    run: TrainingRunInfo
    history: TrainingHistoryInfo | None
    checkpoints: CheckpointCatalog
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "history": self.history.to_dict() if self.history is not None else None,
            "checkpoints": self.checkpoints.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class TrainingRunScanFailure:
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
class TrainingRunCatalog:
    root: str
    runs: tuple[TrainingRunInfo, ...]
    failures: tuple[TrainingRunScanFailure, ...]

    @property
    def total(self) -> int:
        return len(self.runs) + len(self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total": self.total,
            "runs": [run.to_dict() for run in self.runs],
            "failures": [failure.to_dict() for failure in self.failures],
        }


def write_training_run_info(
    directory: Path | str,
    metadata: TrainingRunMetadata,
    result: TrainingResult,
) -> Path:
    """把终态训练记录原子写入 ``run.json``。"""
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    info = TrainingRunInfo.from_training(target_dir, metadata, result)
    target = target_dir / _RUN_RECORD_NAME
    temporary = target_dir / f".{_RUN_RECORD_NAME}.tmp"
    try:
        temporary.write_text(
            json.dumps(info.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def load_training_run_info(path: Path | str) -> TrainingRunInfo:
    """读取一个 run 目录或其 ``run.json``。目录字段始终以实际位置为准。"""
    source = Path(path)
    record_path = source / _RUN_RECORD_NAME if source.is_dir() else source
    if not record_path.is_file():
        raise FileNotFoundError(f"训练运行记录不存在: {record_path}")
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("run.json 顶层必须是映射")
    return TrainingRunInfo.from_dict(raw, directory=record_path.parent)


def scan_training_runs(
    root: Path | str,
    *,
    recursive: bool = False,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> TrainingRunCatalog:
    """轻量扫描 ``run.json``；不读取 checkpoint、不加载模型、不计算 hash。"""
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"训练运行根目录不存在或不是目录: {root_path}")
    candidates = _candidate_directories(root_path, recursive=recursive)
    runs, failures = scan_catalog_candidates(
        candidates,
        inspect_candidate=load_training_run_info,
        failure_factory=lambda directory, exc: TrainingRunScanFailure(
            directory=directory.as_posix(),
            error_type=type(exc).__name__,
            message=str(exc),
        ),
        stage="training_run_catalog_scan",
        candidate_detail_key="directory",
        fail_fast=fail_fast,
        event_callback=event_callback,
        cancellation=cancellation,
    )
    runs.sort(key=lambda item: (item.created_at, item.run_id), reverse=True)
    return TrainingRunCatalog(
        root=root_path.as_posix(),
        runs=tuple(runs),
        failures=tuple(failures),
    )


def _candidate_directories(root: Path, *, recursive: bool) -> list[Path]:
    candidates: set[Path] = set()
    if (root / _RUN_RECORD_NAME).is_file():
        candidates.add(root)
    if recursive:
        candidates.update(path.parent for path in root.rglob(_RUN_RECORD_NAME))
    else:
        candidates.update(
            child
            for child in root.iterdir()
            if child.is_dir() and (child / _RUN_RECORD_NAME).is_file()
        )
    return sorted(candidates, key=lambda path: path.as_posix().casefold())


__all__ = [
    "RUN_RECORD_SCHEMA_VERSION",
    "TrainingRunInfo",
    "TrainingRunDetail",
    "TrainingRunScanFailure",
    "TrainingRunCatalog",
    "write_training_run_info",
    "load_training_run_info",
    "scan_training_runs",
]
