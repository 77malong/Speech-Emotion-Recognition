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
