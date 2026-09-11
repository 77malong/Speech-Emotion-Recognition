from pathlib import Path

import pytest

import ser_lib.data.editor as editor_module
from ser_lib.data import (
    DatasetEditConflictError,
    DatasetEditError,
    DatasetEditor,
    DatasetManifest,
    DatasetTransactionError,
)


def _dataset(tmp_path: Path) -> Path:
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":0,'
        '"speaker_id":"alice","metadata":{"text":"a"}}\n'
        '{"uid":"b","audio_path":"b.wav","label":0,'
        '"speaker_id":"bob","metadata":{"text":"b"}}\n'
        '{"uid":"c","audio_path":"c.wav","label":1,'
        '"speaker_id":"carol","metadata":{"text":"c"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "val.jsonl").write_text(
        '{"uid":"d","audio_path":"d.wav","label":1,'
        '"speaker_id":"dave","metadata":{"text":"d"}}\n',
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        ""
        "dataset_id: editor-demo\n"
        "root: .\n"
        "splits:\n"
        "  train: train.jsonl\n"
        "  val: val.jsonl\n"
        "labels:\n"
        "  0: {en: neutral}\n"
        "  1: {en: happy}\n",
        encoding="utf-8",
    )
    return dataset_yaml


def test_dataset_editor_rollback_discards_in_memory_changes(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    editor = DatasetEditor(dataset_yaml)

    editor.update_record("a", label=1, speaker_id="changed")
    editor.move_records(["a"], "val")
    editor.delete_records(["b"])

    assert editor.dirty is True
    changed = editor.snapshot()
    assert changed.get_records("train")[0].uid == "c"

    editor.rollback()

    assert editor.dirty is False
    restored = editor.snapshot()
    assert [record.uid for record in restored.get_records("train")] == ["a", "b", "c"]
    assert restored.get_records("train")[0].label == 0
    assert restored.get_records("train")[0].speaker_id == "alice"


def test_dataset_editor_commit_persists_batch_edits_and_new_split(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    editor = DatasetEditor(dataset_yaml)

    editor.update_record("a", metadata={"text": "a", "reviewed": True})
    assert editor.replace_label(0, 1, split="train") == 2
    assert editor.update_speaker(["b"], "speaker-b") == 1
    assert editor.move_records(["c"], "review") == 1
    assert editor.delete_records(["d"]) == 1

    committed = editor.commit()

    assert editor.dirty is False
    assert [record.uid for record in committed.get_records("train")] == ["a", "b"]
    assert [record.label for record in committed.get_records("train")] == [1, 1]
    assert committed.get_records("train")[1].speaker_id == "speaker-b"
    assert committed.get_records("train")[0].metadata["reviewed"] is True
    assert [record.uid for record in committed.get_records("review")] == ["c"]
    assert committed.get_records("val") == []
    assert (tmp_path / "review.jsonl").exists()

    reloaded = DatasetManifest.load(dataset_yaml)
    assert [record.uid for record in reloaded.get_records("review")] == ["c"]
    assert reloaded.get_records("val") == []


def test_dataset_editor_update_record_can_clear_optional_fields(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    editor = DatasetEditor(dataset_yaml)

    updated = editor.update_record(
        "a",
        label=None,
        speaker_id=None,
        sample_rate_hint=16000,
    )

    assert updated.label is None
    assert updated.speaker_id is None
    assert updated.sample_rate_hint == 16000
    committed = editor.commit()
    record = next(record for record in committed.records if record.uid == "a")
    assert record.label is None
    assert record.speaker_id is None
    assert record.sample_rate_hint == 16000


def test_dataset_editor_rejects_unknown_uids_invalid_labels_and_unsafe_splits(
    tmp_path: Path,
):
    dataset_yaml = _dataset(tmp_path)
    editor = DatasetEditor(dataset_yaml)

    with pytest.raises(DatasetEditError, match="记录不存在"):
        editor.delete_records(["missing"])
    with pytest.raises(DatasetEditError, match="labels 表范围"):
        editor.update_record("a", label=99)
    with pytest.raises(DatasetEditError, match="路径成分"):
        editor.move_records(["a"], "../escape")


def test_dataset_editor_detects_external_concurrent_change(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    editor = DatasetEditor(dataset_yaml)
    editor.update_record("a", label=1)

    train_path = tmp_path / "train.jsonl"
    external = train_path.read_text(encoding="utf-8").replace(
        '"metadata":{"text":"a"}',
        '"metadata":{"text":"external-change"}',
    )
    train_path.write_text(external, encoding="utf-8")

    with pytest.raises(DatasetEditConflictError):
        editor.commit()

    assert "external-change" in train_path.read_text(encoding="utf-8")


def test_dataset_editor_staging_validation_failure_leaves_source_untouched(
    tmp_path: Path,
):
    dataset_yaml = _dataset(tmp_path)
    original_yaml = dataset_yaml.read_bytes()
    original_train = (tmp_path / "train.jsonl").read_bytes()
    original_val = (tmp_path / "val.jsonl").read_bytes()
    editor = DatasetEditor(dataset_yaml)

    # 人为破坏内部 staging 输入，验证 commit 的最后一道完整 Manifest 校验。
    editor._records.append(editor._records[0])

    with pytest.raises(DatasetTransactionError, match="staging Dataset 验证失败"):
        editor.commit()

    assert dataset_yaml.read_bytes() == original_yaml
    assert (tmp_path / "train.jsonl").read_bytes() == original_train
    assert (tmp_path / "val.jsonl").read_bytes() == original_val


def test_dataset_editor_commit_failure_restores_every_original_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dataset_yaml = _dataset(tmp_path)
    tracked = {
        dataset_yaml: dataset_yaml.read_bytes(),
        tmp_path / "train.jsonl": (tmp_path / "train.jsonl").read_bytes(),
        tmp_path / "val.jsonl": (tmp_path / "val.jsonl").read_bytes(),
    }
    editor = DatasetEditor(dataset_yaml)
    editor.update_record("a", label=1)
    editor.move_records(["c"], "review")

    real_replace = editor_module._commit_replace_file
    calls = 0

    def fail_during_commit(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated commit failure")
        real_replace(source, target)

    monkeypatch.setattr(editor_module, "_commit_replace_file", fail_during_commit)

    with pytest.raises(DatasetTransactionError, match="已恢复原文件"):
        editor.commit()

    for path, original in tracked.items():
        assert path.read_bytes() == original
    assert not (tmp_path / "review.jsonl").exists()
    reloaded = DatasetManifest.load(dataset_yaml)
    assert [record.uid for record in reloaded.get_records("train")] == ["a", "b", "c"]
    assert [record.uid for record in reloaded.get_records("val")] == ["d"]
