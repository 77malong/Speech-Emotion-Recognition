from __future__ import annotations

import pytest
import torch

from ser_lib.data import SERBatch, TensorSpec
from ser_lib.engine import evaluate
from ser_lib.foundation.events import LifecycleEvent
from ser_lib.models import ModelOutput, ModelSpec, SERModel


class CallbackContractModel(SERModel):
    @property
    def model_spec(self) -> ModelSpec:
        return ModelSpec(
            model_id="callback_contract",
            required_inputs={"scores": TensorSpec(layout="D", feature_dim=2)},
            supports_masks=False,
            supports_variable_length=False,
            num_classes=2,
        )

    @property
    def model_config(self):
        return {}

    def forward(self, batch: SERBatch) -> ModelOutput:
        return ModelOutput(logits=batch.inputs["scores"])


def _batch() -> SERBatch:
    return SERBatch(
        inputs={"scores": torch.tensor([[2.0, 0.0]])},
        lengths={},
        masks={},
        labels=torch.tensor([0], dtype=torch.long),
        uids=["sample"],
        metadata=[{}],
    )


def test_evaluator_callback_failure_is_fail_fast_and_restores_model_mode():
    model = CallbackContractModel()
    model.train()
    delivered: list[tuple[str, str]] = []

    def callback(event) -> None:
        if isinstance(event, LifecycleEvent) and event.status == "started":
            raise RuntimeError("callback failed")
        if isinstance(event, LifecycleEvent):
            delivered.append((event.stage, event.status))

    with pytest.raises(RuntimeError, match="callback failed"):
        evaluate(
            model,
            [_batch()],
            num_classes=2,
            event_callback=callback,
        )

    assert model.training is True
    assert delivered == [("evaluation", "failed")]
