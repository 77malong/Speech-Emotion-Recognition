import pytest
import torch

from ser_lib.data.errors import RepresentationError
from ser_lib.data.types import (
    AudioRecord,
    RepresentationOutput,
    SERBatch,
    TensorSpec,
    validate_representation_output,
)


def test_audio_record_treats_missing_start_as_zero():
    record = AudioRecord(uid="a", audio_path=__import__("pathlib").Path("a.wav"), end_ms=10)
    assert record.start_ms is None


def test_audio_record_rejects_non_positive_end_from_zero():
    with pytest.raises(ValueError, match="end_ms > start_ms"):
        AudioRecord(uid="a", audio_path=__import__("pathlib").Path("a.wav"), end_ms=0)


def test_tensor_spec_rejects_feature_dim_for_plain_waveform():
    with pytest.raises(ValueError, match="不允许配置 feature_dim"):
        TensorSpec(layout="T", feature_dim=1)


def test_ser_batch_rejects_misaligned_metadata():
    with pytest.raises(ValueError, match="uids/metadata"):
        SERBatch(
            inputs={"waveform": torch.zeros(2, 4)},
            lengths={"waveform": torch.tensor([4, 4])},
            masks={"waveform": torch.ones(2, 4, dtype=torch.bool)},
            labels=torch.tensor([0, 1]),
            uids=["only-one"],
            metadata=[{}, {}],
        )


def test_ser_batch_rejects_non_boolean_mask():
    with pytest.raises(ValueError, match="bool tensor"):
        SERBatch(
            inputs={"waveform": torch.zeros(1, 4)},
            lengths={"waveform": torch.tensor([4])},
            masks={"waveform": torch.ones(1, 4)},
            labels=None,
            uids=["a"],
            metadata=[{}],
        )



def test_representation_output_requires_length_for_temporal_key():
    output = RepresentationOutput(
        inputs={"waveform": torch.ones(8)},
        lengths={},
    )
    specs = {"waveform": TensorSpec(layout="T")}

    with pytest.raises(RepresentationError, match="缺少 lengths"):
        validate_representation_output(output, specs)


def test_representation_output_rejects_length_for_non_temporal_key():
    output = RepresentationOutput(
        inputs={"global": torch.ones(3)},
        lengths={"global": 3},
    )
    specs = {"global": TensorSpec(layout="D", feature_dim=3)}

    with pytest.raises(RepresentationError, match="非时序输入"):
        validate_representation_output(output, specs)


@pytest.mark.parametrize("length", [0, 7])
def test_representation_output_rejects_invalid_temporal_length(length: int):
    output = RepresentationOutput(
        inputs={"waveform": torch.ones(8)},
        lengths={"waveform": length},
    )
    specs = {"waveform": TensorSpec(layout="T")}

    with pytest.raises(RepresentationError):
        validate_representation_output(output, specs)


def test_representation_output_accepts_exact_temporal_length_contract():
    output = RepresentationOutput(
        inputs={
            "features": torch.ones(4, 6),
            "global": torch.ones(3),
        },
        lengths={"features": 6},
    )
    specs = {
        "features": TensorSpec(layout="FT", feature_dim=4),
        "global": TensorSpec(layout="D", feature_dim=3),
    }

    validate_representation_output(output, specs)



@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label", True),
        ("start_ms", 0.5),
        ("end_ms", 1.5),
        ("sample_rate_hint", 16000.5),
        ("sample_rate_hint", True),
    ],
)
def test_audio_record_rejects_values_manifest_parser_cannot_read(field: str, value):
    kwargs = {field: value}

    with pytest.raises(ValueError):
        AudioRecord(
            uid="roundtrip-safe",
            audio_path=__import__("pathlib").Path("a.wav"),
            **kwargs,
        )
