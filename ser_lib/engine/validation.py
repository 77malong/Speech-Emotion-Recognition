"""实验启动前的无副作用 dry-run 校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from ser_lib.data.manifest import ManifestMeta, load_meta
from ser_lib.data.pipeline import SamplePipeline, build_pipeline
from ser_lib.engine.compatibility import inspect_compatibility
from ser_lib.config import ExperimentConfig, load_experiment_config
from ser_lib.engine.optim import parse_optimizer_config, parse_scheduler_config
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.models.registry import model_registry
from ser_lib.models.specs import ModelSpec


@dataclass(frozen=True, slots=True)
class ExperimentValidationResult:
    """Web/CLI 可直接消费的实验 dry-run 结果。"""

    valid: bool
    diagnostics: tuple[Diagnostic, ...]
    normalized_config: dict[str, Any]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "normalized_config": dict(self.normalized_config),
            "summary": dict(self.summary),
        }


def _diagnostic(
    code: str,
    message: str,
    *,
    field: str | None = None,
    path: Path | str | None = None,
    suggestion: str | None = None,
    details: dict[str, Any] | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=message,
        stage="experiment_validation",
        field=field,
        path=path,
        suggestion=suggestion,
        details=details or {},
    )


def _load_config(
    value: ExperimentConfig | Path | str,
) -> tuple[ExperimentConfig | None, list[Diagnostic]]:
    if isinstance(value, ExperimentConfig):
        return value, []
    path = Path(value).expanduser()
    try:
        return load_experiment_config(path), []
    except Exception as exc:  # 配置加载异常类型可能来自 YAML/Pydantic/领域层
        return None, [
            _diagnostic(
                "experiment_config_invalid",
                f"实验配置无法加载或不满足 Schema: {exc}",
                path=path,
                suggestion="检查当前 YAML 字段、类型与组件参数",
                details={"error_type": type(exc).__name__},
            )
        ]


def _inspect_manifest(
    config: ExperimentConfig,
    diagnostics: list[Diagnostic],
) -> ManifestMeta | None:
    manifest_path = config.data.manifest
    try:
        meta = load_meta(manifest_path)
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "dataset_manifest_invalid",
                f"数据集 manifest 无法加载: {exc}",
                field="data.manifest",
                path=manifest_path,
                suggestion="检查 dataset.yaml 是否存在且格式正确",
                details={"error_type": type(exc).__name__},
            )
        )
        return None

    if not meta.root.exists():
        diagnostics.append(
            _diagnostic(
                "dataset_root_missing",
                f"数据集根目录不存在: {meta.root}",
                field="data.manifest.root",
                path=meta.root,
                suggestion="修正 dataset.yaml 的 root 路径",
            )
        )
    elif not meta.root.is_dir():
        diagnostics.append(
            _diagnostic(
                "dataset_root_not_directory",
                f"数据集 root 不是目录: {meta.root}",
                field="data.manifest.root",
                path=meta.root,
            )
        )

    if not meta.splits:
        diagnostics.append(
            _diagnostic(
                "dataset_splits_missing",
                "dataset.yaml 未声明任何 split",
                field="data.manifest.splits",
                path=manifest_path,
                suggestion="至少声明一个训练或评估 split",
            )
        )
    for split_name, split_path in meta.splits.items():
        if not split_path.exists():
            diagnostics.append(
                _diagnostic(
                    "dataset_split_missing",
                    f"数据集 split '{split_name}' 文件不存在: {split_path}",
                    field=f"data.manifest.splits.{split_name}",
                    path=split_path,
                    suggestion="检查 dataset.yaml 中的 split 文件路径",
                    details={"split": split_name},
                )
            )
        elif not split_path.is_file():
            diagnostics.append(
                _diagnostic(
                    "dataset_split_not_file",
                    f"数据集 split '{split_name}' 不是文件: {split_path}",
                    field=f"data.manifest.splits.{split_name}",
                    path=split_path,
                    details={"split": split_name},
                )
            )

    configured_classes = config.data.num_classes
    manifest_classes = meta.num_classes or None
    if (
        configured_classes is not None
        and manifest_classes is not None
        and configured_classes != manifest_classes
    ):
        diagnostics.append(
            _diagnostic(
                "label_count_mismatch",
                f"实验配置声明 {configured_classes} 个类别，但 dataset.yaml 声明 "
                f"{manifest_classes} 个类别",
                field="data.labels",
                path=manifest_path,
                suggestion="统一 ExperimentConfig.data.labels 与 dataset.yaml labels",
                details={
                    "configured_num_classes": configured_classes,
                    "manifest_num_classes": manifest_classes,
                },
            )
        )
    return meta


def _inspect_pipeline(
    config: ExperimentConfig,
    diagnostics: list[Diagnostic],
) -> SamplePipeline | None:
    data_config = config.data.model_copy(
        update={"cache": config.data.cache.model_copy(update={"enabled": False})}
    )
    try:
        return build_pipeline(data_config, train=True, validate_contract=False)
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "pipeline_config_invalid",
                f"数据流水线无法构建: {exc}",
                field="data",
                suggestion="检查 Representation、Transform、Batching 组件参数",
                details={"error_type": type(exc).__name__},
            )
        )
        return None


def _inspect_model_spec(
    config: ExperimentConfig,
    diagnostics: list[Diagnostic],
) -> tuple[ModelSpec | None, dict[str, Any] | None]:
    try:
        normalized_params = model_registry.validate_config(
            config.model.type, config.model.params
        )
        spec = model_registry.inspect_spec(config.model.type, normalized_params)
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "model_config_invalid",
                f"模型配置无法静态校验: {exc}",
                field="model",
                suggestion="检查模型类型与参数；第三方模型需注册静态 spec_factory",
                details={"error_type": type(exc).__name__},
            )
        )
        return None, None
    return spec, normalized_params


def _inspect_training_options(
    config: ExperimentConfig,
    *,
    num_classes: int | None,
    diagnostics: list[Diagnostic],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    optimizer_summary: dict[str, Any] | None = None
    scheduler_summary: dict[str, Any] | None = None
    try:
        optimizer_summary = parse_optimizer_config(config.optimizer).model_dump(mode="json")
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "optimizer_config_invalid",
                f"Optimizer 配置非法: {exc}",
                field="optimizer",
                details={"error_type": type(exc).__name__},
            )
        )
    try:
        scheduler = parse_scheduler_config(config.scheduler)
        scheduler_summary = scheduler.model_dump(mode="json") if scheduler is not None else None
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "scheduler_config_invalid",
                f"Scheduler 配置非法: {exc}",
                field="scheduler",
                details={"error_type": type(exc).__name__},
            )
        )

    if num_classes is not None:
        if (
            config.loss.class_weights is not None
            and len(config.loss.class_weights) != num_classes
        ):
            diagnostics.append(
                _diagnostic(
                    "loss_class_weights_mismatch",
                    f"loss.class_weights 长度 {len(config.loss.class_weights)} 与 "
                    f"num_classes={num_classes} 不一致",
                    field="loss.class_weights",
                    details={"num_classes": num_classes},
                )
            )
        if (
            config.sampling.class_weights is not None
            and len(config.sampling.class_weights) != num_classes
        ):
            diagnostics.append(
                _diagnostic(
                    "sampling_class_weights_mismatch",
                    f"sampling.class_weights 长度 {len(config.sampling.class_weights)} 与 "
                    f"num_classes={num_classes} 不一致",
                    field="sampling.class_weights",
                    details={"num_classes": num_classes},
                )
            )
    return optimizer_summary, scheduler_summary


def _inspect_paths_and_device(
    config: ExperimentConfig,
    diagnostics: list[Diagnostic],
) -> str | None:
    for field_name, path in (
        ("output_dir", config.output_dir),
        ("trainer.checkpoint_dir", config.trainer.checkpoint_dir),
    ):
        if path is not None and path.exists() and not path.is_dir():
            diagnostics.append(
                _diagnostic(
                    "output_path_not_directory",
                    f"{field_name} 指向已有文件而不是目录: {path}",
                    field=field_name,
                    path=path,
                    suggestion="改为目录路径或移除同名文件",
                )
            )

    try:
        device = torch.device(config.trainer.device)
    except (TypeError, RuntimeError) as exc:
        diagnostics.append(
            _diagnostic(
                "device_invalid",
                f"训练设备配置非法: {config.trainer.device!r}",
                field="trainer.device",
                details={"error_type": type(exc).__name__},
            )
        )
        return None

    if device.type == "cuda":
        if not torch.cuda.is_available():
            diagnostics.append(
                _diagnostic(
                    "device_unavailable",
                    "配置请求 CUDA，但当前运行环境不可用",
                    field="trainer.device",
                    suggestion="改用 cpu，或在有可用 CUDA 的运行节点启动任务",
                )
            )
        elif device.index is not None and device.index >= torch.cuda.device_count():
            diagnostics.append(
                _diagnostic(
                    "device_unavailable",
                    f"CUDA 设备索引 {device.index} 超出当前设备数量 "
                    f"{torch.cuda.device_count()}",
                    field="trainer.device",
                )
            )
    if config.trainer.amp and device.type != "cuda":
        diagnostics.append(
            _diagnostic(
                "amp_device_mismatch",
                "AMP 当前仅支持 CUDA 设备",
                field="trainer.amp",
                suggestion="关闭 amp 或将 trainer.device 配置为可用 CUDA 设备",
            )
        )
    return str(device)


def _spec_summary(pipeline: SamplePipeline | None) -> dict[str, Any]:
    if pipeline is None:
        return {}
    return {
        key: {
            "layout": spec.layout,
            "feature_dim": spec.feature_dim,
            "temporal": spec.temporal,
        }
        for key, spec in pipeline.output_specs.items()
    }


def validate_experiment(
    config: ExperimentConfig | Path | str,
) -> ExperimentValidationResult:
    """执行训练前 dry-run，不加载样本、不创建模型、不分配 GPU。

    ``Path``/``str`` 输入同时覆盖 YAML/Pydantic Schema 校验；已经构造好的
    :class:`ExperimentConfig` 则从领域级静态检查开始。
    """
    resolved, diagnostics = _load_config(config)
    if resolved is None:
        return ExperimentValidationResult(False, tuple(diagnostics), {}, {})

    normalized_config = resolved.model_dump(mode="json")
    meta = _inspect_manifest(resolved, diagnostics)
    pipeline = _inspect_pipeline(resolved, diagnostics)
    model_spec, normalized_model_params = _inspect_model_spec(resolved, diagnostics)
    if normalized_model_params is not None:
        normalized_config["model"]["params"] = normalized_model_params

    configured_classes = resolved.data.num_classes
    manifest_classes = meta.num_classes if meta is not None and meta.num_classes else None
    effective_num_classes = configured_classes if configured_classes is not None else manifest_classes

    if pipeline is not None and model_spec is not None:
        compatibility = inspect_compatibility(
            pipeline.output_specs,
            model_spec,
            resolved.data.batching,
            num_classes=effective_num_classes,
            sample_rate=resolved.data.audio.target_sample_rate,
        )
        diagnostics.extend(compatibility.diagnostics)

    optimizer_summary, scheduler_summary = _inspect_training_options(
        resolved,
        num_classes=effective_num_classes,
        diagnostics=diagnostics,
    )
    normalized_device = _inspect_paths_and_device(resolved, diagnostics)

    summary: dict[str, Any] = {
        "dataset_id": meta.dataset_id if meta is not None else resolved.data.dataset_id,
        "manifest": str(resolved.data.manifest),
        "dataset_root": str(meta.root) if meta is not None else None,
        "splits": sorted(meta.splits) if meta is not None else [],
        "num_classes": effective_num_classes,
        "model_id": resolved.model.type,
        "model_params": normalized_model_params,
        "model_inputs": (
            {
                key: {
                    "layout": spec.layout,
                    "feature_dim": spec.feature_dim,
                    "temporal": spec.temporal,
                }
                for key, spec in model_spec.required_inputs.items()
            }
            if model_spec is not None
            else {}
        ),
        "pipeline_outputs": _spec_summary(pipeline),
        "sample_rate": resolved.data.audio.target_sample_rate,
        "batching_type": resolved.data.batching.type,
        "loss": resolved.loss.model_dump(mode="json"),
        "sampling": resolved.sampling.model_dump(mode="json"),
        "optimizer": optimizer_summary,
        "scheduler": scheduler_summary,
        "device": normalized_device,
        "amp": resolved.trainer.amp,
        "output_dir": str(resolved.output_dir),
        "checkpoint_dir": (
            str(resolved.trainer.checkpoint_dir)
            if resolved.trainer.checkpoint_dir is not None
            else None
        ),
    }
    valid = not any(diagnostic.severity == "error" for diagnostic in diagnostics)
    return ExperimentValidationResult(valid, tuple(diagnostics), normalized_config, summary)


__all__ = ["ExperimentValidationResult", "validate_experiment"]
