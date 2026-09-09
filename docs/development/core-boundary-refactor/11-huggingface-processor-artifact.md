# Stage 11 — Hugging Face Adapter、Processor 与 Artifact 闭环

## 目标

在通用 Torch adapter 稳定后，扩展现有 `hf_audio_classifier`，支持真实 Hugging Face 音频模型家族、processor 持久化和离线 artifact 重建，并用真实 tiny 模型而不是仅 fake monkeypatch 证明兼容性。

## 前置条件

- Stage 10 通用 Torch adapter 与 registry/artifact 基础闭环通过。
- 保留历史注册 ID `hf_audio_classifier` 和旧 artifact 重建语义。

## 目标结构

- 将旧 `models/pretrained.py` 的正式实现迁入 `models/adapters/huggingface.py`
- 配置继续定义在 `config/model.py`
- artifact 中保存 processor/feature extractor 的可复现元数据与必要 assets
- `pyproject.toml` 增加/收敛 `[hf]` optional extra，并按需要保留 `[pretrained]` 兼容别名

## 首期模型族

优先验证：

- Wav2Vec2
- HuBERT
- WavLM

后续候选只有在独立契约测试通过后才能声明支持：Data2Vec Audio、UniSpeech、Whisper encoder、AST 等。

## 具体任务

1. 区分 waveform encoder→pooling→SER head 与 audio-classification→direct logits 两类策略。
2. 根据模型族正确处理 `input_values`、attention mask、output length、hidden state/logits。
3. processor/feature extractor 的采样率、normalization、padding、feature shape、mask 语义写入可复现 artifact 契约。
4. 默认 `local_files_only=True`，禁止隐式网络下载；继续禁用 `trust_remote_code`。
5. num_labels、num_classes、label2id/id2label 与 artifact labels 严格互验。
6. 分类头重置必须显式配置并记录，禁止静默忽略 mismatch。
7. dtype/device/AMP 不通过 `device_map=auto` 隐式处理，训练时遵循统一执行端。
8. 用本地 tiny config + 随机权重建立真实 Transformers 集成测试，不在 CI 下载大模型。
9. 验证 padding/mask 不变性、CPU train、artifact export/load、离线 processor 重建、checkpoint resume、missing extra 错误。
10. 先验证依赖 resolver/min-max matrix，再修改正式支持范围；不能仅因某一版本可安装就声称整个 `<6` 范围兼容。

## 非目标

- 不建立 HF 专用 Trainer。
- 不支持任意托管在 HF Hub 的第三方论文模型。
- 不自动安装 accelerate/datasets/sentencepiece，只有真实调用需要时才加入 extra。

## 验收标准

- 至少一个真实 tiny Wav2Vec2/HuBERT/WavLM 路径完成 train/eval/predict/artifact/resume。
- 完全离线重新加载 artifact 时 processor 和前向行为一致。
- 旧 `hf_audio_classifier` artifact 仍按既定兼容规则工作。
- 基础安装不引入 transformers；`.[hf]` 安装后 `pip check` 通过。

## 风险

- 不同 checkpoint 对 attention mask/normalization 的语义不同。
- processor 未保存导致训练和离线推理输入不一致。
- HF 分类头和 labels 错位但未及时失败。
- 依赖范围过宽，fake test 掩盖真实 transformers API 差异。

## 建议提交

`feat(models): harden huggingface audio adapter and processor artifacts`
