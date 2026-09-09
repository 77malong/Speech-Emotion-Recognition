# Stage 10 — 通用 PyTorch Model Adapter

## 目标

让普通 `torch.nn.Module` 在不继承 SER-lib 内部模型基类的前提下，通过显式 adapter/registry contract 接入训练、评估、推理、checkpoint 与 artifact 闭环，同时不破坏 state_dict 和可重建性。

## 前置条件

- Stage 09 核心 API 已去除应用包装。
- `ModelSpec`、registry、artifact/checkpoint 契约已稳定。

## 目标结构

- `ser_lib/models/adapters/__init__.py`
- `ser_lib/models/adapters/torch.py`
- 必要时完善 `models/specs.py`、`models/registry.py`

## 设计原则

1. Adapter 是模型契约适配，不是新的 Trainer。
2. 普通 `nn.Module` 可以映射输入 key、mask/length、logits/embedding 输出到 `ModelOutput`。
3. factory/config 必须可序列化，artifact 不能保存任意 Python callable 并在加载时执行。
4. 未注册、不可重建的 adapter 在 export 前明确失败。
5. 不自动安装依赖、不自动 clone 论文仓库。

## 具体任务

1. 定义通用 Torch adapter 配置：factory ID、输入映射、输出映射、类别数、采样率/输入类型、冻结能力等。
2. 支持普通 `nn.Module` train/evaluate/predict。
3. adapter 包装不得无意增加 `module.` / `model.` 等 state_dict 前缀；若必须转换，建立明确兼容映射并测试。
4. 支持 registry 中的静态 `ModelSpec` 与 capabilities 查询，dry-run 不实例化重模型。
5. checkpoint save/resume 使用同一模型参数契约。
6. artifact export/load 能依据注册 ID + 可序列化 config 重建模型。
7. labels/num_classes/classifier head 与 ModelSpec 一致性预检。
8. 增加 `examples/custom_torch_adapter.py` 的设计占位需求，但示例实际代码可在最终文档阶段补齐。

## 验收标准

- 至少一个不继承 SERModel 的 tiny `nn.Module` 完成 train→eval→predict→checkpoint resume→artifact export/load。
- export/load 前后 state_dict key 和数值一致。
- 不可序列化 callable、未注册 factory、类别不匹配均在早期给出可行动错误。
- registry 不新增第二套 TorchAdapterRegistry。

## 风险

- state_dict 前缀变化导致旧权重无法恢复。
- 接受任意 callable 导致 artifact 不可移植或存在代码执行风险。
- Adapter 过度抽象，重新制造一套模型框架。

## 建议提交

`feat(models): add explicit torch module adapter contract`
