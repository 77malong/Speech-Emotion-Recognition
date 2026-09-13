"""已落盘评估报告的轻量检查与预测流式读取接口。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ser_lib.engine.evaluation_records import EvaluationRecord
from ser_lib.engine.evaluator import ClassMetrics, PredictionRecord
from ser_lib.foundation.events import CancellationCheck


class _ClassMetricsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_id: int = Field(ge=0)
    label_name: str = Field(min_length=1)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    support: int = Field(ge=0)


class _EvaluationMetricsModel(BaseModel):
    """``metrics.json`` 的严格 schema。"""

    model_config = ConfigDict(extra="forbid")

    metric_unit: Literal["sample", "window"] = "sample"
    loss: float
    accuracy: float = Field(ge=0.0, le=1.0)
    war: float = Field(ge=0.0, le=1.0)
    uar: float = Field(ge=0.0, le=1.0)
    macro_f1: float = Field(ge=0.0, le=1.0)
    weighted_precision: float = Field(ge=0.0, le=1.0)
    weighted_recall: float = Field(ge=0.0, le=1.0)
    weighted_f1: float = Field(ge=0.0, le=1.0)
    balanced_accuracy: float = Field(ge=0.0, le=1.0)
    matthews_correlation_coefficient: float = Field(ge=-1.0, le=1.0)
    cohen_kappa: float = Field(ge=-1.0, le=1.0)
    sample_count: int = Field(ge=1)
    confusion_matrix: list[list[int]]
    per_class: list[_ClassMetricsModel]

    @model_validator(mode="after")
    def _validate_dimensions(self) -> "_EvaluationMetricsModel":
        classes = len(self.per_class)
        if classes < 2:
            raise ValueError("评估报告至少需要两个类别")
        if len(self.confusion_matrix) != classes or any(
            len(row) != classes for row in self.confusion_matrix
        ):
            raise ValueError("confusion_matrix 维度必须与 per_class 类别数一致")
        if any(value < 0 for row in self.confusion_matrix for value in row):
            raise ValueError("confusion_matrix 不能包含负数")
        if sum(sum(row) for row in self.confusion_matrix) != self.sample_count:
            raise ValueError("confusion_matrix 样本总数与 sample_count 不一致")
        return self


class _PredictionRecordModel(BaseModel):
    """``predictions.jsonl`` 单行的严格 schema。"""

    model_config = ConfigDict(extra="forbid")

    uid: str = Field(min_length=1)
    target: int = Field(ge=0)
    predicted: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    probabilities: list[float] = Field(min_length=2)

    @model_validator(mode="after")
    def _validate_probabilities(self) -> "_PredictionRecordModel":
        if any(value < 0.0 or value > 1.0 for value in self.probabilities):
            raise ValueError("probabilities 必须位于 [0, 1]")
        classes = len(self.probabilities)
        if self.target >= classes or self.predicted >= classes:
            raise ValueError("target/predicted 必须落在 probabilities 类别范围内")
        return self


@dataclass(frozen=True, slots=True)
class EvaluationReportInfo:
    """无需读取预测明细即可使用的评估报告信息。"""

    directory: str
    loss: float
    accuracy: float
    war: float
    uar: float
    macro_f1: float
    weighted_precision: float
    weighted_recall: float
    weighted_f1: float
    balanced_accuracy: float
    matthews_correlation_coefficient: float
    cohen_kappa: float
    sample_count: int
    confusion_matrix: tuple[tuple[int, ...], ...]
    per_class: tuple[ClassMetrics, ...]
    predictions_file: str | None
    predictions_bytes: int | None
    metric_unit: Literal["sample", "window"] = "sample"

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": self.directory,
            "metric_unit": self.metric_unit,
            "loss": self.loss,
            "accuracy": self.accuracy,
            "war": self.war,
            "uar": self.uar,
            "macro_f1": self.macro_f1,
            "weighted_precision": self.weighted_precision,
            "weighted_recall": self.weighted_recall,
            "weighted_f1": self.weighted_f1,
            "balanced_accuracy": self.balanced_accuracy,
            "matthews_correlation_coefficient": self.matthews_correlation_coefficient,
            "cohen_kappa": self.cohen_kappa,
            "sample_count": self.sample_count,
            "confusion_matrix": [list(row) for row in self.confusion_matrix],
            "per_class": [metric.to_dict() for metric in self.per_class],
            "predictions_file": self.predictions_file,
            "predictions_bytes": self.predictions_bytes,
        }


@dataclass(frozen=True, slots=True)
class EvaluationPredictionFileInfo:
    """由 evaluation metadata 与文件 stat 得到的 prediction 文件信息。"""

    path: str | None
    exists: bool
    size_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
        }


def inspect_evaluation_report(directory: Path | str) -> EvaluationReportInfo:
    """读取并严格校验 ``metrics.json``，但不读取 ``predictions.jsonl`` 内容。"""
    target = Path(directory)
    metrics_path = target / "metrics.json"
    if not target.is_dir():
        raise NotADirectoryError(f"评估报告目录不存在或不是目录: {target}")
    if not metrics_path.is_file():
        raise FileNotFoundError(f"评估 metrics.json 不存在: {metrics_path}")
    raw = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("metrics.json 顶层必须是映射")
    metrics = _EvaluationMetricsModel.model_validate(raw)
    predictions_path = target / "predictions.jsonl"
    predictions_file = predictions_path.as_posix() if predictions_path.is_file() else None
    predictions_bytes = predictions_path.stat().st_size if predictions_file is not None else None
    return EvaluationReportInfo(
        directory=target.as_posix(),
        loss=metrics.loss,
        accuracy=metrics.accuracy,
        war=metrics.war,
        uar=metrics.uar,
        macro_f1=metrics.macro_f1,
        weighted_precision=metrics.weighted_precision,
        weighted_recall=metrics.weighted_recall,
        weighted_f1=metrics.weighted_f1,
        balanced_accuracy=metrics.balanced_accuracy,
        matthews_correlation_coefficient=metrics.matthews_correlation_coefficient,
        cohen_kappa=metrics.cohen_kappa,
        sample_count=metrics.sample_count,
        confusion_matrix=tuple(tuple(row) for row in metrics.confusion_matrix),
        per_class=tuple(
            ClassMetrics(
                label_id=item.label_id,
                label_name=item.label_name,
                precision=item.precision,
                recall=item.recall,
                f1=item.f1,
                support=item.support,
            )
            for item in metrics.per_class
        ),
        predictions_file=predictions_file,
        predictions_bytes=predictions_bytes,
        metric_unit=metrics.metric_unit,
    )


def inspect_evaluation_prediction_file(
    run: EvaluationRecord,
) -> EvaluationPredictionFileInfo:
    """按 ``evaluation.json`` 声明的文件名做 stat，不打开 prediction 内容。"""
    if run.predictions_file is None:
        return EvaluationPredictionFileInfo(path=None, exists=False, size_bytes=None)

    path = Path(run.directory) / run.predictions_file
    if not path.is_file():
        return EvaluationPredictionFileInfo(
            path=path.as_posix(),
            exists=False,
            size_bytes=None,
        )
    return EvaluationPredictionFileInfo(
        path=path.as_posix(),
        exists=True,
        size_bytes=path.stat().st_size,
    )


def iter_evaluation_predictions(
    directory: Path | str,
    *,
    incorrect_only: bool = False,
    target: int | None = None,
    predicted: int | None = None,
    cancellation: CancellationCheck | None = None,
) -> Iterator[PredictionRecord]:
    """惰性校验并产出 ``predictions.jsonl`` 中满足条件的记录。

    每次只解析当前行；函数不扫描总匹配数，也不提供分页元数据。调用方可使用
    ``itertools.islice`` 等 iterator 工具进行有界切片。
    """
    if target is not None and target < 0:
        raise ValueError("target 必须 >= 0")
    if predicted is not None and predicted < 0:
        raise ValueError("predicted 必须 >= 0")

    predictions_path = Path(directory) / "predictions.jsonl"
    if not predictions_path.is_file():
        raise FileNotFoundError(f"评估 predictions.jsonl 不存在: {predictions_path}")

    def _records() -> Iterator[PredictionRecord]:
        with predictions_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if cancellation is not None:
                    cancellation.raise_if_cancelled()
                if not line.strip():
                    raise ValueError(f"predictions.jsonl 第 {line_number} 行为空")
                try:
                    raw = json.loads(line)
                    item = _PredictionRecordModel.model_validate(raw)
                except (json.JSONDecodeError, ValidationError) as exc:
                    raise ValueError(
                        f"predictions.jsonl 第 {line_number} 行无效: {exc}"
                    ) from exc

                if incorrect_only and item.target == item.predicted:
                    continue
                if target is not None and item.target != target:
                    continue
                if predicted is not None and item.predicted != predicted:
                    continue

                yield PredictionRecord(
                    uid=item.uid,
                    target=item.target,
                    predicted=item.predicted,
                    confidence=item.confidence,
                    probabilities=tuple(item.probabilities),
                )

    return _records()


__all__ = [
    "EvaluationReportInfo",
    "EvaluationPredictionFileInfo",
    "inspect_evaluation_report",
    "inspect_evaluation_prediction_file",
    "iter_evaluation_predictions",
]
