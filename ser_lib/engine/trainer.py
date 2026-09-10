"""统一 Trainer 公开实现：训练循环、optimizer 和 lineage 只保留一条正式路径。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import torch
import torch.nn.functional as F

from ser_lib._version import __version__
from ser_lib.data.types import SERBatch, move_batch_to_device
from ser_lib.engine._trainer_core import (
    EpochResult,
    ObservabilityConfig,
    Trainer as _TrainerCore,
    TrainerConfig,
    TrainingResult,
    TrainingStatus,
    seed_everything,
)
from ser_lib.engine.config import ExperimentConfig
from ser_lib.engine.lineage import TrainingRunMetadata, build_training_run_metadata
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.engine.optim import AdamWConfig, build_optimizer
from ser_lib.foundation.events import CancellationCheck, EventCallback
from ser_lib.models.base import ModelOutput, SERModel


class _AccumulationState:
    """Track online reduction mass for gradients and epoch-level loss metrics."""

    def __init__(
        self,
        accumulation_steps: int,
        optimizer: torch.optim.Optimizer,
    ) -> None:
        self.accumulation_steps = accumulation_steps
        self.optimizer = optimizer
        self.pending_denominator = 0.0
        self.epoch_loss_numerator = 0.0
        self.epoch_loss_denominator = 0.0
        self.active = False

    def begin_epoch(self) -> None:
        self.pending_denominator = 0.0
        self.epoch_loss_numerator = 0.0
        self.epoch_loss_denominator = 0.0
        self.active = True

    def end_epoch(self) -> None:
        self.active = False

    def _rescale_pending_gradients(self, factor: float) -> None:
        if factor == 1.0:
            return
        for group in self.optimizer.param_groups:
            for parameter in group["params"]:
                if parameter.grad is not None:
                    parameter.grad.mul_(factor)

    def scale_loss(self, loss: torch.Tensor, denominator: float) -> torch.Tensor:
        if not self.active:
            return loss
        if denominator <= 0:
            raise ValueError("gradient accumulation denominator 必须大于 0")

        detached_loss = float(loss.detach())
        self.epoch_loss_numerator += detached_loss * denominator
        self.epoch_loss_denominator += denominator

        previous_denominator = self.pending_denominator
        combined_denominator = previous_denominator + denominator
        if previous_denominator > 0:
            self._rescale_pending_gradients(previous_denominator / combined_denominator)

        # _TrainerCore divides the returned scalar by accumulation_steps before
        # backward. Compensate only in the gradient path so the effective
        # contribution is denominator / combined_denominator. The resulting
        # gradient scale is bounded and does not turn a mean loss back into a
        # potentially large numerator before GradScaler sees it.
        gradient_scale = (
            denominator * self.accumulation_steps / combined_denominator
        )
        scaled = loss * gradient_scale
        self.pending_denominator = combined_denominator
        # Preserve the user-visible scalar loss while changing only its gradient scale.
        return loss.detach() + scaled - scaled.detach()

    def finish_step(self) -> None:
        if self.pending_denominator <= 0:
            raise RuntimeError("optimizer step 缺少 gradient accumulation denominator")
        self.pending_denominator = 0.0

    def epoch_mean_loss(self) -> float:
        if self.epoch_loss_denominator <= 0:
            raise RuntimeError("epoch loss 缺少 reduction denominator")
        return self.epoch_loss_numerator / self.epoch_loss_denominator


class _AccumulationAwareLoss(torch.nn.Module):
    """Wrap an explicit scalar loss with logical-batch accumulation semantics."""

    def __init__(
        self,
        base_loss: torch.nn.Module,
        state: _AccumulationState,
    ) -> None:
        super().__init__()
        self.base_loss = base_loss
        self.state = state

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss = self.base_loss(logits, targets)
        if isinstance(self.base_loss, ClassificationLoss):
            denominator = self.base_loss.reduction_denominator(targets)
        else:
            # Public custom scalar losses are interpreted as a mean over samples.
            denominator = float(targets.numel())
        return self.state.scale_loss(loss, denominator)


class Trainer(_TrainerCore):
    """SER 唯一公开训练器。

    低层直接构造时，未显式提供 optimizer 会使用 ``AdamWConfig`` 的标准默认值；
    完整实验应使用 ``Trainer.from_experiment``，optimizer 由
    ``ExperimentConfig.optimizer`` 构造。lineage 是 Trainer 自身状态，checkpoint
    保存和恢复不再依赖 Service 私有子类。

    梯度累积按一个逻辑大 batch 的归约语义执行：不同大小 microbatch 与尾部不足
    ``gradient_accumulation_steps`` 的分组都会按实际有效归约分母重新归一化。显式
    自定义标量 ``loss_fn`` 约定为“对当前 microbatch 样本取 mean”；内置带类别权重
    的 ``ClassificationLoss`` 会使用与 PyTorch weighted cross-entropy 一致的权重
    质量作为分母。累积梯度采用在线加权平均，不会先在 AMP 反向路径中放大为 loss
    numerator；epoch loss 也使用同一 reduction denominator 口径汇总。
    """

    run_metadata: TrainingRunMetadata | None

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
        run_metadata: TrainingRunMetadata | None = None,
    ) -> None:
        resolved_config = config or TrainerConfig()
        resolved_optimizer = optimizer or build_optimizer(
            model.parameters(),
            AdamWConfig(),
        )
        self.run_metadata = run_metadata
        self._sampling_generator: torch.Generator | None = None
        self._accumulation_state = _AccumulationState(
            resolved_config.gradient_accumulation_steps,
            resolved_optimizer,
        )
        wrapped_loss = (
            _AccumulationAwareLoss(loss_fn, self._accumulation_state)
            if loss_fn is not None
            else None
        )
        super().__init__(
            model,
            resolved_config,
            optimizer=resolved_optimizer,
            scheduler=scheduler,
            loss_fn=wrapped_loss,
            event_callback=event_callback,
            cancellation=cancellation,
            observability=observability,
            run_id=run_id,
        )
        self.optimizer_step_attempted = 0
        self.optimizer_step_skipped = 0
        self._accumulation_model_hook = None
        if loss_fn is None:
            self._accumulation_model_hook = self.model.register_forward_hook(
                self._scale_implicit_training_loss
            )

    def attach_sampling_generator(self, generator: torch.Generator | None) -> None:
        """绑定训练 sampler 的独立 RNG，使 checkpoint/resume 可恢复抽样序列。"""
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

    def train_epoch(self, batches: Iterable[SERBatch], *, epoch: int) -> EpochResult:
        applied_before = self.optimizer_step
        self._accumulation_state.begin_epoch()
        try:
            result = super().train_epoch(batches, epoch=epoch)
            return replace(
                result,
                loss=self._accumulation_state.epoch_mean_loss(),
                optimizer_steps=self.optimizer_step - applied_before,
            )
        finally:
            self._accumulation_state.end_epoch()

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
            # GradScaler lowers its scale whenever non-finite gradients cause
            # optimizer.step() to be skipped. Successful steps keep or grow it.
            applied = float(self._scaler.get_scale()) >= scale_before

        self.optimizer.zero_grad(set_to_none=True)
        if applied:
            self.optimizer_step += 1
        else:
            self.optimizer_step_skipped += 1

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
        """按完整实验配置构造 Trainer，并记录调用方已知的训练 lineage。"""
        trainer = cast(
            Trainer,
            super().from_experiment(
                model,
                experiment,
                event_callback=event_callback,
                cancellation=cancellation,
                observability=observability,
                run_id=run_id,
            ),
        )
        trainer.run_metadata = build_training_run_metadata(
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

    def fit(  # type: ignore[override]
        self,
        train_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]],
        *,
        val_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]] | None = None,
        on_epoch_end: Callable[[EpochResult], None] | None = None,
        start_epoch: int | None = None,
    ) -> TrainingResult:
        """执行训练并直接返回稳定的终态 ``TrainingResult``。"""
        super().fit(
            train_batches,
            val_batches=val_batches,
            on_epoch_end=on_epoch_end,
            start_epoch=start_epoch,
        )
        if self.last_result is None:
            raise RuntimeError("Trainer.fit 完成后未生成 TrainingResult")
        return self.last_result

    def _save_checkpoint_with_event(
        self,
        path: Path,
        *,
        kind: str,
        epoch: int,
        metrics: dict[str, float],
        metadata: dict[str, object],
    ) -> Path:
        resolved_metadata = dict(metadata)
        if self.run_metadata is not None:
            resolved_metadata["run_metadata"] = self.run_metadata.to_dict()
        if self._sampling_generator is not None:
            resolved_metadata["sampling_generator_state"] = (
                self._sampling_generator.get_state().cpu()
            )
        previous_last_checkpoint = self._last_checkpoint
        saved = super()._save_checkpoint_with_event(
            path,
            kind=kind,
            epoch=epoch,
            metrics=metrics,
            metadata=resolved_metadata,
        )
        if kind == "epoch":
            # ``last_checkpoint`` denotes the opt-in ``last.pt`` artifact, while
            # epoch-NNNN.pt remains independently available for explicit resume.
            self._last_checkpoint = previous_last_checkpoint
        return saved

    def resume_from(self, path, *, restore_rng: bool = True) -> dict:
        payload = super().resume_from(path, restore_rng=restore_rng)
        raw_checkpoint_metadata = payload.get("metadata")
        saved_run_metadata: TrainingRunMetadata | None = None
        if isinstance(raw_checkpoint_metadata, Mapping):
            raw_lineage = raw_checkpoint_metadata.get("run_metadata")
            if isinstance(raw_lineage, Mapping):
                saved_run_metadata = TrainingRunMetadata.from_dict(raw_lineage)
            sampling_state = raw_checkpoint_metadata.get("sampling_generator_state")
            if (
                restore_rng
                and self._sampling_generator is not None
                and isinstance(sampling_state, torch.Tensor)
            ):
                self._sampling_generator.set_state(sampling_state.cpu())

        if not self._run_id_explicit and saved_run_metadata is not None:
            self.run_metadata = saved_run_metadata.with_run_id(self.run_id)
        elif self.run_metadata is not None:
            self.run_metadata = self.run_metadata.with_run_id(self.run_id)
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
