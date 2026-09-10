from __future__ import annotations

from pathlib import Path

import yaml

from ser_lib.data.manifest import DatasetManifest


def test_manifest_write_preserves_same_basename_split_subdirectories(tmp_path: Path):
    train_dir = tmp_path / "train"
    val_dir = tmp_path / "val"
    train_dir.mkdir()
    val_dir.mkdir()
    (train_dir / "items.jsonl").write_text(
        '{"uid":"train-a","audio_path":"train-a.wav","label":0}\n',
        encoding="utf-8",
    )
    (val_dir / "items.jsonl").write_text(
        '{"uid":"val-a","audio_path":"val-a.wav","label":1}\n',
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "dataset_id": "nested-splits",
                "root": ".",
                "splits": {
                    "train": "train/items.jsonl",
                    "val": "val/items.jsonl",
                },
                "labels": {
                    "0": {"en": "neutral"},
                    "1": {"en": "happy"},
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest = DatasetManifest.load(dataset_yaml)
    before = {
        record.uid: manifest.record_splits[record.uid]
        for record in manifest.records
    }

    manifest.write()

    document = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))
    assert document["splits"] == {
        "train": "train/items.jsonl",
        "val": "val/items.jsonl",
    }
    assert (train_dir / "items.jsonl").is_file()
    assert (val_dir / "items.jsonl").is_file()

    reloaded = DatasetManifest.load(dataset_yaml)
    after = {
        record.uid: reloaded.record_splits[record.uid]
        for record in reloaded.records
    }
    assert after == before == {"train-a": "train", "val-a": "val"}
