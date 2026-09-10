"""模型兼容性契约（设计文档 §13）。

``inspect_compatibility`` 返回结构化报告，适合 Web/dry-run 展示；
``validate_compatibility`` 保留历史 raise 语义，供 CLI、artifact loader 和训练启动
路径继续使用。两者共享完全相同的检查逻辑。

``ModelSpec`` 的正式定义已归属 ``ser_lib.models.specs``；本模块在 Stage 06
兼容性迁入 engine 前继续重导出同一类型，避免出现第二份模型契约。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ser_lib.data.config import BatchingConfig
from ser_lib.data.errors import CompatibilityError
from ser_lib.data.types import TensorSpec
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.models.specs import ModelSpec


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    """模型与数据流水线的非抛异常兼容性检查结果。"""

    compatible: bool
    diagnostics: tuple[Diagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def _problem(
    code: str,
    message: str,
    *,
    field: str | None = None,
    details: dict[str, Any] | None = None,
    suggestion: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code=code,
        message=message,
        stage="compatibility",
        field=field,
        suggestion=suggestion,
        details=details or {},
    )


def inspect_compatibility(
    representation_specs: Mapping[str, TensorSpec],
    model_spec: ModelSpec,
    batching_config: BatchingConfig,
    *,
    num_classes: int | None = None,
    sample_rate: int | None = None,
) -> CompatibilityReport:
    """检查兼容性并返回全部问题，不抛 ``CompatibilityError``。"""
    diagnostics: list[Diagnostic] = []

    missing = sorted(set(model_spec.required_inputs) - set(representation_specs))
    if missing:
        diagnostics.append(
            _problem(
                "missing_model_input",
                f"表示未提供模型必需的输入 key: {missing}（表示输出: {sorted(representation_specs)}）",
                field="required_inputs",
                details={
                    "missing_inputs": missing,
                    "available_inputs": sorted(representation_specs),
                    "model_id": model_spec.model_id,
                },
                suggestion="检查 Representation 输出 key 与模型 required_inputs 配置",
            )
        )

    for key, required in model_spec.required_inputs.items():
        actual = representation_specs.get(key)
        if actual is None:
            continue

        if actual.layout != required.layout:
            diagnostics.append(
                _problem(
                    "input_layout_mismatch",
                    f"输入 '{key}' layout 不匹配: 模型要求 {required.layout}，"
                    f"表示输出 {actual.layout}（第一版不自动转置）",
                    field=key,
                    details={
                        "model_id": model_spec.model_id,
                        "required_layout": required.layout,
                        "actual_layout": actual.layout,
                    },
                    suggestion="选择输出 layout 匹配的 Representation 或调整模型配置",
                )
            )

        if (
            required.feature_dim is not None
            and actual.feature_dim is not None
            and required.feature_dim != actual.feature_dim
        ):
            diagnostics.append(
                _problem(
                    "feature_dim_mismatch",
                    f"输入 '{key}' feature_dim 不匹配: 模型要求 {required.feature_dim}，"
                    f"表示输出 {actual.feature_dim}",
                    field=key,
                    details={
                        "model_id": model_spec.model_id,
                        "required_feature_dim": required.feature_dim,
                        "actual_feature_dim": actual.feature_dim,
                    },
                    suggestion="统一 Representation 特征维度与模型输入维度",
                )
            )

        if actual.temporal and batching_config.type == "dynamic" and not model_spec.supports_masks:
            diagnostics.append(
                _problem(
                    "mask_unsupported",
                    f"输入 '{key}' 为可变长度时序输入且批处理策略为 dynamic，"
                    f"但模型 {model_spec.model_id} 不支持 mask",
                    field=key,
                    details={
                        "model_id": model_spec.model_id,
                        "batching_type": batching_config.type,
                    },
                    suggestion="使用 fixed batching，或选择支持 mask 的模型",
                )
            )

    if not model_spec.supports_variable_length:
        if batching_config.type != "fixed":
            diagnostics.append(
                _problem(
                    "fixed_batching_required",
                    f"模型 {model_spec.model_id} 不支持可变长度输入，"
                    f"必须配置 batching.type='fixed'，实际: {batching_config.type}",
                    field="batching.type",
                    details={
                        "model_id": model_spec.model_id,
                        "actual_batching_type": batching_config.type,
                    },
                    suggestion="将 batching.type 设置为 fixed 并配置各时序输入 max_lengths",
                )
            )
        else:
            assert batching_config.fixed is not None
            temporal_keys = [key for key, spec in representation_specs.items() if spec.temporal]
            missing_lengths = [
                key for key in temporal_keys if key not in batching_config.fixed.max_lengths
            ]
            if missing_lengths:
                diagnostics.append(
                    _problem(
                        "fixed_length_missing",
                        "模型要求固定长度输入，但 fixed.max_lengths 缺少时序 key: "
                        f"{missing_lengths}",
                        field="batching.fixed.max_lengths",
                        details={"missing_inputs": missing_lengths},
                        suggestion="为所有时序输入配置 fixed.max_lengths",
                    )
                )

    if (
        num_classes is not None
        and model_spec.num_classes is not None
        and num_classes != model_spec.num_classes
    ):
        diagnostics.append(
            _problem(
                "num_classes_mismatch",
                f"类别数不一致: 数据集 {num_classes} 类，模型 {model_spec.model_id} "
                f"输出 {model_spec.num_classes} 类",
                field="num_classes",
                details={
                    "dataset_num_classes": num_classes,
                    "model_num_classes": model_spec.num_classes,
                    "model_id": model_spec.model_id,
                },
                suggestion="让数据集标签数量与模型输出类别数保持一致",
            )
        )

    if (
        model_spec.expected_sample_rate is not None
        and sample_rate is not None
        and model_spec.expected_sample_rate != sample_rate
    ):
        diagnostics.append(
            _problem(
                "sample_rate_mismatch",
                f"采样率不一致: 模型 {model_spec.model_id} 要求 "
                f"{model_spec.expected_sample_rate} Hz，数据流水线输出 {sample_rate} Hz",
                field="sample_rate",
                details={
                    "model_id": model_spec.model_id,
                    "expected_sample_rate": model_spec.expected_sample_rate,
                    "actual_sample_rate": sample_rate,
                },
                suggestion="调整 AudioLoader target_sample_rate 或选择匹配的模型",
            )
        )

    if batching_config.type == "sliding" and not model_spec.supports_variable_length:
        diagnostics.append(
            _problem(
                "sliding_batching_unsupported",
                f"批处理策略为 sliding（每批窗口数量可变），但模型 "
                f"{model_spec.model_id} 不支持可变长度输入；"
                f"滑窗推理还需要显式的窗口聚合策略",
                field="batching.type",
                details={"model_id": model_spec.model_id, "batching_type": "sliding"},
                suggestion="使用 fixed batching 或选择支持可变长度输入的模型",
            )
        )

    return CompatibilityReport(
        compatible=not any(diagnostic.severity == "error" for diagnostic in diagnostics),
        diagnostics=tuple(diagnostics),
    )


def validate_compatibility(
    representation_specs: Mapping[str, TensorSpec],
    model_spec: ModelSpec,
    batching_config: BatchingConfig,
    *,
    num_classes: int | None = None,
    sample_rate: int | None = None,
) -> None:
    """保留历史 raise 接口；内部复用 ``inspect_compatibility``。"""
    report = inspect_compatibility(
        representation_specs,
        model_spec,
        batching_config,
        num_classes=num_classes,
        sample_rate=sample_rate,
    )
    if report.compatible:
        return

    problems = [
        diagnostic.message
        for diagnostic in report.diagnostics
        if diagnostic.severity == "error"
    ]
    raise CompatibilityError(
        "模型兼容性校验失败:\n- " + "\n- ".join(problems),
        component="compatibility_check",
        stage="task_startup",
    )


__all__ = [
    "ModelSpec",
    "CompatibilityReport",
    "inspect_compatibility",
    "validate_compatibility",
]
