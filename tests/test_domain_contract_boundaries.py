from __future__ import annotations

import ast
from pathlib import Path

import torch

import ser_lib.engine as engine
import ser_lib.models as models
from ser_lib.data.types import SERBatch, move_batch_to_device
from ser_lib.engine.compatibility import CompatibilityReport
from ser_lib.engine.training import move_batch_to_device as trainer_move_batch_to_device
from ser_lib.foundation.errors import CompatibilityError, RegistryError
from ser_lib.inference import StreamingLatency
from ser_lib.models.specs import ModelSpec
from ser_lib.runtime import RuntimeMetrics


_ROOT = Path(__file__).resolve().parents[1]
_SER_LIB = _ROOT / "ser_lib"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def _assert_tree_avoids(root: Path, forbidden_prefixes: tuple[str, ...]) -> None:
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for imported in sorted(_imports(path)):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden_prefixes
            ):
                violations.append(f"{path.relative_to(_ROOT)} -> {imported}")
    assert violations == []


def test_domain_contracts_have_canonical_owners():
    assert ModelSpec.__module__ == "ser_lib.models.specs"
    assert models.ModelSpec is ModelSpec
    assert CompatibilityReport.__module__ == "ser_lib.engine.compatibility"
    assert engine.CompatibilityReport is CompatibilityReport
    assert RegistryError.__module__ == "ser_lib.foundation.errors.base"
    assert CompatibilityError.__module__ == "ser_lib.foundation.errors.engine"
    assert RuntimeMetrics.__module__ == "ser_lib.runtime"
    assert StreamingLatency.__module__ == "ser_lib.inference.streaming"


def test_batch_device_transfer_has_one_owner_and_preserves_non_tensor_metadata():
    metadata = [{"speaker": "speaker-1"}, {"speaker": "speaker-2"}]
    uids = ["a", "b"]
    batch = SERBatch(
        inputs={"features": torch.tensor([[1.0, 2.0], [3.0, 4.0]])},
        lengths={"features": torch.tensor([2, 1], dtype=torch.long)},
        masks={"features": torch.tensor([[True, True], [True, False]])},
        labels=torch.tensor([0, 1], dtype=torch.long),
        uids=uids,
        metadata=metadata,
        window_map=torch.tensor([0, 1], dtype=torch.long),
    )

    moved = move_batch_to_device(batch, torch.device("cpu"))

    assert trainer_move_batch_to_device is move_batch_to_device
    assert moved.uids is uids
    assert moved.metadata is metadata
    assert torch.equal(moved.inputs["features"], batch.inputs["features"])
    assert torch.equal(moved.lengths["features"], batch.lengths["features"])
    assert torch.equal(moved.masks["features"], batch.masks["features"])
    assert torch.equal(moved.labels, batch.labels)
    assert torch.equal(moved.window_map, batch.window_map)


def test_data_does_not_reverse_import_models_or_engine():
    _assert_tree_avoids(_SER_LIB / "data", ("ser_lib.models", "ser_lib.engine"))
    assert not (_SER_LIB / "data" / "validation.py").exists()


def test_models_do_not_import_dataset_implementation():
    _assert_tree_avoids(_SER_LIB / "models", ("ser_lib.data.dataset",))


def test_retired_trainer_modules_are_absent():
    assert not (_SER_LIB / "engine" / "trainer.py").exists()
    assert not (_SER_LIB / "engine" / "_trainer_core.py").exists()
    assert (_SER_LIB / "engine" / "training" / "trainer.py").is_file()


def test_inference_does_not_import_trainer_implementation():
    _assert_tree_avoids(
        _SER_LIB / "inference",
        ("ser_lib.engine.training.trainer",),
    )


def test_foundation_and_config_remain_free_of_domain_reverse_imports():
    forbidden = (
        "ser_lib.data",
        "ser_lib.models",
        "ser_lib.engine",
        "ser_lib.inference",
        "ser_lib.artifacts",
        "ser_lib.cli",
        "ser_lib.services",
    )
    _assert_tree_avoids(_SER_LIB / "foundation", forbidden)
    _assert_tree_avoids(_SER_LIB / "config", forbidden)


def test_cli_uses_domain_public_surfaces():
    workflow_imports = _imports(_SER_LIB / "cli" / "workflows.py")
    assert "ser_lib.engine" in workflow_imports
    assert "ser_lib.engine.experiment" not in workflow_imports
    assert "ser_lib.engine.lineage" not in workflow_imports

    main_imports = _imports(_SER_LIB / "cli" / "main.py")
    assert "ser_lib.foundation" in main_imports
    assert "ser_lib.foundation.errors" not in main_imports
