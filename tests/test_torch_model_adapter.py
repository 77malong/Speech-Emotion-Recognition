from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest
import torch
from pydantic import ValidationError
from torch import nn

from ser_lib.artifacts import export_model_artifact, load_model_artifact
from ser_lib.data import SERBatch, TensorSpec
from ser_lib.config import AudioConfig, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.engine import Trainer, TrainerConfig, evaluate, load_checkpoint, save_checkpoint
from ser_lib.foundation.errors import RegistryError
from ser_lib.inference import EmotionPredictor
from ser_lib.models import (
    TORCH_ADAPTER_MODEL_ID,
    SERModel,
    TorchModelAdapter,
    model_registry,
)

_FACTORY_ID = "tests.tiny_wave_classifier.v1"
_FACTORY_CALLS = 0


class TinyWaveClassifier(nn.Module):
    def __init__(self, num_classes: int = 2) -> None:
        super().__init__()
        self.classifier = nn.Linear(1, num_classes)

    def forward(self, waveform: torch.Tensor, mask: torch.Tensor):
        weights = mask.to(waveform.dtype)
        pooled = (waveform * weights).sum(dim=-1) / weights.sum(dim=-1).clamp_min(1)
        embeddings = pooled.unsqueeze(-1)
        return {
            "logits": self.classifier(embeddings),
            "embeddings": embeddings,
        }


def _factory(num_classes: int = 2) -> nn.Module:
    global _FACTORY_CALLS
    _FACTORY_CALLS += 1
    return TinyWaveClassifier(num_classes=num_classes)


model_registry.register_torch_factory(_FACTORY_ID, _factory, replace=True)


def _adapter(
    module: nn.Module | None = None,
    *,
    factory_id: str | None = _FACTORY_ID,
    factory_params: dict | None = None,
    num_classes: int = 2,
    freeze_module: bool = False,
) -> TorchModelAdapter:
    return TorchModelAdapter.wrap(
        module or TinyWaveClassifier(num_classes=num_classes),
        required_inputs={"waveform": TensorSpec(layout="T")},
        input_map={"waveform": "inputs.waveform", "mask": "masks.waveform"},
        output={"logits": "logits", "embeddings": "embeddings"},
        supports_masks=True,
        supports_variable_length=True,
        num_classes=num_classes,
        expected_sample_rate=16000,
        freeze_module=freeze_module,
        factory_id=factory_id,
        factory_params=(
            {"num_classes": num_classes} if factory_params is None else factory_params
        ),
    )


def _batch() -> SERBatch:
    return SERBatch(
        inputs={
            "waveform": torch.tensor(
                [[0.1, 0.2, 0.3, 0.0], [-0.2, 0.1, 0.0, 0.0]],
                dtype=torch.float32,
            )
        },
        lengths={"waveform": torch.tensor([3, 2], dtype=torch.long)},
        masks={
            "waveform": torch.tensor(
                [[True, True, True, False], [True, True, False, False]]
            )
        },
        labels=torch.tensor([0, 1], dtype=torch.long),
        uids=["a", "b"],
        metadata=[{}, {}],
    )


def _data_config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "unused.yaml",
        audio=AudioConfig(target_sample_rate=16000),
        representation=ComponentConfig(type="waveform"),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def _write_pcm_wav(path: Path, *, sample_rate: int = 16000, seconds: float = 0.03) -> None:
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


def _assert_same_state(left: nn.Module, right: nn.Module) -> None:
    left_state = left.state_dict()
    right_state = right.state_dict()
    assert tuple(left_state) == tuple(right_state)
    for key in left_state:
        assert torch.equal(left_state[key], right_state[key])


def test_plain_torch_module_full_ser_lifecycle(tmp_path: Path):
    torch.manual_seed(23)
    module = TinyWaveClassifier()
    assert not isinstance(module, SERModel)
    adapter = _adapter(module)

    # Adapter 持久化契约必须与原 module 完全同 key，不引入包装前缀。
    assert tuple(adapter.state_dict()) == tuple(module.state_dict())
    assert all(not key.startswith(("module.", "model.", "_module.")) for key in adapter.state_dict())

    optimizer = torch.optim.AdamW(adapter.parameters(), lr=0.01)
    training = Trainer(
        adapter,
        TrainerConfig(epochs=1, device="cpu"),
        optimizer=optimizer,
        run_id="torch-adapter-test",
    ).fit([_batch()])
    assert training.status == "completed"
    assert len(training.epochs) == 1

    evaluation = evaluate(adapter, [_batch()], num_classes=2)
    assert evaluation.sample_count == 2

    checkpoint = save_checkpoint(
        tmp_path / "adapter.pt",
        adapter,
        optimizer,
        epoch=1,
    )
    resumed = model_registry.create(TORCH_ADAPTER_MODEL_ID, **adapter.model_config)
    resumed_optimizer = torch.optim.AdamW(resumed.parameters(), lr=0.01)
    load_checkpoint(checkpoint, resumed, resumed_optimizer, restore_rng=False)
    _assert_same_state(adapter, resumed)

    artifact = export_model_artifact(
        tmp_path / "artifact",
        adapter,
        model_name=TORCH_ADAPTER_MODEL_ID,
        data_config=_data_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
    )
    loaded = load_model_artifact(artifact)
    assert isinstance(loaded.model, TorchModelAdapter)
    assert tuple(loaded.model.state_dict()) == tuple(module.state_dict())
    _assert_same_state(adapter, loaded.model)

    wav = tmp_path / "predict.wav"
    _write_pcm_wav(wav)
    prediction = EmotionPredictor.from_loaded_artifact(loaded).predict_file(wav)
    assert prediction.label_id in {0, 1}
    assert len(prediction.probabilities) == 2


def test_registry_static_spec_does_not_instantiate_underlying_factory():
    adapter = _adapter()
    before = _FACTORY_CALLS

    spec = model_registry.inspect_spec(TORCH_ADAPTER_MODEL_ID, adapter.model_config)

    assert _FACTORY_CALLS == before
    assert spec.model_id == TORCH_ADAPTER_MODEL_ID
    assert spec.required_inputs["waveform"].layout == "T"
    assert spec.supports_masks is True
    assert spec.supports_variable_length is True
    assert spec.num_classes == 2
    assert spec.expected_sample_rate == 16000


def test_unregistered_factory_is_allowed_locally_but_rejected_before_artifact_write(tmp_path: Path):
    adapter = _adapter(factory_id="tests.missing_factory")
    assert adapter(_batch()).logits.shape == (2, 2)

    target = tmp_path / "artifact"
    with pytest.raises(RegistryError, match="不可重建|未知 Torch factory"):
        export_model_artifact(
            target,
            adapter,
            model_name=TORCH_ADAPTER_MODEL_ID,
            data_config=_data_config(tmp_path),
            labels={0: "neutral", 1: "happy"},
        )
    assert not target.exists()


def test_manual_adapter_without_factory_can_checkpoint_but_not_export(tmp_path: Path):
    adapter = _adapter(factory_id=None, factory_params={})
    checkpoint = save_checkpoint(tmp_path / "manual.pt", adapter, None, epoch=0)
    assert checkpoint.is_file()

    target = tmp_path / "artifact"
    with pytest.raises(RegistryError, match="factory_id"):
        export_model_artifact(
            target,
            adapter,
            model_name=TORCH_ADAPTER_MODEL_ID,
            data_config=_data_config(tmp_path),
            labels={0: "neutral", 1: "happy"},
        )
    assert not target.exists()


def test_callable_factory_config_is_rejected_by_serializable_contract():
    with pytest.raises(ValidationError, match="JSON-safe"):
        _adapter(factory_params={"builder": lambda: TinyWaveClassifier()})


def test_adapter_rejects_runtime_classifier_dimension_mismatch():
    adapter = _adapter(module=TinyWaveClassifier(num_classes=3), num_classes=2)
    with pytest.raises(ValueError, match="类别维.*num_classes"):
        adapter(_batch())


def test_artifact_rejects_label_count_mismatch_before_creating_target(tmp_path: Path):
    adapter = _adapter()
    target = tmp_path / "artifact"
    with pytest.raises(ValueError, match="labels 数量.*num_classes"):
        export_model_artifact(
            target,
            adapter,
            model_name=TORCH_ADAPTER_MODEL_ID,
            data_config=_data_config(tmp_path),
            labels={0: "neutral"},
        )
    assert not target.exists()


def test_freeze_module_disables_gradients_without_changing_state_keys():
    module = TinyWaveClassifier()
    original_keys = tuple(module.state_dict())
    adapter = _adapter(module=module, freeze_module=True)

    assert tuple(adapter.state_dict()) == original_keys
    assert all(not parameter.requires_grad for parameter in adapter.parameters())



@pytest.mark.parametrize(
    "container_factory",
    [
        lambda adapter: nn.ModuleDict({"adapter": adapter}),
        lambda adapter: nn.Sequential(adapter),
    ],
)
def test_adapter_nested_state_dict_strict_round_trip(container_factory):
    torch.manual_seed(91)
    source_adapter = _adapter()
    source = container_factory(source_adapter)
    state = source.state_dict()

    assert state
    assert any("._module." in key for key in state)

    torch.manual_seed(92)
    target = container_factory(_adapter())
    target.load_state_dict(state, strict=True)

    target_state = target.state_dict()
    assert tuple(target_state) == tuple(state)
    for key, value in state.items():
        assert torch.equal(target_state[key], value)


def test_adapter_standalone_state_dict_keeps_original_module_keys():
    module = TinyWaveClassifier()
    adapter = _adapter(module=module)

    assert tuple(adapter.state_dict()) == tuple(module.state_dict())
    assert all("._module." not in key for key in adapter.state_dict())
