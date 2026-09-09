# Stage 04 — 用户配置全量集中

## 目标

把所有内置、面向用户的配置 schema 统一迁入 `ser_lib/config`，消除配置定义散落在 engine、models、data/importers、representations、transforms、inference 中的问题，同时保持执行逻辑仍归各领域。

## 前置条件

- Stage 03 中央 config 基础层已通过全部配置回归。

## 目标文件

新增/完善：

- `config/model.py`
- `config/training.py`
- `config/experiment.py`
- `config/optimizer.py`
- `config/scheduler.py`
- `config/inference.py`
- `config/importers.py`
- `config/representations.py`
- `config/transforms.py`
- `config/presets.py`

## 迁移对象

1. `ModelConfig`、CNN/GRU/Transformer baseline 配置。
2. `HFAudioClassifierConfig`，但配置定义不得 import transformers。
3. `TrainerConfig`、`ObservabilityConfig`、`ExperimentConfig`。
4. AdamW/Adam/SGD 配置与 optimizer 联合 schema。
5. Step/Cosine scheduler 配置与联合 schema。
6. `LossConfig`、`SamplingConfig`；loss 计算实现继续留 engine。
7. `StreamingConfig`。
8. 九类 importer config。
9. RawWaveform、Spectral、Mel/LogMel/MFCC、Acoustic、Composite 等 representation config。
10. Normalize、Noise、Shift、Volume、Pitch、TimeStretch、SpecMasking 等 transform config。
11. Experiment preset 的 schema/template 构造迁到 config，避免继续依赖跨领域 Catalog 包装。

## 实施要求

- 每迁一族配置先迁定义和测试，再更新 factory/registry import。
- 不因为移动类就改变注册 ID、YAML 字段、默认值、枚举值或 JSON schema 语义。
- `ModelCard`、`ModelArtifactManifest`、run/revision/report 持久化模型不是用户配置，不迁到 config。
- `TensorSpec`、`ModelSpec`、`ModelOutput` 等契约类型不因为可序列化就迁 config。

## 验收标准

- 所有内置用户配置只存在一个正式定义位置。
- config 包不依赖训练循环、模型权重加载或 transformers。
- registry 创建、YAML 加载、CLI 配置、preset、artifact rebuild 相关测试通过。
- 旧配置 fixture 均可读取，round-trip 无业务字段漂移。

## 风险

- config validator 通过 import factory 形成循环。
- 分散配置迁移时遗漏某个 importer/representation/transform 内嵌类。
- 联合类型顺序变化导致 Pydantic 解析结果不同。

## 建议提交

可拆 2–4 个实现 commit，但阶段合并前必须满足：

`refactor(config): centralize all user-facing schemas`
