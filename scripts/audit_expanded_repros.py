"""Disposable, offline review probes for 0d4bd75; not production fixes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import torch
import yaml


def error(call):
    try:
        call()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def dataset(root, nested=False):
    from ser_lib.data.manifest import DatasetManifest, write_jsonl
    from ser_lib.data.types import AudioRecord

    root.mkdir(parents=True, exist_ok=True)
    splits = (
        {"train": "train/items.jsonl", "val": "val/items.jsonl"}
        if nested
        else {"train": "manifest.jsonl"}
    )
    for name, filename in splits.items():
        write_jsonl([AudioRecord(name, Path("a.wav"), label=0)], root / filename)
    path = root / "dataset.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "dataset_id": "probe",
                "root": str(root),
                "splits": splits,
                "labels": {"0": {"en": "neutral"}},
            }
        ),
        encoding="utf-8",
    )
    return DatasetManifest.load(path)


def spectral(root):
    from ser_lib.data.representations.spectral import (
        SpectrogramRepresentation,
        LogMelRepresentation,
    )

    m = LogMelRepresentation(power=1.0)
    x = torch.rand(1, 4096)
    a = m.db_transform(m.mel_transform(x))
    b = m.db_transform(m.mel_transform(2 * x))
    return {
        "spectrogram_error": error(SpectrogramRepresentation),
        "amplitude_x2_db_delta": (b - a).mean().item(),
        "amplitude_db_expected": 6.020599913,
    }


def csv_labels(root):
    from ser_lib.data.importers.csv_importer import CsvImporter

    src = root / "mixed.csv"
    src.write_text("audio_path,label\na.wav,1\nb.wav,happy\n", encoding="utf-8")
    p = CsvImporter().scan(src, {})
    return {
        "preview_ok": p.ok,
        "mapping": p.label_mapping,
        "record_labels": [r.label for r in p.records],
    }


def conversion(root):
    from ser_lib.data.importers.csv_importer import CsvImporter

    src = root / "duplicate.csv"
    src.write_text("uid,audio_path,label\nx,a.wav,0\nx,b.wav,0\n", encoding="utf-8")
    dest = root / "existing"
    ds = dataset(dest)
    before = ds.meta.yaml_path.read_bytes()
    imp = CsvImporter()
    p = imp.scan(src, {"uid_column": "uid"})
    failure = error(lambda: imp.convert(src, dest, {"uid_column": "uid"}))
    from ser_lib.data.manifest import DatasetManifest

    return {
        "preview_ok": p.ok,
        "convert_error": failure,
        "old_yaml_changed": before != ds.meta.yaml_path.read_bytes(),
        "old_dataset_load_error": error(lambda: DatasetManifest.load(ds.meta.yaml_path)),
    }


def csv_root(root):
    from ser_lib.data.importers.csv_importer import CsvImporter

    src = root / "relative.csv"
    src.write_text("audio_path,label\na.wav,0\n", encoding="utf-8")
    ds = CsvImporter().convert(src, root / "relative_dest", {"root": "audio"})
    return {
        "stored_path": str(ds.records[0].audio_path),
        "resolved": str(ds.resolve_audio_path(ds.records[0])),
    }


def split_collision(root):
    from ser_lib.data.manifest import DatasetManifest

    ds = dataset(root / "nested", True)
    ds.write()
    return {
        "yaml": yaml.safe_load(ds.meta.yaml_path.read_text()),
        "reload_error": error(lambda: DatasetManifest.load(ds.meta.yaml_path)),
    }


def revision_target(root):
    from ser_lib.data.history import create_dataset_revision, restore_dataset_revision
    from ser_lib.data.fingerprint import fingerprint_manifest

    ds = dataset(root / "revision")
    rev = create_dataset_revision(ds)
    record = Path(rev.directory) / "revision.json"
    payload = json.loads(record.read_text(encoding="utf-8"))
    sentinel = root / "unrelated.txt"
    sentinel.write_text("KEEP ME", encoding="utf-8")
    payload["files"]["split:train"]["target_path"] = str(sentinel)
    record.write_text(json.dumps(payload), encoding="utf-8")
    failure = error(
        lambda: restore_dataset_revision(
            ds, rev.directory, expected_current_fingerprint=fingerprint_manifest(ds).digest
        )
    )
    return {
        "restore_error": failure,
        "unrelated_file_overwritten": sentinel.read_text() != "KEEP ME",
        "new_content": sentinel.read_text(),
    }


def transforms(root):
    from ser_lib.data.transforms.waveform import Normalize
    from ser_lib.data.transforms.feature import SpecMasking
    from ser_lib.data.transforms.base import (
        FeatureTransformPipeline,
        validate_feature_transform_layouts,
    )
    from ser_lib.data.types import TensorSpec

    transform = SpecMasking(2, 2)
    specs = {
        "features": TensorSpec(layout="FT", feature_dim=4),
        "global": TensorSpec(layout="D", feature_dim=3),
    }
    return {
        "single_sample_finite": torch.isfinite(Normalize()(torch.tensor([[0.5]]))).all().item(),
        "layout_validation_error": error(
            lambda: validate_feature_transform_layouts(transform, specs)
        ),
        "pipeline_error": error(
            lambda: FeatureTransformPipeline([transform])(
                {"features": torch.ones(4, 8), "global": torch.ones(3)}
            )
        ),
    }


def contracts(root):
    from ser_lib.config.data import load_data_config
    from ser_lib.data.types import (
        AudioRecord,
        RepresentationOutput,
        TensorSpec,
        validate_representation_output,
    )
    from ser_lib.data.manifest import write_jsonl, read_jsonl

    config = root / "future.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "schema_version": 999,
                "manifest": "dataset.yaml",
                "representation": {"type": "waveform"},
            }
        )
    )
    output = RepresentationOutput(inputs={"waveform": torch.ones(8)}, lengths={})
    file = root / "record.jsonl"
    write_jsonl([AudioRecord("a", Path("a.wav"), label=True, start_ms=0.5)], file)
    return {
        "accepted_schema": load_data_config(config).schema_version,
        "missing_lengths_validation_error": error(
            lambda: validate_representation_output(output, {"waveform": TensorSpec(layout="T")})
        ),
        "record_roundtrip_error": error(lambda: read_jsonl(file)),
    }


def adapter(root):
    from scripts.audit_round2_repros import wrap
    from ser_lib.engine import evaluate

    model = wrap(torch.nn.Linear(2, 2))
    container = torch.nn.ModuleDict({"adapter": model})
    nested_error = error(lambda: container.load_state_dict(container.state_dict()))
    model.train()

    def callback(event):
        raise RuntimeError("observer failed")

    evaluation_error = error(lambda: evaluate(model, [], num_classes=2, event_callback=callback))
    return {
        "nested_roundtrip_error": nested_error,
        "evaluation_error": evaluation_error,
        "training_mode_after_error": model.training,
    }


def more_contracts(root):
    import math
    import time
    import psutil
    from ser_lib.runtime import get_runtime_metrics
    from ser_lib.config.optimizer import AdamWConfig
    from ser_lib.config.data import ComponentConfig
    from ser_lib.data.pipeline import _build_waveform_transforms
    from ser_lib.data.registry import default_registry
    from ser_lib.inference.batch import BatchEmotionPredictor
    from ser_lib.foundation.errors import OperationCancelled
    from ser_lib.data.types import AudioRecord

    class CancelledPredictor:
        def predict_record(self, *args, **kwargs):
            raise OperationCancelled("cancel probe")

    result = BatchEmotionPredictor(CancelledPredictor()).predict_records(
        [AudioRecord("x", Path("x.wav"))], batch_size=1, fail_fast=False
    )
    params = {"n_steps": 25}
    direct = error(
        lambda: default_registry.create(
            "waveform_transform", {"type": "pitch_shift", "params": params}
        )
    )
    injected = error(
        lambda: _build_waveform_transforms(
            [ComponentConfig(type="pitch_shift", params=params)],
            sample_rate=16000,
            allow_random=True,
        )
    )
    process = psutil.Process()
    process.cpu_percent()
    until = time.perf_counter() + 0.25
    while time.perf_counter() < until:
        sum(range(1000))
    reference = process.cpu_percent()
    return {
        "infinite_learning_rate_accepted": math.isinf(
            AdamWConfig(learning_rate=float("inf")).learning_rate
        ),
        "direct_pitch_error": direct,
        "injected_pitch_error": injected,
        "cancel_returned_as_failure": result.failures[0].error_type,
        "reference_cpu_percent": reference,
        "library_cpu_percent": get_runtime_metrics().process_cpu_percent,
    }


def main():
    results = {}
    with tempfile.TemporaryDirectory(prefix="ser-expanded-") as directory:
        root = Path(directory)
        for probe in [
            spectral,
            csv_labels,
            conversion,
            csv_root,
            split_collision,
            revision_target,
            transforms,
            contracts,
            adapter,
            more_contracts,
        ]:
            try:
                results[probe.__name__] = probe(root)
            except Exception as exc:
                results[probe.__name__] = {"probe_error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    assert not any("probe_error" in value for value in results.values())


if __name__ == "__main__":
    main()
