from __future__ import annotations

import json

import pytest

from ser_lib.config import BatchingConfig
from ser_lib.data import TensorSpec
from ser_lib.data.errors import CompatibilityError as DataCompatibilityError
from ser_lib.engine import CompatibilityReport, inspect_compatibility, validate_compatibility
from ser_lib.foundation.errors import CompatibilityError
from ser_lib.models import ModelSpec


def test_compatible_report_is_empty_and_json_safe():
    specs = {"features": TensorSpec(layout="FT", feature_dim=16)}
    model_spec = ModelSpec(
        model_id="cnn",
        required_inputs={"features": TensorSpec(layout="FT", feature_dim=16)},
        supports_masks=True,
        supports_variable_length=True,
        num_classes=4,
        expected_sample_rate=16000,
    )

    report = inspect_compatibility(
        specs,
        model_spec,
        BatchingConfig(type="dynamic"),
        num_classes=4,
        sample_rate=16000,
    )

    assert DataCompatibilityError is CompatibilityError
    assert report == CompatibilityReport(compatible=True, diagnostics=())
    assert report.to_dict() == {"compatible": True, "diagnostics": []}
    json.dumps(report.to_dict(), ensure_ascii=False)
    validate_compatibility(
        specs,
        model_spec,
        BatchingConfig(type="dynamic"),
        num_classes=4,
        sample_rate=16000,
    )


def test_inspection_accumulates_all_compatibility_diagnostics():
    specs = {"features": TensorSpec(layout="TD", feature_dim=8)}
    model_spec = ModelSpec(
        model_id="strict-model",
        required_inputs={"features": TensorSpec(layout="FT", feature_dim=16)},
        supports_masks=False,
        supports_variable_length=False,
        num_classes=6,
        expected_sample_rate=16000,
    )

    report = inspect_compatibility(
        specs,
        model_spec,
        BatchingConfig(type="dynamic"),
        num_classes=4,
        sample_rate=8000,
    )

    assert report.compatible is False
    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "input_layout_mismatch",
        "feature_dim_mismatch",
        "mask_unsupported",
        "fixed_batching_required",
        "num_classes_mismatch",
        "sample_rate_mismatch",
    ]
    assert all(diagnostic.severity == "error" for diagnostic in report.diagnostics)
    assert all(diagnostic.stage == "compatibility" for diagnostic in report.diagnostics)
    assert report.diagnostics[0].field == "features"
    assert report.diagnostics[-1].details["expected_sample_rate"] == 16000
    json.dumps(report.to_dict(), ensure_ascii=False)


def test_missing_inputs_have_machine_readable_details():
    model_spec = ModelSpec(
        model_id="needs-two-inputs",
        required_inputs={
            "features": TensorSpec(layout="FT", feature_dim=16),
            "embedding": TensorSpec(layout="D", feature_dim=8),
        },
        supports_masks=True,
        supports_variable_length=True,
        num_classes=2,
    )

    report = inspect_compatibility(
        {"features": TensorSpec(layout="FT", feature_dim=16)},
        model_spec,
        BatchingConfig(type="dynamic"),
    )

    diagnostic = report.diagnostics[0]
    assert diagnostic.code == "missing_model_input"
    assert diagnostic.field == "required_inputs"
    assert diagnostic.details["missing_inputs"] == ["embedding"]
    assert diagnostic.details["available_inputs"] == ["features"]


def test_validate_compatibility_reuses_report_and_preserves_raise_contract():
    specs = {"features": TensorSpec(layout="FT", feature_dim=8)}
    model_spec = ModelSpec(
        model_id="cnn",
        required_inputs={"features": TensorSpec(layout="FT", feature_dim=16)},
        supports_masks=True,
        supports_variable_length=True,
        num_classes=2,
    )

    report = inspect_compatibility(specs, model_spec, BatchingConfig(type="dynamic"))
    assert [item.code for item in report.diagnostics] == ["feature_dim_mismatch"]

    with pytest.raises(CompatibilityError) as caught:
        validate_compatibility(specs, model_spec, BatchingConfig(type="dynamic"))

    error = caught.value
    assert error.code == "compatibility_error"
    assert "模型兼容性校验失败" in str(error)
    assert "feature_dim 不匹配" in str(error)
    assert error.component == "compatibility_check"
    assert error.stage == "task_startup"
