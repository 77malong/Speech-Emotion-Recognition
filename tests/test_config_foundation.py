from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import ser_lib.config.base as config_base
import ser_lib.config.loader as config_loader
import ser_lib.data.config as legacy_data_config
from ser_lib.config import (
    AudioConfig,
    BatchingConfig,
    CacheConfig,
    ComponentConfig,
    DataConfig,
    StrictConfig,
    load_data_config,
    load_versioned_config,
    load_yaml_mapping,
    require_schema_version,
    resolve_config_path,
)


def test_config_import_does_not_eagerly_load_runtime_domains():
    code = """
import sys
import ser_lib.config
for name in (
    "torch",
    "transformers",
    "ser_lib.data",
    "ser_lib.models",
    "ser_lib.engine",
    "ser_lib.inference",
):
    assert name not in sys.modules, name
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_config_package_has_no_runtime_domain_reverse_imports():
    root = Path(__file__).resolve().parents[1] / "ser_lib" / "config"
    forbidden = {
        "ser_lib.data",
        "ser_lib.models",
        "ser_lib.engine",
        "ser_lib.inference",
        "ser_lib.artifacts",
        "ser_lib.cli",
    }
    for path in root.glob("*.py"):
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


def test_config_public_exports_are_identity_with_canonical_modules():
    assert config_base.StrictConfig is StrictConfig
    assert config_loader.resolve_config_path is resolve_config_path
    assert config_loader.require_schema_version is require_schema_version
    assert config_loader.load_yaml_mapping is load_yaml_mapping
    assert config_loader.load_versioned_config is load_versioned_config


def test_data_config_old_names_are_aliases_of_canonical_schema():
    assert legacy_data_config.AudioSettings is AudioConfig
    assert legacy_data_config.CacheSettings is CacheConfig
    assert legacy_data_config.ComponentConfig is ComponentConfig
    assert legacy_data_config.BatchingConfig is BatchingConfig
    assert legacy_data_config.DataConfig is DataConfig

    from ser_lib.data.audio import AudioLoaderConfig

    assert AudioLoaderConfig is AudioConfig


def test_audio_config_preserves_payload_defaults_and_strict_validation():
    payload = AudioConfig().model_dump(mode="json")
    assert payload == {
        "target_sample_rate": 16000,
        "mono": True,
        "normalize_peak": False,
        "backend": "soundfile",
    }
    assert AudioConfig.model_validate(payload).model_dump(mode="json") == payload
    with pytest.raises(ValidationError):
        AudioConfig.model_validate({**payload, "target_sample_rate_typo": 8000})
    with pytest.raises(ValidationError):
        AudioConfig(target_sample_rate=999)


def test_data_config_round_trip_and_relative_paths_are_based_on_yaml(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    path = config_dir / "demo.yaml"
    path.write_text(
        "schema_version: 1\n"
        "manifest: ../data/dataset.yaml\n"
        "cache:\n"
        "  enabled: true\n"
        "  directory: ../cache/features\n"
        "representation:\n"
        "  type: waveform\n",
        encoding="utf-8",
    )

    loaded = load_data_config(path)
    assert loaded.manifest == (config_dir / "../data/dataset.yaml").resolve()
    assert loaded.cache.directory == (config_dir / "../cache/features").resolve()
    dumped = loaded.model_dump(mode="json")
    assert DataConfig.model_validate(dumped).model_dump(mode="json") == dumped
    assert loaded.audio is not None
    assert isinstance(loaded.audio, AudioConfig)
    assert isinstance(loaded.cache, CacheConfig)


def test_data_config_default_cache_path_is_also_based_on_yaml(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    path = config_dir / "demo.yaml"
    path.write_text(
        "schema_version: 1\n"
        "manifest: dataset.yaml\n"
        "representation:\n"
        "  type: waveform\n",
        encoding="utf-8",
    )

    loaded = load_data_config(path)

    assert loaded.cache.directory == (config_dir / ".ser-cache/features").resolve()


def test_batching_and_label_validation_remain_strict():
    with pytest.raises(ValidationError, match="fixed"):
        DataConfig(
            manifest=Path("dataset.yaml"),
            representation=ComponentConfig(type="waveform"),
            batching=BatchingConfig(type="fixed"),
        )
    with pytest.raises(ValidationError, match="labels"):
        DataConfig(
            manifest=Path("dataset.yaml"),
            representation=ComponentConfig(type="waveform"),
            labels={1: {"en": "happy"}},
        )


def test_strict_config_remains_frozen_and_forbids_unknown_fields():
    class Example(StrictConfig):
        name: str

    with pytest.raises(ValidationError):
        Example(name="demo", typo=True)
    value = Example(name="demo")
    with pytest.raises(ValidationError):
        value.name = "changed"
