from __future__ import annotations

from pathlib import Path

from ser_lib.data.importers.csv_importer import CsvImporter


def _write_csv(path: Path, labels: list[str]) -> None:
    lines = ["audio,label"]
    lines.extend(f"sample-{index}.wav,{label}" for index, label in enumerate(labels))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _scan(tmp_path: Path, labels: list[str], **config):
    source = tmp_path / "data.csv"
    _write_csv(source, labels)
    return CsvImporter().scan(
        source,
        {
            "audio_path_column": "audio",
            "label_column": "label",
            **config,
        },
    )


def test_csv_pure_numeric_labels_preserve_numeric_ids(tmp_path: Path):
    preview = _scan(tmp_path, ["1", "3"])

    assert preview.ok
    assert preview.label_mapping == {"1": 1, "3": 3}
    assert [record.label for record in preview.records] == [1, 3]


def test_csv_pure_text_labels_use_one_canonical_mapping(tmp_path: Path):
    preview = _scan(tmp_path, ["sad", "happy", "sad"])

    assert preview.ok
    assert preview.label_mapping == {"happy": 0, "sad": 1}
    assert [record.label for record in preview.records] == [1, 0, 1]


def test_csv_mixed_numeric_and_text_labels_do_not_silently_merge(tmp_path: Path):
    preview = _scan(tmp_path, ["1", "happy"])

    assert preview.ok
    assert preview.label_mapping == {"1": 0, "happy": 1}
    assert [record.label for record in preview.records] == [0, 1]


def test_csv_explicit_mapping_is_used_for_every_nonempty_label(tmp_path: Path):
    preview = _scan(
        tmp_path,
        ["1", "happy"],
        label_mapping={"1": 7, "happy": 2},
    )

    assert preview.ok
    assert preview.label_mapping == {"1": 7, "happy": 2}
    assert [record.label for record in preview.records] == [7, 2]
