"""评估运行的稳定 lineage、终态记录与原子持久化。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Mapping
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ser_lib._version import __version__
from ser_lib.engine.evaluator import EvaluationResult
from ser_lib.engine.migrations import migrate_engine_payload

EVALUATION_RUN_SCHEMA_VERSION = 1
_EVALUATION_RECORD_NAME = "evaluation.json"
_AGGREGATE_METRICS = (
    "loss",
    "accuracy",
    "war",
    "uar",
    "macro_f1",
    "weighted_precision",
    "weighted_recall",
    "weighted_f1",
    "balanced_accuracy",
    "matthews_correlation_coefficient",
    "cohen_kappa",
)


class _EvaluationRunRecordModel(BaseModel):
    """``evaluation.json`` 的严格磁盘 schema。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schema_version: int = Field(default=EVALUATION_RUN_SCHEMA_VERSION, ge=1, le=1)
    evaluation_id: str = Field(min_length=1)
    directory: str = Field(min_length=1)
    created_at: datetime
    started_at: datetime
    finished_at: datetime
    duration_seconds: float = Field(ge=0.0)
    source_artifact: str = Field(min_length=1)
    source_run_id: str | None = None
    dataset_id: str = Field(min_length=1)
    dataset_fingerprint: str | None = None
    model_name: str = Field(min_length=1)
    split: str = Field(min_length=1)
    device: str = Field(min_length=1)
    library_version: str = Field(min_length=1)
    sample_count: int = Field(ge=1)
    metrics: dict[str, float]
    metrics_file: str = "metrics.json"
    predictions_file: str | None = "predictions.jsonl"

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("evaluation record 时间字段必须包含时区")
        return value

    @field_validator("source_run_id", "dataset_fingerprint")
    @classmethod
    def _optional_nonempty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("可选 lineage 字段不能是空字符串")
        return value

    @field_validator("metrics_file", "predictions_file")
    @classmethod
    def _safe_report_file(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = PurePath(value)
        if path.is_absolute() or len(path.parts) != 1 or value in {"", ".", ".."}:
            raise ValueError("评估报告文件必须是 evaluation 目录内的普通文件名")
        return value

    @model_validator(mode="after")
    def _validate_timeline_and_metrics(self) -> "_EvaluationRunRecordModel":
        if self.started_at < self.created_at:
            raise ValueError("started_at 不能早于 created_at")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at 不能早于 started_at")
        expected = set(_AGGREGATE_METRICS)
        if set(self.metrics) != expected:
            raise ValueError(
                "metrics 必须完整包含标准聚合指标: "
                + ", ".join(sorted(expected))
            )
        return self


@dataclass(frozen=True, slots=True)
class EvaluationRunMetadata:
    """评估开始前即可创建并用于事件上下文的稳定 lineage。"""

    evaluation_id: str
    created_at: datetime
    source_artifact: str
    source_run_id: str | None
    dataset_id: str
    dataset_fingerprint: str | None
    model_name: str
    split: str
    device: str
    library_version: str

    def __post_init__(self) -> None:
        for name in (
            "evaluation_id",
            "source_artifact",
            "dataset_id",
            "model_name",
            "split",
            "device",
            "library_version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} 不能为空")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at 必须包含时区")
        if self.source_run_id is not None and not self.source_run_id.strip():
            raise ValueError("source_run_id 不能是空字符串")
        if self.dataset_fingerprint is not None and not self.dataset_fingerprint.strip():
            raise ValueError("dataset_fingerprint 不能是空字符串")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "created_at": self.created_at.isoformat(),
            "source_artifact": self.source_artifact,
            "source_run_id": self.source_run_id,
            "dataset_id": self.dataset_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "model_name": self.model_name,
            "split": self.split,
            "device": self.device,
            "library_version": self.library_version,
        }


@dataclass(frozen=True, slots=True)
class EvaluationRunInfo:
    """历史列表/详情可直接消费的评估终态记录。"""

    evaluation_id: str
    directory: str
    created_at: datetime
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    source_artifact: str
    source_run_id: str | None
    dataset_id: str
    dataset_fingerprint: str | None
    model_name: str
    split: str
    device: str
    library_version: str
    sample_count: int
    metrics: dict[str, float]
    metrics_file: str
    predictions_file: str | None

    def to_dict(self) -> dict[str, Any]:
        return _EvaluationRunRecordModel(
            schema_version=EVALUATION_RUN_SCHEMA_VERSION,
            **asdict(self),
        ).model_dump(mode="json")

    @classmethod
    def from_evaluation(
        cls,
        directory: Path | str,
        metadata: EvaluationRunMetadata,
        result: EvaluationResult,
        *,
        started_at: datetime,
        finished_at: datetime,
        predictions_file: str | None = "predictions.jsonl",
    ) -> "EvaluationRunInfo":
        metrics = {
            name: float(getattr(result, name))
            for name in _AGGREGATE_METRICS
        }
        return cls(
            evaluation_id=metadata.evaluation_id,
            directory=Path(directory).as_posix(),
            created_at=metadata.created_at,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=max((finished_at - started_at).total_seconds(), 0.0),
            source_artifact=metadata.source_artifact,
            source_run_id=metadata.source_run_id,
            dataset_id=metadata.dataset_id,
            dataset_fingerprint=metadata.dataset_fingerprint,
            model_name=metadata.model_name,
            split=metadata.split,
            device=metadata.device,
            library_version=metadata.library_version,
            sample_count=result.sample_count,
            metrics=metrics,
            metrics_file="metrics.json",
            predictions_file=predictions_file,
        )

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        directory: Path | str | None = None,
    ) -> "EvaluationRunInfo":
        payload = dict(value)
        payload.setdefault("schema_version", EVALUATION_RUN_SCHEMA_VERSION)
        payload = migrate_engine_payload(
            "evaluation_run",
            payload,
            target_version=EVALUATION_RUN_SCHEMA_VERSION,
        )
        if directory is not None:
            payload["directory"] = Path(directory).as_posix()
        record = _EvaluationRunRecordModel.model_validate(payload)
        fields = record.model_dump()
        fields.pop("schema_version", None)
        return cls(**fields)


def build_evaluation_run_metadata(
    *,
    source_artifact: Path | str,
    dataset_id: str,
    model_name: str,
    split: str,
    device: str,
    library_version: str | None = None,
    source_run_id: str | None = None,
    dataset_fingerprint: str | None = None,
    evaluation_id: str | None = None,
    created_at: datetime | None = None,
) -> EvaluationRunMetadata:
    """构造评估 lineage；默认使用当前库版本，不执行隐藏 I/O。"""
    return EvaluationRunMetadata(
        evaluation_id=evaluation_id or f"eval_{uuid4().hex}",
        created_at=created_at or datetime.now(timezone.utc),
        source_artifact=Path(source_artifact).as_posix(),
        source_run_id=source_run_id,
        dataset_id=dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        model_name=model_name,
        split=split,
        device=device,
        library_version=__version__ if library_version is None else library_version,
    )


def write_evaluation_run_info(
    directory: Path | str,
    metadata: EvaluationRunMetadata,
    result: EvaluationResult,
    *,
    started_at: datetime,
    finished_at: datetime,
    predictions_file: str | None = "predictions.jsonl",
) -> Path:
    """把终态评估记录原子写入 ``evaluation.json``。"""
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    info = EvaluationRunInfo.from_evaluation(
        target_dir,
        metadata,
        result,
        started_at=started_at,
        finished_at=finished_at,
        predictions_file=predictions_file,
    )
    target = target_dir / _EVALUATION_RECORD_NAME
    temporary = target_dir / f".{_EVALUATION_RECORD_NAME}.tmp"
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


def load_evaluation_run_info(path: Path | str) -> EvaluationRunInfo:
    """读取 evaluation 目录或 ``evaluation.json``；目录以实际位置为准。"""
    source = Path(path)
    record_path = source / _EVALUATION_RECORD_NAME if source.is_dir() else source
    if not record_path.is_file():
        raise FileNotFoundError(f"评估运行记录不存在: {record_path}")
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evaluation.json 顶层必须是映射")
    return EvaluationRunInfo.from_dict(raw, directory=record_path.parent)


__all__ = [
    "EVALUATION_RUN_SCHEMA_VERSION",
    "EvaluationRunMetadata",
    "EvaluationRunInfo",
    "build_evaluation_run_metadata",
    "write_evaluation_run_info",
    "load_evaluation_run_info",
]
