from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ser_lib.data.importers.csv_importer import CsvImporter
from ser_lib.data.manifest import DatasetManifest


def _write_existing_dataset(destination: Path) -> tuple[str, str]:
    destination.mkdir(parents=True)
    manifest_text = '{"uid":"old","audio_path":"old.wav","label":0}\n'
    yaml_text = yaml.safe_dump(
        {
            "schema_version": 1,
            "dataset_id": "existing",
            "root": ".",
            "splits": {"default": "manifest.jsonl"},
            "labels": {"0": {"en": "neutral"}},
        },
        allow_unicode=True,
        sort_keys=False,
    )
    (destination / "manifest.jsonl").write_text(manifest_text, encoding="utf-8")
    (destination / "dataset.yaml").write_text(yaml_text, encoding="utf-8")
    DatasetManifest.load(destination / "dataset.yaml")
    return yaml_text, manifest_text


def test_failed_csv_conversion_does_not_replace_existing_dataset(tmp_path: Path):
    destination = tmp_path / "dataset"
    old_yaml, old_manifest = _write_existing_dataset(destination)
    source = tmp_path / "duplicate.csv"
    source.write_text(
        "audio,label,uid\n"
        "a.wav,happy,duplicate\n"
        "b.wav,sad,duplicate\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        CsvImporter().convert(
            source,
            destination,
            {
                "audio_path_column": "audio",
                "label_column": "label",
                "uid_column": "uid",
            },
        )

    assert (destination / "dataset.yaml").read_text(encoding="utf-8") == old_yaml
    assert (destination / "manifest.jsonl").read_text(encoding="utf-8") == old_manifest
    manifest = DatasetManifest.load(destination / "dataset.yaml")
    assert [record.uid for record in manifest.records] == ["old"]
