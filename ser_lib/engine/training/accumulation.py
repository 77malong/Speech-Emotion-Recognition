"""Gradient accumulation helpers for Trainer."""

from __future__ import annotations

import torch


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

        gradient_scale = denominator * self.accumulation_steps / combined_denominator
        scaled = loss * gradient_scale
        self.pending_denominator = combined_denominator
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

    def reduction_denominator(self, targets: torch.Tensor) -> float:
        """Expose the wrapped loss reduction contract to validation/evaluation."""
        denominator_fn = getattr(self.base_loss, "reduction_denominator", None)
        denominator = (
            float(denominator_fn(targets))
            if callable(denominator_fn)
            else float(targets.numel())
        )
        if denominator <= 0:
            raise ValueError("loss reduction denominator 必须大于 0")
        return denominator

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss = self.base_loss(logits, targets)
        return self.state.scale_loss(
            loss,
            self.reduction_denominator(targets),
        )


__all__ = ["_AccumulationState", "_AccumulationAwareLoss"]
