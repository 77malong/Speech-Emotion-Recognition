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

## 实施记录

- 开始本阶段实现前重新读取了 `docs/development/review/SER_LIB_CORE_BOUNDARY_AUDIT.md` 与 `docs/development/review/SER_LIB_CORE_BOUNDARY_EVIDENCE.md`，并以两者作为 migration 归域、扫描解耦和 `ser_lib/core` 退役的设计/证据依据。
- Migration 已按持久化格式归属拆分到 `ser_lib/config/migrations.py`、`ser_lib/data/migrations.py`、`ser_lib/engine/migrations.py` 与 `ser_lib/artifacts/migrations.py`；未建立新的 foundation migration 总线。当前版本、future version、缺少迁移链和非法版本等既有错误语义继续由各领域入口保持。
- `core/_catalog_scan.py` 的跨领域扫描抽象已退出；Dataset revision、checkpoint、training run、evaluation run 与 artifact catalog 使用各自领域内的最小扫描控制流，继续保留 cancellation、坏文件隔离、稳定排序、scan failure 信息与 no-load 性质，没有重新抽象新的跨领域 Catalog 框架。
- `data/history.py` 已直接使用 data migration，并将 revision Catalog 扫描控制流归回 data 域；Services、Importer 家族与 Trainer 等剩余调用方均已切到 `foundation`、`config` 或领域事件的 canonical import。
- Stage 02/03/04 的过渡 compatibility shim 已完成退役，`ser_lib/core/` 整包从源码树删除；对应测试从验证旧 shim 调整为验证 canonical ownership 与 `ser_lib/core` 不存在。
- Stage 01 的 `tests/fixtures/pre_refactor_contract_snapshot.json` 保持原样，继续作为迁移前公开 API/coverage 的历史基线证据；当前合同测试不再要求已经退役的 `ser_lib.core` namespace 可导入。
- Coverage policy 删除了已经不存在的 `ser_lib/core/` 门禁，但没有降低任何现存包阈值；`ser_lib/foundation/` 与 `ser_lib/config/` 仍分别保持 85% 门禁，其余既有 active package 阈值保持不变。
- Wheel smoke-test 已改为在仓库根目录之外的 `.wheel-smoke` 虚拟环境工作目录执行，避免源码 checkout 抢先于已安装 wheel，并显式断言 `importlib.util.find_spec("ser_lib.core") is None`。该检查已经在 Ubuntu Python 3.12 的构建 wheel 流程中通过。
- `Trainer._emit()` 使用 `foundation.events.EventLike` structural Protocol 接受 common 与 domain events；`LibraryEvent` 仍保持 common-event union，没有为了通过类型检查扩大其公开语义。该修复的 commit compare 仅包含 `EventLike` import 与 `_emit` 注解调整，没有训练逻辑漂移。
- 代码验收 HEAD `30f9e203dcc7513519a698441a5f5f901fabb4e8` 对应 CI #293（run `34425817255`）全部 7 个 job 成功：Ruff、mypy、按包 coverage、Ubuntu/Windows/macOS × Python 3.10/3.12 六个运行矩阵均通过；Ubuntu Python 3.12 的 distributions build、真实 wheel smoke、全量测试和训练 smoke 同样通过。
- 本阶段全量测试基线为 372 passed；端到端训练 smoke 输出 `ONE_EPOCH_SMOKE_TEST=PASS`，覆盖 8 samples、2 batches、2 optimizer steps。
