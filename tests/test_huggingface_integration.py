from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest
import torch

from ser_lib.artifacts import export_model_artifact, load_model_artifact
from ser_lib.config import AudioConfig, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.data import SERBatch
from ser_lib.engine import Trainer, TrainerConfig, evaluate, load_checkpoint, save_checkpoint
from ser_lib.inference import EmotionPredictor
from ser_lib.models import HFAudioClassifier, model_registry

transformers = pytest.importorskip("transformers")


_FAMILY_TYPES = ("wav2vec2", "hubert", "wavlm")
_LABELS = {0: "neutral", 1: "happy"}


def _tiny_encoder_config(model_type: str, *, feat_extract_norm: str = "group") -> dict:
    config = transformers.AutoConfig.for_model(
        model_type,
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
        feat_extract_norm=feat_extract_norm,
    )
    return config.to_dict()


def _processor_snapshot(*, return_attention_mask: bool = False) -> dict:
    processor = transformers.Wav2Vec2FeatureExtractor(
        feature_size=1,
        sampling_rate=16000,
        padding_value=0.0,
        do_normalize=True,
        return_attention_mask=return_attention_mask,
    )
    return {
        "class_name": type(processor).__name__,
        "config": processor.to_dict(),
    }


def _batch(*, first_length: int = 80, second_length: int = 112) -> SERBatch:
    torch.manual_seed(41)
    maximum = max(first_length, second_length)
    waveform = torch.zeros(2, maximum, dtype=torch.float32)
    waveform[0, :first_length] = torch.randn(first_length)
    waveform[1, :second_length] = torch.randn(second_length)
    lengths = torch.tensor([first_length, second_length], dtype=torch.long)
    mask = torch.arange(maximum).unsqueeze(0) < lengths.unsqueeze(1)
    return SERBatch(
        inputs={"waveform": waveform},
        lengths={"waveform": lengths},
        masks={"waveform": mask},
        labels=torch.tensor([0, 1], dtype=torch.long),
        uids=["first", "second"],
        metadata=[{}, {}],
    )


def _single_batch(signal: torch.Tensor) -> SERBatch:
    length = signal.numel()
    return SERBatch(
        inputs={"waveform": signal.reshape(1, length)},
        lengths={"waveform": torch.tensor([length], dtype=torch.long)},
        masks={"waveform": torch.ones(1, length, dtype=torch.bool)},
        labels=torch.tensor([0], dtype=torch.long),
        uids=["first"],
        metadata=[{}],
    )


def _model(
    model_type: str = "wav2vec2",
    *,
    feat_extract_norm: str = "group",
    return_attention_mask: bool = False,
) -> HFAudioClassifier:
    return HFAudioClassifier(
        num_classes=2,
        encoder_config=_tiny_encoder_config(model_type, feat_extract_norm=feat_extract_norm),
        processor_config=_processor_snapshot(return_attention_mask=return_attention_mask),
        dropout=0.0,
    )


def _data_config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "unused.yaml",
        audio=AudioConfig(target_sample_rate=16000),
        representation=ComponentConfig(type="waveform"),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def _write_pcm_wav(path: Path, *, sample_rate: int = 16000, seconds: float = 0.02) -> None:
    frame_count = int(sample_rate * seconds)
    frames = bytearray()
    for index in range(frame_count):
        value = int(8000 * math.sin(2 * math.pi * 220 * index / sample_rate))
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)


def _assert_same_state(left: torch.nn.Module, right: torch.nn.Module) -> None:
    left_state = left.state_dict()
    right_state = right.state_dict()
    assert tuple(left_state) == tuple(right_state)
    for key in left_state:
        assert torch.equal(left_state[key], right_state[key]), key


@pytest.mark.parametrize("model_type", _FAMILY_TYPES)
def test_real_tiny_verified_audio_families_forward(model_type: str):
    torch.manual_seed(7)
    model = _model(model_type).eval()
    output = model(_batch())

    assert model.verified_family == model_type
    assert output.logits.shape == (2, 2)
    assert output.embeddings is not None
    assert output.embeddings.shape == (2, 8)


def test_real_wav2vec2_padding_and_output_length_contract():
    torch.manual_seed(11)
    model = _model(
        "wav2vec2",
        feat_extract_norm="layer",
        return_attention_mask=True,
    ).eval()
    batch = _batch(first_length=80, second_length=112)
    first_signal = batch.inputs["waveform"][0, :80].clone()

    with torch.no_grad():
        single = model(_single_batch(first_signal))
        mixed = model(batch)

    assert single.embeddings is not None and mixed.embeddings is not None
    assert torch.allclose(single.embeddings[0], mixed.embeddings[0], atol=2e-4, rtol=2e-4)

    valid = batch.masks["waveform"]
    assert valid is not None
    prepared, attention_mask = model._prepare_waveform(batch.inputs["waveform"], valid)
    assert attention_mask is not None
    hidden = model.encoder(
        input_values=prepared,
        attention_mask=attention_mask,
        return_dict=True,
    ).last_hidden_state
    encoded_mask = model._encoded_mask(valid, hidden.shape[1])
    expected_lengths = model.encoder._get_feat_extract_output_lengths(batch.lengths["waveform"])
    assert encoded_mask.sum(dim=1).tolist() == expected_lengths.tolist()


def test_real_group_norm_processor_does_not_request_attention_mask():
    model = _model("wav2vec2").eval()
    batch = _batch()
    valid = batch.masks["waveform"]
    assert valid is not None
    _, attention_mask = model._prepare_waveform(batch.inputs["waveform"], valid)
    assert model.encoder.config.feat_extract_norm == "group"
    assert attention_mask is None


def test_real_wav2vec2_full_offline_lifecycle(tmp_path: Path, monkeypatch):
    torch.manual_seed(13)
    model = _model("wav2vec2")
    batch = _batch()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    training = Trainer(
        model,
        TrainerConfig(epochs=1, device="cpu"),
        optimizer=optimizer,
        run_id="hf-tiny",
    ).fit([batch])
    assert training.status == "completed"
    assert evaluate(model, [batch], num_classes=2).sample_count == 2

    checkpoint = save_checkpoint(tmp_path / "hf.pt", model, optimizer, epoch=1)
    resumed = model_registry.create("hf_audio_classifier", **model.model_config)
    resumed_optimizer = torch.optim.AdamW(resumed.parameters(), lr=1e-3)
    load_checkpoint(checkpoint, resumed, resumed_optimizer, restore_rng=False)
    _assert_same_state(model, resumed)

    artifact = export_model_artifact(
        tmp_path / "artifact",
        model,
        model_name="hf_audio_classifier",
        data_config=_data_config(tmp_path),
        labels=_LABELS,
    )
    assert (artifact / "processor_config.json").is_file()

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    loaded = load_model_artifact(artifact)
    _assert_same_state(model, loaded.model)
    assert loaded.manifest.processor == model.artifact_processor_config
    assert loaded.model.artifact_processor_config == model.artifact_processor_config

    model.eval()
    loaded.model.eval()
    with torch.no_grad():
        assert torch.allclose(model(batch).logits, loaded.model(batch).logits, atol=1e-6)

    wav = tmp_path / "predict.wav"
    _write_pcm_wav(wav)
    prediction = EmotionPredictor.from_loaded_artifact(loaded).predict_file(wav)
    assert prediction.label_id in _LABELS
    assert len(prediction.probabilities) == 2


def test_real_processor_local_directory_is_snapshotted(tmp_path: Path):
    processor = transformers.Wav2Vec2FeatureExtractor(
        feature_size=1,
        sampling_rate=16000,
        padding_value=0.0,
        do_normalize=True,
        return_attention_mask=False,
    )
    directory = tmp_path / "processor"
    processor.save_pretrained(directory)

    model = HFAudioClassifier(
        num_classes=2,
        encoder_config=_tiny_encoder_config("wav2vec2"),
        processor_name_or_path=str(directory),
        dropout=0.0,
    )

    assert model.processor_config is not None
    assert model.processor_config.class_name == "Wav2Vec2FeatureExtractor"
    assert model.model_config["processor_name_or_path"] is None
    assert model.model_config["processor_config"] == model.artifact_processor_config


def test_real_direct_classification_requires_explicit_head_reset_and_label_mapping(tmp_path: Path):
    params = dict(
        num_classes=2,
        encoder_config=_tiny_encoder_config("wav2vec2"),
        processor_config=_processor_snapshot(),
        strategy="audio_classification",
        label_names=_LABELS,
        dropout=0.0,
    )
    with pytest.raises(ValueError, match="reset_classifier_head=True"):
        HFAudioClassifier(**params)

    model = HFAudioClassifier(**params, reset_classifier_head=True)
    output = model(_batch())
    assert output.logits.shape == (2, 2)
    assert output.embeddings is None

    wrong = tmp_path / "wrong-labels"
    with pytest.raises(ValueError, match="artifact labels"):
        export_model_artifact(
            wrong,
            model,
            model_name="hf_audio_classifier",
            data_config=_data_config(tmp_path),
            labels={0: "neutral", 1: "angry"},
        )
    assert not wrong.exists()
