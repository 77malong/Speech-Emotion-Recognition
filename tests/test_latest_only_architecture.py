from __future__ import annotations

from pathlib import Path

import ser_lib.engine as engine
import ser_lib.runtime as runtime


_ROOT = Path(__file__).resolve().parents[1]
_SER_LIB = _ROOT / "ser_lib"


_RETIRED_SOURCE_TERMS = (
    "ser_lib.data.config",
    "ser_lib.engine.config",
    "ser_lib.data.errors",
    "ser_lib.engine.events",
    "ser_lib.inference.events",
    "DatasetEditor",
    "DatasetEditError",
    "DatasetRevision",
    "create_dataset_revision",
    "restore_dataset_revision",
    "iter_records",
    "AudioSettings",
    "CacheSettings",
    "_TrainerCore",
    "allow_legacy_pickle",
    "SchemaMigration",
    "migrate_schema_payload",
    "EvaluationRunInfo",
    "TrainingRunInfo",
    "TrainingHistoryInfo",
    "RuntimeMetrics",
    "get_runtime_metrics",
    "schema_version",
    "format_version",
    "0.2.x 兼容",
    "面向 Web",
    "Web 训练曲线",
)


def test_production_source_contains_no_retired_latest_only_contracts():
    violations: list[str] = []
    for path in sorted(_SER_LIB.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for term in _RETIRED_SOURCE_TERMS:
            if term in text:
                violations.append(f"{path.relative_to(_ROOT)}: {term}")
    assert violations == []


def test_retired_modules_and_management_catalogs_are_absent():
    retired_paths = (
        "data/config.py",
        "data/editor.py",
        "data/history.py",
        "data/query.py",
        "engine/config.py",
        "engine/trainer.py",
        "engine/_trainer_core.py",
        "engine/evaluation_catalog.py",
        "benchmark.py",
        "services",
        "catalog.py",
    )
    for relative in retired_paths:
        assert not (_SER_LIB / relative).exists(), relative

    retired_engine_api = (
        "TrainingRunCatalog",
        "TrainingRunScanFailure",
        "scan_training_runs",
        "EvaluationRunCatalog",
        "EvaluationRunScanFailure",
        "scan_evaluation_runs",
    )
    for name in retired_engine_api:
        assert not hasattr(engine, name), name

    assert not hasattr(runtime, "RuntimeMetrics")
    assert not hasattr(runtime, "get_runtime_metrics")


def test_current_config_templates_do_not_carry_format_versions():
    for path in sorted((_ROOT / "configs").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        assert "schema_version" not in text, path.name
        assert "format_version" not in text, path.name


def test_project_metadata_has_no_retired_compatibility_extras():
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "pretrained = [" not in pyproject
    assert "psutil" not in pyproject


def test_review_docs_are_explicitly_historical():
    review_readme = (
        _ROOT / "docs" / "development" / "review" / "README.md"
    ).read_text(encoding="utf-8")
    assert "历史架构基线" in review_readme
    assert "不代表当前 API" in review_readme


def test_examples_do_not_use_retired_public_api():
    retired_terms = (
        "load_training_run_info",
        "load_evaluation_run_info",
        "TrainingRunInfo",
        "EvaluationRunInfo",
        "TrainingHistoryInfo",
        "get_runtime_metrics",
        "RuntimeMetrics",
        "ser_lib.benchmark",
        "ser_lib.engine.config",
        "ser_lib.data.config",
    )
    violations: list[str] = []
    for path in sorted((_ROOT / "examples").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for term in retired_terms:
            if term in text:
                violations.append(f"{path.relative_to(_ROOT)}: {term}")
    assert violations == []
