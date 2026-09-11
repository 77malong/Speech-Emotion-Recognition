"""Hugging Face audio models adapted to the stable SER model contract.

Transformers remains optional. Loading defaults to local files only, remote code is
never trusted, and feature-extractor state is persisted as JSON-safe configuration.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any, Literal

import torch
from torch import nn

from ser_lib.config.model import HFAudioClassifierConfig, HFProcessorConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.models.base import ModelOutput, SERModel
from ser_lib.models.registry import ModelDescriptor, model_registry
from ser_lib.models.specs import ModelSpec

_SUPPORTED_PROCESSORS = {"Wav2Vec2FeatureExtractor"}
_VERIFIED_AUDIO_FAMILIES = {"wav2vec2", "hubert", "wavlm"}


def _transformers() -> Any:
    try:
        return importlib.import_module("transformers")
    except ImportError as exc:
        raise ImportError(
            "hf_audio_classifier 需要可选依赖；请安装 ser-lib[hf] "
            "（ser-lib[pretrained] 仍是兼容别名）"
        ) from exc


def _normalize_label_names(value: Mapping[int, str] | None) -> dict[int, str] | None:
    if value is None:
        return None
    return {int(index): str(label) for index, label in value.items()}


def _snapshot_processor(processor: object) -> HFProcessorConfig:
    class_name = type(processor).__name__
    if class_name not in _SUPPORTED_PROCESSORS:
        raise ValueError(
            f"当前仅验证 {_SUPPORTED_PROCESSORS}，不声明支持 processor {class_name!r}"
        )
    to_dict = getattr(processor, "to_dict", None)
    if not callable(to_dict):
        raise ValueError("Hugging Face processor 必须提供 to_dict()")
    raw = to_dict()
    if not isinstance(raw, dict):
        raise ValueError("Hugging Face processor.to_dict() 必须返回映射")
    return HFProcessorConfig.model_validate({"class_name": class_name, "config": raw})


def _load_processor(
    transformers: Any,
    config: HFAudioClassifierConfig,
) -> tuple[Any | None, HFProcessorConfig | None]:
    if config.processor_config is not None:
        class_name = config.processor_config.class_name
        if class_name not in _SUPPORTED_PROCESSORS:
            raise ValueError(f"不支持 processor class: {class_name!r}")
        processor_class = getattr(transformers, class_name, None)
        if processor_class is None:
            raise ImportError(f"当前 transformers 未提供 {class_name}")
        from_dict = getattr(processor_class, "from_dict", None)
        if not callable(from_dict):
            raise ValueError(f"{class_name} 不支持 from_dict() 离线重建")
        processor = from_dict(dict(config.processor_config.config))
    elif config.processor_name_or_path is not None:
        auto_feature_extractor = getattr(transformers, "AutoFeatureExtractor", None)
        if auto_feature_extractor is None:
            raise ImportError("当前 transformers 未提供 AutoFeatureExtractor")
        processor = auto_feature_extractor.from_pretrained(
            config.processor_name_or_path,
            local_files_only=config.local_files_only,
            revision=config.processor_revision or config.revision,
            trust_remote_code=False,
        )
    else:
        return None, None

    snapshot = _snapshot_processor(processor)
    sampling_rate = snapshot.config.get("sampling_rate")
    if not isinstance(sampling_rate, int) or sampling_rate < 1:
        raise ValueError("processor config 缺少合法 sampling_rate")
    if sampling_rate != config.expected_sample_rate:
        raise ValueError(
            "processor sampling_rate 与 expected_sample_rate 不一致: "
            f"{sampling_rate} != {config.expected_sample_rate}"
        )
    return processor, snapshot


def _set_label_mapping(hf_config: Any, labels: Mapping[int, str]) -> None:
    id2label = {int(index): str(label) for index, label in labels.items()}
    label2id = {label: index for index, label in id2label.items()}
    hf_config.num_labels = len(id2label)
    hf_config.id2label = id2label
    hf_config.label2id = label2id


def _label_mapping_matches(hf_config: Any, labels: Mapping[int, str]) -> bool:
    expected = {int(index): str(label) for index, label in labels.items()}
    raw_id2label = getattr(hf_config, "id2label", None)
    if not isinstance(raw_id2label, Mapping):
        return False
    try:
        actual = {int(index): str(label) for index, label in raw_id2label.items()}
    except (TypeError, ValueError):
        return False
    return actual == expected and int(getattr(hf_config, "num_labels", -1)) == len(expected)


def _reset_pretrained_classifier_head(model: Any) -> None:
    """Reinitialize the native HF classifier after pretrained weights are loaded.

    ``ignore_mismatched_sizes`` only helps when the class count changes. An explicit
    reset must also discard a same-shaped head when label semantics change, while
    preserving the pretrained encoder/projector. Use public PyTorch module reset
    hooks rather than Transformers private initialization helpers so the behavior
    stays stable across supported Transformers releases.
    """
    classifier = getattr(model, "classifier", None)
    if not isinstance(classifier, nn.Module):
        raise ValueError("HF audio-classification model 缺少可重置的 classifier")

    reset_count = 0

    def reset_module(module: nn.Module) -> None:
        nonlocal reset_count
        reset_parameters = getattr(module, "reset_parameters", None)
        if callable(reset_parameters):
            reset_parameters()
            reset_count += 1

    classifier.apply(reset_module)
    if reset_count == 0:
        raise ValueError("HF audio-classification classifier 不支持参数重置")


def _build_hf_model(transformers: Any, config: HFAudioClassifierConfig) -> Any:
    if config.encoder_config is not None:
        raw = dict(config.encoder_config)
        model_type = raw.pop("model_type", None)
        if not isinstance(model_type, str) or not model_type:
            raise ValueError("encoder_config 必须包含非空 model_type")
        hf_config = transformers.AutoConfig.for_model(model_type, **raw)
        if config.strategy == "audio_classification":
            assert config.label_names is not None
            if not _label_mapping_matches(hf_config, config.label_names):
                if not config.reset_classifier_head:
                    raise ValueError(
                        "HF classification config 的 num_labels/label2id/id2label 与 "
                        "label_names 不一致；如需重置分类头必须显式设置 reset_classifier_head=True"
                    )
                _set_label_mapping(hf_config, config.label_names)
            return transformers.AutoModelForAudioClassification.from_config(hf_config)
        return transformers.AutoModel.from_config(hf_config)

    source = config.pretrained_model_name_or_path
    if config.strategy == "audio_classification":
        assert config.label_names is not None
        hf_config = transformers.AutoConfig.from_pretrained(
            source,
            local_files_only=config.local_files_only,
            revision=config.revision,
            trust_remote_code=False,
        )
        if not _label_mapping_matches(hf_config, config.label_names):
            if not config.reset_classifier_head:
                raise ValueError(
                    "HF classification checkpoint 的 num_labels/label2id/id2label 与 "
                    "label_names 不一致；如需重置分类头必须显式设置 reset_classifier_head=True"
                )
            _set_label_mapping(hf_config, config.label_names)
        model = transformers.AutoModelForAudioClassification.from_pretrained(
            source,
            config=hf_config,
            local_files_only=config.local_files_only,
            revision=config.revision,
            trust_remote_code=False,
            ignore_mismatched_sizes=config.reset_classifier_head,
        )
        if config.reset_classifier_head:
            _reset_pretrained_classifier_head(model)
        return model

    return transformers.AutoModel.from_pretrained(
        source,
        local_files_only=config.local_files_only,
        revision=config.revision,
        trust_remote_code=False,
    )


class HFAudioClassifier(SERModel):
    """Hugging Face waveform encoder/classifier adapted to ``SERBatch``.

    ``encoder_head`` preserves the historical SER-owned classification head.
    ``audio_classification`` consumes logits from a native HF classification model and
    therefore requires explicit label names so its head mapping can be verified.
    """

    def __init__(
        self,
        num_classes: int,
        pretrained_model_name_or_path: str | None = None,
        encoder_config: dict[str, Any] | None = None,
        local_files_only: bool = True,
        revision: str | None = None,
        freeze_encoder: bool = False,
        dropout: float = 0.1,
        pooling: Literal["mean", "max"] = "mean",
        expected_sample_rate: int = 16000,
        strategy: Literal["encoder_head", "audio_classification"] = "encoder_head",
        reset_classifier_head: bool = False,
        label_names: dict[int, str] | None = None,
        processor_name_or_path: str | None = None,
        processor_config: dict[str, Any] | HFProcessorConfig | None = None,
        processor_revision: str | None = None,
    ) -> None:
        super().__init__()
        config = HFAudioClassifierConfig(
            num_classes=num_classes,
            pretrained_model_name_or_path=pretrained_model_name_or_path,
            encoder_config=encoder_config,
            local_files_only=local_files_only,
            revision=revision,
            freeze_encoder=freeze_encoder,
            dropout=dropout,
            pooling=pooling,
            expected_sample_rate=expected_sample_rate,
            strategy=strategy,
            reset_classifier_head=reset_classifier_head,
            label_names=label_names,
            processor_name_or_path=processor_name_or_path,
            processor_config=(
                HFProcessorConfig.model_validate(processor_config)
                if isinstance(processor_config, dict)
                else processor_config
            ),
            processor_revision=processor_revision,
        )
        transformers = _transformers()
        self.encoder: Any = _build_hf_model(transformers, config)
        serialized = self.encoder.config.to_dict()
        if not isinstance(serialized, dict) or not serialized.get("model_type"):
            raise ValueError("Hugging Face model config.to_dict() 必须包含 model_type")

        model_type = str(serialized["model_type"])
        self.verified_family = model_type if model_type in _VERIFIED_AUDIO_FAMILIES else None
        self.processor, processor_snapshot = _load_processor(transformers, config)
        self.processor_config: HFProcessorConfig | None = processor_snapshot
        self.num_classes = config.num_classes
        self.encoder_config = serialized
        self.local_files_only = config.local_files_only
        self.revision = config.revision
        self.freeze_encoder = config.freeze_encoder
        self.dropout_probability = config.dropout
        self.pooling = config.pooling
        self.expected_sample_rate = config.expected_sample_rate
        self.strategy = config.strategy
        self.reset_classifier_head = config.reset_classifier_head
        self.label_names = _normalize_label_names(config.label_names)
        self.processor_revision = config.processor_revision
        self.dropout: nn.Module
        self.classifier: nn.Linear | None

        if self.strategy == "encoder_head":
            hidden_size = getattr(self.encoder.config, "hidden_size", None)
            if not isinstance(hidden_size, int) or hidden_size < 1:
                raise ValueError("Hugging Face encoder 配置缺少合法 hidden_size")
            self.dropout = nn.Dropout(config.dropout)
            self.classifier = nn.Linear(hidden_size, config.num_classes)
        else:
            self.dropout = nn.Identity()
            self.classifier = None

        if self.freeze_encoder:
            self._freeze_encoder_parameters()

    @property
    def model_spec(self) -> ModelSpec:
        return _model_spec_from_config(self.model_config)

    @property
    def model_config(self) -> dict[str, Any]:
        return HFAudioClassifierConfig(
            num_classes=self.num_classes,
            encoder_config=self.encoder_config,
            local_files_only=True,
            revision=None,
            freeze_encoder=self.freeze_encoder,
            dropout=self.dropout_probability,
            pooling=self.pooling,
            expected_sample_rate=self.expected_sample_rate,
            strategy=self.strategy,
            reset_classifier_head=self.reset_classifier_head,
            label_names=self.label_names,
            processor_config=self.processor_config,
            processor_revision=None,
        ).model_dump(mode="json")

    @property
    def artifact_processor_config(self) -> dict[str, Any] | None:
        if self.processor_config is None:
            return None
        return self.processor_config.model_dump(mode="json")

    def validate_artifact_labels(self, labels: Mapping[int, str]) -> None:
        if len(labels) != self.num_classes:
            raise ValueError(
                f"artifact labels 数量与 HF num_classes 不一致: {len(labels)} != {self.num_classes}"
            )
        if self.strategy == "audio_classification":
            expected = self.label_names or {}
            actual = {int(index): str(label) for index, label in labels.items()}
            if actual != expected:
                raise ValueError("artifact labels 与 HF classification label2id/id2label 不一致")

    def _freeze_encoder_parameters(self) -> None:
        if self.strategy == "encoder_head":
            self.encoder.requires_grad_(False)
            return
        base_model = getattr(self.encoder, "base_model", None)
        if not isinstance(base_model, nn.Module):
            raise ValueError("HF classification model 缺少可识别的 base_model，无法只冻结 encoder")
        base_model.requires_grad_(False)

    def train(self, mode: bool = True) -> "HFAudioClassifier":
        super().train(mode)
        if self.freeze_encoder:
            if self.strategy == "encoder_head":
                self.encoder.eval()
            else:
                base_model = getattr(self.encoder, "base_model", None)
                if isinstance(base_model, nn.Module):
                    base_model.eval()
        return self

    def _mask(self, batch: SERBatch, waveform: torch.Tensor) -> torch.Tensor:
        batch_size, time = waveform.shape
        lengths = batch.lengths.get("waveform")
        mask = batch.masks.get("waveform")
        if lengths is None and mask is None:
            return torch.ones(batch_size, time, dtype=torch.bool, device=waveform.device)
        if lengths is not None:
            if lengths.shape != (batch_size,):
                raise ValueError("waveform lengths 必须是 [B]")
            if torch.any(lengths <= 0) or torch.any(lengths > time):
                raise ValueError("waveform lengths 必须位于 [1,T]")
            expected = torch.arange(time, device=waveform.device).unsqueeze(0) < (
                lengths.to(waveform.device).unsqueeze(1)
            )
            if mask is None:
                return expected
        if mask is None or mask.shape != (batch_size, time):
            raise ValueError("waveform mask 必须是 [B,T]")
        mask = mask.to(device=waveform.device, dtype=torch.bool)
        if lengths is not None and not torch.equal(mask, expected):
            raise ValueError("waveform mask 必须是由 lengths 定义的连续前缀 mask")
        if torch.any(mask.sum(1) == 0):
            raise ValueError("waveform mask 每行至少包含一个有效采样点")
        return mask

    def _prepare_waveform(
        self,
        waveform: torch.Tensor,
        valid: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        if self.processor_config is None:
            return waveform, valid.to(torch.long)
        raw = self.processor_config.config
        prepared = waveform
        if bool(raw.get("do_normalize", False)):
            weights = valid.to(waveform.dtype)
            counts = weights.sum(dim=1, keepdim=True).clamp_min(1)
            means = (waveform * weights).sum(dim=1, keepdim=True) / counts
            variances = ((waveform - means).square() * weights).sum(dim=1, keepdim=True) / counts
            prepared = (waveform - means) / torch.sqrt(variances + 1e-7)
        padding_value = float(raw.get("padding_value", 0.0))
        prepared = torch.where(valid, prepared, torch.full_like(prepared, padding_value))
        if bool(raw.get("return_attention_mask", False)):
            return prepared, valid.to(torch.long)
        return prepared, None

    def _encoded_mask(self, valid: torch.Tensor, encoded_time: int) -> torch.Tensor:
        lengths = valid.sum(dim=1).to(torch.long)
        length_fn = getattr(self.encoder, "_get_feat_extract_output_lengths", None)
        if callable(length_fn):
            encoded_lengths = length_fn(lengths)
        else:
            kernels = getattr(self.encoder.config, "conv_kernel", None)
            strides = getattr(self.encoder.config, "conv_stride", None)
            if isinstance(kernels, (list, tuple)) and isinstance(strides, (list, tuple)):
                if len(kernels) != len(strides) or not kernels:
                    raise ValueError("HF conv_kernel/conv_stride 配置不完整")
                encoded_lengths = lengths
                for kernel, stride in zip(kernels, strides):
                    encoded_lengths = torch.div(
                        encoded_lengths - int(kernel),
                        int(stride),
                        rounding_mode="floor",
                    ) + 1
            elif encoded_time == valid.shape[1]:
                encoded_lengths = lengths
            else:
                raise ValueError("HF encoder 发生时间下采样但未提供可验证的输出长度变换")
        encoded_lengths = encoded_lengths.to(device=valid.device, dtype=torch.long)
        if torch.any(encoded_lengths <= 0) or torch.any(encoded_lengths > encoded_time):
            raise ValueError("HF encoder 输出长度计算结果超出有效范围")
        return torch.arange(encoded_time, device=valid.device).unsqueeze(0) < encoded_lengths.unsqueeze(1)

    def forward(self, batch: SERBatch) -> ModelOutput:
        waveform = batch.inputs.get("waveform")
        if waveform is None:
            raise ValueError("HFAudioClassifier 需要 batch.inputs['waveform']")
        if waveform.dim() != 2 or waveform.shape[0] < 1 or waveform.shape[1] < 1:
            raise ValueError("HFAudioClassifier 期望非空 waveform [B,T]")
        if not waveform.is_floating_point():
            raise ValueError("waveform 必须是浮点 tensor")

        valid = self._mask(batch, waveform)
        input_values, attention_mask = self._prepare_waveform(waveform, valid)
        options: dict[str, Any] = {"input_values": input_values, "return_dict": True}
        if attention_mask is not None:
            options["attention_mask"] = attention_mask
        output = self.encoder(**options)

        if self.strategy == "audio_classification":
            logits = getattr(output, "logits", None)
            if not isinstance(logits, torch.Tensor) or logits.dim() != 2:
                raise ValueError("HF audio-classification model 必须返回 logits [B,C]")
            if logits.shape[1] != self.num_classes:
                raise ValueError(
                    "HF classification logits 类别维与 num_classes 不一致: "
                    f"{logits.shape[1]} != {self.num_classes}"
                )
            return ModelOutput(logits=logits)

        hidden = getattr(output, "last_hidden_state", None)
        if not isinstance(hidden, torch.Tensor) or hidden.dim() != 3:
            raise ValueError("Hugging Face encoder 必须返回 last_hidden_state [B,T,D]")
        encoded_valid = self._encoded_mask(valid, hidden.shape[1])
        if self.pooling == "mean":
            weights = encoded_valid.unsqueeze(-1).to(hidden.dtype)
            embeddings = (hidden * weights).sum(1) / weights.sum(1).clamp_min(1)
        else:
            embeddings = hidden.masked_fill(
                ~encoded_valid.unsqueeze(-1), float("-inf")
            ).max(1).values
        if self.classifier is None:
            raise RuntimeError("encoder_head strategy 缺少 SER classifier")
        return ModelOutput(
            logits=self.classifier(self.dropout(embeddings)),
            embeddings=embeddings,
        )


def _model_spec_from_config(params: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        model_id="hf_audio_classifier",
        required_inputs={"waveform": TensorSpec(layout="T")},
        supports_masks=True,
        supports_variable_length=True,
        num_classes=int(params["num_classes"]),
        expected_sample_rate=int(params["expected_sample_rate"]),
    )


model_registry.register(
    "hf_audio_classifier",
    HFAudioClassifier,
    config_model=HFAudioClassifierConfig,
    descriptor=ModelDescriptor(
        id="hf_audio_classifier",
        display_name="Hugging Face 音频分类适配器",
        description=(
            "可选依赖、默认仅本地加载；已验证 Wav2Vec2/HuBERT/WavLM encoder family，"
            "支持 processor 快照与 artifact 离线重建。"
        ),
        config_schema=HFAudioClassifierConfig.model_json_schema(),
        input_layouts={"waveform": "T"},
        status="optional",
    ),
    spec_factory=_model_spec_from_config,
)


__all__ = ["HFAudioClassifier", "HFAudioClassifierConfig", "HFProcessorConfig"]
