from __future__ import annotations

from types import SimpleNamespace

import pytest

import ser_lib.artifacts.loader as artifact_loader
from ser_lib.engine.experiment import evaluate_artifact, train_experiment


def test_training_rejects_experiment_labels_that_disagree_with_manifest(current_experiment_config):
    config = current_experiment_config
    swapped = config.data.model_copy(
        update={
            "labels": {
                0: {"en": "happy"},
                1: {"en": "neutral"},
            }
        }
    )
    config = config.model_copy(update={"data": swapped})

    with pytest.raises(ValueError, match="训练标签语义.*manifest"):
        train_experiment(config)


def test_artifact_evaluation_rejects_same_ids_with_reversed_meaning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    dataset_yaml = tmp_path / "dataset.yaml"
    (tmp_path / "test.jsonl").write_text("", encoding="utf-8")
    dataset_yaml.write_text(
        "\n".join(
            [
                "dataset_id: label-mismatch",
                "root: .",
                "splits:",
                "  test: test.jsonl",
                "labels:",
                "  0: {en: happy}",
                "  1: {en: neutral}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = SimpleNamespace(
        manifest=SimpleNamespace(
            labels={0: "neutral", 1: "happy"},
            preprocessing={"manifest": str(dataset_yaml)},
            metadata={},
            model_name="cnn_baseline",
        )
    )
    monkeypatch.setattr(artifact_loader, "load_model_artifact", lambda *args, **kwargs: loaded)

    with pytest.raises(ValueError, match="artifact 标签语义.*manifest"):
        evaluate_artifact(
            tmp_path / "artifact",
            manifest_path=dataset_yaml,
            output=tmp_path / "evaluation",
        )


def test_artifact_evaluation_rejects_manifest_without_named_label_semantics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    dataset_yaml = tmp_path / "dataset.yaml"
    (tmp_path / "test.jsonl").write_text("", encoding="utf-8")
    dataset_yaml.write_text(
        "\n".join(
            [
                "dataset_id: unnamed-labels",
                "root: .",
                "splits:",
                "  test: test.jsonl",
                "labels:",
                "  0: {}",
                "  1: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = SimpleNamespace(
        manifest=SimpleNamespace(
            labels={0: "neutral", 1: "happy"},
            preprocessing={"manifest": str(dataset_yaml)},
            metadata={},
            model_name="cnn_baseline",
        )
    )
    monkeypatch.setattr(artifact_loader, "load_model_artifact", lambda *args, **kwargs: loaded)

    with pytest.raises(ValueError, match="无法确定.*label=0"):
        evaluate_artifact(
            tmp_path / "artifact",
            manifest_path=dataset_yaml,
            output=tmp_path / "evaluation",
        )
