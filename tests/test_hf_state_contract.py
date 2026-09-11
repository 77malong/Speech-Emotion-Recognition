from types import SimpleNamespace

from torch import nn

from ser_lib.models import HFAudioClassifier, model_registry


class _FakeConfig:
    model_type = "fake_audio"
    hidden_size = 4

    def __init__(self, **values):
        self.hidden_size = values.get("hidden_size", 4)

    def to_dict(self):
        return {"model_type": self.model_type, "hidden_size": self.hidden_size}


class _FakeEncoder(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or _FakeConfig()
        self.projection = nn.Linear(1, self.config.hidden_size, bias=False)


def test_hf_registration_and_state_dict_key_shape_are_locked(monkeypatch):
    class AutoConfig:
        @staticmethod
        def for_model(model_type, **values):
            assert model_type == "fake_audio"
            return _FakeConfig(**values)

    class AutoModel:
        @staticmethod
        def from_config(config):
            return _FakeEncoder(config)

    monkeypatch.setattr(
        "ser_lib.models.adapters.huggingface._transformers",
        lambda: SimpleNamespace(AutoConfig=AutoConfig, AutoModel=AutoModel),
    )
    model = HFAudioClassifier(
        num_classes=2,
        encoder_config={"model_type": "fake_audio", "hidden_size": 4},
        dropout=0,
    )

    assert "hf_audio_classifier" in model_registry.names()
    descriptor = model_registry.descriptor("hf_audio_classifier")
    assert descriptor["id"] == "hf_audio_classifier"
    assert descriptor["status"] == "optional"
    assert tuple(model.state_dict()) == (
        "encoder.projection.weight",
        "classifier.weight",
        "classifier.bias",
    )
