# Changelog

本项目遵循语义化版本。当前内容尚未发布。

## [0.3.0] - Unreleased

### Added

- 统一 Manifest、Representation、Collator 数据流水线。
- CNN、GRU、轻量 Transformer 和可选 Hugging Face 音频模型适配器。
- Hugging Face Wav2Vec2、HuBERT、WavLM 的真实本地 tiny-model 集成验证、processor 配置持久化和离线 artifact 重建。
- 可复现训练、完整 SER 指标、checkpoint v2 和安全 artifact v2。
- 单文件、批量、纯 PCM 流式推理与 `ser` CLI。
- RAVDESS importer、音频 profile 和 benchmark 回归比较。
- CNN、GRU 和 Transformer 实验配置模板及可执行 Python API 示例。
- 覆盖真实 WAV 数据链路的单 epoch 训练冒烟测试，并接入 Linux/Windows/macOS × Python 3.10–3.12 CI。
- 验证集训练、可配置监控指标、early stopping 及 best/last checkpoint。
- 类别加权交叉熵、focal loss、WeightedRandomSampler 和逐 epoch JSONL 日志。
- weighted precision/recall/F1、balanced accuracy、MCC 与 Cohen's kappa 指标。
- CSEMOTIONS 专用 importer、元数据保留和性别平衡的说话人独立划分。
- ESD 中英双语 importer、转写保留、语言过滤和语言分层的说话人独立划分。
- CREMA-D importer、人口统计元数据、固定语句解析和性别分层的演员独立划分。
- EmotionTalk importer、完整逐句标注保留及说话人独立/官方对话两种划分策略。
- CSEMOTIONS、ESD、CREMA-D 和 EmotionTalk 的可校验训练配置与模型卡。
- 真实 EmotionTalk 三轮 GPU 训练、artifact 导出和独立测试评估的工程验收记录。
- foundation/config 等领域级覆盖率门禁，以及源码树外隔离 wheel 安装验证。

### Changed

- 仓库边界收缩为纯 SER Core/SDK；配置、数据、模型、训练评估、artifact、推理和运行时能力分别由对应领域子包负责。
- `ser_lib` 根包收缩为少量高层惰性便利入口；配置、运行时、诊断、兼容性、lineage、catalog 等 API 不再从根包重导出。
- CLI 只通过领域公开 API 编排，不依赖 `engine.experiment`、`engine.lineage` 等内部实现路径。
- Hugging Face 的正式可选依赖名称为 `hf`。`pretrained` extra 暂时保留为安装兼容别名，新代码与新文档统一使用 `.[hf]`。
- 完全移除三个旧 Dataset 包装器，统一使用 `SERDataset`。

### Removed

- 桌面端、Web UI 和本地 HTTP service 代码。
- `ser_lib.core`、`ser_lib.services` 与跨领域 `ser_lib.catalog` facade。
- Page/View/Detail/ComponentCatalog 等面向应用展示或聚合的包装类型；调用方应直接组合所属领域资源 API。
- 旧 `ser_lib.models.pretrained` 模块；Hugging Face 模型实现位于 `ser_lib.models.adapters.huggingface`，公开入口由 `ser_lib.models` 提供。

### Breaking API migration

`0.3.0` 明确承载本轮 breaking Python API 边界调整；不把删除/迁移后的公开 API 面继续伪装成 `0.2.0` 的兼容更新。
以下是本轮核心边界重构中的典型 Python API 迁移：

```python
# before
from ser_lib import build_experiment_config
from ser_lib import RuntimeMetrics, get_runtime_metrics
from ser_lib import CompatibilityReport, validate_experiment, TrainingRunMetadata
from ser_lib import Diagnostic, ModelCard, ModelArtifactManifest

# after
from ser_lib.config import build_experiment_config
from ser_lib.runtime import RuntimeMetrics, get_runtime_metrics
from ser_lib.engine import CompatibilityReport, validate_experiment, TrainingRunMetadata
from ser_lib.foundation import Diagnostic
from ser_lib.artifacts import ModelCard, ModelArtifactManifest
```

旧 `Service`、Page/View/Detail/Catalog facade 不提供一对一替代包装；请直接使用
`ser_lib.data`、`ser_lib.engine`、`ser_lib.artifacts`、`ser_lib.inference` 等领域 API。
具体入口参见 `docs/API_REFERENCE.md`。

### Persistence compatibility

Python 导入路径的 breaking change 不等同于持久化格式失效。现有 config、dataset、run、
checkpoint 与 artifact 的版本门禁和真实 migration 仍由各领域维护。artifact v2 继续使用
`safetensors` 与 SHA-256 完整性校验；真实存在的 v1 artifact 仍只能在调用方显式授权可信
pickle 时加载。不会为了兼容从未存在过的历史格式而伪造 migration。
