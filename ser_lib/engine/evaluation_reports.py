"""已落盘评估报告的轻量检查与预测分页查询接口。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    """无需读取预测明细即可展示的评估报告信息。"""

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": self.directory,
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
class EvaluationPredictionPage:
    """对 ``predictions.jsonl`` 的一次有界内存分页查询结果。"""

    source_file: str
    offset: int
    limit: int
    matched_count: int
    records: tuple[PredictionRecord, ...]
    has_more: bool
    next_offset: int | None

    @property
    def returned_count(self) -> int:
        return len(self.records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "offset": self.offset,
            "limit": self.limit,
            "matched_count": self.matched_count,
            "returned_count": self.returned_count,
            "has_more": self.has_more,
            "next_offset": self.next_offset,
            "records": [record.to_dict() for record in self.records],
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
    )


def query_evaluation_predictions(
    directory: Path | str,
    *,
    offset: int = 0,
    limit: int = 100,
    incorrect_only: bool = False,
    target: int | None = None,
    predicted: int | None = None,
    cancellation: CancellationCheck | None = None,
) -> EvaluationPredictionPage:
    """顺序扫描预测 JSONL，并按过滤后的结果执行 offset/limit 分页。

    整个文件只扫描一次，内存中最多保留 ``limit`` 条记录。``matched_count`` 是
    满足过滤条件的总记录数，因此调用方无需再次扫描即可渲染分页信息。
    """
    if offset < 0:
        raise ValueError("offset 必须 >= 0")
    if limit < 1 or limit > 1000:
        raise ValueError("limit 必须位于 [1, 1000]")
    if target is not None and target < 0:
        raise ValueError("target 必须 >= 0")
    if predicted is not None and predicted < 0:
        raise ValueError("predicted 必须 >= 0")

    predictions_path = Path(directory) / "predictions.jsonl"
    if not predictions_path.is_file():
        raise FileNotFoundError(f"评估 predictions.jsonl 不存在: {predictions_path}")

    records: list[PredictionRecord] = []
    matched_count = 0
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

            if matched_count >= offset and len(records) < limit:
                records.append(
                    PredictionRecord(
                        uid=item.uid,
                        target=item.target,
                        predicted=item.predicted,
                        confidence=item.confidence,
                        probabilities=tuple(item.probabilities),
                    )
                )
            matched_count += 1

    has_more = matched_count > offset + len(records)
    return EvaluationPredictionPage(
        source_file=predictions_path.as_posix(),
        offset=offset,
        limit=limit,
        matched_count=matched_count,
        records=tuple(records),
        has_more=has_more,
        next_offset=offset + len(records) if has_more else None,
    )


__all__ = [
    "EvaluationReportInfo",
    "EvaluationPredictionPage",
    "inspect_evaluation_report",
    "query_evaluation_predictions",
]