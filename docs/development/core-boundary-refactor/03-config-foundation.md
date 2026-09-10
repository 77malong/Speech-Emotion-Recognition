# Stage 03 — 中央 Config 基础层

## 目标

建立独立的 `ser_lib/config` 包，先迁移配置基础设施和最核心的数据配置，解决 `core/config.py` 与 `data/config.py` 的职责混杂问题，同时保持旧配置 payload 语义。

## 前置条件

- Stage 02 foundation 已稳定。
- 配置迁移不能让 `config` 反向依赖 engine/models/inference 的执行实现。

## 修改范围

来源：

- `ser_lib/core/config.py`
- `ser_lib/data/config.py`
- `ser_lib/data/audio.py` 中 `AudioLoaderConfig`

目标：

- `ser_lib/config/__init__.py`
- `ser_lib/config/base.py`
- `ser_lib/config/loader.py`
- `ser_lib/config/data.py`

## 具体任务

1. 迁移严格 Pydantic 配置基类、unknown-field 策略和通用校验基础。
2. 迁移 YAML 读取、schema version、确定性路径解析。
3. 迁移 `DataConfig`、`ComponentConfig`、`BatchingConfig`、`FixedBatching`、`SlidingBatching`。
4. 将 `CacheSettings` 收敛为中央数据配置定义。
5. 合并字段重复的 `AudioSettings` 与 `AudioLoaderConfig` 为单一 `AudioConfig`。
6. 保持旧 YAML/payload 的字段语义、默认值和路径行为；如类型名变化，提供明确读兼容而不是复制两套正式 schema。
7. `data/audio.py` 只保留音频运行逻辑，引用中央 `AudioConfig`。
8. 更新 config/data/audio 的测试与导出，禁止产生 `config -> data runtime` 的循环。

## 非目标

- 本阶段不一次性迁所有模型、训练和 importer 配置。
- 不改 optimizer/scheduler/loss 的执行逻辑。
- 不删除 `core` 剩余文件。

## 验收标准

- 基础配置可在不 import torch/transformers 的情况下导入。
- 所有数据配置 round-trip、严格字段、版本、路径测试通过。
- `AudioSettings`/`AudioLoaderConfig` 不再作为两套独立正式定义存在。
- 同一旧配置文件在迁移前后解析出的业务含义一致。

## 风险

- Pydantic validator import 执行模块造成环。
- Audio 默认值或采样率/声道字段合并时发生隐式行为变化。
- 配置文件相对路径解析基准改变。

## 建议提交

`refactor(config): introduce central config foundation`

## 实施记录（2026-09-09）

本阶段开始前再次读取：

- 设计依据：`docs/development/review/SER_LIB_CORE_BOUNDARY_AUDIT.md`
- 证据依据：`docs/development/review/SER_LIB_CORE_BOUNDARY_EVIDENCE.md`

Stage 02 的最终 exact HEAD `1621caabdc9bed5e1a658c0b1fc9005ceaedc153` 对应 CI #217 已全部通过，包含 Ruff、mypy、coverage 与 Windows/macOS/Linux × Python 3.10/3.12 矩阵，因此本阶段在稳定 foundation 基线上开始。

本阶段实现范围严格限定为 config 基础层与核心 data config：

- 新增 `ser_lib/config/base.py`，`StrictConfig` 成为唯一正式严格配置基类；
- 新增 `ser_lib/config/loader.py`，承接 YAML、schema version、路径解析与版本化配置加载；Stage 05 前 migration 调用仍通过旧 `core.migrations` 的局部兼容入口，不把 migrations 放进 foundation/config；
- 新增 `ser_lib/config/data.py`，集中 `DataConfig`、组件、batching、audio、cache schema；
- `AudioSettings` 与 `AudioLoaderConfig` 不再各自定义类型，统一为 `AudioConfig`；旧名称仅作为同一类对象的 0.2.x alias；
- `CacheSettings` 同理兼容 alias 到正式 `CacheConfig`；
- `ser_lib/core/config.py` 和 `ser_lib/data/config.py` 降为旧路径兼容 shim，不再包含正式配置实现；
- `ser_lib/data/audio.py` 删除独立运行时配置 dataclass，直接消费中央 `AudioConfig`，保留旧 `AudioLoaderConfig` 名称作为 alias；
- `load_data_config` 继续只把 `manifest` 相对配置文件所在目录解析，不改变默认 audio/cache/batching payload；
- 新增 config 轻量导入、依赖方向、identity shim、round-trip、严格字段和路径行为测试；
- coverage 门禁新增 `ser_lib/config/ >= 85%`。

本阶段没有迁移模型、训练、optimizer/scheduler、loss、streaming 或 importer 配置，也没有删除剩余 `core`。CI 结果必须以本阶段 exact HEAD 的 GitHub Actions 为准，提交记录不提前声明通过。
