# Stage 02 — Foundation 拆分与事件归域

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
