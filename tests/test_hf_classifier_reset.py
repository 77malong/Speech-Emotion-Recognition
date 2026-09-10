from __future__ import annotations

from pathlib import Path

import pytest
import torch

from ser_lib.models import HFAudioClassifier

transformers = pytest.importorskip("transformers")


def _tiny_wav2vec2_classification_config(labels: dict[int, str]):
    config = transformers.AutoConfig.for_model(
        "wav2vec2",
        hidden_size=8,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=16,
        conv_dim=(8, 8),
        conv_stride=(2, 2),
        conv_kernel=(3, 3),
        num_conv_pos_embeddings=8,
        num_conv_pos_embedding_groups=2,
        hidden_dropout=0.0,
        activation_dropout=0.0,
        attention_dropout=0.0,
        feat_proj_dropout=0.0,
        final_dropout=0.0,
        layerdrop=0.0,
        feat_extract_norm="group",
        num_labels=len(labels),
    )
    config.id2label = dict(labels)
    config.label2id = {name: index for index, name in labels.items()}
    return config


def _save_distinct_checkpoint(path: Path) -> tuple[dict[str, torch.Tensor], torch.Tensor, torch.Tensor]:
    labels = {0: "neutral", 1: "happy"}
    config = _tiny_wav2vec2_classification_config(labels)
    model = transformers.AutoModelForAudioClassification.from_config(config)
    with torch.no_grad():
        model.classifier.weight.fill_(0.123)
        model.classifier.bias.copy_(torch.tensor([7.0, -7.0]))
    base_state = {key: value.detach().clone() for key, value in model.base_model.state_dict().items()}
    head_weight = model.classifier.weight.detach().clone()
    head_bias = model.classifier.bias.detach().clone()
    model.save_pretrained(path)
    return base_state, head_weight, head_bias


def test_pretrained_reset_reinitializes_same_shape_classifier_and_preserves_encoder(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint"
    base_state, old_weight, old_bias = _save_distinct_checkpoint(checkpoint)

    torch.manual_seed(123)
    model = HFAudioClassifier(
        num_classes=2,
        pretrained_model_name_or_path=str(checkpoint),
        local_files_only=True,
        strategy="audio_classification",
        reset_classifier_head=True,
        label_names={0: "angry", 1: "sad"},
    )

    assert model.encoder.config.id2label == {0: "angry", 1: "sad"}
    assert model.encoder.config.label2id == {"angry": 0, "sad": 1}
    assert not torch.equal(model.encoder.classifier.weight.detach(), old_weight)
    assert not torch.equal(model.encoder.classifier.bias.detach(), old_bias)
    for key, expected in base_state.items():
        assert torch.equal(model.encoder.base_model.state_dict()[key], expected), key


def test_pretrained_without_reset_preserves_matching_classifier(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint"
    _, old_weight, old_bias = _save_distinct_checkpoint(checkpoint)

    model = HFAudioClassifier(
        num_classes=2,
        pretrained_model_name_or_path=str(checkpoint),
        local_files_only=True,
        strategy="audio_classification",
        reset_classifier_head=False,
        label_names={0: "neutral", 1: "happy"},
    )

    assert torch.equal(model.encoder.classifier.weight.detach(), old_weight)
    assert torch.equal(model.encoder.classifier.bias.detach(), old_bias)
