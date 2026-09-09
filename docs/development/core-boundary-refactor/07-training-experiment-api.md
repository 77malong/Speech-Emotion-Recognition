# Stage 07 — Trainer / Evaluation / Experiment API 收紧

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
