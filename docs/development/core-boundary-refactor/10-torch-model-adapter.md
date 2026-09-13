# Stage 10 — 通用 PyTorch Model Adapter

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


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

## 实施记录

Stage 10 开始前重新读取了 `docs/development/review/SER_LIB_CORE_BOUNDARY_AUDIT.md`、`docs/development/review/SER_LIB_CORE_BOUNDARY_EVIDENCE.md` 与本阶段计划。实现严格限定为普通 `torch.nn.Module` 到既有 `SERModel`、`ModelSpec`、`ModelRegistry`、checkpoint 与 artifact 契约的适配，没有新增 Trainer、第二套 adapter registry，也没有修改 checkpoint format 或提前进入 Stage 11 的 Hugging Face processor 持久化工作。

本阶段从 Stage 09 closure `d02ad52988de0194df612213c423bcb64c4b27ce` 推进到代码验收 HEAD `f400a86f817768fe36e4f2f3facced32e5a4b993`，共 13 个提交：`0fe93707a194c87144cef360e73a1e5663f5dab0`、`3960f754226a97dcfec64e11b718b809ef1d569a`、`c1e0762da3e4900b4e3b04155db4696ccdcef466`、`19947d7301614222791aaca07892965474b8d9b4`、`18054e1680200d6eb5a797f0a9d52a972b33b89c`、`a2bc35b76441797c641c113db6884114c9180928`、`e4e592e87b106fd11f9b812882c598bdba545cbb`、`45d897f9f3aa62ceb0c69dcef0d5391dc8b46188`、`a43301f0190af5356c932f002bd185fe6f2bbe91`、`3b2b6710182a5e226c3ea951e69d2937b13304ba`、`67acadff7667f059fa6ceb85b1efdc0e25f1ae55`、`53a8af37f49132033ca08dc9794e6f722abde46a`、`f400a86f817768fe36e4f2f3facced32e5a4b993`。

中央配置新增 Torch adapter 的 factory ID、JSON-safe factory params、input mapping、output mapping、required input specs、`num_classes`、sample rate、mask/variable-length capability 与冻结选项。配置定义本身不导入 torch；任意 callable 或其他不可 JSON 序列化值不会进入 artifact model_config。

`ModelRegistry` 继续是唯一模型注册表。普通 Torch factory 作为同一 registry 的受控能力登记，通过稳定 factory ID 重建 `nn.Module`；`validate_reconstructible()` 可以在 artifact 写盘前验证 adapter 是否拥有已注册的可重建 factory，而无需把 callable 写入 artifact。静态 `ModelSpec` 查询继续使用原 registry dry-run 路径，不实例化底层重模型。

新增 `ser_lib/models/adapters/torch.py:TorchModelAdapter`，将 `SERBatch.inputs`、`masks`、`lengths`、`labels` 通过显式路径映射为普通 module 参数，并将 tensor、mapping/tuple/object 输出按显式 selector 归一到 `ModelOutput`。adapter 不接管训练循环；Trainer、evaluate 与 EmotionPredictor 仍只依赖现有 `SERModel` contract。

state_dict 兼容是本阶段的强约束：adapter 的 `state_dict()` / `load_state_dict()` 直接委托被包装 module，因此 export、artifact load 与 checkpoint resume 看到的 key 与原始 module 完全一致，不引入 `module.`、`model.` 或 `_module.` 前缀。冻结能力只修改底层参数 `requires_grad`，不改变权重 key。

artifact exporter 在创建 staging 目录前调用 registry reconstructibility 校验，并预检 labels 数量与 `ModelSpec.num_classes`。因此手工 wrap 且没有 factory ID、未注册 factory、不可序列化 factory config 或 labels/分类头不一致均会早期失败；checkpoint 仍允许本地手工 adapter，因为 checkpoint 是可信本地恢复格式，不要求跨进程 registry 重建。artifact schema 与 checkpoint format 均未升级。

新增 `tests/test_torch_model_adapter.py`，使用一个明确不继承 `SERModel` 的 tiny `nn.Module` 覆盖 train → evaluate → checkpoint save/resume → artifact export/load → file predict 全链路，并检查 export/load 前后 state_dict key 与 tensor 数值一致；同时覆盖 static spec 无实例化、unregistered factory、无 factory ID、callable config、运行时分类维不一致、labels mismatch 与 freeze 行为。Stage 01 历史 fixture 保持不变；Stage 10 新增 public API 只在当前契约测试中显式记录。

首轮 exact-head CI #391 / run `34445513042` 中 package install、dependency check、compile、Ubuntu 3.12 distribution build/wheel smoke、Ruff 与 mypy 均通过；完整测试为 378 passed / 1 failed。唯一失败来自新测试把现有 Trainer 的 keyword-only `optimizer` 错误地作为第三个位置参数传入，并非 adapter 实现缺陷。`f400a86f817768fe36e4f2f3facced32e5a4b993` 将调用修正为 `optimizer=optimizer`。

修复后的代码验收 CI #392 / run `34445777856` 为 7/7 `completed/success`：Static checks（dependency consistency、Ruff、mypy、package coverage）全部成功；Ubuntu、macOS、Windows × Python 3.10/3.12 六个运行矩阵的 package install、compile、完整 tests 与 end-to-end training smoke 全部成功，Ubuntu Python 3.12 的 distribution build 与独立 wheel smoke 同样成功。

Stage 09 closure 到 Stage 10 代码 HEAD 的 compare 仅包含 `ser_lib/config/model.py`、`ser_lib/config/__init__.py`、`ser_lib/models/registry.py`、`ser_lib/models/__init__.py`、新增 `ser_lib/models/adapters/`、`ser_lib/artifacts/exporter.py` 及对应 API/adapter tests；没有改动 Trainer 实现、checkpoint 格式、HF processor 或 Stage 11 目标文件。因此 Stage 10 代码验收满足计划边界与验收标准。
