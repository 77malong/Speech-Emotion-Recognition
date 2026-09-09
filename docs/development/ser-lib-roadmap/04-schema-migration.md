# 04 - Schema Migration Framework

## 背景

Config、Dataset、Run、Evaluation、Revision、Artifact 都已经出现或将出现 `schema_version`。继续用分散的 `if version == 1 / elif ...` 会使兼容逻辑不可审计。

## 目标

建立统一、显式、可测试的 migration 机制：

```text
old payload
  -> ordered migrations
  -> current payload
  -> current model validation
```

首批适用对象：

- ExperimentConfig
- Dataset manifest
- `run.json`
- `evaluation.json`
- `revision.json`
- Artifact manifest

## 设计原则

1. migration 只处理 schema 结构升级，不做业务 I/O；
2. 每一步只负责 `N -> N+1`，支持链式升级；
3. 禁止静默降级未知未来版本；
4. migration 输入/输出为普通 mapping，最后才进入当前 DTO/Pydantic validation；
5. 迁移过程不修改原文件，除非未来提供显式 rewrite 命令；本任务默认 read-time migration；
6. 每个 domain 明确 current version；
7. 无需 migration 的 vCurrent 路径尽量零额外复杂度。

## 建议模块

可新增：

- `ser_lib/core/migrations.py`

建议抽象：

```python
SchemaMigration
MigrationRegistry
register(domain, from_version, to_version, fn)
migrate(domain, payload, target_version=...)
```

具体实现不必过度框架化；当前只有少数版本时，简单 registry + ordered loop 即可。

## 接入顺序

为降低风险，分层接入：

1. 先实现 migration engine 与纯单测；
2. 选择一个已有版本字段且格式清晰的 domain 作为首个接入；
3. 再逐个接入 Config / Dataset / Run / Evaluation / Revision / Artifact；
4. 每接一个 domain 都保留当前版本直接读取测试与旧版本 fixture。

如果某类文件目前从未有旧 schema，不要虚构无意义 migration；只接入版本检查与 registry，为未来升级做准备。

## 错误模型

至少区分：

- missing/invalid schema version；
- unsupported future version；
- missing migration path；
- migration function failure；
- migrated payload current validation failure。

优先复用项目现有 exception/Diagnostic 体系。

## 测试

- v1 -> v2；
- v1 -> v3 连续链；
- current -> current no-op；
- future version 明确失败；
- 缺迁移步骤明确失败；
- migration 不修改输入 mapping；
- 接入 domain 的旧 fixture 可读；
- current fixture 行为不回归。

## 验收

- schema 兼容逻辑集中、可枚举、可测试；
- 不再在各 loader 中无限增长版本分支；
- 未知未来 schema 不被错误接受；
- 现有 current 文件读取不受影响。

## 建议提交

任务可能较大，建议拆：

1. `feat(core): add schema migration framework`
2. `feat(config): route experiment config through migrations`
3. `feat(data): route dataset metadata through migrations`
4. `feat(engine): migrate run and evaluation metadata`
5. `feat(artifacts): migrate artifact metadata`
