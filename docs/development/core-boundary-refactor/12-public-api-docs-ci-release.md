# Stage 12 — Public API、CLI、文档、依赖与发布验收收口

## 目标

完成整个核心边界重构的最终清场：收缩公开 API、删除所有过渡 shim 和死路径、同步 CLI/示例/配置/教程/文档、收紧依赖与 CI，并从源码树外对 wheel 做最终验证。

## 前置条件

- Stage 01–11 全部完成。
- `core/`、`services/`、Page/View/Detail 包装已经按计划退役。
- Torch/HF adapter 全链路已有真实测试证据。

## 修改范围

重点包括：

- `ser_lib/__init__.py`
- 各子包 `__init__.py` / `__all__`
- `ser_lib/_version.py`
- `ser_lib/cli/*`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `scripts/check_coverage.py`
- `tests/test_coverage_policy.py`
- `README.md`
- `docs/API_REFERENCE.md`
- `docs/MODEL_DEVELOPMENT.md`
- `docs/TRAINING_AND_CLI.md`
- `docs/ARTIFACTS_AND_SECURITY.md`
- examples/configs/tutorials/notebooks
- `CHANGELOG.md`

## 具体任务

1. 收缩根包重导出，避免 import `ser_lib` 加载几乎全部 package。
2. 删除所有中间 deprecation shim、旧 `core`/`services` import alias、Page/View/Detail/Catalog 残留。
3. 搜索源码、测试、示例、配置、notebook、文档中的旧路径，必须归零或明确作为历史兼容说明。
4. 更新 CLI，使所有命令只调用新的 public domain API。
5. 更新 API reference、模型开发、训练 CLI、artifact/security、安装说明和示例。
6. 检查 tutorial/notebook 是否仍引用旧 Service/DTO；不可执行教程继续明确标注状态。
7. 更新 coverage policy：删除 core 门槛，foundation/config 分别建立合理门槛且不降低其他领域标准。
8. 清洁环境验证基础安装不引入 transformers；单独验证 `.[hf]`。
9. Linux/Windows/macOS × 已声明 Python 版本运行 pip check、compileall、pytest、Ruff、mypy、coverage、CPU training smoke、build/wheel smoke。
10. wheel smoke 必须在源码树外、隔离 venv 中执行，避免源码遮蔽和系统 site-packages 污染。
11. 检查 wheel 内容：不得包含 core/services/应用包装；必须包含新 config、foundation、adapter 和必要 processor assets/entry metadata。
12. 固定旧 config/dataset/checkpoint/artifact fixture 做最终读兼容验证。
13. 更新 CHANGELOG，明确 breaking API、保留的持久化兼容面和迁移示例。
14. 最终比较本分支与 main，确认没有无意删除真实 SER 能力。

## 完成定义

- `ser_lib` 是纯 Python SER Core/SDK，边界清晰，不预置未来 Web/Desktop 的 Service/Page/DTO。
- foundation 足够小，无领域反向依赖；所有内置用户配置集中在 config。
- 只有一套正式 Trainer/evaluate/predict 路径和一套 model registry。
- Torch/HF 模型均可通过统一契约训练、评估、推理、保存和恢复。
- 文档、示例、CLI、wheel 与源码真实 API 一致。
- CI 全部通过后才允许合并，不用旧 commit 的绿色结果替代当前 HEAD。

## 风险

- 最终清理遗漏旧 import，源码环境可运行但 wheel 失败。
- 更新文档时继续保留已删除的 Service-first 架构描述。
- coverage 因模块移动被错误下调。
- HF extra 支持范围没有真实 matrix 证据。

## 建议提交

可按 docs/ci/dependency 分拆，但最终阶段收口提交建议：

`chore(refactor): finalize SER-lib core boundary migration`

## 实施记录

Stage 12 以本阶段计划和前 11 个阶段已经锁定的领域边界为基准完成最终发布收口，没有为了兼容旧应用包装重新引入 `core`、`services`、Page/View/Detail/Catalog facade，也没有通过降低覆盖率、放宽配置校验或恢复根包大规模重导出来换取 CI 通过。

实际完成：

- `ser_lib` 根包收缩为 12 个惰性高层便利入口；配置、数据、模型、训练/评估、推理、artifact、foundation 与 runtime 的完整能力由各领域 public API 提供。`tests/test_public_api.py` 与预重构契约快照共同锁定最终根包和领域公开面，防止后续无意重新扩大根包 API。
- 物理退役 `ser_lib.core`、`ser_lib.services`、跨领域 `ser_lib.catalog`、旧 `ser_lib.models.pretrained`、Page/View/Detail 等应用包装和过渡 shim。源码树外 isolated wheel smoke 明确断言这些路径不可导入，同时验证 `ser_lib.config`、`ser_lib.foundation`、Torch/HF adapter 与 `ser` entry point 均存在。
- CLI 收口为薄编排层，只依赖领域公开 API。期间曾为 CLI lineage 转换把 `artifact_provenance_from_training_run` 意外加入 `ser_lib.engine.__all__`；精确 public API 快照立即报错，最终选择保持已锁定的 engine public surface，而不是修改快照扩大 API。
- `readme.md`、`CONTRIBUTING.md`、`docs/INSTALLATION.md`、`docs/API_REFERENCE.md`、示例和 `CHANGELOG.md` 已与真实边界同步，移除已删除 `core`/旧实现计划的失效引用；Hugging Face 正式 optional extra 统一为 `.[hf]`，`.[pretrained]` 仅保留为安装兼容别名。
- coverage policy 删除已退役 core 门槛，为 `foundation` 与 `config` 建立各 85% 的独立门槛，并保留 artifacts 85%、engine/inference/models 80%、data 60%、cli 65% 等既有领域要求，没有因模块迁移下调其他领域标准。
- CI 扩展为 Linux/Windows/macOS × Python 3.10/3.11/3.12 的 9 个普通矩阵 job、Transformers 4.38.2/5.17.0 两个真实 tiny-model HF lane，以及独立 Static job。普通矩阵覆盖 `pip check`、compileall、pytest 和 CPU training smoke；Ubuntu/Python 3.12 额外验证基础安装不含 Transformers、distribution build、源码树外 isolated wheel 安装及 wheel 内容；Static 覆盖 Ruff、mypy 和分包 coverage。
- 增加固定 release compatibility fixture，分别验证旧 ExperimentConfig v1 的相对路径解析、无显式 `schema_version` 的旧 dataset manifest、checkpoint v1 状态恢复，以及 artifact v1 的 inspect/verify 与安全授权语义。legacy artifact 默认拒绝 pickle 权重，只有调用方显式设置 `allow_legacy_pickle=True` 才允许可信加载。
- legacy experiment fixture 首轮使用 `log_mel.n_mels=4`，真实当前 `LogMelConfig` 正确拒绝了该非法配置。修复选择把该 experiment fixture 的 `n_mels` 与模型 `feature_dim` 同步为合法的 16，没有放宽 `n_mels >= 16` 的正式配置约束；随后把兼容验收提升为运行时生成小 WAV、通过公开 `train_experiment()` 实际执行一轮训练并验证真实 checkpoint/lineage，而不再只证明 YAML 可以解析。
- 最终再次比较本分支与 `main`：2026-09-10 复核时 main HEAD 仍为 `7018e05dbbfd5e40207ac8ccfd886cbaedbebfe6`，没有新的 main 提交需要同步。当前递归文件树再次确认 `ser_lib/core`、`ser_lib/services` 不存在，而 `data`、`models`、`engine`、`inference`、`artifacts`、`config`、`foundation` 以及 Torch/HF adapters 均存在；后续 strict-review 修复只增强数值正确性、恢复语义和测试，没有新增计划外能力删除。

### Strict review 后续修复

Stage 12 初次收口后又执行了 `docs/development/SER_LIB_STRICT_REVIEW_2026-09-10.md` 的逐模块严格审计。该审计是问题发现基线，不因后续修复而改写原结论；本节记录在同一分支上的后续 remediation：

- 梯度累积改为按一个逻辑大 batch 的实际归约分母归一化，覆盖尾组、不同 microbatch 大小和 weighted cross-entropy，不再固定除以 `gradient_accumulation_steps`。
- 实验 seed 移到随机模型/组件创建之前；同一 experiment seed 不再受调用前全局 RNG 状态影响模型初始化。
- F0 修正 TorchAudio pitch smoothing 的 `win_length` 单位，并定义静音/短输入语义；未实现的 jitter/shimmer/HNR 不再伪造零值输出，而是显式拒绝。
- CNN 采用 mask-aware BatchNorm 并在卷积层间清零 padding，使变长输入在不同右侧 padding/batch 组合下保持不变，同时保留既有 BatchNorm state-dict 表面。
- 流式重采样改为有状态带限 sinc，实现 chunk partition invariance、与离线 TorchAudio 对齐，并新增目标 Nyquist 以上频率的抗混叠测试和有界 buffer 测试。
- 高层训练/评估入口增加 label-id 语义一致性校验；整数范围相同但 label 含义不同的 manifest/artifact 不再静默计算无意义指标。
- WeightedRandomSampler 的独立 `torch.Generator` 状态随 checkpoint 保存/恢复；resume 配置校验区分算法字段与运行字段，允许修改 `epochs`、`checkpoint_dir`、`save_last`、`save_best`，仍严格拒绝会改变数值训练语义的配置差异。
- `DatasetEditor.update_record()` 先完成所有验证再一次应用内存修改，失败操作不再留下可被后续 commit 误提交的 dirty 状态。
- 高层 checkpoint 返回值改为复用 `TrainingResult` 的实际保存结果；同时修正 `last_checkpoint` 契约，使逐 epoch checkpoint 不再冒充可选的 `last.pt`，`save_last=False` 时 fresh run 不会声称存在 `last.pt`。

兼容性证据边界必须保留：当前仓库中的 v1 checkpoint/artifact fixture 可以验证旧 schema、安全授权和加载路径，但其权重仍由当前实现构造，**不能等价宣称已用真实 0.1.0 发布环境生成的 golden checkpoint/artifact 做跨版本二进制回归**。若将来要把“真实历史二进制兼容”作为强发布承诺，应从实际 0.1.0 环境生成并固定最小 golden 制品，再执行加载→推理/续训验收。

版本语义复核：`pyproject.toml` 与 `ser_lib/_version.py` 均为 `0.2.0`，`CHANGELOG.md` 已把本轮从旧 API 面迁移到新领域 API 的 breaking changes 放在 Unreleased 中，历史 artifact fixture 标记 `0.1.0`。没有证据支持为了本次收口再次无依据 bump 到 0.3/1.0，因此保持 0.2.0 作为此次不兼容 API 面的目标版本。

CI 记录：

- CI #422 首先暴露测试仍从根包导入已迁移的兼容性、runtime、lineage、config 等 API；修复统一迁移到所属领域 public API，并加强“这些符号不得重新回到根包”的测试，而不是恢复旧根包导出。
- CI #426 暴露 CLI 收口过程中意外扩大的 `ser_lib.engine` public surface；精确契约快照捕获新增 `artifact_provenance_from_training_run`，后续恢复已锁定的 engine public API，CI #427 重新 12/12 全绿。
- CI #428 在新增旧格式 fixture 后暴露 legacy experiment 的 `n_mels=4` 不符合当前合法 Log-Mel schema；修复 fixture 自身维度契约，不修改生产校验。
- 初次 Stage 12 代码验收 HEAD `70e6ad02be640dc966e447bee07e1426a345cf01` 对应 CI #430 / run `34462775677`，当时 12/12 jobs 全部成功。之后 strict review 又发现并修复了数值/恢复/兼容性问题，因此 #430 不再作为最终验收依据。
- Strict-review remediation 代码验收 HEAD `b684f90bcc5183c334e382afa888bbd390fb80c0` 对应 CI #458 / run `34477790449`：12/12 jobs 全部 `completed/success`。Linux/Windows/macOS × Python 3.10/3.11/3.12、两个 Transformers lane、Ruff、mypy、分包 coverage、基础安装无 Transformers、distribution build、源码树外 isolated wheel smoke、完整 pytest 与 CPU training smoke 全部通过。

结论：Stage 12 的代码、文档、兼容性与发布门禁，以及 strict-review 中已列出的 P1/P2 remediation，均已完成到当前声明的证据边界。本记录提交后必须再以新的 doc-only exact HEAD 运行完整 CI；只有该 closure CI 也 12/12 全绿，才正式关闭 Stage 12，并完成全部 12 个核心边界重构阶段。
