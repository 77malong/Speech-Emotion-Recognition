import json
from pathlib import Path

from ser_lib.data import AudioRecord
from ser_lib.foundation.events import EventContext, ProgressEvent
from ser_lib.inference import BatchEmotionPredictor, PredictionResult
from ser_lib.inference.events import PredictionEvent


class FakePredictor:
    def predict_record(self, record: AudioRecord) -> PredictionResult:
        if record.uid == "bad":
            raise ValueError("bad audio")
        label_id = 1 if record.uid.endswith("1") else 0
        probabilities = [0.2, 0.8] if label_id == 1 else [0.9, 0.1]
        return PredictionResult(
            uid=record.uid,
            label_id=label_id,
            emotion="happy" if label_id == 1 else "neutral",
            confidence=max(probabilities),
            probabilities=probabilities,
        )

    def predict_records(self, records):
        if any(record.uid == "bad" for record in records):
            raise ValueError("batch contains bad audio")
        return [self.predict_record(record) for record in records]


def _records(*uids: str) -> list[AudioRecord]:
    return [AudioRecord(uid=uid, audio_path=Path(f"{uid}.wav")) for uid in uids]


def test_batch_predict_emits_prediction_event_as_each_result_finishes():
    events = []
    context = EventContext(run_id="run-batch")
    predictor = BatchEmotionPredictor(FakePredictor())

    result = predictor.predict_records(
        _records("sample-0", "sample-1", "sample-2"),
        batch_size=2,
        event_callback=events.append,
        event_context=context,
    )

    predictions = [event for event in events if isinstance(event, PredictionEvent)]
    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert result.succeeded == 3
    assert [event.uid for event in predictions] == ["sample-0", "sample-1", "sample-2"]
    assert [event.details["completed"] for event in predictions] == [1, 2, 3]
    assert predictions[1].emotion == "happy"
    assert predictions[1].label_id == 1
    assert predictions[1].context.run_id == "run-batch"
    assert [event.completed for event in progress] == [1, 2, 3]
    json.dumps(predictions[0].to_dict(), ensure_ascii=False)


def test_batch_predict_only_emits_prediction_events_for_successes():
    events = []
    predictor = BatchEmotionPredictor(FakePredictor())

    result = predictor.predict_records(
        _records("sample-0", "bad", "sample-1"),
        batch_size=3,
        fail_fast=False,
        event_callback=events.append,
    )

    predictions = [event for event in events if isinstance(event, PredictionEvent)]
    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert result.succeeded == 2
    assert result.failed == 1
    assert [event.uid for event in predictions] == ["sample-0", "sample-1"]
    assert [event.completed for event in progress] == [1, 2, 3]
    assert progress[-1].message == "succeeded=2, failed=1"


def test_prediction_event_validates_and_serializes_public_fields():
    event = PredictionEvent(
        uid="audio-001",
        label_id=2,
        emotion="sad",
        confidence=0.92,
        probabilities=(0.03, 0.05, 0.92),
    )

    payload = event.to_dict()
    assert payload["schema_version"] == 2
    assert payload["event_type"] == "prediction"
    assert payload["uid"] == "audio-001"
    assert payload["emotion"] == "sad"
    assert payload["confidence"] == 0.92
    assert payload["probabilities"] == [0.03, 0.05, 0.92]
    json.dumps(payload)
