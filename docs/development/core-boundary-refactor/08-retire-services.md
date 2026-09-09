# Stage 08 — 退役七个 Service Facade

## 目标

在底层正式 API 已经具备等价能力后，彻底移除 `ser_lib/services`，让 Python 用户、CLI 和未来上层应用直接依赖 data/models/engine/inference/artifacts 的领域 API，而不是维护一层应用包装。

## 前置条件

- Stage 07 已提供稳定的 Trainer/Experiment 直接入口。
- 必须逐项证明 Service 隐藏能力已有替代实现，禁止直接 `rm -rf services`。

## 迁移对象

审计结论要求七个 Service 全部退役。逐项核对现有 service 文件和调用方，包括但不限于：

- Training
- Evaluation
- Inference
- Artifact
- Dataset
- Catalog
- Runtime

以当前源码真实文件为准，不因文档名称强造不存在的对象。

## 必须接回的隐藏行为

1. Training lineage 注入与 resume run_id 规则。
2. Predictor / recognizer 构造便利入口。
3. Artifact export provenance、model card/labels/config 组装。
4. 训练、评估、推理结果的原子保存便利能力。
5. Runtime capability 的按需查询。
6. Dataset importer/editor/history 的直接领域入口。
7. CatalogService 中仍有价值的 preset/registry introspection 改由真实 registry/config API 提供。

## 具体任务

1. 建立 Service 方法 → 替代领域 API 的逐项映射表。
2. 先迁 CLI、tests、examples、configs/notebooks 中的调用方。
3. 将 Service 行为测试迁到真实领域 API，删除仅断言 facade 身份的测试。
4. 搜索 `ser_lib.services`、具体 Service 类和 re-export，确保引用归零。
5. 删除 `ser_lib/services/` 整包及根包/子包相关导出。
6. 更新错误信息，避免仍提示用户“通过 Service 调用”。

## 非目标

- 不删除 training/evaluation/inference/artifact/dataset 的真实能力。
- 不删除 lineage、结果保存、runtime metrics。
- 不新增另一个名为 manager/controller/facade 的替代层。

## 验收标准

- 源码树、wheel、公开 API 中不存在 `ser_lib.services`。
- CLI train/evaluate/predict/export/resume E2E 全部通过。
- 原 Service 的领域行为均有直接 API 测试。
- 仓库内无 Service import、字符串文档示例或类型注解残留。

## 风险

最高风险是把“包装”误判为“无行为”，从而丢失 lineage、默认路径、provenance 或预测器构造。

## 建议提交

`refactor(api): retire service facades after direct API migration`
