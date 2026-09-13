# Changelog

本项目从 1.0.0 起按语义化版本维护公开 Python API 与 CLI。历史开发分支中的 0.x
版本用于架构收敛，没有作为稳定兼容基线发布。

## [1.0.0] - 2026-09-13

### Release status

- 首个稳定版。发布基线为 codex/ser-lib-latest-only@495f8f5。
- 基线 CI #581 全部通过：Linux/Windows/macOS × Python 3.10–3.12、HF
  Transformers 4.38.2/5.17.0、Ruff、mypy、分模块覆盖率、wheel 隔离安装和 CPU
  单 epoch smoke 均通过。
- 普通测试矩阵记录 518 passed / 3 skipped；质量任务记录 528 passed / 1 skipped。

### Added

- 标准 DatasetManifest + JSONL 数据格式，以及 Folder、CSV、JSONL、CASIA、
  RAVDESS、CSEMOTIONS、ESD、CREMA-D、EmotionTalk importer。
- 统一 AudioLoader、Representation、Transform、SERDataset、SERCollator 数据链，
  支持 waveform、spectral、Log-Mel、MFCC 和组合输入。
- CNN、GRU/BiGRU、轻量 Transformer，以及可选 Hugging Face Wav2Vec2、HuBERT、
  WavLM 音频分类适配。
- 完整训练与评估能力：确定性 seed、AMP、梯度累积、梯度裁剪、scheduler、
  early stopping、类别权重、focal loss、WeightedRandomSampler、WAR/UAR/F1、
  MCC、Cohen's kappa、逐类指标和混淆矩阵。
- 可恢复训练 checkpoint、training/evaluation records、history、lineage 和资源检查 API。
- safetensors 模型 artifact、模型卡、processor 配置、SHA-256 完整性校验和离线恢复。
- 单文件、批量和纯 PCM streaming 推理。
- ser CLI：components、dataset、train、evaluate、predict、artifact。
- 跨平台 CI、类型检查、静态检查、覆盖率门禁、构建/wheel smoke 和 HF 版本矩阵。

### Reliability fixes completed before 1.0

- 修复 weighted loss 在不同 validation batch 划分下聚合不一致，以及训练事件和最终
  TrainingResult loss 口径不一致。
- 修复跨 checkpoint 目录续训后的 best 引用、历史 checkpoint 的 best 身份、
  保存/恢复计数和采样器状态。
- checkpoint 恢复增加前置验证和失败回滚，避免模型、优化器、scheduler、scaler
  或 RNG 停留在半恢复状态。
- artifact 导出严格校验 checkpoint lineage、manifest、配置中的标签语义、数据身份和
  预处理契约，避免同类别数下静默交换标签。
- fresh run 与 resume 的 metrics/history 生命周期分离；回溯续训会裁剪未来历史。
- 修复非有限 logits、evaluation report/prediction 文件一致性、streaming 已完成结果保留。
- 修复 manifest 的未分配记录/同名 split 冲突、空 split 保留，以及共享 pipeline
  严格校验状态相互污染等跨模块边界问题。

### Architecture and compatibility

- ser_lib 是纯 SER Core SDK；不包含 Web、Desktop、本地 HTTP service 或产品工作区。
- 根包只保留少量惰性高层入口；领域 API 位于 config、data、models、engine、
  artifacts、inference、foundation、runtime。
- 1.x 中，文档列出的公开 Python API、CLI 参数与 artifact 契约遵循语义化版本。
  未公开的内部模块不属于兼容承诺。
- checkpoint 使用 Torch 序列化，只用于来源可信的本地训练恢复；它不是模型分发格式，
  也不承诺作为不可信或任意历史版本的交换格式。
- 分发模型固定使用当前 safetensors artifact。
- 不提供 pre-1.0 import shim、Service/Page/View/Detail facade、历史 schema migration
  或 pickle artifact 回退入口。

### Removed before stable release

- ser_lib.core、ser_lib.services、跨领域 ser_lib.catalog。
- 旧 Dataset 包装器、历史 training/evaluation catalog facade、ser_lib.benchmark。
- 旧 ser_lib.models.pretrained 路径和 pretrained extra 别名。
- RuntimeMetrics/get_runtime_metrics 等持续资源监控包装。
