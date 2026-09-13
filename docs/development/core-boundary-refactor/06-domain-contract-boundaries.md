# Stage 06 — Data / Models / Engine 契约归位与依赖边界整理

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


## 目标

修正当前跨领域类型归属和 helper 依赖，使 data、models、engine、inference 之间的静态依赖方向符合核心库边界，为后续删除页面包装和 Service 做准备。

## 前置条件

- Stage 05 已删除 `core/`。
- 新 `foundation` 与 `config` 依赖方向稳定。

## 重点问题

当前审计明确指出：

- `ModelSpec` 位于 `data.validation`，模型概念归属错误。
- evaluation 与 inference 为了 `move_batch_to_device` 反向依赖 trainer。
- `RegistryError`、`CompatibilityError` 等错误归属混杂。

## 具体任务

1. 将 `ModelSpec`、相关模型静态规格迁入 `models/specs.py`。
2. 将跨模型/数据兼容检查迁入 `engine/compatibility.py`。
3. 将 `move_batch_to_device` 等通用 batch/device helper 迁到适当的数据契约层，例如 `data/types.py`。
4. 让 trainer、evaluator、offline inference 从同一 batch helper 获取行为，不再相互 import。
5. 核对 `TensorSpec`、`ModelOutput`、runtime metric、streaming latency 等类型的真实领域归属。
6. 将跨 registry 通用错误放到 foundation；数据专属错误继续留 data；兼容性诊断归 engine。
7. 建立静态架构测试：
   - foundation/config 无领域反向边；
   - data 不 import engine/models；
   - models 不 import Dataset 实现；
   - inference 不 import trainer 内部实现。
8. 保持字段、异常 code、ModelSpec 读兼容和 artifact 中已有模型规格兼容。

## 非目标

- 不在本阶段重写 Trainer。
- 不删除 Service。
- 不实现 Torch/HF adapter。

## 验收标准

- 关键模块可按多种 import 顺序加载，无循环初始化问题。
- 训练、评估、推理设备迁移后的 batch metadata、mask、length 保持不变。
- ModelSpec 成为 models 的正式契约，兼容检查成为 engine 的正式职责。
- 架构依赖测试进入 CI。

## 风险

- 移动类型后 artifact/registry 反序列化路径失效。
- helper 迁移时丢失 metadata 或 non-blocking/device 语义。
- 为了“干净分层”把真实领域对象错误下沉到 foundation。

## 建议提交

`refactor(architecture): realign model data and engine contracts`

## 实施记录

- 开始 Stage 06 前已重新读取设计依据 `SER_LIB_CORE_BOUNDARY_AUDIT.md`、证据依据 `SER_LIB_CORE_BOUNDARY_EVIDENCE.md` 以及本阶段计划；前置 Stage 05 最终 HEAD `4b1abd0325628bfdf53c08350bc3547c49159e77` 的 CI #294 已 7/7 全绿。
- `RegistryError` 与跨 data/models 的 `CompatibilityError` 正式归属 `foundation.errors`；`data.errors` 仅保留指向同一类型对象的 0.2.x 兼容导出，数据专属异常继续留在 data。
- `ModelSpec` 的唯一真实定义迁入 `models/specs.py`，模型基类、内置模型和 model registry 均直接依赖 models 契约；旧 `data.validation` 最终删除，不保留会制造 data→models/engine 回边的兼容 shim。
- `CompatibilityReport`、`inspect_compatibility()`、`validate_compatibility()` 及原有兼容检查算法迁入 `engine/compatibility.py`；检查顺序、Diagnostic code、异常 code 与错误上下文语义保持不变。根包原有 `CompatibilityReport` / `inspect_compatibility` 名称继续惰性解析到 engine。
- `move_batch_to_device()` 的唯一实现迁入 `data/types.py`；trainer、evaluator、offline inference 复用同一 helper，`engine.trainer.move_batch_to_device` 仅作为兼容重导出。新增测试锁定 uids、metadata、inputs、lengths、masks、labels 与 window_map 在设备迁移后的保真行为。
- 核对后保持 `TensorSpec` 位于 `data/types.py`、`ModelOutput` 位于 `models/base.py`、`RuntimeMetrics` 位于 `runtime.py`、`StreamingLatency` 位于 `inference/streaming.py`，未为了形式统一错误下沉真实领域对象。
- 新增静态架构测试，约束 foundation/config 无领域反向依赖、data 不 import models/engine、models 不 import Dataset 实现、inference 不 import trainer 内部实现，并锁定 canonical owner 与旧错误别名 identity。
- Stage 01 的 pre-refactor JSON fixture 保持原样作为历史证据；测试代码显式记录 Stage 06 的计划内 namespace delta，而不是修改旧快照掩盖 API 迁移。
- CI #295 的 6 个运行矩阵全部成功，仅发现 `RegistryError` 兼容重导出的 Ruff F401，随后以显式 self-alias 修复。CI #298 的 Ruff/mypy 已通过，运行矩阵和 coverage 唯一阻塞为 `test_pretrained_adapter.py` 遗留的旧 data compatibility import；修复后最终代码 HEAD `6741362d2d310297745891d4eea9d0accab0a175` 对应 CI #299（run `34432010642`）7/7 job 全部 success，包括 Ruff、mypy、coverage、Windows/macOS/Linux × Python 3.10/3.12、Ubuntu 3.12 wheel smoke 与端到端训练 smoke。
