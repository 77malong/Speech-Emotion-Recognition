# Stage 06 — Data / Models / Engine 契约归位与依赖边界整理

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
