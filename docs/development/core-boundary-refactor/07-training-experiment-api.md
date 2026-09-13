# Stage 07 — Trainer / Evaluation / Experiment API 收紧

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


## 目标

把可复用实验编排从 CLI/Service 包装中提升为真正的 engine API，并让 `Trainer.fit()` 直接返回完整训练结果，减少调用方依赖 `last_result` 或 Service facade 的情况。

## 前置条件

- Stage 06 依赖边界稳定。
- 训练、评估、checkpoint、lineage 回归测试已锁定。

## 修改范围

重点涉及：

- `ser_lib/engine/trainer.py`
- `ser_lib/engine/_trainer_core.py`
- `ser_lib/engine/evaluator.py`
- `ser_lib/engine/config.py` 已迁后的调用方
- `ser_lib/cli/workflows.py`
- 新增/完善 `ser_lib/engine/experiment.py`

## 具体任务

1. 将 `Trainer.fit()` 正式返回值改为 `TrainingResult`。
2. 保持 `TrainingResult.epochs`、终态、metrics、异常后可检查状态等现有语义。
3. 明确旧 `history = trainer.fit(...)` 调用的迁移方式；仓库内调用全部迁移。
4. 将 CLI 中可复用的 train/evaluate experiment orchestration 提取到 `engine/experiment.py`。
5. CLI 只保留参数解析、输出格式和必要的命令级适配。
6. 不新增仅为了结构对称的 `Evaluator` 包装类；继续以现有 `evaluate()` 核心路径为准，除非真实实现需要内部对象。
7. 设计 `Trainer.from_experiment(...)` 或等价正式入口，为下一阶段替代 `TrainingService.create_trainer()` 做准备。
8. 固定 lineage 输入：dataset fingerprint、run_id、resume 优先级和 checkpoint metadata。
9. 确保验证集/评估流程不重复构造不必要的模型或 processor。

## 非目标

- 本阶段不删除 services 包。
- 不改变 optimizer/scheduler/checkpoint 算法。
- 不创建 HF 专用 Trainer。

## 验收标准

- 普通 Python 用户无需 import CLI/Service 即可完成实验训练和评估。
- `Trainer.fit()` 返回完整且稳定的 `TrainingResult`。
- resume、lineage、observability、cancellation、early stop、scheduler 相关测试通过。
- CLI 与 engine 不维护两套训练业务逻辑。

## 风险

- 返回类型变化导致仓库调用方遗漏。
- 提取 experiment orchestration 时丢 lineage 或输出目录默认规则。
- Service 仍是隐藏的唯一 predictor/artifact 构造来源。

## 建议提交

`refactor(engine): expose direct training and experiment APIs`

## 实施记录

进入本阶段前已重新读取 `SER_LIB_CORE_BOUNDARY_AUDIT.md`、`SER_LIB_CORE_BOUNDARY_EVIDENCE.md` 与本阶段计划，并严格保持“不删除 Service、不创建 Evaluator、不修改 optimizer/scheduler/checkpoint 算法”的边界。

- `fc164405ca6b741159adbdc53ca0d22230fded22`：公开 `Trainer.fit()` 直接返回 `TrainingResult`；`Trainer.from_experiment()` 接管 dataset/run lineage 构造。
- `f1b2bf86edc1dd7d81c9f778c8b70985eb175799`：`TrainingService` 收缩为兼容 facade，训练构造与执行直接委托 engine API。
- `1f8f25ec1f4bc8c62084a6bf3d9ded9f33b74838` / `571b7c6d64f213f45a584d00ee2a430dfef72c04`：新增并公开 `engine.experiment`，提供 typed `TrainingExperimentResult`、`EvaluationExperimentResult`、`train_experiment()`、`evaluate_artifact()`。
- `5060d37a20ec782df0e5f8a7684dd79f5f029da8`：CLI 的 train/evaluate 流程缩为参数转发与输出适配；lineage、loader、history、run record、evaluation report 等业务逻辑不再在 CLI 重复维护。
- validation 路径只重建 `train=False` 的数据 pipeline/collator，并复用同一个训练模型；评估直接使用 artifact 中已加载的模型，没有引入 `Evaluator` 或重复 model/processor 构造。
- 仓库内旧 `history = trainer.fit(...)` 消费方式全部迁到 `TrainingResult.epochs`；resume、observability、early stop、cancellation、scheduler、checkpoint lineage 与端到端 experiment lineage 都有回归测试覆盖。
- `64ee2a40dc5dc6f9c92a8169ea5de2ec04bf0ba6` 修复最后一个 resume 测试的旧 list 假设；`8eb69de4cec75e38e6fa6ad9e1038bc5f1c50249` 将实验组件 Protocol 调整为只读属性，解决 structural typing，不改变运行行为。

代码验收：exact HEAD `8eb69de4cec75e38e6fa6ad9e1038bc5f1c50249` 的 CI #315（run `34435443201`）7/7 job 全部成功，包括 Ruff、mypy、coverage、Windows/macOS/Linux × Python 3.10/3.12、Ubuntu 3.12 wheel build/smoke、完整测试与 training smoke。
