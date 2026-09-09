"""实验启动前的无副作用 dry-run 校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from ser_lib.data.manifest import ManifestMeta, load_meta
from ser_lib.data.pipeline import SamplePipeline, build_pipeline
from ser_lib.data.validation import ModelSpec, inspect_compatibility
from ser_lib.engine.config import ExperimentConfig, load_experiment_config
from ser_lib.engine.optim import parse_optimizer_config, parse_scheduler_config
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.models.registry import model_registry


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
    try:
        return load_experiment_config(value), []
    except Exception as exc:
        return None, [
            _diagnostic(
                "experiment_config_invalid",
                str(exc),
                path=value,
                suggestion="修正配置 schema、字段类型或相对路径后重试",
            )
        ]


def validate_experiment(
    value: ExperimentConfig | Path | str,
    *,
    check_dataset: bool = True,
    check_device: bool = True,
) -> ExperimentValidationResult:
    """执行不加载模型权重、不打开音频的实验预检。"""
    config, diagnostics = _load_config(value)
    if config is None:
        return ExperimentValidationResult(False, tuple(diagnostics), {}, {})

    normalized = config.model_dump(mode="json")
    summary: dict[str, Any] = {
        "model_type": config.model.type,
        "device": config.trainer.device,
        "batching_type": config.data.batching.type,
        "num_classes": config.data.num_classes,
    }

    try:
        model_params = model_registry.validate_config(config.model.type, config.model.params)
        model = model_registry.create(config.model.type, **model_params)
        summary["model_id"] = model.model_spec.model_id
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "model_config_invalid",
                str(exc),
                field="model",
                suggestion="检查 model.type 与 model.params 是否匹配已注册模型 schema",
            )
        )
        model = None

    try:
        pipeline: SamplePipeline = build_pipeline(config.data, train=True)
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "pipeline_config_invalid",
                str(exc),
                field="data",
                suggestion="检查表示、变换与 batching 配置",
            )
        )
        pipeline = None  # type: ignore[assignment]

    if model is not None and pipeline is not None:
        report = inspect_compatibility(
            pipeline.output_specs,
            model.model_spec,
            config.data.batching,
            num_classes=config.data.num_classes,
            sample_rate=config.data.audio.target_sample_rate,
        )
        diagnostics.extend(report.diagnostics)

    try:
        parse_optimizer_config(config.optimizer)
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "optimizer_config_invalid",
                str(exc),
                field="optimizer",
            )
        )

    try:
        parse_scheduler_config(config.scheduler)
    except Exception as exc:
        diagnostics.append(
            _diagnostic(
                "scheduler_config_invalid",
                str(exc),
                field="scheduler",
            )
        )

    if check_dataset:
        try:
            meta: ManifestMeta = load_meta(config.data.manifest_path)
            summary["dataset_id"] = meta.dataset_id
            summary["dataset_splits"] = sorted(meta.splits)
            if meta.labels and len(meta.labels) != config.data.num_classes:
                diagnostics.append(
                    _diagnostic(
                        "dataset_num_classes_mismatch",
                        f"dataset labels={len(meta.labels)} 与 data.num_classes="
                        f"{config.data.num_classes} 不一致",
                        field="data.num_classes",
                        path=config.data.manifest_path,
                    )
                )
        except Exception as exc:
            diagnostics.append(
                _diagnostic(
                    "dataset_manifest_invalid",
                    str(exc),
                    field="data.manifest_path",
                    path=config.data.manifest_path,
                    suggestion="检查 dataset.yaml 是否存在且 schema/路径合法",
                )
            )

    if check_device and config.trainer.device.startswith("cuda") and not torch.cuda.is_available():
        diagnostics.append(
            _diagnostic(
                "device_unavailable",
                f"训练设备 {config.trainer.device!r} 请求 CUDA，但当前环境不可用",
                field="trainer.device",
                suggestion="改用 cpu 或在 CUDA 环境运行",
            )
        )

    valid = not any(item.severity == "error" for item in diagnostics)
    return ExperimentValidationResult(valid, tuple(diagnostics), normalized, summary)


__all__ = ["ExperimentValidationResult", "validate_experiment"]
