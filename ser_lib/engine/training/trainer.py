"""表示无关、可观测且可取消的 SER 分类训练内部核心。"""

from __future__ import annotations

import logging
import random
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence, Sized
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from ser_lib._version import __version__
from ser_lib.data.types import SERBatch, move_batch_to_device
from ser_lib.config.experiment import ExperimentConfig
from ser_lib.config.training import ObservabilityConfig, TrainerConfig
from ser_lib.engine.eta import EtaEstimator
from ser_lib.engine.lineage import TrainingMetadata, build_training_metadata
from ser_lib.foundation.events import CheckpointEvent
from ser_lib.engine.optim import (
    AdamWConfig,
    SchedulerConfig,
    build_optimizer,
    build_scheduler,
    parse_optimizer_config,
    parse_scheduler_config,
)
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import (
    CancellationCheck,
    EventCallback,
    EventContext,
    EventLike,
    LibraryEvent,
    LifecycleEvent,
    MetricEvent,
    ProgressEvent,
)
from ser_lib.models.base import ModelOutput, SERModel
from ser_lib.engine.training.accumulation import _AccumulationAwareLoss, _AccumulationState
from ser_lib.engine.training.results import EpochResult, TrainingResult, TrainingStatus

logger = logging.getLogger(__name__)

def seed_everything(seed: int, *, deterministic: bool = True) -> None:
    """为 Python 与 PyTorch 设置可复现 seed。"""
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = deterministic
    torch.backends.cudnn.benchmark = not deterministic


def _safe_len(value: object) -> int | None:
    if not isinstance(value, Sized):
        return None
    try:
        return len(value)
    except TypeError:
        return None


def _infer_total_samples(batches: object) -> int | None:
    dataset = getattr(batches, "dataset", None)
    if isinstance(dataset, Sized):
        try:
            return len(dataset)
        except TypeError:
            pass
    if isinstance(batches, Sequence):
        total = 0
        for batch in batches:
            if not isinstance(batch, SERBatch) or batch.labels is None:
                return None
            total += int(batch.labels.shape[0])
        return total
    return None


_RUNTIME_ONLY_EXPERIMENT_FIELDS = {"output_dir"}
_RUNTIME_ONLY_EXPERIMENT_TRAINER_FIELDS = {
    "epochs",
    "checkpoint_dir",
    "save_best",
    "save_last",
}


def _resume_experiment_signature(config: Mapping[str, Any]) -> dict[str, Any]:
    """Remove fields that may legitimately change when continuing the same run."""
    normalized = {
        key: value for key, value in config.items() if key not in _RUNTIME_ONLY_EXPERIMENT_FIELDS
    }
    trainer = normalized.get("trainer")
    if isinstance(trainer, Mapping):
        normalized["trainer"] = {
            key: value
            for key, value in trainer.items()
            if key not in _RUNTIME_ONLY_EXPERIMENT_TRAINER_FIELDS
        }
    return normalized


def _validate_run_resume_compatibility(
    current: TrainingMetadata,
    saved: TrainingMetadata,
) -> None:
    if current.model_id != saved.model_id:
        raise ValueError("checkpoint lineage 的 model_id 与当前实验不一致")
    if (
        saved.dataset_id is not None
        and current.dataset_id is not None
        and current.dataset_id != saved.dataset_id
    ):
        raise ValueError("checkpoint lineage 的 dataset_id 与当前实验不一致")
    if (
        saved.dataset_fingerprint is not None
        and current.dataset_fingerprint is not None
        and current.dataset_fingerprint != saved.dataset_fingerprint
    ):
        raise ValueError("checkpoint lineage 的 dataset fingerprint 与当前实验不一致")
    if _resume_experiment_signature(saved.config) != _resume_experiment_signature(
        current.config
    ):
        raise ValueError(
            "checkpoint experiment config 与当前实验不兼容；仅允许修改 "
            "output_dir、epochs、checkpoint_dir、save_best、save_last"
        )


class Trainer:
    run_metadata: TrainingMetadata | None

    def __init__(
        self,
        model: SERModel,
        config: TrainerConfig | None = None,
        *,
        optimizer: torch.optim.Optimizer | None = None,
        scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
        loss_fn: torch.nn.Module | None = None,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        observability: ObservabilityConfig | None = None,
        run_id: str | None = None,
        run_metadata: TrainingMetadata | None = None,
    ) -> None:
        self.model = model
        self.config = config or TrainerConfig()
        try:
            self.device = torch.device(self.config.device)
        except (TypeError, RuntimeError) as exc:
            raise ValueError(f"无效训练设备: {self.config.device!r}") from exc
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise ValueError("配置请求 CUDA，但当前环境不可用")
        if self.config.amp and self.device.type != "cuda":
            raise ValueError("AMP 当前仅支持 CUDA 设备")
        if run_id is not None and not run_id.strip():
            raise ValueError("run_id 不能为空字符串")

        seed_everything(self.config.seed, deterministic=self.config.deterministic)
        self.model.to(self.device)
        self.optimizer = optimizer or build_optimizer(model.parameters(), AdamWConfig())
        self.scheduler = scheduler
        self.run_metadata = run_metadata
        self._sampling_generator: torch.Generator | None = None
        self._accumulation_state = _AccumulationState(
            self.config.gradient_accumulation_steps,
            self.optimizer,
        )
        wrapped_loss = (
            _AccumulationAwareLoss(loss_fn, self._accumulation_state)
            if loss_fn is not None
            else None
        )
        self.loss_fn = wrapped_loss.to(self.device) if wrapped_loss is not None else None
        self.event_callback = event_callback
        self.cancellation = cancellation
        self.observability = observability or ObservabilityConfig()
        self._eta_estimator = EtaEstimator(
            window_size=self.observability.eta_window_batches,
            warmup_batches=self.observability.eta_warmup_batches,
        )
        self._validation_last_progress_perf: float | None = None
        self._run_id_explicit = run_id is not None
        self.run_id = run_id or f"run_{uuid.uuid4().hex}"
        self._scaler = torch.cuda.amp.GradScaler() if self.config.amp else None
        self.last_completed_epoch = 0
        self.best_metric: float | None = None
        self.best_epoch: int | None = None
        self.epochs_without_improvement = 0
        self.global_step = 0
        self.optimizer_step = 0
        self.optimizer_step_attempted = 0
        self.optimizer_step_skipped = 0
        self.last_result: TrainingResult | None = None
        self._last_checkpoint: Path | None = None
        self._best_checkpoint: Path | None = None
        self._run_started_perf: float | None = None
        self._accumulation_model_hook = None
        if loss_fn is None:
            self._accumulation_model_hook = self.model.register_forward_hook(
                self._scale_implicit_training_loss
            )

    def attach_sampling_generator(self, generator: torch.Generator | None) -> None:
        if generator is not None and not isinstance(generator, torch.Generator):
            raise TypeError("sampling generator 必须是 torch.Generator 或 None")
        self._sampling_generator = generator

    def _scale_implicit_training_loss(
        self,
        module: torch.nn.Module,
        args: tuple[object, ...],
        output: ModelOutput,
    ) -> ModelOutput:
        _ = module
        if not self._accumulation_state.active:
            return output
        if not self.model.training or not torch.is_grad_enabled():
            return output
        if not args or not isinstance(args[0], SERBatch):
            return output
        batch = args[0]
        if batch.labels is None:
            return output
        base_loss = (
            output.loss
            if output.loss is not None
            else F.cross_entropy(output.logits, batch.labels)
        )
        scaled_loss = self._accumulation_state.scale_loss(
            base_loss,
            float(batch.labels.numel()),
        )
        return ModelOutput(
            logits=output.logits,
            embeddings=output.embeddings,
            loss=scaled_loss,
        )

    @classmethod
    def from_experiment(
        cls,
        model: SERModel,
        experiment: ExperimentConfig,
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        observability: ObservabilityConfig | None = None,
        run_id: str | None = None,
        dataset_id: str | None = None,
        dataset_fingerprint: str | None = None,
    ) -> "Trainer":
        """按实验配置构造训练器，并记录当前训练 lineage。"""
        from ser_lib.models.registry import model_registry

        if model.model_spec.model_id != experiment.model.type:
            raise ValueError(
                f"实验模型 {experiment.model.type!r} 与实例声明 "
                f"{model.model_spec.model_id!r} 不一致"
            )
        expected_model_config = model_registry.validate_config(
            experiment.model.type, experiment.model.params
        )
        if expected_model_config != model.model_config:
            raise ValueError("实验 model.params 与模型实例的实际配置不一致")

        optimizer_config = parse_optimizer_config(experiment.optimizer)
        optimizer = build_optimizer(model.parameters(), optimizer_config)
        scheduler_config: SchedulerConfig | None = parse_scheduler_config(experiment.scheduler)
        scheduler = build_scheduler(optimizer, scheduler_config)

        from ser_lib.engine.objectives import ClassificationLoss

        num_classes = model.model_spec.num_classes
        if num_classes is None:
            raise ValueError("分类训练要求模型声明 num_classes")

        trainer = cls(
            model,
            experiment.trainer,
            optimizer=optimizer,
            scheduler=scheduler,
            loss_fn=ClassificationLoss(experiment.loss, num_classes),
            event_callback=event_callback,
            cancellation=cancellation,
            observability=observability,
            run_id=run_id,
        )
        trainer.run_metadata = build_training_metadata(
            run_id=trainer.run_id,
            dataset_id=dataset_id if dataset_id is not None else experiment.data.dataset_id,
            dataset_fingerprint=dataset_fingerprint,
            model_id=model.model_spec.model_id,
            config=experiment.model_dump(mode="json"),
            seed=experiment.trainer.seed,
            device=str(trainer.device),
            library_version=__version__,
        )
        return trainer

    def _emit(self, event: EventLike) -> None:
        if self.event_callback is not None:
            self.event_callback(event)

    def _check_cancelled(self) -> None:
        if self.cancellation is not None:
            self.cancellation.raise_if_cancelled()

    def _context(
        self,
        *,
        epoch: int | None = None,
        batch: int | None = None,
        total_batches: int | None = None,
        split: str | None = None,
    ) -> EventContext:
        return EventContext(
            run_id=self.run_id,
            epoch=epoch,
            total_epochs=self.config.epochs,
            batch=batch,
            total_batches=total_batches,
            global_step=self.global_step,
            split=split,
        )

    def _current_learning_rate(self) -> float:
        if not self.optimizer.param_groups:
            return 0.0
        return float(self.optimizer.param_groups[0].get("lr", 0.0))

    def _build_training_result(
        self,
        history: Sequence[EpochResult],
        *,
        status: TrainingStatus,
        started_at: datetime,
        finished_at: datetime,
        duration_seconds: float,
        stop_reason: str | None,
    ) -> TrainingResult:
        return TrainingResult(
            run_id=self.run_id,
            status=status,
            epochs=tuple(history),
            best_epoch=self.best_epoch,
            best_metric=self.best_metric,
            monitored_metric=self.config.monitor,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=max(float(duration_seconds), 0.0),
            last_checkpoint=self._last_checkpoint,
            best_checkpoint=self._best_checkpoint,
            stop_reason=stop_reason,
        )

    def _optimizer_step(self) -> None:
        self._accumulation_state.finish_step()
        self.optimizer_step_attempted += 1
        if self._scaler is not None:
            self._scaler.unscale_(self.optimizer)
        if self.config.gradient_clip_norm is not None:
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(), self.config.gradient_clip_norm
            )

        applied = True
        if self._scaler is None:
            self.optimizer.step()
        else:
            scale_before = float(self._scaler.get_scale())
            self._scaler.step(self.optimizer)
            self._scaler.update()
            applied = float(self._scaler.get_scale()) >= scale_before

        self.optimizer.zero_grad(set_to_none=True)
        if applied:
            self.optimizer_step += 1
        else:
            self.optimizer_step_skipped += 1

    def _emit_live_metrics(
        self,
        *,
        epoch: int,
        batch_index: int,
        total_batches: int | None,
        batch_loss: float,
        running_loss: float,
        running_accuracy: float,
        samples_per_second: float,
    ) -> None:
        context = self._context(
            epoch=epoch,
            batch=batch_index,
            total_batches=total_batches,
            split="train",
        )
        values = {
            "batch_loss": batch_loss,
            "running_loss": running_loss,
            "running_accuracy": running_accuracy,
            "learning_rate": self._current_learning_rate(),
            "samples_per_second": samples_per_second,
        }
        for name, value in values.items():
            self._emit(
                MetricEvent(
                    name,
                    value,
                    step=self.global_step,
                    split="train",
                    context=context,
                )
            )

    def train_epoch(self, batches: Iterable[SERBatch], *, epoch: int) -> EpochResult:
        applied_before = self.optimizer_step
        self._accumulation_state.begin_epoch()
        try:
            result = self._train_epoch_impl(batches, epoch=epoch)
            return replace(
                result,
                loss=self._accumulation_state.epoch_mean_loss(),
                optimizer_steps=self.optimizer_step - applied_before,
            )
        finally:
            self._accumulation_state.end_epoch()

    def _train_epoch_impl(self, batches: Iterable[SERBatch], *, epoch: int) -> EpochResult:
        self.model.train()
        total_correct = 0
        total_samples = 0
        optimizer_steps = 0
        pending_batches = 0
        total_batches = _safe_len(batches)
        samples_total = _infer_total_samples(batches)
        epoch_started = time.perf_counter()
        if self._run_started_perf is None:
            self._run_started_perf = epoch_started
        self.optimizer.zero_grad(set_to_none=True)

        for batch_index, batch in enumerate(batches, start=1):
            batch_started = time.perf_counter()
            self._check_cancelled()
            if batch.labels is None:
                raise ValueError("训练 batch 必须包含 labels")
            batch = move_batch_to_device(batch, self.device)
            labels = batch.labels
            assert labels is not None
            with torch.autocast(
                device_type=self.device.type,
                dtype=torch.float16,
                enabled=self.config.amp,
            ):
                output = self.model(batch)
                loss = (
                    self.loss_fn(output.logits, labels)
                    if self.loss_fn is not None
                    else output.loss if output.loss is not None
                    else F.cross_entropy(output.logits, labels)
                )
            if not torch.isfinite(loss):
                raise FloatingPointError(f"训练 loss 非有限值: {loss.item()}")
            scaled_loss = loss / self.config.gradient_accumulation_steps
            if self._scaler is None:
                scaled_loss.backward()
            else:
                self._scaler.scale(scaled_loss).backward()
            pending_batches += 1
            if pending_batches == self.config.gradient_accumulation_steps:
                self._optimizer_step()
                optimizer_steps += 1
                pending_batches = 0

            count = int(labels.shape[0])
            batch_loss = float(loss.detach())
            total_samples += count
            total_correct += int((output.logits.detach().argmax(-1) == labels).sum())
            self.global_step += 1

            batch_duration = max(time.perf_counter() - batch_started, 0.0)
            self._eta_estimator.record_batch(batch_duration, count, phase="train")
            future_batches = (
                max(self.config.epochs - epoch, 0) * total_batches
                if total_batches is not None
                else 0
            )
            eta = self._eta_estimator.snapshot(
                phase="train",
                completed_batches=batch_index,
                total_batches=total_batches,
                future_batches=future_batches,
            )
            epoch_elapsed = max(time.perf_counter() - epoch_started, 0.0)
            run_elapsed = max(time.perf_counter() - self._run_started_perf, 0.0)
            running_loss = self._accumulation_state.epoch_mean_loss()
            running_accuracy = total_correct / total_samples
            samples_per_second = total_samples / epoch_elapsed if epoch_elapsed > 0 else 0.0
            batches_per_second = batch_index / epoch_elapsed if epoch_elapsed > 0 else 0.0

            should_emit_progress = (
                batch_index % self.observability.progress_interval_batches == 0
                or total_batches is not None and batch_index == total_batches
            )
            if should_emit_progress:
                self._emit(
                    ProgressEvent(
                        stage="train_batch",
                        completed=batch_index,
                        total=total_batches,
                        message=f"epoch={epoch}",
                        context=self._context(
                            epoch=epoch,
                            batch=batch_index,
                            total_batches=total_batches,
                            split="train",
                        ),
                        details={
                            "samples_processed": total_samples,
                            "samples_total": samples_total,
                            "optimizer_steps": self.optimizer_step,
                            "batch_loss": batch_loss,
                            "running_loss": running_loss,
                            "running_accuracy": running_accuracy,
                            "learning_rate": self._current_learning_rate(),
                            "elapsed_seconds": run_elapsed,
                            "epoch_elapsed_seconds": epoch_elapsed,
                            "estimated_epoch_remaining_seconds": eta.phase_remaining_seconds,
                            "estimated_remaining_seconds": eta.global_remaining_seconds,
                            "samples_per_second": samples_per_second,
                            "batches_per_second": batches_per_second,
                            "eta_ready": eta.ready,
                            "eta_window_batches": self.observability.eta_window_batches,
                            "recent_batches_per_second": eta.batches_per_second,
                            "recent_samples_per_second": eta.samples_per_second,
                        },
                    )
                )

            if batch_index % self.observability.metric_interval_batches == 0:
                self._emit_live_metrics(
                    epoch=epoch,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    batch_loss=batch_loss,
                    running_loss=running_loss,
                    running_accuracy=running_accuracy,
                    samples_per_second=samples_per_second,
                )

        if pending_batches:
            self._optimizer_step()
            optimizer_steps += 1
        if total_samples == 0:
            raise ValueError("训练数据为空")

        result = EpochResult(
            epoch=epoch,
            loss=self._accumulation_state.epoch_mean_loss(),
            accuracy=total_correct / total_samples,
            sample_count=total_samples,
            optimizer_steps=optimizer_steps,
        )
        epoch_context = self._context(epoch=epoch, split="train")
        self._emit(
            MetricEvent("loss", result.loss, step=epoch, split="train", context=epoch_context)
        )
        self._emit(
            MetricEvent(
                "accuracy", result.accuracy, step=epoch, split="train", context=epoch_context
            )
        )
        return result

    def _emit_validation_event(
        self,
        event: LibraryEvent,
        *,
        epoch: int,
        total_batches: int | None,
    ) -> None:
        if isinstance(event, ProgressEvent):
            resolved_total = event.total if event.total is not None else total_batches
            now = time.perf_counter()
            if self._validation_last_progress_perf is not None:
                self._eta_estimator.record_batch(
                    max(now - self._validation_last_progress_perf, 0.0),
                    phase="validation",
                )
            self._validation_last_progress_perf = now
            eta = self._eta_estimator.snapshot(
                phase="validation",
                completed_batches=event.completed,
                total_batches=resolved_total,
            )
            event = replace(
                event,
                total=resolved_total,
                details={
                    **event.details,
                    "estimated_validation_remaining_seconds": eta.phase_remaining_seconds,
                    "eta_ready": eta.ready,
                    "eta_window_batches": self.observability.eta_window_batches,
                    "recent_batches_per_second": eta.batches_per_second,
                },
                context=self._context(
                    epoch=epoch,
                    batch=event.context.batch or event.completed,
                    total_batches=event.context.total_batches or resolved_total,
                    split="val",
                ),
            )
        elif isinstance(event, MetricEvent):
            event = replace(
                event,
                split="val",
                context=self._context(
                    epoch=epoch,
                    batch=event.context.batch,
                    total_batches=event.context.total_batches or total_batches,
                    split="val",
                ),
            )
        self._emit(event)

    def _save_checkpoint_with_event(
        self,
        path: Path,
        *,
        kind: str,
        epoch: int,
        metrics: dict[str, float],
        metadata: dict[str, object],
    ) -> Path:
        from ser_lib.engine.checkpoint import save_checkpoint

        resolved_metadata = dict(metadata)
        if self.run_metadata is not None:
            resolved_metadata["run_metadata"] = self.run_metadata.to_dict()
        if self._sampling_generator is not None:
            resolved_metadata["sampling_generator_state"] = (
                self._sampling_generator.get_state().cpu()
            )
        if kind == "best":
            resolved_metadata["best_checkpoint"] = path.name
        elif self._best_checkpoint is not None:
            resolved_metadata["best_checkpoint"] = self._best_checkpoint.name

        previous_last_checkpoint = self._last_checkpoint
        metric_name = self.config.monitor if kind == "best" else None
        metric_value = self.best_metric if kind == "best" else None
        context = self._context(epoch=epoch)
        self._emit(
            CheckpointEvent(
                "started",
                kind,
                path,
                epoch,
                metric_name=metric_name,
                metric_value=metric_value,
                context=context,
            )
        )
        try:
            saved = save_checkpoint(
                path,
                self.model,
                self.optimizer,
                epoch=epoch,
                scheduler=self.scheduler,
                scaler=self._scaler,
                metrics=metrics,
                metadata=resolved_metadata,
                trainer_config=self.config.model_dump(mode="json"),
            )
        except Exception as exc:
            self._emit(
                CheckpointEvent(
                    "failed",
                    kind,
                    path,
                    epoch,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    message=str(exc),
                    details={"error_type": type(exc).__name__},
                    context=context,
                )
            )
            raise

        if kind in {"epoch", "last"}:
            self._last_checkpoint = saved
        if kind == "best":
            self._best_checkpoint = saved
        self._emit(
            CheckpointEvent(
                "saved",
                kind,
                saved,
                epoch,
                metric_name=metric_name,
                metric_value=metric_value,
                context=context,
            )
        )
        if kind == "best":
            self._emit(
                CheckpointEvent(
                    "best_model_updated",
                    kind,
                    saved,
                    epoch,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    context=context,
                )
            )
        if kind == "epoch":
            self._last_checkpoint = previous_last_checkpoint
        return saved

    def fit(
        self,
        train_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]],
        *,
        val_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]] | None = None,
        on_epoch_end: Callable[[EpochResult], None] | None = None,
        start_epoch: int | None = None,
    ) -> TrainingResult:
        if self.config.early_stopping_patience is not None and val_batches is None:
            raise ValueError("启用 early stopping 时必须提供 val_batches")
        first_epoch = self.last_completed_epoch + 1 if start_epoch is None else start_epoch
        if first_epoch < 1:
            raise ValueError("start_epoch 必须 >= 1")

        history: list[EpochResult] = []
        stop_reason: str | None = None
        started_at = datetime.now(timezone.utc)
        self.last_result = None
        self._eta_estimator.reset()
        self._validation_last_progress_perf = None
        self._run_started_perf = time.perf_counter()
        self._emit(
            LifecycleEvent(
                "training",
                "started",
                details={
                    "device": str(self.device),
                    "first_epoch": first_epoch,
                    "total_epochs": self.config.epochs,
                },
                context=self._context(),
            )
        )

        try:
            for epoch in range(first_epoch, self.config.epochs + 1):
                self._check_cancelled()
                self._emit(
                    LifecycleEvent(
                        "epoch",
                        "started",
                        context=self._context(epoch=epoch),
                    )
                )

                batches = train_batches() if callable(train_batches) else train_batches
                train_total_batches = _safe_len(batches)
                self._emit(
                    LifecycleEvent(
                        "train",
                        "phase_started",
                        details={"total_batches": train_total_batches},
                        context=self._context(
                            epoch=epoch,
                            total_batches=train_total_batches,
                            split="train",
                        ),
                    )
                )
                result = self.train_epoch(batches, epoch=epoch)
                self._emit(
                    LifecycleEvent(
                        "train",
                        "phase_completed",
                        details={
                            "loss": result.loss,
                            "accuracy": result.accuracy,
                            "sample_count": result.sample_count,
                            "optimizer_steps": result.optimizer_steps,
                        },
                        context=self._context(
                            epoch=epoch,
                            total_batches=train_total_batches,
                            split="train",
                        ),
                    )
                )

                if self.scheduler is not None:
                    self.scheduler.step()
                self.last_completed_epoch = epoch
                improved = False

                if val_batches is not None and epoch % self.config.validation_interval == 0:
                    from ser_lib.engine.evaluator import evaluate

                    validation_batches = val_batches() if callable(val_batches) else val_batches
                    validation_total_batches = _safe_len(validation_batches)
                    self._validation_last_progress_perf = time.perf_counter()
                    self._emit(
                        LifecycleEvent(
                            "validation",
                            "phase_started",
                            details={"total_batches": validation_total_batches},
                            context=self._context(
                                epoch=epoch,
                                total_batches=validation_total_batches,
                                split="val",
                            ),
                        )
                    )
                    num_classes = self.model.model_spec.num_classes
                    if num_classes is None:
                        raise ValueError("验证要求模型声明 num_classes")
                    validation_result = evaluate(
                        self.model,
                        validation_batches,
                        num_classes=num_classes,
                        device=self.device,
                        event_callback=partial(
                            self._emit_validation_event,
                            epoch=epoch,
                            total_batches=validation_total_batches,
                        ),
                        cancellation=self.cancellation,
                        loss_fn=self.loss_fn,
                    )
                    validation = {
                        "loss": validation_result.loss,
                        "accuracy": validation_result.accuracy,
                        "war": validation_result.war,
                        "uar": validation_result.uar,
                        "macro_f1": validation_result.macro_f1,
                    }
                    result = replace(result, validation=validation)
                    validation_context = self._context(epoch=epoch, split="val")
                    for name, value in validation.items():
                        self._emit(
                            MetricEvent(
                                name,
                                value,
                                step=epoch,
                                split="val",
                                context=validation_context,
                            )
                        )
                    monitored = validation[self.config.monitor.removeprefix("val_")]
                    improved = self._is_improved(monitored)
                    if improved:
                        self.best_metric = monitored
                        self.best_epoch = epoch
                        self.epochs_without_improvement = 0
                    else:
                        self.epochs_without_improvement += 1
                    self._emit(
                        LifecycleEvent(
                            "validation",
                            "phase_completed",
                            details={**validation, "improved": improved},
                            context=self._context(
                                epoch=epoch,
                                total_batches=validation_total_batches,
                                split="val",
                            ),
                        )
                    )

                history.append(result)
                logger.info(
                    "epoch=%d train_loss=%.6f train_accuracy=%.4f validation=%s",
                    epoch, result.loss, result.accuracy, result.validation,
                )
                self._check_cancelled()

                if self.config.checkpoint_dir is not None:
                    metrics = {"loss": result.loss, "accuracy": result.accuracy}
                    if result.validation is not None:
                        metrics.update({f"val_{k}": v for k, v in result.validation.items()})
                    metadata: dict[str, object] = {
                        "best_metric": self.best_metric,
                        "best_epoch": self.best_epoch,
                        "epochs_without_improvement": self.epochs_without_improvement,
                        "monitor": self.config.monitor,
                        "run_id": self.run_id,
                        "global_step": self.global_step,
                        "optimizer_step": self.optimizer_step,
                    }
                    self._save_checkpoint_with_event(
                        self.config.checkpoint_dir / f"epoch-{epoch:04d}.pt",
                        kind="epoch",
                        epoch=epoch,
                        metrics=metrics,
                        metadata=metadata,
                    )
                    if self.config.save_last:
                        self._save_checkpoint_with_event(
                            self.config.checkpoint_dir / "last.pt",
                            kind="last",
                            epoch=epoch,
                            metrics=metrics,
                            metadata=metadata,
                        )
                    if improved and self.config.save_best:
                        self._save_checkpoint_with_event(
                            self.config.checkpoint_dir / "best.pt",
                            kind="best",
                            epoch=epoch,
                            metrics=metrics,
                            metadata=metadata,
                        )

                if on_epoch_end is not None:
                    on_epoch_end(result)

                self._emit(
                    LifecycleEvent(
                        "epoch",
                        "completed",
                        details={
                            "loss": result.loss,
                            "accuracy": result.accuracy,
                            "validation": result.validation,
                            "best_epoch": self.best_epoch,
                            "best_metric": self.best_metric,
                        },
                        context=self._context(epoch=epoch),
                    )
                )

                if (
                    self.config.early_stopping_patience is not None
                    and self.epochs_without_improvement >= self.config.early_stopping_patience
                ):
                    stop_reason = "early_stopped"
                    self._emit(
                        LifecycleEvent(
                            "training",
                            "early_stopped",
                            details={
                                "patience": self.config.early_stopping_patience,
                                "monitor": self.config.monitor,
                                "best_epoch": self.best_epoch,
                                "best_metric": self.best_metric,
                            },
                            context=self._context(epoch=epoch),
                        )
                    )
                    break

            elapsed = max(time.perf_counter() - self._run_started_perf, 0.0)
            finished_at = datetime.now(timezone.utc)
            status: TrainingStatus = (
                "early_stopped" if stop_reason == "early_stopped" else "completed"
            )
            self.last_result = self._build_training_result(
                history,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=elapsed,
                stop_reason=stop_reason,
            )
            self._emit(
                LifecycleEvent(
                    "training",
                    "completed",
                    details={
                        "status": status,
                        "stop_reason": stop_reason,
                        "epochs_completed": len(history),
                        "last_completed_epoch": self.last_completed_epoch,
                        "best_epoch": self.best_epoch,
                        "best_metric": self.best_metric,
                        "global_step": self.global_step,
                        "optimizer_step": self.optimizer_step,
                        "elapsed_seconds": elapsed,
                    },
                    context=self._context(epoch=self.last_completed_epoch or None),
                )
            )
            if self.last_result is None:
                raise RuntimeError("Trainer.fit 完成后未生成 TrainingResult")
            return self.last_result
        except OperationCancelled:
            elapsed = max(time.perf_counter() - self._run_started_perf, 0.0)
            finished_at = datetime.now(timezone.utc)
            self.last_result = self._build_training_result(
                history,
                status="cancelled",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=elapsed,
                stop_reason="cancelled",
            )
            self._emit(
                LifecycleEvent(
                    "training",
                    "cancelled",
                    details={
                        "last_completed_epoch": self.last_completed_epoch,
                        "global_step": self.global_step,
                        "elapsed_seconds": elapsed,
                    },
                    context=self._context(epoch=self.last_completed_epoch or None),
                )
            )
            raise
        except Exception as exc:
            elapsed = max(time.perf_counter() - self._run_started_perf, 0.0)
            finished_at = datetime.now(timezone.utc)
            reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            self.last_result = self._build_training_result(
                history,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=elapsed,
                stop_reason=reason,
            )
            self._emit(
                LifecycleEvent(
                    "training",
                    "failed",
                    message=str(exc),
                    details={
                        "error_type": type(exc).__name__,
                        "last_completed_epoch": self.last_completed_epoch,
                        "global_step": self.global_step,
                        "elapsed_seconds": elapsed,
                    },
                    context=self._context(epoch=self.last_completed_epoch or None),
                )
            )
            raise

    def _is_improved(self, value: float) -> bool:
        if self.best_metric is None:
            return True
        delta = self.config.early_stopping_min_delta
        if self.config.monitor == "val_loss":
            return value < self.best_metric - delta
        return value > self.best_metric + delta

    def resume_from(self, path, *, restore_rng: bool = True) -> dict[str, Any]:
        """在应用训练状态前校验完整实验 lineage，并恢复可发现的 best artifact。"""
        from ser_lib.engine.checkpoint import load_checkpoint

        checkpoint_path = Path(path)
        current_run_metadata = self.run_metadata
        saved_run_metadata: TrainingMetadata | None = None

        def validate_metadata(metadata: dict[str, Any]) -> None:
            nonlocal saved_run_metadata
            raw_lineage = metadata.get("run_metadata")
            if isinstance(raw_lineage, Mapping):
                saved_run_metadata = TrainingMetadata.from_dict(raw_lineage)
                if current_run_metadata is not None:
                    _validate_run_resume_compatibility(
                        current_run_metadata,
                        saved_run_metadata,
                    )

        payload = load_checkpoint(
            checkpoint_path,
            self.model,
            self.optimizer,
            scheduler=self.scheduler,
            scaler=self._scaler,
            map_location=self.device,
            restore_rng=restore_rng,
            expected_trainer_config=self.config.model_dump(mode="json"),
            metadata_validator=validate_metadata,
        )

        epoch = payload.get("epoch")
        if not isinstance(epoch, int) or epoch < 0:
            raise ValueError("checkpoint epoch 非法")
        self.last_completed_epoch = epoch
        self._last_checkpoint = checkpoint_path
        metadata = payload.get("metadata") or {}
        if metadata.get("monitor") in (None, self.config.monitor):
            best_metric = metadata.get("best_metric")
            best_epoch = metadata.get("best_epoch")
            without_improvement = metadata.get("epochs_without_improvement", 0)
            self.best_metric = float(best_metric) if best_metric is not None else None
            self.best_epoch = int(best_epoch) if best_epoch is not None else None
            self.epochs_without_improvement = int(without_improvement)

        if self.best_epoch is not None:
            raw_best_checkpoint = metadata.get("best_checkpoint")
            if raw_best_checkpoint is not None:
                if not isinstance(raw_best_checkpoint, str) or not raw_best_checkpoint:
                    raise ValueError("checkpoint metadata.best_checkpoint 必须是相对文件名")
                relative_best = Path(raw_best_checkpoint)
                if relative_best.is_absolute() or len(relative_best.parts) != 1:
                    raise ValueError("checkpoint metadata.best_checkpoint 必须是相对文件名")
                best_path = checkpoint_path.parent / relative_best
                if not best_path.is_file():
                    raise FileNotFoundError(
                        f"checkpoint 引用的 best artifact 不存在: {best_path}"
                    )
                self._best_checkpoint = best_path
            else:
                best_path = checkpoint_path.parent / "best.pt"
                self._best_checkpoint = best_path if best_path.is_file() else None

        saved_run_id = metadata.get("run_id")
        if not self._run_id_explicit and isinstance(saved_run_id, str) and saved_run_id:
            self.run_id = saved_run_id
        saved_global_step = metadata.get("global_step")
        saved_optimizer_step = metadata.get("optimizer_step")
        if isinstance(saved_global_step, int) and saved_global_step >= 0:
            self.global_step = saved_global_step
        if isinstance(saved_optimizer_step, int) and saved_optimizer_step >= 0:
            self.optimizer_step = saved_optimizer_step

        sampling_state = metadata.get("sampling_generator_state")
        if (
            restore_rng
            and self._sampling_generator is not None
            and isinstance(sampling_state, torch.Tensor)
        ):
            self._sampling_generator.set_state(sampling_state.cpu())

        if current_run_metadata is not None:
            created_at = (
                saved_run_metadata.created_at
                if saved_run_metadata is not None
                else current_run_metadata.created_at
            )
            self.run_metadata = replace(
                current_run_metadata,
                run_id=self.run_id,
                created_at=created_at,
            )
        elif saved_run_metadata is not None:
            self.run_metadata = saved_run_metadata.with_run_id(self.run_id)
        return payload


__all__ = [
    "TrainerConfig",
    "ObservabilityConfig",
    "EpochResult",
    "TrainingResult",
    "TrainingStatus",
    "Trainer",
    "move_batch_to_device",
    "seed_everything",
]
