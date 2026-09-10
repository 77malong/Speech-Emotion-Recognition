from __future__ import annotations

from pathlib import Path

from ser_lib.data.importers.csv_importer import CsvImporter


def test_csv_relative_root_is_applied_once_from_destination_manifest(tmp_path: Path):
    source_dir = tmp_path / "source"
    destination = tmp_path / "exported"
    source_dir.mkdir()
    source = source_dir / "data.csv"
    source.write_text("audio,label\na.wav,happy\n", encoding="utf-8")

    manifest = CsvImporter().convert(
        source,
        destination,
        {
            "audio_path_column": "audio",
            "label_column": "label",
            "root": "audio",
        },
    )

    assert manifest.meta.root == destination / "audio"
    assert manifest.records[0].audio_path == Path("a.wav")
    assert manifest.resolved_records("default")[0].audio_path == destination / "audio" / "a.wav"
