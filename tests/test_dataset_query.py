import json
from pathlib import Path

import pytest

from ser_lib.data import RecordPage, query_records


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
        "schema_version: 1\n"
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


def test_query_records_filters_and_preserves_manifest_order(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    page = query_records(dataset_yaml, split="train", label_id=1)

    assert isinstance(page, RecordPage)
    assert page.total == 1
    assert [item.uid for item in page.items] == ["train-happy"]
    assert page.items[0].split == "train"
    assert page.items[0].audio_path == "speaker-a/happy.wav"
    assert page.items[0].label_id == 1


def test_query_records_supports_speaker_keyword_and_unicode(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    speaker_page = query_records(dataset_yaml, speaker_id="alice")
    assert [item.uid for item in speaker_page.items] == ["train-happy", "val-happy"]

    keyword_page = query_records(dataset_yaml, keyword="你好")
    assert keyword_page.total == 1
    assert keyword_page.items[0].uid == "train-neutral"

    path_page = query_records(dataset_yaml, keyword="SPEAKER-C")
    assert path_page.total == 1
    assert path_page.items[0].uid == "train-unlabeled"


def test_query_records_returns_stable_pagination_metadata(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    first = query_records(dataset_yaml, offset=0, limit=2)
    second = query_records(dataset_yaml, offset=2, limit=2)

    assert [item.uid for item in first.items] == ["train-happy", "train-neutral"]
    assert first.total == 4
    assert first.offset == 0
    assert first.limit == 2
    assert first.has_more is True

    assert [item.uid for item in second.items] == ["train-unlabeled", "val-happy"]
    assert second.total == 4
    assert second.offset == 2
    assert second.limit == 2
    assert second.has_more is False
    payload = second.to_dict()
    assert payload["has_more"] is False
    json.dumps(payload, ensure_ascii=False)


def test_query_records_validates_pagination(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)

    with pytest.raises(ValueError, match="offset"):
        query_records(dataset_yaml, offset=-1)
    with pytest.raises(ValueError, match="limit"):
        query_records(dataset_yaml, limit=0)
