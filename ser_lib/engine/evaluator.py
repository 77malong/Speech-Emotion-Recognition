"""SER 分类模型评估、样本预测和机器可读报告。"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping, Sized
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

import torch
import torch.nn.functional as F

from ser_lib.data.types import SERBatch, move_batch_to_device
from ser_lib.foundation.events import (
    CancellationCheck,
    EventCallback,
    EventContext,
    LifecycleEvent,
    ProgressEvent,
)
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.models.base import SERModel


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    label_id: int
    label_name: str
    precision: float
    recall: float
    f1: float
    support: int

    def to_dict(self) -> dict[str, object]:
        """返回稳定、可直接 JSON 序列化的类别指标。"""
        return {
            "label_id": self.label_id,
            "label_name": self.label_name,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "support": self.support,
        }


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    uid: str
    target: int
    predicted: int
    confidence: float
    probabilities: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        """返回单样本预测的 JSON-safe 表示。"""
        return {
            "uid": self.uid,
            "target": self.target,
            "predicted": self.predicted,
            "confidence": self.confidence,
            "probabilities": list(self.probabilities),
        }


class PredictionSink(Protocol):
    """评估逐样本结果的增量消费者协议。"""

    def write(self, record: PredictionRecord) -> None:
        """消费一条已经完成 softmax/argmax 的预测记录。"""
        ...


class JsonlPredictionSink:
    """把评估预测增量写入 JSONL，避免完整预测常驻内存。

    Sink 生命周期由调用方管理；推荐使用 ``with``。评估器只调用 ``write()``，
    不会擅自关闭外部资源。
    """

    def __init__(
        self,
        path: Path | str,
        *,
        append: bool = False,
        flush_each: bool = False,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush_each = flush_each
        mode = "a" if append else "w"
        self._stream = self.path.open(mode, encoding="utf-8", newline="\n")

    def write(self, record: PredictionRecord) -> None:
        if self._stream.closed:
            raise ValueError("JsonlPredictionSink 已关闭")
        self._stream.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        if self._flush_each:
            self._stream.flush()

    def flush(self) -> None:
        if not self._stream.closed:
            self._stream.flush()

    def close(self) -> None:
        if not self._stream.closed:
            self._stream.close()

    def __enter__(self) -> "JsonlPredictionSink":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    accuracy: float
    macro_f1: float
    uar: float
    confusion_matrix: torch.Tensor
    sample_count: int
    loss: float
    war: float
    per_class: tuple[ClassMetrics, ...]
    predictions: tuple[PredictionRecord, ...]
    weighted_precision: float
    weighted_recall: float
    weighted_f1: float
    balanced_accuracy: float
    matthews_correlation_coefficient: float
    cohen_kappa: float

    def to_dict(self, *, include_predictions: bool = True) -> dict[str, object]:
        """返回公开 Result 的统一 JSON-safe 表示。

        ``include_predictions=False`` 适合指标摘要和 ``metrics.json``；默认保留
        完整预测，方便 Web Backend 直接消费结果而无需了解内部 dataclass/Tensor。
        """
        payload: dict[str, object] = {
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
            "confusion_matrix": self.confusion_matrix.tolist(),
            "per_class": [item.to_dict() for item in self.per_class],
        }
        if include_predictions:
            payload["predictions"] = [item.to_dict() for item in self.predictions]
        return payload

    def summary_dict(self) -> dict[str, object]:
        """兼容旧 API：返回不含样本明细的 JSON-safe 聚合报告。"""
        return self.to_dict(include_predictions=False)


def _safe_len(value: object) -> int | None:
    if not isinstance(value, Sized):
        return None
    try:
        return len(value)
    except TypeError:
        return None


def _validate_labels(labels: Mapping[int, str] | None, num_classes: int) -> dict[int, str]:
    if labels is None:
        return {index: str(index) for index in range(num_classes)}
    normalized = dict(labels)
    expected = set(range(num_classes))
    if set(normalized) != expected:
        raise ValueError(
            f"labels 必须覆盖 0..{num_classes - 1}，实际: {sorted(normalized)}"
        )
    if any(not isinstance(name, str) or not name for name in normalized.values()):
        raise ValueError("labels 名称必须是非空字符串")
    return normalized


def _loss_reduction_denominator(
    loss_fn: torch.nn.Module | None,
    targets: torch.Tensor,
) -> float:
    """返回可跨 batch 组合 scalar loss 的归约分母。

    自定义 loss 默认按当前 batch 的 sample mean 解释；如果 loss 对象公开
    ``reduction_denominator(targets)``，则使用该值。内置 ClassificationLoss
    通过该协议为 weighted cross entropy 返回目标类别权重质量。
    """
    denominator_fn = getattr(loss_fn, "reduction_denominator", None)
    if callable(denominator_fn):
        denominator = float(denominator_fn(targets))
    else:
        denominator = float(targets.numel())
    if denominator <= 0:
        raise ValueError("loss reduction denominator 必须大于 0")
    return denominator


def _resolve_event_context(
    context: EventContext | None,
    *,
    split: str | None,
    total_batches: int | None,
) -> EventContext:
    base = context or EventContext()
    if split is not None and not split:
        raise ValueError("split 不能为空字符串")
    if split is not None and base.split is not None and split != base.split:
        raise ValueError("split 与 event_context.split 不一致")
    if (
        total_batches is not None
        and base.total_batches is not None
        and total_batches != base.total_batches
    ):
        raise ValueError("可迭代对象长度与 event_context.total_batches 不一致")
    return replace(
        base,
        split=split or base.split or "eval",
        total_batches=total_batches if total_batches is not None else base.total_batches,
    )


def _result_event_details(result: EvaluationResult) -> dict[str, object]:
    """生命周期完成事件只携带紧凑聚合值，避免把预测明细塞进事件流。"""
    return {
        "loss": result.loss,
        "accuracy": result.accuracy,
        "war": result.war,
        "uar": result.uar,
        "macro_f1": result.macro_f1,
        "weighted_f1": result.weighted_f1,
        "balanced_accuracy": result.balanced_accuracy,
        "sample_count": result.sample_count,
    }


@torch.inference_mode()
def evaluate(
    model: SERModel,
    batches: Iterable[SERBatch],
    *,
    num_classes: int,
    device: str | torch.device = "cpu",
    labels: Mapping[int, str] | None = None,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
    loss_fn: torch.nn.Module | None = None,
    event_context: EventContext | None = None,
    split: str | None = None,
    prediction_sink: PredictionSink | None = None,
    retain_predictions: bool = True,
) -> EvaluationResult:
    """评估分类模型，并可增量输出每个样本的预测。

    ``prediction_sink`` 会在每条预测生成后同步接收 ``PredictionRecord``；设置
    ``retain_predictions=False`` 后，``EvaluationResult.predictions`` 保持为空，
    可将百万级评估的预测内存从 O(N) 降为 O(1)。默认值完全保持旧行为。

    ``loss_fn`` 的 scalar 输出默认按当前 batch 的 sample mean 解释。需要不同归约
    质量的 loss 可以实现 ``reduction_denominator(targets)``；评估器会按
    ``Σ(loss_i × denominator_i) / Σ denominator_i`` 汇总，从而保持 batch 划分不变性。

    ``event_context`` 是与 Web/传输无关的运行上下文，可原生携带 ``run_id``、
    ``epoch``、``total_epochs``、``global_step`` 等字段；``split`` 用于 standalone
    evaluation 的便捷覆盖。能获取 ``len(batches)`` 时进度事件会提供 ``total``，
    否则保持 ``None``。

    ``event_callback`` 是同步 fail-fast hook：callback 异常会终止评估并传播给调用方；
    评估器仍保证在退出前恢复模型原始 train/eval 状态。

    Sliding collator 产生的窗口被视为独立行；原始样本级窗口聚合属于推理层，
    评估器不会根据重复 UID 隐式猜测聚合策略。
    """
    if num_classes < 2:
        raise ValueError("num_classes 必须 >= 2")
    label_names = _validate_labels(labels, num_classes)
    try:
        target_device = torch.device(device)
    except (TypeError, RuntimeError) as exc:
        raise ValueError(f"无效评估设备: {device!r}") from exc
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("评估请求 CUDA，但当前环境不可用")

    total_batches = _safe_len(batches)
    base_context = _resolve_event_context(
        event_context,
        split=split,
        total_batches=total_batches,
    )

    def emit(event: LifecycleEvent | ProgressEvent) -> None:
        if event_callback is not None:
            event_callback(event)

    model.to(target_device)
    if loss_fn is not None:
        loss_fn.to(target_device)
    was_training = model.training
    model.eval()
    confusion = torch.zeros(num_classes, num_classes, dtype=torch.long)
    records: list[PredictionRecord] = []
    total_loss_numerator = 0.0
    total_loss_denominator = 0.0
    total_samples = 0
    started = time.perf_counter()

    try:
        emit(
            LifecycleEvent(
                "evaluation",
                "started",
                details={
                    "num_classes": num_classes,
                    "total_batches": base_context.total_batches,
                    "device": str(target_device),
                    "prediction_sink": prediction_sink is not None,
                    "retain_predictions": retain_predictions,
                },
                context=base_context,
            )
        )

        for batch_index, batch in enumerate(batches, start=1):
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            if batch.labels is None:
                raise ValueError("评估 batch 必须包含 labels")
            batch = move_batch_to_device(batch, target_device)
            labels_tensor = batch.labels
            assert labels_tensor is not None
            output = model(batch)
            if output.logits.shape != (labels_tensor.shape[0], num_classes):
                raise ValueError(
                    f"模型 logits 期望 [B,{num_classes}]，实际 {tuple(output.logits.shape)}"
                )
            if torch.any(labels_tensor < 0) or torch.any(labels_tensor >= num_classes):
                raise ValueError("评估标签超出 [0, num_classes) 范围")
            loss = (
                loss_fn(output.logits, labels_tensor)
                if loss_fn is not None
                else output.loss
                if output.loss is not None
                else F.cross_entropy(output.logits, labels_tensor)
            )
            if not torch.isfinite(loss):
                raise FloatingPointError("评估 loss 为 NaN/Inf")
            probabilities = output.logits.softmax(dim=-1)
            confidence, predictions = probabilities.max(dim=-1)
            flat = labels_tensor * num_classes + predictions
            counts = torch.bincount(flat, minlength=num_classes * num_classes)
            confusion += counts.reshape(num_classes, num_classes).cpu()
            count = int(labels_tensor.shape[0])
            batch_loss = float(loss)
            loss_denominator = _loss_reduction_denominator(loss_fn, labels_tensor)
            total_loss_numerator += batch_loss * loss_denominator
            total_loss_denominator += loss_denominator
            total_samples += count
            for index, uid in enumerate(batch.uids):
                record = PredictionRecord(
                    uid=uid,
                    target=int(labels_tensor[index]),
                    predicted=int(predictions[index]),
                    confidence=float(confidence[index]),
                    probabilities=tuple(
                        float(value) for value in probabilities[index].cpu()
                    ),
                )
                if prediction_sink is not None:
                    prediction_sink.write(record)
                if retain_predictions:
                    records.append(record)

            elapsed = max(time.perf_counter() - started, 0.0)
            emit(
                ProgressEvent(
                    stage="evaluate_batch",
                    completed=batch_index,
                    total=base_context.total_batches,
                    message=f"samples={total_samples}",
                    context=replace(base_context, batch=batch_index),
                    details={
                        "batch_samples": count,
                        "samples_processed": total_samples,
                        "batch_loss": batch_loss,
                        "running_loss": total_loss_numerator / total_loss_denominator,
                        "elapsed_seconds": elapsed,
                        "samples_per_second": (
                            total_samples / elapsed if elapsed > 0 else 0.0
                        ),
                    },
                )
            )

        total = int(confusion.sum().item())
        if total == 0:
            raise ValueError("评估数据为空")
        true_positive = confusion.diag().to(torch.float64)
        support = confusion.sum(dim=1).to(torch.float64)
        predicted_count = confusion.sum(dim=0).to(torch.float64)
        recall = true_positive / support.clamp_min(1)
        precision = true_positive / predicted_count.clamp_min(1)
        denominator = precision + recall
        f1 = torch.where(
            denominator > 0,
            2
            * precision
            * recall
            / denominator.clamp_min(torch.finfo(torch.float64).eps),
            torch.zeros_like(denominator),
        )
        present = support > 0
        accuracy = float(true_positive.sum().item() / total)
        # WAR 是按 support 加权的 recall；单标签分类中与 accuracy 数值相同。
        war = float((recall * support).sum().item() / total)
        weighted_precision = float((precision * support).sum().item() / total)
        weighted_f1 = float((f1 * support).sum().item() / total)
        predicted_float = predicted_count.to(torch.float64)
        correct = true_positive.sum()
        sample_total = torch.tensor(float(total), dtype=torch.float64)
        mcc_denominator = torch.sqrt(
            (
                (sample_total.square() - predicted_float.square().sum())
                * (sample_total.square() - support.square().sum())
            ).clamp_min(0)
        )
        mcc = (
            float(
                (correct * sample_total - (predicted_float * support).sum())
                / mcc_denominator
            )
            if float(mcc_denominator) > 0
            else 0.0
        )
        expected_agreement = float(
            (predicted_float * support).sum() / sample_total.square()
        )
        kappa = (
            (accuracy - expected_agreement) / (1.0 - expected_agreement)
            if expected_agreement < 1.0
            else 0.0
        )
        per_class = tuple(
            ClassMetrics(
                label_id=index,
                label_name=label_names[index],
                precision=float(precision[index]),
                recall=float(recall[index]),
                f1=float(f1[index]),
                support=int(support[index]),
            )
            for index in range(num_classes)
        )
        result = EvaluationResult(
            accuracy=accuracy,
            macro_f1=float(f1[present].mean()),
            uar=float(recall[present].mean()),
            confusion_matrix=confusion,
            sample_count=total,
            loss=total_loss_numerator / total_loss_denominator,
            war=war,
            per_class=per_class,
            predictions=tuple(records),
            weighted_precision=weighted_precision,
            weighted_recall=war,
            weighted_f1=weighted_f1,
            balanced_accuracy=float(recall[present].mean()),
            matthews_correlation_coefficient=mcc,
            cohen_kappa=kappa,
        )
        emit(
            LifecycleEvent(
                "evaluation",
                "completed",
                details={
                    **_result_event_details(result),
                    "duration_seconds": max(time.perf_counter() - started, 0.0),
                    "predictions_retained": len(records),
                },
                context=base_context,
            )
        )
        return result
    except OperationCancelled:
        emit(
            LifecycleEvent(
                "evaluation",
                "cancelled",
                details={
                    "samples_processed": total_samples,
                    "duration_seconds": max(time.perf_counter() - started, 0.0),
                },
                context=base_context,
            )
        )
        raise
    except Exception as exc:
        emit(
            LifecycleEvent(
                "evaluation",
                "failed",
                message=str(exc),
                details={
                    "error_type": type(exc).__name__,
                    "samples_processed": total_samples,
                    "duration_seconds": max(time.perf_counter() - started, 0.0),
                },
                context=base_context,
            )
        )
        raise
    finally:
        model.train(was_training)


def write_evaluation_report(directory: Path | str, result: EvaluationResult) -> Path:
    """原子写入 ``metrics.json`` 与 ``predictions.jsonl``。"""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    metrics_path = target / "metrics.json"
    metrics_tmp = target / "metrics.json.tmp"
    metrics_tmp.write_text(
        json.dumps(result.to_dict(include_predictions=False), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    predictions_path = target / "predictions.jsonl"
    predictions_tmp = target / "predictions.jsonl.tmp"
    with predictions_tmp.open("w", encoding="utf-8", newline="\n") as stream:
        for record in result.predictions:
            stream.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    metrics_tmp.replace(metrics_path)
    predictions_tmp.replace(predictions_path)
    return target


__all__ = [
    "ClassMetrics",
    "PredictionRecord",
    "PredictionSink",
    "JsonlPredictionSink",
    "EvaluationResult",
    "evaluate",
    "write_evaluation_report",
]
