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

## 实施记录（2026-09-09）

Stage 04 已完成，采用分批迁移、旧路径兼容导出的方式收口全部面向用户的配置定义。

### 第一批：模型、训练、实验、优化器、调度器与推理配置

- 将 model/training/experiment/optimizer/scheduler/inference 等用户配置迁入 `ser_lib.config`。
- 旧 engine/models/inference 路径改为导出中央定义，避免出现两套 class/schema。
- 保持既有注册 ID、字段名、默认值、validator、联合类型顺序与 YAML/JSON 语义。
- `HFAudioClassifierConfig` 的中央定义不 import transformers。

对应实现提交以本阶段分批 commit 为准；第一批 exact-head CI #219 已全部通过。

### 第二批：Importer 配置

- 新增 `ser_lib/config/importers.py`，集中 9 类 importer config 与 `DEFAULT_AUDIO_EXTENSIONS`。
- `CasiaImportConfig`、`CsvImportConfig`、`CsemotionsImportConfig`、`CremaDImportConfig`、`EmotionTalkImportConfig`、`EsdImportConfig`、`FolderImportConfig`、`JsonlImportConfig`、`RavdessImportConfig` 只保留一个正式 class 定义。
- 原 `ser_lib.data.importers.*` 模块继续兼容导出同一个 class object，扫描和转换执行逻辑不迁移。
- 为保持已有可变 `BaseModel` 行为，不因集中配置而强制继承 frozen `StrictConfig`。

实现提交：

- `3004d13a3747a5791b72f88e30fa325be05141a6` — `refactor(config): centralize importer schemas`
- `0766d7dabd60e24e87ade48b34c966daddd0bf1f` — `fix(config): remove unused importer constant`

验证：CI #221 全部通过。

### 第三批：Representation、Transform 与 Preset

- 新增 `ser_lib/config/representations.py`，集中 RawWaveform、Spectral、Spectrogram、Mel、LogMel、MFCC、Acoustic、Composite 等 schema。
- 新增 `ser_lib/config/transforms.py`，集中 Normalize、GaussianNoise、TimeShift、VolumeScale、PitchShift、TimeStretch、SpecMasking 等 schema。
- 原 representation/transform 执行模块继续保留算法、Torch/Torchaudio 组件与 descriptor，只导入中央 schema。
- 新增 `ser_lib/config/presets.py`，迁移 experiment preset payload/template/build 逻辑；`ExperimentPresetInfo`、`ExperimentPresetCatalog`、`list_experiment_presets()`、`get_experiment_preset()` 暂时保留在 engine，避免提前执行 Stage 09 的 Catalog/API 清理。
- 新增回归测试，验证旧路径与中央路径的配置类为同一个对象，并验证独立导入中央 representation/transform config 不会加载 `torch`/`torchaudio`。

实现提交：

- `32e7e837b94cdc3aaeede388726a177a39a25772` — `refactor(config): centralize representation and transform schemas`
- `bbca962c136be4bd5b4b273079db715ec6cf1c02` — `fix(config): remove unused representation type import`

验证：CI #223 对 exact HEAD `bbca962c136be4bd5b4b273079db715ec6cf1c02` 完成并成功：

- Ruff：success
- mypy：success
- package coverage gate：success
- Windows / Python 3.10：success
- Windows / Python 3.12：success
- macOS / Python 3.10：success
- macOS / Python 3.12：success
- Ubuntu / Python 3.10：success
- Ubuntu / Python 3.12：success

### 阶段结论

Stage 04 的验收目标已经满足：内置用户配置已集中到 `ser_lib.config`，旧路径保留兼容 identity；配置层没有引入训练循环、模型权重加载或 transformers 依赖；现有 registry、preset、训练 smoke 与全平台测试均通过。后续 Stage 05 可以在此稳定边界上拆分 migrations 与 scan control，而不再承担配置定义迁移。
