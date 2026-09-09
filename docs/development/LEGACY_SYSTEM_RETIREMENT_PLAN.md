# SER-lib 旧系统退役与新体系收口计划

更新时间：2026-09-09

目标分支：`refactor/remove-legacy-ser-system`

基线：`main@ff01c437f544ac606fb5b807bce06aae0e5627e8`

## 1. 背景

当前 `ser_lib` 的新体系已经具备稳定的 Dataset Importer、Service facade、Event/Diagnostic、Run Catalog、ExperimentConfig、Artifact、Training/Evaluation/Inference 等能力，但仓库仍保留了多轮重构过程中形成的旧实现与过渡兼容层。

这些旧路径虽然大多仍可运行，但会形成双轨或多轨维护：

- `data/base_processor.py` / `data/casia_process.py` 与 `ser_lib.data.importers` 并存；
- Importer 同时维护 `ImportIssue`、`warnings: list[str]`、`structured_diagnostics` 与统一 `Diagnostic`；
- CLI 某些工作流直接拼接领域模块，绕过已经存在的 `ser_lib.services`；
- TrainingService 通过 `_LineageTrainer` 子类补 lineage，而不是由 Trainer 本身提供稳定扩展点；
- 多个 Importer 重复实现 scan 后的 manifest/yaml 写盘逻辑；
- 多个 Catalog scanner 重复实现 candidate / cancellation / fail-fast / progress / failure 收集循环；
- `TrainerConfig.learning_rate` / `weight_decay` 与 `ExperimentConfig.optimizer` 双轨；
- 测试、文档仍保留旧入口与重复 fixture。

本次重构的目标不是增加新功能，而是**彻底停止维护旧运行路径，让仓库只保留新体系作为唯一业务逻辑来源**。

## 2. 总体原则

1. 新体系优先：Dataset 统一使用 `ser_lib.data.importers`、`DatasetManifest`、`DatasetService`。
2. 应用边界统一：CLI / future Worker 统一通过 `ser_lib.services` 进入领域逻辑，不在应用层重新拼业务。
3. Diagnostic 单轨：Importer 对外只暴露统一 `Diagnostic`，不再维护 issue/warning/structured 三套状态。
4. Training 单轨：ExperimentConfig 的 `optimizer` 节点是唯一优化器配置来源；不再让 TrainerConfig 同时承担 optimizer 参数。
5. 内部重复允许抽象，公共领域 DTO 不强行合并：Catalog 扫描器可共享内部 primitive，但 Training/Evaluation/Artifact/Checkpoint/Dataset Revision 继续保留各自 DTO。
6. 删除旧代码时同步删除旧测试、旧文档、旧依赖和旧示例，不能留下假入口。
7. 不为了“删旧”破坏仍有现实数据价值的持久化格式读取能力。Artifact v1 / checkpoint v1 是否退役必须以文件格式安全性和用户已有产物为依据单独处理；本计划默认只移除旧代码路径，不主动删除历史文件读取兼容。
8. 所有提交必须保持可审查；每一阶段完成后检查引用、测试和 CI。

## 3. 本次明确退役的旧系统

### 3.1 Legacy DatasetProcessor

删除：

- `data/base_processor.py`
- `data/casia_process.py`
- `tests/test_dataset_processor.py`

迁移：

- CASIA 数据准备统一到 `ser_lib.data.importers.casia.CasiaImporter` + `scripts/prepare_casia.py`。
- 若旧脚本的 speaker split 行为仍有测试价值，将其作为新 prepare/importer 的显式策略实现，而不是保留旧 Processor。
- `data/readme.md` 改为新入口。
- `pyproject.toml` 中仅为旧 Processor 测试引入的依赖若无其他用途则移除。

验收：仓库中不再出现 `DatasetProcessor`、`CasiaProcessor`、`python data/casia_process.py`。

### 3.2 Legacy Importer Diagnostics

删除：

- `ImportIssue`
- `ImportPreview.issues`
- `ImportPreview.warnings`
- `ImportPreview.structured_diagnostics`
- 兼容桥接型 `diagnostics` property

替换为：

- `ImportPreview.diagnostics: list[Diagnostic]`
- error / warning / info 均通过 `DiagnosticSeverity` 表达。

所有 importer 必须直接创建 `Diagnostic`，CLI/Service/Test 只读取一个 diagnostics 集合。

验收：Importer 生产代码中不存在 `.issues` / `.warnings` / `ImportIssue`。

### 3.3 CLI 业务旁路

重构 `ser_lib/cli/workflows.py`：

- Artifact inspect/verify/load/export 统一调用 `ArtifactService`；
- 推理统一优先调用 `InferenceService`；
- Evaluation/Training 继续通过 Service；
- CLI 仅保留参数解析、DataLoader 构建、I/O 展示等应用层职责，不重新实现 Service 已提供的领域行为。

验收：CLI 不再直接调用与 Service 重复的 Artifact/Inference 领域函数。

### 3.4 `_LineageTrainer` 过渡层

删除 `ser_lib.services.training._LineageTrainer`。

在 `Trainer` 中加入最小、正式的 lineage/checkpoint metadata 扩展点，使：

- `TrainingService.create_trainer()` 负责构造 `TrainingRunMetadata`；
- `Trainer` 负责在 checkpoint save/resume 时携带该 metadata；
- 直接构造 Trainer 时 lineage 可为空，不产生隐式文件 I/O。

验收：Service 不再通过继承 Trainer 改写私有方法。

### 3.5 Importer convert 重复实现

在 importer 内部层增加共享写盘 helper，统一：

- destination 创建；
- scan 结果验证；
- JSONL 写入；
- dataset.yaml 写入；
- ProgressEvent 阶段；
- DatasetManifest.load 回读；
- cancellation 边界。

各 importer 只保留：

- scan 逻辑；
- dataset_id/root/splits/labels 等领域差异；
- 必要的 record/split 变换。

验收：CSV/JSONL/Folder/CASIA 等 importer 不再复制同一套 3-step convert 流程和 YAML helper。

### 3.6 Catalog scanner 重复实现

增加内部通用扫描 primitive，统一：

- candidate 迭代；
- cancellation；
- fail_fast；
- failure 捕获；
- progress event。

保留：

- `TrainingRunCatalog`
- `EvaluationRunCatalog`
- `CheckpointCatalog`
- `ArtifactCatalog`
- `DatasetRevisionCatalog`

验收：领域 Catalog DTO 和排序规则仍独立，重复的扫描控制流被消除。

### 3.7 Legacy Trainer optimizer 配置

退役：

- `TrainerConfig.learning_rate`
- `TrainerConfig.weight_decay`

正式唯一来源：

- `ExperimentConfig.optimizer`
- `ser_lib.engine.optim`

直接构造 `Trainer` 时：

- 调用方若未传 optimizer，使用统一默认 optimizer config 构建；
- 不再从 TrainerConfig 读取 lr / weight decay。

同步更新 smoke tests / examples / docs。

验收：仓库生产代码与测试中不再使用 `TrainerConfig(learning_rate=...)` / `weight_decay=...`。

### 3.8 测试与文档收口

- 把 run detail validation-error 回归测试并回对应 training/evaluation 测试文件，去掉重复 fixture；
- 更新 `data/readme.md`、README/API 文档中旧入口；
- 已完成的旧 roadmap 不参与业务实现，必要时标记为历史资料；
- 检查示例不再演示旧路径。

## 4. 本次暂不删除的兼容能力

以下内容虽然属于历史兼容，但不是“旧业务系统双轨”，默认保留：

- Artifact v1 的受控读取；
- Checkpoint v1 的可信本地读取；
- Schema migration framework；
- 根包已经锁定的稳定 public re-export；
- ETA 旧字段，只要仍属于已发布事件契约。

如果后续决定做 breaking major version，再单独建立 deprecation/removal 文档处理这些持久化/API 兼容问题。

## 5. 开发顺序

### Task 01 — Legacy DatasetProcessor Removal

1. 确认旧 Processor 全部引用。
2. 将 CASIA 唯一入口切到新 Importer/prepare。
3. 删除旧 Processor、脚本和测试。
4. 更新 data 文档与依赖。
5. 跑 dataset/importer 测试。

### Task 02 — Diagnostic Single Track

1. 修改 ImportPreview 数据结构。
2. 全量迁移 importer。
3. 更新 DatasetService/CLI/测试消费方式。
4. 搜索并确保无 `ImportIssue` / `.issues` / `.warnings` 生产引用。

### Task 03 — Shared Importer Conversion Pipeline

1. 抽共享 convert helper。
2. 依次迁移 folder/csv/jsonl/casia/ravdess/crema-d/esd/csemotions/emotiontalk。
3. 保证生成文件与旧新体系当前输出语义一致。

### Task 04 — Service-first CLI

1. Artifact CLI 统一走 ArtifactService。
2. Inference CLI 统一走 InferenceService。
3. 保持输出格式不变。
4. 更新 CLI 测试。

### Task 05 — Trainer Lineage Integration

1. 将 lineage 作为 Trainer 正式可选状态/扩展点。
2. 合并 checkpoint metadata save/resume。
3. 删除 `_LineageTrainer`。
4. 更新 TrainingService 和测试。

### Task 06 — Optimizer Config Single Track

1. 移除 TrainerConfig legacy optimizer 字段。
2. Trainer 无显式 optimizer 时使用 `engine.optim` 的默认配置。
3. 更新 smoke/examples/tests/docs。

### Task 07 — Shared Catalog Scan Primitive

1. 抽内部 scanner helper。
2. 迁移 Training/Evaluation/Checkpoint/Artifact/DatasetRevision scanner。
3. 保留每个领域的 candidate/sort/DTO 语义。

### Task 08 — Test & Docs Cleanup

1. 合并重复 run-detail fixture/tests。
2. 全仓搜索旧符号和旧命令。
3. 清理只服务旧路径的依赖/文档。
4. 更新本计划完成状态。

### Task 09 — Full Validation

至少执行：

- `python -m compileall ser_lib scripts tests`
- `pytest`
- Ruff
- mypy
- coverage gate
- training smoke
- package build / wheel smoke（如 CI 已配置）
- Linux / Windows / macOS，Python 3.10 / 3.12 GitHub Actions

## 6. Commit 规划

建议保持以下粒度：

1. `docs(refactor): plan legacy system retirement`
2. `refactor(data): remove legacy dataset processor`
3. `refactor(data): unify importer diagnostics`
4. `refactor(data): centralize importer conversion pipeline`
5. `refactor(cli): route workflows through services`
6. `refactor(training): integrate lineage into trainer`
7. `refactor(training): remove legacy trainer optimizer fields`
8. `refactor(core): share catalog scan control flow`
9. `test(refactor): consolidate legacy cleanup coverage`
10. `docs(refactor): finalize legacy system retirement`

若一个阶段包含大量机械迁移，可拆成同一主题下多个 commit，但不得把互不相关的重构混在一个提交中。

## 7. 最终验收标准

完成后必须满足：

- 仓库只有一套 Dataset 导入/准备体系；
- Importer 只有一套 Diagnostic 表示；
- CLI 与 future Worker 的推荐业务入口都是 `ser_lib.services`；
- Training 不再依赖 `_LineageTrainer`；
- optimizer 参数只有一个正式配置来源；
- Importer convert 与 Catalog scan 不再复制大段控制流；
- 旧测试、旧命令、旧文档入口、只为旧路径存在的依赖被同步清理；
- 当前新体系行为、JSON-safe DTO、事件、取消、轻量 inspect 成本边界不退化；
- 全平台 CI 通过后才允许合并回 `main`。
