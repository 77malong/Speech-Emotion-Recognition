"""Independent strict-review probes for 0d4bd75; use only disposable local data."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import soundfile as sf
import torch
import yaml

from ser_lib.config.training import LossConfig, TrainerConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.engine import evaluate
from ser_lib.engine.config import load_experiment_config
from ser_lib.engine.experiment import train_experiment
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.engine.trainer import Trainer
from ser_lib.models.adapters.torch import TorchModelAdapter


def batch(x, y=None, key="features", length=None):
    size = len(x)
    lengths = {} if length is None else {key: torch.full((size,), length)}
    masks = (
        {}
        if length is None
        else {key: torch.arange(x.shape[-1])[None, :].expand(size, -1) < length}
    )
    return SERBatch(
        {key: x}, lengths, masks, y, [str(i) for i in range(size)], [{} for _ in range(size)]
    )


def wrap(module):
    return TorchModelAdapter.wrap(
        module,
        required_inputs={"features": TensorSpec(layout="D", feature_dim=2)},
        input_map={"input": "inputs.features"},
        num_classes=2,
    )


def amp_probe():
    if not torch.cuda.is_available():
        return {"skipped": "CUDA unavailable"}
    torch.manual_seed(17)
    base = torch.nn.Linear(2, 2, bias=False)
    initial = base.weight.detach().clone()
    x = torch.tensor([[1.0, 2.0], [-1.0, 0.5], [0.25, -0.75], [2.0, -1.0], [0.5, 1.5]])
    y = torch.tensor([0, 1, 1, 0, 1])
    results = []
    for amp, steps, chunks in [
        (False, 1, [(0, 5)]),
        (True, 1, [(0, 5)]),
        (True, 4, [(0, 2), (2, 5)]),
    ]:
        module = copy.deepcopy(base)
        model = wrap(module)
        trainer = Trainer(
            model,
            TrainerConfig(device="cuda", amp=amp, gradient_accumulation_steps=steps),
            optimizer=torch.optim.SGD(model.parameters(), lr=0.1),
        )
        epoch = trainer.train_epoch([batch(x[a:b], y[a:b]) for a, b in chunks], epoch=1)
        results.append(
            {
                "amp": amp,
                "steps": steps,
                "reported_optimizer_steps": epoch.optimizer_steps,
                "update_norm": float((module.weight.detach().cpu() - initial).norm()),
                "scaler": trainer._scaler.get_scale() if amp else None,
            }
        )
    native = copy.deepcopy(base).cuda()
    optimizer = torch.optim.SGD(native.parameters(), lr=0.1)
    scaler = torch.cuda.amp.GradScaler()
    with torch.autocast("cuda", dtype=torch.float16):
        loss = torch.nn.functional.cross_entropy(native(x.cuda()), y.cuda())
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
    results.append(
        {
            "native_torch_amp": True,
            "update_norm": float((native.weight.detach().cpu() - initial).norm()),
            "scaler": scaler.get_scale(),
        }
    )
    return results


def cnn_fixed_probe():
    from ser_lib.config.data import BatchingConfig
    from ser_lib.data.collate import SERCollator
    from ser_lib.data.types import SERSample
    from ser_lib.models.cnn_models import CNNBaseline

    torch.manual_seed(123)
    model = CNNBaseline(2, 2, hidden_dim=4, dropout=0).eval()
    sample = SERSample("short", {"features": torch.randn(2, 7)}, {"features": 7}, 0, {})
    outputs = []
    for maximum in (7, 22):
        cfg = BatchingConfig.model_validate(
            {"type": "fixed", "fixed": {"max_lengths": {"features": maximum}}}
        )
        assembled = SERCollator({"features": TensorSpec(layout="FT", feature_dim=2)}, cfg)([sample])
        with torch.no_grad():
            outputs.append(model(assembled).logits)
    return {"fixed_7_vs_22_difference": float((outputs[0] - outputs[1]).abs().max())}


def streaming_peak_probe(root):
    from ser_lib.config import DataConfig, AudioConfig, ComponentConfig, BatchingConfig
    from ser_lib.config.inference import StreamingConfig
    from ser_lib.data.pipeline import build_components
    from ser_lib.data.collate import build_collator
    from ser_lib.inference.offline import EmotionPredictor
    from ser_lib.inference.streaming import StreamingEmotionRecognizer

    class Amplitude(torch.nn.Module):
        def forward(self, x):
            mean = x.abs().mean(-1)
            return torch.stack([mean, -mean], -1)

    cfg = DataConfig(
        manifest=root / "unused.yaml",
        audio=AudioConfig(normalize_peak=True),
        representation=ComponentConfig(type="waveform"),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "a"}, 1: {"en": "b"}},
    )
    loader, pipeline = build_components(cfg, train=False)
    model = TorchModelAdapter.wrap(
        Amplitude(),
        required_inputs={"waveform": TensorSpec(layout="T")},
        input_map={"x": "inputs.waveform"},
        num_classes=2,
        supports_masks=True,
        supports_variable_length=True,
    )
    predictor = EmotionPredictor(
        model, loader, pipeline, build_collator(pipeline.output_specs, cfg.batching)
    )
    pcm = torch.full((320,), 0.2)
    path = root / "peak.wav"
    sf.write(path, pcm.numpy(), 16000, subtype="FLOAT")
    offline = predictor.predict_file(path)
    stream = StreamingEmotionRecognizer(predictor, StreamingConfig(window_ms=20, hop_ms=20))
    online = stream.push_pcm(pcm)[0].prediction
    return {
        "offline_probabilities": offline.probabilities,
        "stream_probabilities": online.probabilities,
    }


def artifact_probe(root):
    from ser_lib.artifacts import export_model_artifact, load_model_artifact, verify_model_artifact
    from ser_lib.config import DataConfig, ComponentConfig
    from ser_lib.models import CNNBaseline

    cfg = DataConfig(
        manifest=root / "unused.yaml",
        labels={0: {"en": "a"}, 1: {"en": "b"}},
        representation=ComponentConfig(type="log_mel", params={"n_mels": 32}),
    )
    model = CNNBaseline(16, 2, hidden_dim=4)
    exported = export_model_artifact(
        root / "bad-preprocessing",
        model,
        model_name="cnn_baseline",
        data_config=cfg,
        labels={0: "a", 1: "b"},
    )
    result = {"export_succeeded": exported.is_dir()}
    verify_model_artifact(exported)
    result["verification_succeeded"] = True
    try:
        load_model_artifact(exported)
        result["load_succeeded"] = True
    except Exception as exc:
        result["load_error"] = type(exc).__name__ + ": " + str(exc)
    return result


def numpy_resume_probe(root):
    import numpy as np
    from ser_lib.engine.checkpoint import save_checkpoint, load_checkpoint

    model = wrap(torch.nn.Linear(2, 2))
    np.random.seed(7)
    path = save_checkpoint(root / "rng.pt", model, None, epoch=1)
    expected = float(np.random.random())
    np.random.seed(999)
    load_checkpoint(path, model, restore_rng=True)
    return {"expected_next_numpy_random": expected, "actual": float(np.random.random())}


def weighted_eval_probe():
    model = wrap(torch.nn.Identity())
    x = torch.tensor([[4.0, 0.0], [4.0, 0.0]])
    y = torch.tensor([0, 1])
    loss = ClassificationLoss(LossConfig(class_weights=[1.0, 9.0]), 2)
    combined = evaluate(model, [batch(x, y)], num_classes=2, loss_fn=loss)
    split = evaluate(model, [batch(x[:1], y[:1]), batch(x[1:], y[1:])], num_classes=2, loss_fn=loss)
    return {
        "combined_loss": combined.loss,
        "split_loss": split.loss,
        "direct_reference": float(loss(x, y)),
    }


def hf_head_probe(root):
    import transformers
    from ser_lib.models.adapters.huggingface import HFAudioClassifier

    config = transformers.Wav2Vec2Config(
        hidden_size=8,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=16,
        conv_dim=(8, 8),
        conv_stride=(2, 2),
        conv_kernel=(3, 3),
        num_conv_pos_embeddings=8,
        num_conv_pos_embedding_groups=2,
        classifier_proj_size=8,
        num_labels=2,
        id2label={0: "neutral", 1: "happy"},
        label2id={"neutral": 0, "happy": 1},
    )
    source = transformers.Wav2Vec2ForSequenceClassification(config)
    with torch.no_grad():
        source.classifier.weight.fill_(0.123)
        source.classifier.bias.copy_(torch.tensor([7.0, -7.0]))
    path = root / "hf"
    source.save_pretrained(path)
    loaded = HFAudioClassifier(
        num_classes=2,
        pretrained_model_name_or_path=str(path),
        strategy="audio_classification",
        label_names={0: "angry", 1: "sad"},
        reset_classifier_head=True,
    )
    return {
        "head_weights_unchanged": torch.equal(
            source.classifier.weight, loaded.encoder.classifier.weight
        ),
        "bias_after_reset": loaded.encoder.classifier.bias.detach().tolist(),
        "new_labels": loaded.encoder.config.id2label,
    }


def resume_probe(root):
    raw = load_experiment_config("tests/fixtures/release_compat/experiment_v1.yaml").model_dump(
        mode="json"
    )
    root.mkdir(parents=True, exist_ok=True)
    for index in range(2):
        sf.write(
            root / f"{index}.wav",
            torch.sin(torch.arange(1600) * (0.1 + index * 0.04)).numpy(),
            16000,
        )
    records = [
        {"uid": f"x{i}", "audio_path": f"{i}.wav", "label": i, "speaker_id": f"s{i}"}
        for i in range(2)
    ]
    for split in ["train", "val"]:
        (root / f"{split}.jsonl").write_text(
            "\n".join(json.dumps({**v, "uid": split + v["uid"]}) for v in records), encoding="utf-8"
        )
    # Same speakers/audio intentionally used across splits to probe the absence of leakage gates.
    (root / "dataset.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "dataset_id": "round2",
                "root": str(root),
                "splits": {"train": "train.jsonl", "val": "val.jsonl"},
                "labels": {0: {"en": "neutral"}, 1: {"en": "happy"}},
            }
        ),
        encoding="utf-8",
    )
    raw["data"]["manifest"] = str(root / "dataset.yaml")
    raw["data"]["dataset_id"] = "round2"
    raw["trainer"]["checkpoint_dir"] = str(root / "run" / "checkpoints")
    raw["trainer"]["early_stopping_min_delta"] = 100.0
    raw["output_dir"] = str(root / "run")
    config_type = type(load_experiment_config("tests/fixtures/release_compat/experiment_v1.yaml"))
    first = train_experiment(config_type.model_validate(raw), batch_size=2)
    raw["trainer"]["epochs"] = 2
    raw["loss"]["type"] = "focal"
    second = train_experiment(
        config_type.model_validate(raw), batch_size=2, resume=first.last_checkpoint
    )
    history = json.loads(second.history_path.read_text(encoding="utf-8"))
    metrics = second.metrics_log.read_text(encoding="utf-8").strip().splitlines()
    return {
        "cross_split_identical_audio_accepted": True,
        "changed_loss_resume_accepted": True,
        "actual_loss": raw["loss"]["type"],
        "reported_loss": second.run.config["loss"]["type"],
        "actual_epochs": 2,
        "reported_config_epochs": second.run.config["trainer"]["epochs"],
        "history_epochs": [v["epoch"] for v in history],
        "metrics_lines": len(metrics),
        "best_epoch": second.training.best_epoch,
        "best_checkpoint": str(second.best_checkpoint),
        "existing_best_file": (root / "run" / "checkpoints" / "best.pt").is_file(),
    }


def nonfinite_probe(root):
    from ser_lib.config import DataConfig, ComponentConfig, BatchingConfig
    from ser_lib.data.pipeline import build_components
    from ser_lib.data.collate import build_collator
    from ser_lib.data.types import AudioData
    from ser_lib.inference.offline import EmotionPredictor

    class Nonfinite(torch.nn.Module):
        def forward(self, x):
            return torch.full((x.shape[0], 2), float("nan"))

    cfg = DataConfig(
        manifest=root / "unused.yaml",
        representation=ComponentConfig(type="waveform"),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "a"}, 1: {"en": "b"}},
    )
    loader, pipeline = build_components(cfg, train=False)
    model = TorchModelAdapter.wrap(
        Nonfinite(),
        required_inputs={"waveform": TensorSpec(layout="T")},
        input_map={"x": "inputs.waveform"},
        num_classes=2,
        supports_masks=True,
        supports_variable_length=True,
    )
    predictor = EmotionPredictor(
        model, loader, pipeline, build_collator(pipeline.output_specs, cfg.batching)
    )
    prediction = predictor.predict_audio(
        AudioData(torch.ones(1, 320), 16000, root / "memory.wav", 16000, 320)
    )
    return {
        "returned_probabilities": [str(v) for v in prediction.probabilities],
        "returned_label": prediction.label_id,
        "confidence": str(prediction.confidence),
        "raised": False,
    }


def main():
    torch.set_num_threads(1)
    results = {}
    with tempfile.TemporaryDirectory(prefix="ser-round2-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        for name, probe in [
            ("amp", amp_probe),
            ("weighted_evaluation", weighted_eval_probe),
            ("cnn_fixed", cnn_fixed_probe),
            ("streaming_peak", lambda: streaming_peak_probe(root)),
            ("hf_reset", lambda: hf_head_probe(root)),
            ("resume", lambda: resume_probe(root / "data")),
            ("artifact", lambda: artifact_probe(root)),
            ("numpy_resume", lambda: numpy_resume_probe(root)),
            ("nonfinite_inference", lambda: nonfinite_probe(root)),
        ]:
            try:
                results[name] = probe()
            except Exception as exc:
                results[name] = {"probe_error": type(exc).__name__ + ": " + str(exc)}
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
