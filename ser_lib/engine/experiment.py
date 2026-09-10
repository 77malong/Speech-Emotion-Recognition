"""可复用的训练与 artifact 评估实验编排。

该模块承接原先 CLI/Service 中具有 Python SDK 价值的执行流程；CLI 只负责参数与
输出适配。这里不引入新的 Trainer/Evaluator 包装层，训练仍走 :class:`Trainer`，
评估仍走 :func:`evaluate`。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, cast

from torch.utils.data import DataLoader

from ser_lib._version import __version__
from ser_lib.config.experiment import ExperimentConfig
from ser_lib.data.collate import SERCollator, build_collator
from ser_lib.data.dataset import SERDataset
from ser_lib.data.fingerprint import fingerprint_manifest
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.pipeline import SamplePipeline, build_components
from ser_lib.engine.compatibility import validate_compatibility
from ser_lib.engine.config import build_experiment_components, load_experiment_config
from ser_lib.engine.evaluation_runs import (
    EvaluationRunInfo,
    build_evaluation_run_metadata,
    load_evaluation_run_info,
    write_evaluation_run_info,
)
from ser_lib.engine.evaluator import EvaluationResult, evaluate, write_evaluation_report
from ser_lib.engine.objectives import build_weighted_sampler
from ser_lib.engine.runs import TrainingRunInfo, load_training_run_info, write_training_run_info
from ser_lib.engine.trainer import Trainer, TrainingResult
from ser_lib.foundation.events import EventContext


class _DataComponents(Protocol):
    @property
    def audio_loader(self) -> Any: ...

    @property
    def pipeline(self) -> SamplePipeline: ...

    @property
    def collator(self) -> SERCollator: ...


@dataclass(frozen=True, slots=True)
class _ValidationComponents:
    audio_loader: Any
    pipeline: SamplePipeline
    collator: SERCollator


@dataclass(frozen=True, slots=True)
class TrainingExperimentResult:
    """一次完整实验训练的 typed 结果与持久化位置。"""

    output_dir: Path
    training: TrainingResult
    run: TrainingRunInfo
    run_record: Path
    metrics_log: Path
    history_path: Path
    resumed_from: Path | None
    last_checkpoint: Path | None
    best_checkpoint: Path | None

    def to_dict(self) -> dict[str, Any]:
        """返回与既有 CLI ``train`` 输出兼容的 JSON-safe 字典。"""
        return {
            "output_dir": str(self.output_dir),
            "run_id": self.run.run_id,
            "run_record": str(self.run_record),
            "dataset_id": self.run.dataset_id,
            "dataset_fingerprint": self.run.dataset_fingerprint,
            "last_checkpoint": (
                str(self.last_checkpoint) if self.last_checkpoint is not None else None
            ),
            "best_checkpoint": (
                str(self.best_checkpoint) if self.best_checkpoint is not None else None
            ),
            "best_epoch": self.training.best_epoch,
            "best_metric": self.training.best_metric,
            "metrics_log": str(self.metrics_log),
            "history": [asdict(item) for item in self.training.epochs],
            "resumed_from": (
                str(self.resumed_from) if self.resumed_from is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class EvaluationExperimentResult:
    """一次 artifact + dataset 评估的 typed 结果与持久化记录。"""

    output_dir: Path
    evaluation: EvaluationResult
    run: EvaluationRunInfo
    evaluation_record: Path

    def to_dict(self) -> dict[str, Any]:
        """返回与既有 CLI ``evaluate`` 输出兼容的 JSON-safe 字典。"""
        return {
            "output_dir": str(self.output_dir),
            "evaluation_id": self.run.evaluation_id,
            "evaluation_record": str(self.evaluation_record),
            "source_run_id": self.run.source_run_id,
            "dataset_id": self.run.dataset_id,
            "dataset_fingerprint": self.run.dataset_fingerprint,
            **self.evaluation.summary_dict(),
        }


def _resolve_experiment_config(config: ExperimentConfig | Path | str) -> ExperimentConfig:
    return load_experiment_config(config) if isinstance(config, (Path, str)) else config


def _loader(
    manifest: DatasetManifest,
    split: str,
    components: _DataComponents,
    *,
    batch_size: int,
    workers: int,
    shuffle: bool = False,
    sampling: Any = None,
    seed: int = 42,
    num_classes: int | None = None,
) -> DataLoader:
    records = manifest.resolved_records(split)
    dataset = SERDataset(records, components.audio_loader, components.pipeline)
    sampler = None
    if sampling is not None:
        if num_classes is None:
            raise ValueError("构建训练 sampler 时必须提供 num_classes")
        sampler = build_weighted_sampler(
            dataset.get_labels(),
            num_classes=num_classes,
            config=sampling,
            seed=seed,
        )
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle and sampler is None,
        sampler=sampler,
        num_workers=workers,
        collate_fn=components.collator,
    )


def _build_validation_components(
    config: ExperimentConfig,
    trainer: Trainer,
) -> _ValidationComponents:
    """为 validation 构建无随机增强的数据链，但复用已训练的同一个模型。"""
    audio_loader, pipeline = build_components(config.data, train=False)
    validate_compatibility(
        pipeline.output_specs,
        trainer.model.model_spec,
        config.data.batching,
        num_classes=config.data.num_classes,
        sample_rate=config.data.audio.target_sample_rate,
    )
    return _ValidationComponents(
        audio_loader=audio_loader,
        pipeline=pipeline,
        collator=build_collator(pipeline.output_specs, config.data.batching),
    )


def _write_training_history(path: Path, result: TrainingResult) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps([asdict(item) for item in result.epochs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def train_experiment(
    config: ExperimentConfig | Path | str,
    *,
    split: str = "train",
    batch_size: int = 16,
    workers: int = 0,
    resume: Path | str | None = None,
) -> TrainingExperimentResult:
    """从实验配置直接完成训练、lineage、history 与 run record 持久化。"""
    resolved = _resolve_experiment_config(config)
    if resolved.trainer.checkpoint_dir is None:
        resolved = resolved.model_copy(
            update={
                "trainer": resolved.trainer.model_copy(
                    update={"checkpoint_dir": resolved.output_dir / "checkpoints"}
                )
            }
        )

    components = build_experiment_components(resolved, train=True)
    manifest = DatasetManifest.load(resolved.data.manifest)
    dataset_fingerprint = fingerprint_manifest(manifest)
    batches = _loader(
        manifest,
        split,
        components,
        batch_size=batch_size,
        workers=workers,
        shuffle=True,
        sampling=resolved.sampling,
        seed=resolved.trainer.seed,
        num_classes=components.model.model_spec.num_classes,
    )
    trainer = Trainer.from_experiment(
        components.model,
        resolved,
        dataset_id=manifest.meta.dataset_id,
        dataset_fingerprint=dataset_fingerprint.digest,
    )

    val_batches = None
    if "val" in manifest.meta.splits:
        validation_components = _build_validation_components(resolved, trainer)
        val_batches = _loader(
            manifest,
            "val",
            validation_components,
            batch_size=batch_size,
            workers=workers,
        )

    resumed_from = Path(resume) if resume is not None else None
    if resumed_from is not None:
        trainer.resume_from(resumed_from)

    resolved.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_log = resolved.output_dir / "metrics.jsonl"
    if resumed_from is None:
        metrics_log.write_text("", encoding="utf-8")

    def log_epoch(result) -> None:
        with metrics_log.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
            stream.flush()

    training_result = trainer.fit(
        lambda: batches,
        val_batches=(lambda: val_batches) if val_batches is not None else None,
        on_epoch_end=log_epoch,
    )

    history_path = resolved.output_dir / "history.json"
    _write_training_history(history_path, training_result)
    if trainer.run_metadata is None:
        raise RuntimeError("Trainer.from_experiment 未生成 TrainingRunMetadata")
    run_record = write_training_run_info(
        resolved.output_dir,
        trainer.run_metadata,
        training_result,
    )
    run_info = load_training_run_info(run_record)

    checkpoint_dir = cast(Path, resolved.trainer.checkpoint_dir)
    last_checkpoint = (
        checkpoint_dir / f"epoch-{trainer.last_completed_epoch:04d}.pt"
        if trainer.last_completed_epoch
        else resumed_from
    )
    best_checkpoint = (
        checkpoint_dir / "best.pt" if trainer.best_epoch is not None else None
    )
    return TrainingExperimentResult(
        output_dir=resolved.output_dir,
        training=training_result,
        run=run_info,
        run_record=run_record,
        metrics_log=metrics_log,
        history_path=history_path,
        resumed_from=resumed_from,
        last_checkpoint=last_checkpoint,
        best_checkpoint=best_checkpoint,
    )


def evaluate_artifact(
    artifact: Path | str,
    *,
    manifest_path: Path | str | None = None,
    split: str = "test",
    batch_size: int = 16,
    workers: int = 0,
    device: str = "cpu",
    output: Path | str,
) -> EvaluationExperimentResult:
    """直接加载 artifact 并在指定 DatasetManifest 上完成评估与 lineage 落盘。"""
    from ser_lib.artifacts.loader import load_model_artifact

    artifact_path = Path(artifact)
    output_dir = Path(output)
    loaded = load_model_artifact(artifact_path, map_location=device)
    manifest_source = manifest_path or loaded.manifest.preprocessing["manifest"]
    manifest = DatasetManifest.load(manifest_source)
    dataset_fingerprint = fingerprint_manifest(manifest)

    raw_source_run_id = loaded.manifest.metadata.get("source_run_id")
    if raw_source_run_id is not None and (
        not isinstance(raw_source_run_id, str) or not raw_source_run_id.strip()
    ):
        raise ValueError("artifact metadata.source_run_id 必须是非空字符串")
    source_run_id = cast(str | None, raw_source_run_id)
    run_metadata = build_evaluation_run_metadata(
        source_artifact=artifact_path,
        source_run_id=source_run_id,
        dataset_id=manifest.meta.dataset_id,
        dataset_fingerprint=dataset_fingerprint.digest,
        model_name=loaded.manifest.model_name,
        split=split,
        device=device,
        library_version=__version__,
    )
    batches = _loader(
        manifest,
        split,
        loaded,
        batch_size=batch_size,
        workers=workers,
    )

    started_at = datetime.now(timezone.utc)
    result = evaluate(
        loaded.model,
        batches,
        num_classes=len(loaded.manifest.labels),
        device=device,
        labels=loaded.manifest.labels,
        event_context=EventContext(run_id=run_metadata.evaluation_id, split=split),
    )
    finished_at = datetime.now(timezone.utc)
    write_evaluation_report(output_dir, result)
    evaluation_record = write_evaluation_run_info(
        output_dir,
        run_metadata,
        result,
        started_at=started_at,
        finished_at=finished_at,
    )
    run_info = load_evaluation_run_info(evaluation_record)
    return EvaluationExperimentResult(
        output_dir=output_dir,
        evaluation=result,
        run=run_info,
        evaluation_record=evaluation_record,
    )


__all__ = [
    "TrainingExperimentResult",
    "EvaluationExperimentResult",
    "train_experiment",
    "evaluate_artifact",
]
