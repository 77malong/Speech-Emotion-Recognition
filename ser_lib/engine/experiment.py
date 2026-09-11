"""高层实验工作流：从稳定配置直接训练或评估 artifact。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, cast

import torch
from torch.utils.data import DataLoader

from ser_lib._version import __version__
from ser_lib.data.collate import SERCollator, build_collator
from ser_lib.data.dataset import SERDataset
from ser_lib.data.fingerprint import fingerprint_manifest
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.pipeline import SamplePipeline, build_components
from ser_lib.engine.compatibility import validate_compatibility
from ser_lib.engine.config import ExperimentConfig, load_experiment_config
from ser_lib.engine.evaluator import (
    EvaluationResult,
    PredictionSink,
    evaluate,
    write_evaluation_report,
)
from ser_lib.engine.evaluation_runs import (
    EvaluationRunInfo,
    build_evaluation_run_metadata,
    load_evaluation_run_info,
    write_evaluation_run_info,
)
from ser_lib.engine.runs import (
    TrainingRunInfo,
    load_training_run_info,
    write_training_run_info,
)
from ser_lib.engine.objectives import build_weighted_sampler
from ser_lib.engine.trainer import Trainer, TrainingResult
from ser_lib.foundation.events import EventContext
from ser_lib.models.base import SERModel
from ser_lib.models.registry import model_registry


@dataclass(frozen=True, slots=True)
class _DataComponents:
    audio_loader: Any
    pipeline: SamplePipeline
    collator: SERCollator
    model: SERModel


@dataclass(frozen=True, slots=True)
class _ValidationComponents:
    audio_loader: Any
    pipeline: SamplePipeline
    collator: SERCollator


class _LoaderComponents(Protocol):
    @property
    def audio_loader(self) -> Any: ...

    @property
    def pipeline(self) -> SamplePipeline: ...

    @property
    def collator(self) -> SERCollator: ...


@dataclass(frozen=True, slots=True)
class TrainingExperimentResult:
    output_dir: Path
    training: TrainingResult
    run: TrainingRunInfo
    run_record: Path
    metrics_log: Path
    history_path: Path
    resumed_from: Path | None
    last_checkpoint: Path | None
    best_checkpoint: Path | None

    def to_dict(self) -> dict[str, object]:
        training = self.training.to_dict()
        run = self.run.to_dict()
        return {
            "run_id": self.training.run_id,
            "status": self.training.status,
            "history": training["epochs"],
            "best_epoch": self.training.best_epoch,
            "best_metric": self.training.best_metric,
            "monitored_metric": self.training.monitored_metric,
            "dataset_id": self.run.dataset_id,
            "dataset_fingerprint": self.run.dataset_fingerprint,
            "model_id": self.run.model_id,
            "output_dir": str(self.output_dir),
            "training": training,
            "run": run,
            "run_record": str(self.run_record),
            "metrics_log": str(self.metrics_log),
            "history_path": str(self.history_path),
            "resumed_from": str(self.resumed_from) if self.resumed_from is not None else None,
            "last_checkpoint": str(self.last_checkpoint) if self.last_checkpoint is not None else None,
            "best_checkpoint": str(self.best_checkpoint) if self.best_checkpoint is not None else None,
        }


@dataclass(frozen=True, slots=True)
class EvaluationExperimentResult:
    output_dir: Path
    evaluation: EvaluationResult
    run: EvaluationRunInfo
    run_record: Path
    metrics_path: Path
    predictions_path: Path | None
    metric_unit: str = "sample"

    @property
    def evaluation_record(self) -> Path:
        """0.2.x compatibility alias for the persisted evaluation run record."""
        return self.run_record

    def to_dict(self) -> dict[str, object]:
        evaluation = self.evaluation.to_dict()
        run = self.run.to_dict()
        return {
            "evaluation_id": self.run.evaluation_id,
            "source_artifact": self.run.source_artifact,
            "source_run_id": self.run.source_run_id,
            "dataset_id": self.run.dataset_id,
            "dataset_fingerprint": self.run.dataset_fingerprint,
            "model_name": self.run.model_name,
            "split": self.run.split,
            "device": self.run.device,
            "sample_count": self.run.sample_count,
            "metrics": dict(self.run.metrics),
            "output_dir": str(self.output_dir),
            "evaluation": evaluation,
            "run": run,
            "run_record": str(self.run_record),
            "metrics_path": str(self.metrics_path),
            "predictions_path": (
                str(self.predictions_path) if self.predictions_path is not None else None
            ),
            "metric_unit": self.metric_unit,
        }


def _resolve_experiment_config(config: ExperimentConfig | Path | str) -> ExperimentConfig:
    return config if isinstance(config, ExperimentConfig) else load_experiment_config(config)


def build_experiment_components(
    config: ExperimentConfig,
    *,
    train: bool,
) -> _DataComponents:
    from ser_lib.engine._seed import seed_experiment_rng

    seed_experiment_rng(config.trainer.seed, deterministic=config.trainer.deterministic)
    audio_loader, pipeline = build_components(config.data, train=train)
    model = cast(SERModel, model_registry.create(config.model.type, **config.model.params))
    validate_compatibility(
        pipeline.output_specs,
        model.model_spec,
        config.data.batching,
        num_classes=config.data.num_classes,
        sample_rate=config.data.audio.target_sample_rate,
    )
    return _DataComponents(
        audio_loader=audio_loader,
        pipeline=pipeline,
        collator=build_collator(pipeline.output_specs, config.data.batching),
        model=model,
    )


def _canonical_dataset_labels(
    labels: Mapping[int, Mapping[str, Any]],
    *,
    source: str,
) -> dict[int, str]:
    if not labels:
        raise ValueError(f"{source} 缺少 labels，无法验证标签语义")
    normalized: dict[int, str] = {}
    for raw_index, names in labels.items():
        index = int(raw_index)
        if not isinstance(names, Mapping):
            raise ValueError(f"{source}[{index}] 必须是语言→名称映射")
        selected = names.get("en")
        if not isinstance(selected, str) or not selected.strip():
            candidates = [
                str(value).strip()
                for _, value in sorted(names.items(), key=lambda item: str(item[0]))
                if isinstance(value, str) and value.strip()
            ]
            if not candidates:
                raise ValueError(f"无法确定 {source} label={index} 的非空标签名称")
            selected = candidates[0]
        normalized[index] = selected.strip()
    if sorted(normalized) != list(range(len(normalized))):
        raise ValueError(f"{source} 必须使用连续标签 id 0..N-1，实际: {sorted(normalized)}")
    return normalized


def _validate_training_label_semantics(
    experiment_labels: Mapping[int, Mapping[str, Any]] | None,
    manifest_labels: Mapping[int, Mapping[str, Any]],
) -> None:
    if not experiment_labels:
        return
    expected = _canonical_dataset_labels(experiment_labels, source="experiment data.labels")
    actual = _canonical_dataset_labels(manifest_labels, source="manifest labels")
    if expected != actual:
        raise ValueError(
            "训练标签语义与 manifest 不一致："
            f"experiment={expected}, manifest={actual}"
        )


def _validate_artifact_label_semantics(
    artifact_labels: Mapping[int, str],
    manifest_labels: Mapping[int, Mapping[str, Any]],
) -> None:
    expected = {int(index): str(name).strip() for index, name in artifact_labels.items()}
    actual = _canonical_dataset_labels(manifest_labels, source="evaluation manifest labels")
    if sorted(expected) != list(range(len(expected))) or any(
        not name for name in expected.values()
    ):
        raise ValueError(f"artifact labels 非法，无法验证语义: {expected}")
    if expected != actual:
        raise ValueError(
            "artifact 标签语义与 manifest 不一致："
            f"artifact={expected}, manifest={actual}"
        )


def _loader(
    manifest: DatasetManifest,
    split: str,
    components: _LoaderComponents,
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
    """原子维护完整 run history；TrainingResult 仍只描述本次 fit segment。"""
    by_epoch: dict[int, dict[str, Any]] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"history.json 不是合法 JSON: {path}") from exc
        if not isinstance(existing, list):
            raise ValueError("history.json 顶层必须是 epoch 列表")
        for item in existing:
            if not isinstance(item, dict):
                raise ValueError("history.json epoch 记录必须是映射")
            epoch = item.get("epoch")
            if not isinstance(epoch, int) or epoch < 1:
                raise ValueError("history.json epoch 必须是正整数")
            if epoch in by_epoch:
                raise ValueError(f"history.json 包含重复 epoch={epoch}")
            by_epoch[epoch] = dict(item)

    for item in result.epochs:
        by_epoch[item.epoch] = asdict(item)

    payload = [by_epoch[epoch] for epoch in sorted(by_epoch)]
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _evaluation_metric_unit(preprocessing: Mapping[str, Any]) -> str:
    batching = preprocessing.get("batching")
    if isinstance(batching, Mapping):
        batching_type = batching.get("type")
        if batching_type == "sliding":
            return "window"
        if batching_type in {"dynamic", "fixed"}:
            return "sample"
    return "batch_row"


def _write_evaluation_summary(
    directory: Path,
    result: EvaluationResult,
    *,
    metric_unit: str,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    metrics_path = directory / "metrics.json"
    temporary = directory / "metrics.json.tmp"
    payload = result.to_dict(include_predictions=False)
    payload["metric_unit"] = metric_unit
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(metrics_path)


def train_experiment(
    config: ExperimentConfig | Path | str,
    *,
    split: str = "train",
    batch_size: int = 16,
    workers: int = 0,
    resume: Path | str | None = None,
) -> TrainingExperimentResult:
    resolved = _resolve_experiment_config(config)
    if resolved.trainer.checkpoint_dir is None:
        resolved = resolved.model_copy(
            update={
                "trainer": resolved.trainer.model_copy(
                    update={"checkpoint_dir": resolved.output_dir / "checkpoints"}
                )
            }
        )

    manifest = DatasetManifest.load(resolved.data.manifest)
    _validate_training_label_semantics(resolved.data.labels, manifest.meta.labels)
    components = build_experiment_components(resolved, train=True)
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
    sampler_generator = getattr(getattr(batches, "sampler", None), "generator", None)
    if isinstance(sampler_generator, torch.Generator):
        trainer.attach_sampling_generator(sampler_generator)

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

    return TrainingExperimentResult(
        output_dir=resolved.output_dir,
        training=training_result,
        run=run_info,
        run_record=run_record,
        metrics_log=metrics_log,
        history_path=history_path,
        resumed_from=resumed_from,
        last_checkpoint=training_result.last_checkpoint,
        best_checkpoint=training_result.best_checkpoint,
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
    prediction_sink: PredictionSink | None = None,
    retain_predictions: bool = True,
) -> EvaluationExperimentResult:
    from ser_lib.artifacts.loader import load_model_artifact

    artifact_path = Path(artifact)
    output_dir = Path(output)
    loaded = load_model_artifact(artifact_path, map_location=device)
    manifest_source = manifest_path or loaded.manifest.preprocessing["manifest"]
    manifest = DatasetManifest.load(manifest_source)
    _validate_artifact_label_semantics(loaded.manifest.labels, manifest.meta.labels)
    dataset_fingerprint = fingerprint_manifest(manifest)
    metric_unit = _evaluation_metric_unit(loaded.manifest.preprocessing)

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
        prediction_sink=prediction_sink,
        retain_predictions=retain_predictions,
    )
    finished_at = datetime.now(timezone.utc)
    if retain_predictions:
        write_evaluation_report(output_dir, result)
    _write_evaluation_summary(output_dir, result, metric_unit=metric_unit)
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
        run_record=evaluation_record,
        metrics_path=output_dir / "metrics.json",
        predictions_path=(output_dir / "predictions.jsonl") if retain_predictions else None,
        metric_unit=metric_unit,
    )


__all__ = [
    "TrainingExperimentResult",
    "EvaluationExperimentResult",
    "build_experiment_components",
    "train_experiment",
    "evaluate_artifact",
]
