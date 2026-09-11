import json
from pathlib import Path

from ser_lib.artifacts import ArtifactEntry, export_model_artifact, scan_model_artifacts
from ser_lib.config import AudioConfig, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.foundation.events import ProgressEvent
from ser_lib.models import CNNBaseline


def _config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "unused-dataset.yaml",
        dataset_id="catalog-dataset",
        audio=AudioConfig(target_sample_rate=16000),
        representation=ComponentConfig(
            type="log_mel",
            params={
                "sample_rate": 16000,
                "n_mels": 16,
                "n_fft": 128,
                "win_length": 128,
                "hop_length": 64,
                "f_max": 8000,
            },
        ),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def test_artifact_catalog_scans_without_hashing_and_returns_manifest_entry(
    tmp_path: Path,
    monkeypatch,
):
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)
    root = tmp_path / "models"
    root.mkdir()
    artifact_dir = root / "model-a"
    export_model_artifact(
        artifact_dir,
        model,
        model_name="cnn_baseline",
        data_config=_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
        metrics={"uar": 0.75},
        metadata={
            "source_run_id": "run-123",
            "dataset_fingerprint": "abc123",
        },
    )
    bad = root / "broken"
    bad.mkdir()
    (bad / "manifest.json").write_text("{}", encoding="utf-8")

    import ser_lib.artifacts.loader as loader_module

    def forbidden_hash(_path):
        raise AssertionError("Artifact Catalog 不应计算 SHA256")

    monkeypatch.setattr(loader_module, "_sha256", forbidden_hash)
    events = []
    catalog = scan_model_artifacts(root, event_callback=events.append)

    assert len(catalog.artifacts) == 1
    assert len(catalog.failures) == 1
    entry = catalog.artifacts[0]
    assert isinstance(entry, ArtifactEntry)
    assert entry.path == artifact_dir.as_posix()
    assert entry.manifest.model_name == "cnn_baseline"
    assert entry.manifest.preprocessing["dataset_id"] == "catalog-dataset"
    assert entry.manifest.metadata["dataset_fingerprint"] == "abc123"
    assert entry.manifest.metadata["source_run_id"] == "run-123"
    assert entry.manifest.metrics == {"uar": 0.75}
    assert entry.weights_bytes > 0
    assert catalog.failures[0].directory.endswith("broken")
    json.dumps(catalog.to_dict())

    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert len(progress) == 2
    assert progress[-1].completed == progress[-1].total == 2


def test_artifact_scan_supports_recursive_catalog(tmp_path: Path):
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)
    root = tmp_path / "models"
    nested = root / "experiment-a"
    nested.mkdir(parents=True)
    export_model_artifact(
        nested / "model-a",
        model,
        model_name="cnn_baseline",
        data_config=_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
    )

    assert scan_model_artifacts(root).artifacts == ()
    recursive = scan_model_artifacts(root, recursive=True)
    assert len(recursive.artifacts) == 1
    assert recursive.artifacts[0].manifest.model_name == "cnn_baseline"
