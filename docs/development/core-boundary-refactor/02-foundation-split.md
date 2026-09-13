# Stage 02 — Foundation 拆分与事件归域

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


## 目标

把 `ser_lib/core` 中真正跨领域、轻量且稳定的基础设施迁入 `ser_lib/foundation`，同时把训练和推理领域事件拆回各自领域，降低核心包反向依赖风险。

## 前置条件

- Stage 01 回归基线已建立并通过。
- 不改变持久化字段、事件语义和 error code。

## 修改范围

主要来源：

- `ser_lib/core/exceptions.py`
- `ser_lib/core/diagnostics.py`
- `ser_lib/core/logging.py`
- `ser_lib/core/events.py`

目标：

- `ser_lib/foundation/errors.py`
- `ser_lib/foundation/diagnostics.py`
- `ser_lib/foundation/logging.py`
- `ser_lib/foundation/events.py`
- `ser_lib/engine/events.py`
- `ser_lib/inference/events.py`
- `ser_lib/_version.py`

## 具体任务

1. 建立 `foundation` 包，只容纳异常、诊断、通用事件/取消、显式日志 helper。
2. 将 `SERError`、`ConfigurationError`、`SchemaMigrationError`、`OperationCancelled` 迁入 foundation。
3. 将 `Diagnostic` 迁入 foundation，去除仅面向 Web/UI 的措辞，不改变 stable code。
4. 将通用进度、指标、日志、生命周期、取消令牌迁入 foundation。
5. 将 `CheckpointEvent` 迁入 `engine/events.py`，将 `PredictionEvent` 迁入 `inference/events.py`。
6. 保证 foundation 不 import `data/models/engine/inference/artifacts/cli`。
7. 建立独立 `_version.py`，避免 artifact 或其他模块通过根包回引版本。
8. 更新生产代码、测试和公开导出到新路径；如必须保留短期 shim，只允许作为过渡，并标记 Stage 05 前删除。

## 非目标

- 本阶段不迁 config。
- 不迁 migration registry。
- 不删除整个 `core/`。
- 不重写事件模型，不新增 UI 进度字段。

## 验收标准

- foundation 无领域反向 import。
- events/diagnostics/logging/cancellation 现有测试全部通过。
- 序列化后的事件字段、时间戳、run_id/split/step/sample uid 等算法语义保持。
- 不因 import `ser_lib.foundation` 加载训练、推理或模型重依赖。

## 风险

- 为了类型联合让 foundation 回 import engine/inference。
- 改名时无意改变事件 JSON shape 或错误码。
- 根包版本回引形成初始化循环。

## 建议提交

`refactor(core): split foundation and domain events`

## 实施记录（2026-09-09）

本阶段开始前重新读取并以以下两份文件作为直接依据：

- 设计依据：`docs/development/review/SER_LIB_CORE_BOUNDARY_AUDIT.md`
- 证据依据：`docs/development/review/SER_LIB_CORE_BOUNDARY_EVIDENCE.md`

同时先复核 Stage 01。`1022a329` 的第一次 CI 暴露了测试自身把
`ModelRegistry.descriptor()` 的 `dict` 返回误当成对象的问题；修复提交
`9c2bf8c9f727b10ea115c735d09d61b0c9678281` 对应 CI #214 已通过，随后才开始本阶段生产代码迁移。

本阶段实现：

- 新增 `ser_lib/foundation/`：
  - `errors.py`：稳定根异常与 error code；
  - `diagnostics.py`：结构化 Diagnostic，去除 Web/UI 专属措辞；
  - `events.py`：Progress/Metric/Log/Lifecycle、EventContext、取消协议与共享事件序列；
  - `logging.py`：显式库日志 helper。
- `CheckpointEvent` 的实现归 `ser_lib/engine/events.py`；
  `PredictionEvent` 的实现归 `ser_lib/inference/events.py`。两个领域事件继续复用
  foundation 的 schema、JSON helper 和全局 sequence，避免事件排序语义变化。
- foundation 的 `LibraryEvent` 只表达通用事件；callback 使用结构化 `EventLike`
  协议接受领域事件，foundation 不反向 import engine/inference。
- 新增 `ser_lib/_version.py`；artifact exporter/loader 直接从该模块取版本，不再
  `from ser_lib import __version__`。
- 根 `ser_lib/__init__.py` 保留原 0.2.x `__all__` 顺序和名称，但改为惰性导出。
  这是满足 `import ser_lib.foundation` 不加载 torch/models/engine/inference 的必要条件，
  不是 Stage 12 的公开 API 收缩。
- `ser_lib/core/{exceptions,diagnostics,logging,events}.py` 与 `ser_lib.core` 保留为
  0.2.x 兼容 shim；旧名称仍解析到同一个新实现对象。shim 明确标记在 Stage 05 前删除。
  config、migration registry、`_catalog_scan.py` 本阶段保持原位。
- coverage 门禁新增 `ser_lib/foundation/ >= 85%`；Stage 01 快照测试改为验证旧门槛
  不得降低，同时允许本阶段新增 package 门槛。
- 新增 `tests/test_foundation_boundaries.py`，锁定：
  - foundation 无领域反向 import；
  - 轻量导入不加载 torch/models/engine/inference；
  - legacy core alias 与新实现对象 identity；
  - domain event 所属模块；
  - common/domain event 共用全局 sequence；
  - artifact 版本来源不再回引根包。

本阶段不迁移 config/migrations，不删除整个 `core/`，也不修改事件字段、schema version、
error code 或持久化格式。CI 结果以本阶段 exact HEAD 的 GitHub Actions 为准，不在提交前预判。
