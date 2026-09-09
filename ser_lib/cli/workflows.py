"""CLI 的薄编排层；领域行为统一通过 Service facade。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

from torch.utils.data import DataLoader

from ser_lib.artifacts import ModelCard
from ser_lib.data import DatasetManifest, SERDataset, fingerprint_manifest
from ser_lib.engine import (
    TrainingRunMetadata,
    build_experiment_components,
    build_weighted_sampler,
    load_checkpoint,
    load_experiment_config,
)
from ser_lib.foundation.events import EventContext
from ser_lib.services import (
    ArtifactService,
    EvaluationService,
    InferenceService,
    TrainingService,
)


def _labels(meta_labels: dict[int, dict[str, Any]]) -> dict[int, str]:
    return {
        index: str(values.get("en") or values.get("zh") or index)
        for index, values in sorted(meta_labels.items())
    }


def _loader(
    manifest,
    split,
    components,
    *,
    batch_size,
    workers,
    shuffle=False,
    sampling=None,
    seed=42,
    num_classes=None,
):
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


def train_experiment(
    config_path: Path,
    *,
    split: str,
    batch_size: int,
    workers: int,
    resume: Path | None,
) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    if config.trainer.checkpoint_dir is None:
        config = config.model_copy(
            update={
                "trainer": config.trainer.model_copy(
                    update={"checkpoint_dir": config.output_dir / "checkpoints"}
                )
            }
        )
    components = build_experiment_components(config, train=True)
    manifest = DatasetManifest.load(config.data.manifest)
    dataset_fingerprint = fingerprint_manifest(manifest)
    batches = _loader(
        manifest,
        split,
        components,
        batch_size=batch_size,
        workers=workers,
        shuffle=True,
        sampling=config.sampling,
        seed=config.trainer.seed,
        num_classes=components.model.model_spec.num_classes,
    )
    trainer = TrainingService.create_trainer(
        components.model,
        config,
        dataset_id=manifest.meta.dataset_id,
        dataset_fingerprint=dataset_fingerprint.digest,
    )
    val_batches = None
    if "val" in manifest.meta.splits:
        validation_components = build_experiment_components(config, train=False)
        val_batches = _loader(
            manifest,
            "val",
            validation_components,
            batch_size=batch_size,
            workers=workers,
        )
    if resume is not None:
        trainer.resume_from(resume)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_log = config.output_dir / "metrics.jsonl"
    if resume is None:
        metrics_log.write_text("", encoding="utf-8")

    def log_epoch(result) -> None:
        with metrics_log.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
            stream.flush()

    training_result = TrainingService.run(
        trainer,
        lambda: batches,
        val_batches=(lambda: val_batches) if val_batches is not None else None,
        on_epoch_end=log_epoch,
    )
    history = list(training_result.epochs)
    history_path = config.output_dir / "history.json"
    temporary = history_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps([asdict(item) for item in history], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(history_path)
    run_info = TrainingService.save_run(config.output_dir, trainer, training_result)
    last_checkpoint = (
        cast(Path, config.trainer.checkpoint_dir)
        / f"epoch-{trainer.last_completed_epoch:04d}.pt"
        if trainer.last_completed_epoch
        else resume
    )
    return {
        "output_dir": str(config.output_dir),
        "run_id": run_info.run_id,
        "run_record": str(config.output_dir / "run.json"),
        "dataset_id": run_info.dataset_id,
        "dataset_fingerprint": run_info.dataset_fingerprint,
        "last_checkpoint": str(last_checkpoint) if last_checkpoint else None,
        "best_checkpoint": str(config.trainer.checkpoint_dir / "best.pt")
        if trainer.best_epoch is not None and config.trainer.checkpoint_dir
        else None,
        "best_epoch": trainer.best_epoch,
        "best_metric": trainer.best_metric,
        "metrics_log": str(metrics_log),
        "history": [asdict(item) for item in history],
        "resumed_from": str(resume) if resume else None,
    }


def evaluate_artifact(
    artifact: Path,
    *,
    manifest_path: Path | None,
    split: str,
    batch_size: int,
    workers: int,
    device: str,
    output: Path,
) -> dict[str, Any]:
    loaded = ArtifactService.load(artifact, map_location=device)
    manifest = DatasetManifest.load(
        manifest_path or loaded.manifest.preprocessing["manifest"]
    )
    dataset_fingerprint = fingerprint_manifest(manifest)
    raw_source_run_id = loaded.manifest.metadata.get("source_run_id")
    if raw_source_run_id is not None and (
        not isinstance(raw_source_run_id, str) or not raw_source_run_id.strip()
    ):
        raise ValueError("artifact metadata.source_run_id 必须是非空字符串")
    source_run_id = cast(str | None, raw_source_run_id)
    run_metadata = EvaluationService.create_run_metadata(
        source_artifact=artifact,
        source_run_id=source_run_id,
        dataset_id=manifest.meta.dataset_id,
        dataset_fingerprint=dataset_fingerprint.digest,
        model_name=loaded.manifest.model_name,
        split=split,
        device=device,
    )
    batches = _loader(
        manifest,
        split,
        loaded,
        batch_size=batch_size,
        workers=workers,
    )
    started_at = datetime.now(timezone.utc)
    result = EvaluationService.run(
        loaded.model,
        batches,
        num_classes=len(loaded.manifest.labels),
        device=device,
        labels=loaded.manifest.labels,
        event_context=EventContext(run_id=run_metadata.evaluation_id, split=split),
    )
    finished_at = datetime.now(timezone.utc)
    EvaluationService.write_report(output, result)
    run_info = EvaluationService.save_run(
        output,
        run_metadata,
        result,
        started_at=started_at,
        finished_at=finished_at,
    )
    return {
        "output_dir": str(output),
        "evaluation_id": run_info.evaluation_id,
        "evaluation_record": str(output / "evaluation.json"),
        "source_run_id": run_info.source_run_id,
        "dataset_id": run_info.dataset_id,
        "dataset_fingerprint": run_info.dataset_fingerprint,
        **result.summary_dict(),
    }


def predict_artifact(
    artifact: Path,
    *,
    source: Path,
    split: str | None,
    batch_size: int,
    device: str,
    output: Path,
    keep_going: bool,
    recursive: bool,
    window_aggregation: Literal[
        "mean_logits", "mean_probabilities", "max_confidence"
    ] | None,
) -> dict[str, Any]:
    loaded = ArtifactService.load(artifact, map_location=device)
    predictor = InferenceService.create_predictor(
        loaded,
        device=device,
        window_aggregation=window_aggregation,
    )
    if source.is_dir():
        result = InferenceService.predict_directory(
            predictor,
            source,
            recursive=recursive,
            batch_size=batch_size,
            fail_fast=not keep_going,
        )
    elif source.suffix.lower() in {".yaml", ".yml"}:
        result = InferenceService.predict_manifest(
            predictor,
            source,
            split=split,
            batch_size=batch_size,
            fail_fast=not keep_going,
        )
    else:
        result = InferenceService.predict_files(
            predictor,
            [source],
            batch_size=batch_size,
            fail_fast=not keep_going,
        )
    InferenceService.write_predictions(output, result)
    return {
        "output": str(output),
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
    }


def export_checkpoint_artifact(
    config_path: Path,
    checkpoint: Path,
    destination: Path,
    *,
    model_card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    components = build_experiment_components(config, train=False)
    payload = load_checkpoint(
        checkpoint,
        components.model,
        map_location="cpu",
        restore_rng=False,
    )
    manifest = DatasetManifest.load(config.data.manifest)
    source_labels = config.data.labels or manifest.meta.labels
    labels = _labels(source_labels)
    expected_classes = components.model.model_config.get("num_classes")
    if expected_classes is not None and len(labels) != expected_classes:
        raise ValueError(
            f"标签数 {len(labels)} 与模型 num_classes={expected_classes} 不一致"
        )
    source_run = None
    checkpoint_metadata = payload.get("metadata")
    if isinstance(checkpoint_metadata, Mapping):
        raw_run_metadata = checkpoint_metadata.get("run_metadata")
        if isinstance(raw_run_metadata, Mapping):
            source_run = TrainingRunMetadata.from_dict(raw_run_metadata)
    target = ArtifactService.export(
        destination,
        components.model,
        model_name=config.model.type,
        data_config=config.data,
        labels=labels,
        metrics=payload.get("metrics") or {},
        metadata={"checkpoint_epoch": payload.get("epoch")},
        source_run=source_run,
        model_card=ModelCard(**(model_card or {})),
    )
    return {
        "artifact": str(target),
        "model": config.model.type,
        "labels": labels,
        "source_run_id": source_run.run_id if source_run is not None else None,
    }


def inspect_artifact(path: Path, *, verify: bool) -> dict[str, Any]:
    manifest = ArtifactService.verify(path) if verify else ArtifactService.inspect(path)
    return manifest.model_dump(mode="json")


__all__ = [
    "train_experiment",
    "evaluate_artifact",
    "predict_artifact",
    "export_checkpoint_artifact",
    "inspect_artifact",
]