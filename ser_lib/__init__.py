"""ser_lib：语音情感识别库。

根包使用惰性解析，避免导入轻量子包时连带加载 torch、训练引擎、
推理和模型实现。规范入口仍以各一级领域包为准。
"""

from __future__ import annotations

import importlib
from typing import Any

from ser_lib._version import __version__ as __version__

_MODULE_EXPORTS: dict[str, tuple[str, ...]] = {
    "ser_lib.foundation": ("Diagnostic", "DiagnosticSeverity"),
    "ser_lib.config": ("build_experiment_config",),
    "ser_lib.data": (
        "SERDataset", "SERSample", "SERBatch", "TensorSpec", "ComponentDescriptor",
    ),
    "ser_lib.artifacts": (
        "ArtifactCatalog", "ArtifactEntry", "ArtifactScanFailure",
        "ModelArtifactManifest", "ModelCard", "export_model_artifact",
        "inspect_model_artifact", "load_model_artifact",
        "scan_model_artifacts", "verify_model_artifact",
    ),
    "ser_lib.engine": (
        "CompatibilityReport", "inspect_compatibility",
        "EVALUATION_RUN_SCHEMA_VERSION", "RUN_RECORD_SCHEMA_VERSION",
        "CheckpointCatalog", "CheckpointInfo", "CheckpointKind", "CheckpointScanFailure",
        "EtaEstimator", "EtaSnapshot", "EvaluationPredictionFileInfo",
        "EvaluationReportInfo", "EvaluationRunCatalog", "EvaluationRunInfo",
        "EvaluationRunMetadata", "EvaluationRunScanFailure", "ExperimentConfig",
        "ExperimentValidationResult", "ModelConfig", "ObservabilityConfig", "Trainer",
        "TrainerConfig", "TrainingHistoryInfo", "TrainingResult", "TrainingRunCatalog",
        "TrainingRunInfo", "TrainingRunMetadata", "TrainingRunScanFailure", "TrainingStatus",
        "build_evaluation_run_metadata", "build_experiment_components",
        "build_training_run_metadata", "evaluate", "inspect_checkpoint_file",
        "inspect_evaluation_prediction_file", "inspect_evaluation_report",
        "iter_evaluation_predictions", "load_evaluation_run_info",
        "load_training_history", "load_training_run_info", "scan_checkpoints",
        "scan_evaluation_runs", "scan_training_runs", "validate_experiment",
        "write_evaluation_report", "write_evaluation_run_info", "write_training_run_info",
    ),
    "ser_lib.inference": (
        "BatchEmotionPredictor", "BatchPredictionResult", "BatchPredictionSink",
        "EmotionPredictor", "JsonlBatchPredictionSink", "PredictionFailure",
        "PredictionResult", "StreamingConfig", "StreamingEmotionRecognizer",
        "StreamingLatency", "StreamingPrediction", "write_batch_predictions",
    ),
    "ser_lib.models": (
        "CNNBaseline", "GRUBaseline", "HFAudioClassifier",
        "ModelOutput", "SERModel", "TransformerBaseline",
    ),
    "ser_lib.runtime": (
        "RuntimeCapabilities", "RuntimeDevice", "RuntimeMetrics",
        "get_runtime_capabilities", "get_runtime_metrics",
    ),
}

_LAZY_EXPORTS = {
    name: (module_name, name)
    for module_name, names in _MODULE_EXPORTS.items()
    for name in names
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "CompatibilityReport",
    "inspect_compatibility",
    "ComponentDescriptor",
    "RuntimeDevice",
    "RuntimeCapabilities",
    "RuntimeMetrics",
    "get_runtime_capabilities",
    "get_runtime_metrics",
    "SERDataset",
    "SERSample",
    "SERBatch",
    "TensorSpec",
    "ModelCard",
    "ModelArtifactManifest",
    "ArtifactEntry",
    "ArtifactScanFailure",
    "ArtifactCatalog",
    "scan_model_artifacts",
    "export_model_artifact",
    "inspect_model_artifact",
    "verify_model_artifact",
    "load_model_artifact",
    "SERModel",
    "ModelOutput",
    "CNNBaseline",
    "GRUBaseline",
    "TransformerBaseline",
    "HFAudioClassifier",
    "Trainer",
    "TrainerConfig",
    "ObservabilityConfig",
    "TrainingResult",
    "TrainingStatus",
    "EtaSnapshot",
    "EtaEstimator",
    "TrainingRunMetadata",
    "build_training_run_metadata",
    "RUN_RECORD_SCHEMA_VERSION",
    "TrainingRunInfo",
    "TrainingRunScanFailure",
    "TrainingRunCatalog",
    "write_training_run_info",
    "load_training_run_info",
    "scan_training_runs",
    "TrainingHistoryInfo",
    "load_training_history",
    "CheckpointKind",
    "CheckpointInfo",
    "CheckpointScanFailure",
    "CheckpointCatalog",
    "inspect_checkpoint_file",
    "scan_checkpoints",
    "EVALUATION_RUN_SCHEMA_VERSION",
    "EvaluationRunMetadata",
    "EvaluationRunInfo",
    "EvaluationPredictionFileInfo",
    "inspect_evaluation_prediction_file",
    "build_evaluation_run_metadata",
    "write_evaluation_run_info",
    "load_evaluation_run_info",
    "EvaluationRunScanFailure",
    "EvaluationRunCatalog",
    "scan_evaluation_runs",
    "EvaluationReportInfo",
    "inspect_evaluation_report",
    "iter_evaluation_predictions",
    "evaluate",
    "write_evaluation_report",
    "ExperimentConfig",
    "build_experiment_config",
    "ExperimentValidationResult",
    "validate_experiment",
    "ModelConfig",
    "build_experiment_components",
    "EmotionPredictor",
    "PredictionResult",
    "PredictionFailure",
    "BatchPredictionSink",
    "JsonlBatchPredictionSink",
    "BatchPredictionResult",
    "BatchEmotionPredictor",
    "write_batch_predictions",
    "StreamingConfig",
    "StreamingPrediction",
    "StreamingLatency",
    "StreamingEmotionRecognizer",
]
