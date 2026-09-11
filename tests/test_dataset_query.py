from itertools import islice
from pathlib import Path

import pytest

from ser_lib.data import iter_records


def _dataset(tmp_path: Path) -> Path:
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"train-happy","audio_path":"speaker-a/happy.wav","label":1,'
        '"speaker_id":"alice","metadata":{"text":"hello world","lang":"en"}}\n'
        '{"uid":"train-neutral","audio_path":"speaker-b/neutral.wav","label":0,'
        '"speaker_id":"bob","metadata":{"text":"你好世界","lang":"zh"}}\n'
        '{"uid":"train-unlabeled","audio_path":"speaker-c/sample.wav",'
        '"speaker_id":"carol","metadata":{"note":"review me"}}\n',
        encoding="utf-8",
    )
    (tmp_path / "val.jsonl").write_text(
        '{"uid":"val-happy","audio_path":"speaker-a/val.wav","label":1,'
        '"speaker_id":"alice","metadata":{"text":"validation"}}\n',
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        ""
        "dataset_id: query-demo\n"
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


def test_iter_records_filters_and_preserves_manifest_order(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    records = list(iter_records(dataset_yaml, split="train", label_id=1))

    assert [record.uid for record in records] == ["train-happy"]
    assert records[0].audio_path.as_posix() == "speaker-a/happy.wav"
    assert records[0].label == 1


def test_iter_records_supports_speaker_keyword_and_unicode(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    speaker_records = list(iter_records(dataset_yaml, speaker_id="alice"))
    assert [record.uid for record in speaker_records] == ["train-happy", "val-happy"]

    keyword_records = list(iter_records(dataset_yaml, keyword="你好"))
    assert [record.uid for record in keyword_records] == ["train-neutral"]

    path_records = list(iter_records(dataset_yaml, keyword="SPEAKER-C"))
    assert [record.uid for record in path_records] == ["train-unlabeled"]


def test_iter_records_supports_caller_side_pagination(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    records = iter_records(dataset_yaml)

    first = list(islice(records, 2))
    second = list(islice(records, 2))

    assert [record.uid for record in first] == ["train-happy", "train-neutral"]
    assert [record.uid for record in second] == ["train-unlabeled", "val-happy"]


def test_iter_records_validates_filters(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    with pytest.raises(ValueError, match="split"):
        list(iter_records(dataset_yaml, split=""))
    with pytest.raises(ValueError, match="speaker_id"):
        list(iter_records(dataset_yaml, speaker_id=""))
