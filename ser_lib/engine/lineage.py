"""训练运行的可追踪元数据。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TrainingMetadata:
    """一次训练运行的稳定、JSON-safe lineage 描述。

    该对象只保存调用方已经知道的信息；它不会自行读取 manifest、扫描数据集或
    计算 fingerprint，因此构造 Trainer 不会引入隐藏 I/O。
    """

    run_id: str
    created_at: datetime
    dataset_id: str | None
    dataset_fingerprint: str | None
    model_id: str
    config: dict[str, Any]
    seed: int
    device: str
    library_version: str

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id 不能为空")
        if not self.model_id.strip():
            raise ValueError("model_id 不能为空")
        if not self.device.strip():
            raise ValueError("device 不能为空")
        if not self.library_version.strip():
            raise ValueError("library_version 不能为空")
        if self.seed < 0:
            raise ValueError("seed 不能为负数")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at 必须包含时区")
        if self.dataset_id is not None and not self.dataset_id.strip():
            raise ValueError("dataset_id 不能是空字符串")
        if self.dataset_fingerprint is not None and not self.dataset_fingerprint.strip():
            raise ValueError("dataset_fingerprint 不能是空字符串")
        object.__setattr__(self, "config", dict(self.config))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "dataset_id": self.dataset_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "model_id": self.model_id,
            "config": dict(self.config),
            "seed": self.seed,
            "device": self.device,
            "library_version": self.library_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TrainingMetadata":
        created_at = value.get("created_at")
        if not isinstance(created_at, str):
            raise ValueError("TrainingMetadata.created_at 必须是 ISO 8601 字符串")
        parsed_created_at = datetime.fromisoformat(created_at)
        config = value.get("config")
        if not isinstance(config, Mapping):
            raise ValueError("TrainingMetadata.config 必须是映射")
        return cls(
            run_id=str(value.get("run_id") or ""),
            created_at=parsed_created_at,
            dataset_id=(
                str(value["dataset_id"])
                if value.get("dataset_id") is not None
                else None
            ),
            dataset_fingerprint=(
                str(value["dataset_fingerprint"])
                if value.get("dataset_fingerprint") is not None
                else None
            ),
            model_id=str(value.get("model_id") or ""),
            config=dict(config),
            seed=int(value.get("seed", -1)),
            device=str(value.get("device") or ""),
            library_version=str(value.get("library_version") or ""),
        )

    def with_run_id(self, run_id: str) -> "TrainingMetadata":
        return replace(self, run_id=run_id)


def build_training_metadata(
    *,
    run_id: str,
    model_id: str,
    config: Mapping[str, Any],
    seed: int,
    device: str,
    library_version: str,
    dataset_id: str | None = None,
    dataset_fingerprint: str | None = None,
    created_at: datetime | None = None,
) -> TrainingMetadata:
    """构造训练 lineage；不执行任何文件系统或数据集探测。"""
    return TrainingMetadata(
        run_id=run_id,
        created_at=created_at or datetime.now(timezone.utc),
        dataset_id=dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        model_id=model_id,
        config=dict(config),
        seed=seed,
        device=device,
        library_version=library_version,
    )


def artifact_provenance_from_training_run(
    source_run: TrainingMetadata,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """把训练 lineage 转成 artifact 可接收的通用 metadata。

    artifacts 层只接收 JSON-safe provenance 映射，不反向依赖 engine 类型；调用方
    若已显式提供同名 metadata，则保持调用方值优先。
    """
    resolved = dict(metadata or {})
    resolved.setdefault("source_run_id", source_run.run_id)
    if source_run.dataset_id is not None:
        resolved.setdefault("dataset_id", source_run.dataset_id)
    if source_run.dataset_fingerprint is not None:
        resolved.setdefault("dataset_fingerprint", source_run.dataset_fingerprint)
    return resolved


__all__ = [
    "TrainingMetadata",
    "build_training_metadata",
    "artifact_provenance_from_training_run",
]
