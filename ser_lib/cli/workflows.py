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
from ser_lib.data import DatasetManifest, fingerprint_manifest
from ser_lib.engine import (
    ExperimentConfig,
    TrainingMetadata,
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


def _labels(
    meta_labels: Mapping[int, Mapping[str, Any]],
    *,
    source: str = "labels",
) -> dict[int, str]:
    labels: dict[int, str] = {}
    for raw_index, values in sorted(meta_labels.items()):
        index = int(raw_index)
        name = values.get("en") or values.get("zh")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{source} label={index} 缺少非空名称")
        labels[index] = name.strip()
    if sorted(labels) != list(range(len(labels))):
        raise ValueError(f"{source} 必须使用连续标签 id 0..N-1")
    return labels


def _validate_export_semantics(
    config: ExperimentConfig,
    manifest: DatasetManifest,
    source_run: TrainingMetadata | None,
) -> dict[int, str]:
    manifest_labels = _labels(manifest.meta.labels, source="manifest labels")
    if config.data.labels is not None:
        config_labels = _labels(config.data.labels, source="export config labels")
        if config_labels != manifest_labels:
            raise ValueError(
                "导出标签语义与 manifest 不一致："
                f"config={config_labels}, manifest={manifest_labels}"
            )

    if source_run is None:
        return manifest_labels

    if source_run.dataset_id is not None and source_run.dataset_id != manifest.meta.dataset_id:
        raise ValueError(
            "checkpoint dataset_id 与导出 manifest 不一致："
            f"checkpoint={source_run.dataset_id!r}, manifest={manifest.meta.dataset_id!r}"
        )

    source_config = ExperimentConfig.model_validate(source_run.config)
    if source_config.data.labels is not None:
        trained_labels = _labels(
            source_config.data.labels,
            source="checkpoint training labels",
        )
        if trained_labels != manifest_labels:
            raise ValueError(
                "checkpoint 训练标签语义与导出标签不一致："
                f"checkpoint={trained_labels}, export={manifest_labels}"
            )

    if source_run.dataset_fingerprint is not None:
        current_fingerprint = fingerprint_manifest(manifest).digest
        if current_fingerprint != source_run.dataset_fingerprint:
            raise ValueError(
                "checkpoint dataset fingerprint 与导出 manifest 不一致"
            )

    return manifest_labels


def _artifact_provenance(
    source_run: TrainingMetadata,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """把已解析的训练 lineage 转成 artifact metadata，不扩大 engine API。"""
    resolved = dict(metadata or {})
    resolved.setdefault("source_run_id", source_run.run_id)
    if source_run.dataset_id is not None:
        resolved.setdefault("dataset_id", source_run.dataset_id)
    if source_run.dataset_fingerprint is not None:
        resolved.setdefault("dataset_fingerprint", source_run.dataset_fingerprint)
    return resolved


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
    source_run = None
    checkpoint_metadata = payload.get("metadata")
    if isinstance(checkpoint_metadata, Mapping):
        raw_run_metadata = checkpoint_metadata.get("run_metadata")
        if isinstance(raw_run_metadata, Mapping):
            source_run = TrainingMetadata.from_dict(raw_run_metadata)

    labels = _validate_export_semantics(config, manifest, source_run)
    expected_classes = components.model.model_config.get("num_classes")
    if expected_classes is not None and len(labels) != expected_classes:
        raise ValueError(
            f"标签数 {len(labels)} 与模型 num_classes={expected_classes} 不一致"
        )

    metadata: dict[str, Any] = {"checkpoint_epoch": payload.get("epoch")}
    if source_run is not None:
        metadata = _artifact_provenance(source_run, metadata=metadata)
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
