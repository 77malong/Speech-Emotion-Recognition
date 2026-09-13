"""Data-boundary review probes for 64ff7e2; writes only temporary fixtures."""

import json
import tempfile
from pathlib import Path

import torch
import yaml

from ser_lib.foundation.errors import RepresentationError

from ser_lib.data.manifest import DatasetManifest, ManifestMeta
from ser_lib.data.dataset import SERDataset
from ser_lib.data.pipeline import SamplePipeline
from ser_lib.data.representations.waveform import RawWaveform
from ser_lib.data.types import AudioData, AudioRecord, RepresentationOutput


def unassigned_collision(root):
    root.mkdir()
    records = [AudioRecord("assigned", root / "a.wav"), AudioRecord("pending", root / "b.wav")]
    manifest = DatasetManifest(
        ManifestMeta(
            "collision", root, root / "dataset.yaml", {"unassigned": root / "unassigned.jsonl"}
        ),
        records,
        {"assigned": "unassigned"},
    )
    manifest.write()
    restored = DatasetManifest.load(root / "dataset.yaml")
    assert [r.uid for r in restored.records] == ["pending"]
    return {"before": [r.uid for r in records], "after": [r.uid for r in restored.records]}


def empty_split(root):
    root.mkdir()
    meta = ManifestMeta(
        "empty",
        root,
        root / "dataset.yaml",
        {"train": root / "train.jsonl", "val": root / "val.jsonl"},
    )
    (root / "val.jsonl").write_text("")
    manifest = DatasetManifest(meta, [AudioRecord("train", root / "a.wav")], {"train": "train"})
    (root / "train.jsonl").write_text(json.dumps({"uid": "train", "audio_path": "a.wav"}) + "\n")
    (root / "dataset.yaml").write_text(
        yaml.safe_dump(
            {
                "dataset_id": "empty",
                "root": ".",
                "splits": {"train": "train.jsonl", "val": "val.jsonl"},
            }
        )
    )
    manifest = DatasetManifest.load(root / "dataset.yaml")
    manifest.write()
    restored = DatasetManifest.load(root / "dataset.yaml")
    assert set(restored.meta.splits) == {"train"}
    return {"declared_before": list(meta.splits), "declared_after": list(restored.meta.splits)}


class InvalidRepresentation(RawWaveform):
    def forward(self, audio):
        return RepresentationOutput(
            inputs={"waveform": torch.ones(4, dtype=torch.float64)}, lengths={"waveform": 4}
        )


class MemoryLoader:
    def load(self, record, *, base_dir=None):
        return AudioData(torch.ones(1, 4), 16000, record.audio_path, 16000, 4)


def shared_strict(root):
    record = AudioRecord("sample", root / "a.wav")
    pipeline = SamplePipeline(InvalidRepresentation())
    first = SERDataset([record], MemoryLoader(), pipeline, strict=True)
    try:
        first[0]
    except RepresentationError:
        pass
    else:
        raise AssertionError("Expected strict rejection before second dataset")
    SERDataset([record], MemoryLoader(), pipeline, strict=False)
    result = first[0]
    assert result.inputs["waveform"].dtype == torch.float64
    return {
        "strict_dataset_rejected_before": True,
        "accepted_after_other_dataset": True,
        "accepted_dtype": str(result.inputs["waveform"].dtype),
    }


def main():
    with tempfile.TemporaryDirectory(prefix="ser-data-review-") as directory:
        root = Path(directory)
        print(
            json.dumps(
                {
                    probe.__name__: probe(root / probe.__name__)
                    for probe in (unassigned_collision, empty_split, shared_strict)
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
