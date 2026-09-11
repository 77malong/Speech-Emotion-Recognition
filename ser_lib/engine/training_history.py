"""已完成训练的 history.json 严格读取与曲线 DTO。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ser_lib.engine.training import EpochResult

_HISTORY_FILE_NAME = "history.json"


class _EpochResultModel(BaseModel):
    """CLI 已有 ``history.json`` 单个 epoch 的严格 schema。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    epoch: int = Field(ge=1)
    loss: float
    accuracy: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=1)
    optimizer_steps: int = Field(default=0, ge=0)
    validation: dict[str, float] | None = None

    @field_validator("validation")
    @classmethod
    def _validate_validation_metrics(
        cls,
        value: dict[str, float] | None,
    ) -> dict[str, float] | None:
        if value is None:
            return None
        if any(not name.strip() for name in value):
            raise ValueError("validation 指标名不能为空")
        if any(not math.isfinite(metric) for metric in value.values()):
            raise ValueError("validation 指标必须是有限数值")
        return value


@dataclass(frozen=True, slots=True)
class TrainingHistoryInfo:
    """Web 训练曲线页可直接消费的完整 epoch 历史。"""

    directory: str
    history_file: str
    epochs: tuple[EpochResult, ...]

    @property
    def epoch_count(self) -> int:
        return len(self.epochs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": self.directory,
            "history_file": self.history_file,
            "epoch_count": self.epoch_count,
            "epochs": [epoch.to_dict() for epoch in self.epochs],
        }


def load_training_history(path: Path | str) -> TrainingHistoryInfo:
    """读取 run 目录或其 ``history.json``；不读取 checkpoint / metrics.jsonl。"""
    source = Path(path)
    history_path = source / _HISTORY_FILE_NAME if source.is_dir() else source
    if not history_path.is_file():
        raise FileNotFoundError(f"训练 history.json 不存在: {history_path}")
    raw = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("history.json 顶层必须是列表")
    parsed = [_EpochResultModel.model_validate(item) for item in raw]
    epochs = [item.epoch for item in parsed]
    if epochs != sorted(epochs) or len(epochs) != len(set(epochs)):
        raise ValueError("history.json epoch 必须严格递增且不能重复")
    return TrainingHistoryInfo(
        directory=history_path.parent.as_posix(),
        history_file=history_path.as_posix(),
        epochs=tuple(
            EpochResult(
                epoch=item.epoch,
                loss=item.loss,
                accuracy=item.accuracy,
                sample_count=item.sample_count,
                optimizer_steps=item.optimizer_steps,
                validation=dict(item.validation) if item.validation is not None else None,
            )
            for item in parsed
        ),
    )


__all__ = ["TrainingHistoryInfo", "load_training_history"]
