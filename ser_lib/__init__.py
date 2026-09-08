"""ser_lib：语音情感识别库。"""

__version__ = "0.2.0"

from ser_lib.core import Diagnostic, DiagnosticSeverity
from ser_lib.data import (
    CompatibilityReport,
    SERBatch,
    SERDataset,
    SERSample,
    TensorSpec,
    inspect_compatibility,
)
from ser_lib.artifacts import (
    ModelArtifactManifest,
    ModelCard,
    export_model_artifact,
    load_model_artifact,
    verify_model_artifact,
)
from ser_lib.engine import (
    ExperimentConfig,
    ExperimentValidationResult,
    ModelConfig,
    ObservabilityConfig,
    Trainer,
    TrainerConfig,
    TrainingResult,
    TrainingStatus,
    build_experiment_components,
    evaluate,
    validate_experiment,
    write_evaluation_report,
)
from ser_lib.inference import (
    BatchEmotionPredictor,
    BatchPredictionResult,
    EmotionPredictor,
    PredictionFailure,
    PredictionResult,
    StreamingConfig,
    StreamingEmotionRecognizer,
    StreamingLatency,
    StreamingPrediction,
    write_batch_predictions,
)
from ser_lib.models import (
    CNNBaseline,
    GRUBaseline,
    HFAudioClassifier,
    ModelOutput,
    SERModel,
    TransformerBaseline,
)

__all__ = [
    "Diagnostic", "DiagnosticSeverity",
    "CompatibilityReport", "inspect_compatibility",
    "SERDataset", "SERSample", "SERBatch", "TensorSpec",
    "ModelCard", "ModelArtifactManifest", "export_model_artifact",
    "verify_model_artifact", "load_model_artifact",
    "SERModel", "ModelOutput", "CNNBaseline", "GRUBaseline",
    "TransformerBaseline", "HFAudioClassifier",
    "Trainer", "TrainerConfig", "ObservabilityConfig", "TrainingResult", "TrainingStatus",
    "evaluate", "write_evaluation_report",
    "ExperimentConfig", "ExperimentValidationResult", "validate_experiment",
    "ModelConfig", "build_experiment_components",
    "EmotionPredictor", "PredictionResult",
    "PredictionFailure", "BatchPredictionResult", "BatchEmotionPredictor",
    "write_batch_predictions",
    "StreamingConfig", "StreamingPrediction", "StreamingLatency",
    "StreamingEmotionRecognizer",
]
