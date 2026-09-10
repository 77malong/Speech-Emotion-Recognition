"""CLI 的薄编排层；可复用实验执行委托给 engine 公共 API。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from ser_lib.artifacts import (
    ModelCard,
    export_model_artifact,
    inspect_model_artifact,
    load_model_artifact,
    verify_model_artifact,
)
from ser_lib.data import DatasetManifest
from ser_lib.engine import (
    TrainingRunMetadata,
    artifact_provenance_from_training_run,
    build_experiment_components,
    evaluate_artifact as run_artifact_evaluation,
    load_checkpoint,
    load_experiment_config,
    train_experiment as run_training_experiment,
)
from ser_lib.inference import (
    BatchEmotionPredictor,
    EmotionPredictor,
    write_batch_predictions,
)


def _labels(meta_labels: dict[int, dict[str, Any]]) -> dict[int, str]:
    return {
        index: str(values.get("en") or values.get("zh") or index)
        for index, values in sorted(meta_labels.items())
    }


def train_experiment(
    config_path: Path,
    *,
    split: str,
    batch_size: int,
    workers: int,
    resume: Path | None,
) -> dict[str, Any]:
    """CLI 兼容入口；训练业务逻辑由 ``ser_lib.engine`` 提供。"""
    return run_training_experiment(
        config_path,
        split=split,
        batch_size=batch_size,
        workers=workers,
        resume=resume,
    ).to_dict()


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
    """CLI 兼容入口；评估业务逻辑由 ``ser_lib.engine`` 提供。"""
    return run_artifact_evaluation(
        artifact,
        manifest_path=manifest_path,
        split=split,
        batch_size=batch_size,
        workers=workers,
        device=device,
        output=output,
    ).to_dict()


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
    loaded = load_model_artifact(artifact, map_location=device)
    predictor = EmotionPredictor.from_loaded_artifact(
        loaded,
        device=device,
        window_aggregation=window_aggregation,
    )
    batch_predictor = BatchEmotionPredictor(predictor)
    if source.is_dir():
        result = batch_predictor.predict_directory(
            source,
            recursive=recursive,
            batch_size=batch_size,
            fail_fast=not keep_going,
        )
    elif source.suffix.lower() in {".yaml", ".yml"}:
        result = batch_predictor.predict_manifest(
            source,
            split=split,
            batch_size=batch_size,
            fail_fast=not keep_going,
        )
    else:
        result = batch_predictor.predict_files(
            [source],
            batch_size=batch_size,
            fail_fast=not keep_going,
        )
    write_batch_predictions(output, result)
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
    metadata: dict[str, Any] = {"checkpoint_epoch": payload.get("epoch")}
    if source_run is not None:
        metadata = artifact_provenance_from_training_run(
            source_run,
            metadata=metadata,
        )
    target = export_model_artifact(
        destination,
        components.model,
        model_name=config.model.type,
        data_config=config.data,
        labels=labels,
        metrics=payload.get("metrics") or {},
        metadata=metadata,
        model_card=ModelCard(**(model_card or {})),
    )
    return {
        "artifact": str(target),
        "model": config.model.type,
        "labels": labels,
        "source_run_id": source_run.run_id if source_run is not None else None,
    }


def inspect_artifact(path: Path, *, verify: bool) -> dict[str, Any]:
    manifest = verify_model_artifact(path) if verify else inspect_model_artifact(path)
    return manifest.model_dump(mode="json")


__all__ = [
    "train_experiment",
    "evaluate_artifact",
    "predict_artifact",
    "export_checkpoint_artifact",
    "inspect_artifact",
]
