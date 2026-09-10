import json
from pathlib import Path

from ser_lib.artifacts import scan_model_artifacts
from ser_lib.data.config import AudioSettings, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.foundation.events import ProgressEvent
from ser_lib.models import CNNBaseline
from ser_lib.services import ArtifactService


def _config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "unused-dataset.yaml",
        dataset_id="catalog-dataset",
        audio=AudioSettings(target_sample_rate=16000),
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


def test_artifact_catalog_scans_without_hashing_and_exposes_management_metadata(
    tmp_path: Path,
    monkeypatch,
):
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)
    root = tmp_path / "models"
    root.mkdir()
    ArtifactService.export(
        root / "model-a",
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
    info = catalog.artifacts[0]
    assert info.model_name == "cnn_baseline"
    assert info.dataset_id == "catalog-dataset"
    assert info.dataset_fingerprint == "abc123"
    assert info.source_run_id == "run-123"
    assert info.created_at
    assert info.artifact_id
    assert info.parameter_count == sum(parameter.numel() for parameter in model.parameters())
    assert info.weights_bytes > 0
    assert info.total_bytes > info.weights_bytes
    assert info.metrics == {"uar": 0.75}
    assert catalog.failures[0].directory.endswith("broken")
    json.dumps(catalog.to_dict())

    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert len(progress) == 2
    assert progress[-1].completed == progress[-1].total == 2


def test_artifact_service_scan_supports_recursive_catalog(tmp_path: Path):
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)
    root = tmp_path / "models"
    nested = root / "experiment-a"
    nested.mkdir(parents=True)
    ArtifactService.export(
        nested / "model-a",
        model,
        model_name="cnn_baseline",
        data_config=_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
    )

    assert ArtifactService.scan(root).artifacts == ()
    recursive = ArtifactService.scan(root, recursive=True)
    assert len(recursive.artifacts) == 1
    assert recursive.artifacts[0].model_name == "cnn_baseline"
