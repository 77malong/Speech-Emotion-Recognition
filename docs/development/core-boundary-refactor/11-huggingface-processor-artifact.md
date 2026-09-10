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

## 实施记录

Stage 11 开始前重新读取并以 `docs/development/SER_LIB_CORE_BOUNDARY_AUDIT.md`、`docs/development/SER_LIB_CORE_BOUNDARY_EVIDENCE.md` 与本阶段计划作为实现依据。实现严格限定在 HF adapter、processor、artifact 和依赖验证范围，没有新增 HF 专用 Trainer，也没有提前进入 Stage 12 的最终发布整理。

实际完成：

- 正式实现迁至 `ser_lib/models/adapters/huggingface.py`，物理删除旧 `ser_lib/models/pretrained.py`；持久化注册 ID `hf_audio_classifier` 保持不变，public API 与 wheel smoke 明确验证旧模块不可导入。
- 中央配置新增 `HFProcessorConfig`，processor 通过类名和 JSON-safe 配置快照离线重建；基础安装不依赖 Transformers，新增 `[hf]` extra，并保留 `[pretrained]` 兼容别名。
- `HFAudioClassifier` 支持 `encoder_head` 与 `audio_classification` 两条策略；后者使用原生 HF logits，不重复叠加 SER 分类头，并严格校验 `num_labels`、`num_classes`、`id2label`、`label2id` 与 artifact labels。分类头不匹配只有显式 `reset_classifier_head=True` 才允许重置。
- processor snapshot 写入 `processor_config.json` 并纳入 artifact `files_sha256`；manifest 同时保存同一快照，离线 load 后验证 processor identity 与 label contract。旧无 processor 的 artifact 继续按原兼容规则读取，没有伪造格式迁移。
- 默认继续 `local_files_only=True`、`trust_remote_code=False`，不使用 `device_map=auto`；训练、评估与推理仍服从统一 SER 执行端。
- 删除旧 nearest-interpolation encoded mask 假设，优先使用 HF 模型 `_get_feat_extract_output_lengths()`，必要时按 `conv_kernel/conv_stride` 计算真实输出长度。
- 用本地 tiny config + 随机权重真实验证 Wav2Vec2、HuBERT、WavLM；Wav2Vec2 额外覆盖 CPU train、evaluate、checkpoint save/load、artifact export/offline load、processor 重建和文件预测。processor 测试不访问 Hub。
- padding/mask 测试按 HF feature extractor 语义区分：group-norm 路径不要求 attention mask；layer-norm 路径用 attention mask 验证 padding 与真实 output-length 行为，不通过扩大数值容差掩盖差异。

CI 记录：

- CI #411 / run `34448958792` 是首轮 9-job HF 扩展验证。普通矩阵首先暴露两个仍指向 `ser_lib.models.pretrained` 的测试入口；Static 暴露 integration test import 顺序的 Ruff E402；Transformers 4.38.2 与 5.17.0 均得到相同的 `14 passed / 2 failed`，失败分别来自 fake processor 类名和过强的 group-norm padding 不变性断言，因此没有观察到 4.x/5.x API 分叉。
- 上述问题按正式 adapter 路径和真实 feature-norm/mask 语义修复，没有恢复旧 `pretrained.py` shim，也没有放宽行为契约。
- 代码验收 HEAD `7defe672752e5ea0fd197a1ed0a48569a42176a1` 对应 CI #415 / run `34450291387`：9/9 jobs 全部 `completed/success`。Linux/Windows/macOS × Python 3.10/3.12、Ruff、mypy、coverage、distribution build、wheel smoke、training smoke 全部通过；Transformers 4.38.2 与 5.17.0 两个独立 HF lane 的 `pip check` 和真实 tiny integration 均通过。

结论：Stage 11 的代码与依赖兼容门禁已满足；本记录提交后仍需以新的 doc-only exact HEAD 再运行一次完整 CI，只有该 closure CI 也 9/9 全绿后才正式关闭 Stage 11。
