# Stage 08 — 退役七个 Service Facade

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


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

## 实施记录

Stage 08 开始前重新读取了 `SER_LIB_CORE_BOUNDARY_AUDIT.md`、`SER_LIB_CORE_BOUNDARY_EVIDENCE.md` 与本阶段计划，并逐个核对七个 Service 的真实方法和调用方；没有用 manager/controller/facade 创建替代层。

隐藏能力先于删除完成下沉：`4e6744afe18d6325ce275d263d8fde38255541f5` 将训练 lineage 转 artifact provenance 的便利逻辑归 engine；`324b15e5d3a504778dabf01ec5e8a6bd455dc4ae` 让 evaluation metadata builder 自带 library version 默认值；`20e4e95aad6d444f3f8db6551e4a3c98a26aed2e` 增加 `EmotionPredictor.from_loaded_artifact()`。该中间 HEAD 的 CI #319 / run `34436074706` 7/7 成功。

`84bb2f5c811b63ddeddcdc1899170ffed6cc6f6d` 将 CLI 的 predict/export/inspect 从 ArtifactService/InferenceService 改为 artifacts、inference、engine 的直接 API。Training/Evaluation 的详情聚合仍属于 Stage 09 的待退役对象，因此本阶段只把 Service 中独占的聚合行为原样下沉：`87255319bcc8da78fb6704c5bb9327509cb77531` / `2108aece2938c03b0e64713f491f0057acd90d22` 提供并公开 evaluation detail inspection，`9dc667d0e1e6bd62b73cddfd597d95cd9ef1bc4f` / `599b87afb820bbb60e093101a2904f8311984108` 提供并公开 training detail inspection；这些 Detail/Page 类型的真正删除留给 Stage 09。

原 facade 行为测试已迁到领域 API：artifact lineage/catalog、dataset profile/history、runtime、training history/checkpoint/run、evaluation metadata/catalog/report/query/detail、batch prediction 等均直接调用正式模块；通用 facade 身份测试改为 `tests/test_direct_domain_apis.py`，重复的 Service-only preset 测试删除。Stage 01 历史 fixture 未修改，当前契约测试只显式记录 `ser_lib.services` 是计划内退役 namespace。示例、`docs/API_REFERENCE.md` 与 `data/readme.md` 也已切换到 direct API；审计/证据/阶段计划中的历史 Service 名称作为设计证据保留。

CI wheel smoke 增加 `find_spec("ser_lib.services") is None`。最终删除提交 `54e12c2efef395801308bed3b64a157bcc2f08fa` 一次性移除 `ser_lib/services` 的 8 个文件，单提交 compare 只包含该目录删除。其 exact-head CI #349 / run `34440397192` 为 `completed/success`：Ruff、mypy、package coverage、Ubuntu/macOS/Windows × Python 3.10/3.12、完整测试与 training smoke 全部通过；Ubuntu 3.12 的 distribution build 与独立 wheel smoke 也通过，确认安装后的 wheel 同时不存在 `ser_lib.core` 与 `ser_lib.services`。

因此 Stage 08 的代码验收已满足：七个 Service facade 已从源码与 wheel 退役，真实 SER 能力和隐藏便利行为由领域 API 接管，且没有建立新的应用包装层。
