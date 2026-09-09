# Stage 05 — Migration 归域与扫描基础设施解耦

## 目标

拆除 `core/migrations.py` 与 `_catalog_scan.py` 这类跨领域基础设施，让持久化迁移回到格式所属领域，让扫描循环回到各自资源域。完成本阶段后，`ser_lib/core` 应具备被完全删除的条件。

## 前置条件

- Stage 04 所有用户配置已经集中。
- Stage 01 固定的旧 schema/artifact/checkpoint/revision fixture 必须可用。

## 修改范围

来源：

- `ser_lib/core/migrations.py`
- `ser_lib/core/_catalog_scan.py`

目标：

- `ser_lib/config/migrations.py`
- `ser_lib/data/migrations.py`
- `ser_lib/engine/migrations.py`
- `ser_lib/artifacts/migrations.py`
- Dataset revision / checkpoint / training run / evaluation run / artifact catalog 各自私有扫描逻辑

## 具体任务

1. 按持久化格式归属拆 migration registry，不建立新的 foundation migration 总线。
2. 保留缺链、坏版本、只读迁移、版本门禁等错误语义。
3. Artifact v1/v2 继续使用其真实兼容规则，不虚构 v1 不存在的 hash 字段。
4. Checkpoint `format_version` 继续按 checkpoint 语义处理，不强套 config 的 `schema_version`。
5. 拆除跨领域 Catalog candidate/failure 协议；每个领域维护最小扫描控制流。
6. 保留 cancellation、坏文件隔离、稳定排序、scan failure 信息和 no-load 性质。
7. 清理所有对 `core.migrations`、`core._catalog_scan` 的引用。
8. 核对 Stage 02/03/04 已迁出的 core 内容，满足后删除 `ser_lib/core/` 整包及旧导出。

## 非目标

- 不删除真实资源 Catalog 能力。
- 不删除 artifact/checkpoint/dataset revision/run 历史。
- 不因为扫描代码有少量重复就重新抽象一个跨领域框架。

## 验收标准

- `ser_lib/core` 在源码树和 wheel 中消失。
- 所有旧格式 fixture 仍能按既定门禁读取或明确拒绝。
- 扫描目录不隐式加载模型权重或完整 prediction 文件。
- migration/scan 相关定向测试与全量测试通过。

## 风险

- 跨域 migration 拆分时遗漏注册顺序。
- 为消除重复重新引入新的全局 Catalog 框架。
- 删除 core 时连带删除取消、错误或持久化兼容能力。

## 建议提交

`refactor(core): retire global migrations and scan primitives`
