"""统一 Trainer 公开实现：训练循环、optimizer 和 lineage 只保留一条正式路径。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import torch

from ser_lib.data.types import move_batch_to_device
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
from ser_lib.engine.lineage import TrainingRunMetadata
from ser_lib.engine.optim import AdamWConfig, build_optimizer
from ser_lib.foundation.events import CancellationCheck, EventCallback
from ser_lib.models.base import SERModel


class Trainer(_TrainerCore):
    """SER 唯一公开训练器。

    低层直接构造时，未显式提供 optimizer 会使用 ``AdamWConfig`` 的标准默认值；
    完整实验应使用 ``Trainer.from_experiment``，optimizer 由
    ``ExperimentConfig.optimizer`` 构造。lineage 是 Trainer 自身状态，checkpoint
    保存和恢复不再依赖 Service 私有子类。
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
        resolved_optimizer = optimizer or build_optimizer(
            model.parameters(),
            AdamWConfig(),
        )
        self.run_metadata = run_metadata
        super().__init__(
            model,
            config,
            optimizer=resolved_optimizer,
            scheduler=scheduler,
            loss_fn=loss_fn,
            event_callback=event_callback,
            cancellation=cancellation,
            observability=observability,
            run_id=run_id,
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
    ) -> "Trainer":
        """按完整 ExperimentConfig 构造当前公开 Trainer 类型。"""
        return cast(
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
        return super()._save_checkpoint_with_event(
            path,
            kind=kind,
            epoch=epoch,
            metrics=metrics,
            metadata=resolved_metadata,
        )

    def resume_from(self, path, *, restore_rng: bool = True) -> dict:
        payload = super().resume_from(path, restore_rng=restore_rng)
        raw_checkpoint_metadata = payload.get("metadata")
        saved_run_metadata: TrainingRunMetadata | None = None
        if isinstance(raw_checkpoint_metadata, Mapping):
            raw_lineage = raw_checkpoint_metadata.get("run_metadata")
            if isinstance(raw_lineage, Mapping):
                saved_run_metadata = TrainingRunMetadata.from_dict(raw_lineage)

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
