from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ser_lib.core import Diagnostic
from ser_lib.data.errors import (
    AudioDecodeError,
    AudioNotFoundError,
    CollationError,
    CompatibilityError,
    InvalidAudioSegmentError,
    ManifestError,
    RegistryError,
    RepresentationError,
    TransformError,
)
from ser_lib.data.importers import ImportIssue, ImportPreview


def test_diagnostic_is_json_safe_and_validates_contract(tmp_path: Path):
    diagnostic = Diagnostic(
        severity="warning",
        code="audio_missing",
        message="音频不存在",
        stage="dataset_scan",
        field="audio_path",
        path=tmp_path / "a.wav",
        uid="sample-a",
        suggestion="检查数据集根路径",
        details={
            "attempt": 2,
            "when": datetime(2026, 9, 8, tzinfo=timezone.utc),
            "paths": [tmp_path / "a.wav"],
        },
    )

    payload = diagnostic.to_dict()
    assert payload["severity"] == "warning"
    assert payload["path"] == str(tmp_path / "a.wav")
    assert payload["details"]["when"].endswith("+00:00")
    assert payload["details"]["paths"] == [str(tmp_path / "a.wav")]
    json.dumps(payload, ensure_ascii=False)

    with pytest.raises(ValueError, match="severity"):
        Diagnostic("fatal", "bad", "message")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="code"):
        Diagnostic("error", "bad-code", "message")
    with pytest.raises(TypeError, match="不可 JSON"):
        Diagnostic("error", "bad_details", "message", details={"value": object()})


def test_diagnostic_from_ser_error_preserves_machine_context(tmp_path: Path):
    error = ManifestError(
        "manifest 无法读取",
        uid="record-1",
        path=tmp_path / "dataset.yaml",
        component="manifest",
        stage="load",
    )

    diagnostic = Diagnostic.from_error(error, suggestion="检查 YAML 格式")

    assert diagnostic.severity == "error"
    assert diagnostic.code == "manifest_error"
    assert diagnostic.uid == "record-1"
    assert diagnostic.path == str(tmp_path / "dataset.yaml")
    assert diagnostic.stage == "load"
    assert diagnostic.suggestion == "检查 YAML 格式"
    assert diagnostic.details["component"] == "manifest"
    json.dumps(diagnostic.to_dict(), ensure_ascii=False)


def test_data_error_subclasses_expose_stable_codes():
    cases = [
        (ManifestError, "manifest_error"),
        (AudioNotFoundError, "audio_not_found"),
        (AudioDecodeError, "audio_decode_error"),
        (InvalidAudioSegmentError, "audio_invalid_segment"),
        (RepresentationError, "representation_error"),
        (TransformError, "transform_error"),
        (CollationError, "collation_error"),
        (CompatibilityError, "compatibility_error"),
        (RegistryError, "registry_error"),
    ]

    for error_type, expected_code in cases:
        error = error_type("failed")
        assert error.code == expected_code
        assert error.to_dict()["code"] == expected_code


def test_import_preview_bridges_legacy_issues_and_warnings_to_diagnostics(tmp_path: Path):
    # 前五个位置参数保持历史 ImportIssue 构造方式不变。
    issue = ImportIssue(3, tmp_path / "broken.wav", "validate", "无法解析", "bad header")
    preview = ImportPreview(
        importer_id="folder",
        issues=[issue],
        warnings=["许可证需要确认"],
        structured_diagnostics=[
            Diagnostic("info", "import_hint", "建议检查标签映射", stage="map_labels")
        ],
    )

    diagnostics = preview.diagnostics
    assert [item.severity for item in diagnostics] == ["error", "warning", "info"]
    assert [item.code for item in diagnostics] == [
        "import_issue",
        "import_warning",
        "import_hint",
    ]
    assert diagnostics[0].details == {"entry_index": 3, "detail": "bad header"}
    assert preview.ok is False

    payload = preview.summary()
    assert payload["num_issues"] == 1
    assert payload["issues"][0]["entry_index"] == 3
    assert payload["warnings"] == ["许可证需要确认"]
    assert payload["num_diagnostics"] == 3
    assert payload["diagnostics"][0]["code"] == "import_issue"
    json.dumps(payload, ensure_ascii=False)


def test_warning_only_import_preview_remains_ok():
    preview = ImportPreview(importer_id="ravdess", warnings=["license warning"])

    assert preview.ok is True
    assert len(preview.diagnostics) == 1
    assert preview.diagnostics[0].severity == "warning"
