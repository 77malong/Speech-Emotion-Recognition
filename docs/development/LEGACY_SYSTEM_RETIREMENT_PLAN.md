# SER-lib 旧系统退役与新体系收口计划

更新时间：2026-09-09

目标分支：`refactor/remove-legacy-ser-system`

基线：`main@ff01c437f544ac606fb5b807bce06aae0e5627e8`

## 0. 当前执行状态

本计划已经进入最终验证阶段。Task 01–08 的代码重构与测试/文档收口均已实施，Task 09 等待最新 exact-HEAD CI 全平台验证完成后关闭。

| Task | 状态 | 结果 |
| --- | --- | --- |
| 01 Legacy DatasetProcessor Removal | ✅ 完成 | 旧 `DatasetProcessor/CasiaProcessor`、脚本和专用测试已删除；CASIA 只保留 Importer/prepare 新入口 |
| 02 Diagnostic Single Track | ✅ 完成 | `ImportIssue`、`issues`、`warnings`、`structured_diagnostics` 退役，Importer 只使用 `Diagnostic` |
| 03 Shared Importer Conversion Pipeline | ✅ 完成 | 9 个 importer 按 single-manifest / partitioned-manifest 两类共享 convert 编排 |
| 04 Service-first CLI | ✅ 完成 | Artifact / Inference / Evaluation / Training 工作流统一通过 Service facade |
| 05 Trainer Lineage Integration | ✅ 完成 | lineage 成为公开 `Trainer` 的正式状态；`_LineageTrainer` 已删除 |
| 06 Optimizer Config Single Track | ✅ 完成 | `TrainerConfig.learning_rate/weight_decay` 已删除；正式实验只认 `ExperimentConfig.optimizer` |
| 07 Shared Catalog Scan Primitive | ✅ 完成 | Training / Evaluation / Checkpoint / Artifact / Dataset Revision 共用扫描控制流 |
| 08 Test & Docs Cleanup | ✅ 完成 | run-detail ValidationError 回归并回领域测试；重复测试文件删除；本文件更新为当前架构记录 |
| 09 Full Validation | ⏳ 进行中 | exact-HEAD GitHub Actions 全平台 CI 通过后完成 |

## 1. 背景与目标

`ser_lib` 已经形成稳定的 Dataset Importer、Service facade、Event/Diagnostic、Run Catalog、ExperimentConfig、Artifact、Training/Evaluation/Inference 等新体系。此前仓库仍保留多轮重构产生的旧实现和过渡兼容层，导致同一业务存在两套甚至多套入口。

本次重构不增加 UI 功能，而是彻底停止维护旧业务路径，让新 `ser_lib` 体系成为唯一逻辑来源，为后续 SER-Studio / Worker 层提供稳定边界。

## 2. 当前唯一架构

未来应用层必须遵循：

```text
SER-Studio / CLI / Worker
          ↓
     ser_lib.services
          ↓
Dataset / Training / Evaluation / Inference / Artifact / Catalog
          ↓
Event + Diagnostic + Cancellation + versioned DTO
```

核心约束：

1. Dataset 统一使用 `ser_lib.data.importers`、`DatasetManifest`、`DatasetService`。
2. CLI / future Worker 通过 `ser_lib.services` 进入领域逻辑，不重新拼装已有业务流程。
3. Importer 所有 error / warning / info 只通过 `Diagnostic` 表达。
4. `ExperimentConfig.optimizer` + `ser_lib.engine.optim` 是正式 optimizer 配置来源。
5. `Trainer` 自身负责训练状态与 checkpoint lineage；Service 负责应用级构造和持久化编排。
6. Catalog 共享内部扫描 primitive，但 Training/Evaluation/Checkpoint/Artifact/Dataset Revision DTO 和领域排序保持独立。
7. Importer 共享 convert 写盘控制流，各数据集 scan、label、speaker/split 语义保持独立。

## 3. 已退役的旧路径

### 3.1 Legacy DatasetProcessor

已删除：

- `data/base_processor.py`
- `data/casia_process.py`
- `tests/test_dataset_processor.py`

CASIA 唯一准备入口：

- `ser_lib.data.importers.casia.CasiaImporter`
- `scripts/prepare_casia.py`

### 3.2 Legacy Importer Diagnostics

已删除：

- `ImportIssue`
- `ImportPreview.issues`
- `ImportPreview.warnings`
- `ImportPreview.structured_diagnostics`
- legacy diagnostics bridge

当前 `ImportPreview` 只保存：

```text
records
label_mapping
diagnostics: list[Diagnostic]
```

### 3.3 CLI 业务旁路

CLI 不再直接承担已有 Service 能力：

- Artifact inspect / verify / load / export → `ArtifactService`
- batch/offline inference → `InferenceService`
- Evaluation → `EvaluationService`
- Training → `TrainingService`

CLI 只负责命令参数、展示格式和必要的应用级 DataLoader 组装。

### 3.4 `_LineageTrainer`

`ser_lib.services.training._LineageTrainer` 已删除。

当前 lineage 流程：

```text
TrainingService.create_trainer()
        ↓ 创建 TrainingRunMetadata
Trainer.run_metadata
        ↓
checkpoint save / resume
```

直接构造 `Trainer` 时 lineage 可以为空，不发生隐式 manifest/fingerprint I/O。

### 3.5 Importer convert 重复实现

当前有两类内部共享流程：

- single manifest conversion
- partitioned manifest conversion

共享 destination、scan 校验、manifest/yaml 写盘、progress、cancellation 和回读逻辑；各 importer 只保留领域差异。

### 3.6 Catalog scanner 重复实现

内部共享 scanner 统一：

- cancellation
- fail-fast
- failure 捕获
- progress event

以下 DTO 仍保持独立：

- `TrainingRunCatalog`
- `EvaluationRunCatalog`
- `CheckpointCatalog`
- `ArtifactCatalog`
- `DatasetRevisionCatalog`

### 3.7 Legacy Trainer optimizer 配置

已从 `TrainerConfig` 删除：

- `learning_rate`
- `weight_decay`

正式实验配置：

```yaml
optimizer:
  type: adamw
  params:
    learning_rate: 0.001
    weight_decay: 0.0
```

直接低层构造 `Trainer` 时，调用方可以显式传入 optimizer；未传时使用 `engine.optim.AdamWConfig` 的统一默认值。

## 4. 明确保留的历史兼容能力

以下内容不是双轨业务系统，因此不会在本次重构中删除：

- Artifact v1 的受控读取；
- Checkpoint v1 的可信本地读取；
- Schema migration framework；
- 已锁定的稳定 public re-export；
- 已发布事件契约中的兼容字段，例如 ETA 旧字段。

这些能力只负责读取历史产物/维持已发布契约，不允许成为创建新任务时的第二套业务路径。未来若要删除，应在 breaking major version 中单独处理。

## 5. 实施提交记录

主要提交按执行顺序包括：

1. `1f79e464` — `docs(refactor): plan legacy system retirement`
2. `7464ea00` — `refactor(data): remove legacy dataset processor`
3. `ff8d7252` — `refactor(data): unify importer diagnostics`
4. `656ee7f6` — `refactor(data): centralize simple importer conversion`
5. `e2aaa3d2` — `refactor(data): centralize partitioned importer conversion`
6. `ad022a41` — `refactor(cli): route workflows through services`
7. `ab5b5ec4` — `refactor(training): make lineage and optimizer single-path`
8. `418311e8` — `refactor(core): share catalog scan control flow`
9. `bdcf8af9` — `refactor(data): reuse shared catalog scanner for revisions`
10. `5008f2e7` — `test(refactor): consolidate run detail regression coverage`
11. `e483e51e` — `fix(training): preserve public trainer type in service path`

中间历史中存在一次无业务内容的 `noop` 提交；未采用 force-push 改写历史，最终合并策略可在 PR 阶段再决定是否 squash。

## 6. 验证记录

已确认：

- Diagnostic 单轨化后的 CI #183 全平台通过；
- Task 05/06 的行为测试在 Linux / Windows / macOS、Python 3.10 / 3.12 全部通过；
- training smoke 全部通过；
- Linux Python 3.12 distribution build / wheel smoke 通过；
- Task 05/06 首轮 static check 仅暴露公开 Trainer 返回类型的 mypy 问题，已由 `e483e51e` 修复。

最终 Task 09 必须以最新 HEAD 再验证：

- dependency consistency
- compileall
- pytest
- Ruff
- mypy
- coverage gate
- training smoke
- package build / wheel smoke
- Linux / Windows / macOS
- Python 3.10 / 3.12

## 7. 最终验收标准

合并到 `main` 前必须满足：

- 仓库只有一套 Dataset 导入/准备体系；
- Importer 只有一套 Diagnostic 表示；
- CLI 与 future Worker 推荐业务入口都是 `ser_lib.services`；
- Training 不依赖 `_LineageTrainer`；
- optimizer 参数只有一个正式配置来源；
- Importer convert 与 Catalog scan 不复制大段公共控制流；
- 旧测试、旧命令、旧文档入口、只为旧路径存在的依赖已清理；
- 当前 JSON-safe DTO、事件、取消、轻量 inspect 成本边界不退化；
- 最新 exact-HEAD 全平台 CI 通过。
