from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import ser_lib
from ser_lib._version import __version__
from ser_lib.foundation.events import CheckpointEvent
from ser_lib.foundation import CancellationToken, OperationCancelled, ProgressEvent, SERError
from ser_lib.foundation.events import PredictionEvent


def test_version_source_is_independent_and_root_reexports_it():
    assert ser_lib.__version__ == __version__


def test_foundation_import_does_not_eagerly_load_heavy_domains():
    code = """
import sys
import ser_lib.foundation
for name in ("torch", "ser_lib.models", "ser_lib.engine", "ser_lib.inference"):
    assert name not in sys.modules, name
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_foundation_has_no_reverse_domain_imports():
    root = Path(__file__).resolve().parents[1] / "ser_lib" / "foundation"
    forbidden = {
        "ser_lib.data",
        "ser_lib.models",
        "ser_lib.engine",
        "ser_lib.inference",
        "ser_lib.artifacts",
        "ser_lib.cli",
    }
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert not any(
            imported == prefix or imported.startswith(prefix + ".")
            for imported in imports
            for prefix in forbidden
        ), path.name


def test_retired_core_source_package_is_absent():
    root = Path(__file__).resolve().parents[1] / "ser_lib"
    assert not (root / "core").exists()


def test_retired_error_and_event_modules_are_absent():
    root = Path(__file__).resolve().parents[1] / "ser_lib"
    assert not (root / "data" / "errors.py").exists()
    assert not (root / "engine" / "events.py").exists()
    assert not (root / "inference" / "events.py").exists()
    assert not (root / "foundation" / "errors.py").exists()
    assert not (root / "foundation" / "events.py").exists()
    assert (root / "foundation" / "errors").is_dir()
    assert (root / "foundation" / "events").is_dir()


def test_domain_events_have_canonical_owners():
    assert CheckpointEvent.__module__ == "ser_lib.foundation.events.training"
    assert PredictionEvent.__module__ == "ser_lib.foundation.events.inference"


def test_domain_and_foundation_events_share_global_sequence():
    progress = ProgressEvent(stage="sequence", completed=0, total=1)
    checkpoint = CheckpointEvent(
        action="saved",
        kind="last",
        path="last.pt",
        epoch=1,
    )
    prediction = PredictionEvent(uid="sample", emotion="neutral", confidence=0.8)
    assert progress.sequence < checkpoint.sequence < prediction.sequence


def test_cancellation_uses_foundation_error_identity():
    token = CancellationToken()
    token.cancel()
    try:
        token.raise_if_cancelled()
    except SERError as exc:
        assert isinstance(exc, OperationCancelled)
        assert exc.code == "operation_cancelled"
    else:
        raise AssertionError("CancellationToken must raise OperationCancelled")


def test_artifacts_no_longer_import_version_from_root_package():
    root = Path(__file__).resolve().parents[1] / "ser_lib" / "artifacts"
    for name in ("exporter.py", "loader.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "from ser_lib import __version__" not in source
        if name == "exporter.py":
            assert "from ser_lib._version import __version__" in source
        else:
            assert "from ser_lib._version import __version__" not in source
