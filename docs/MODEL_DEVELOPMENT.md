# 模型扩展

SER-lib 1.0 的模型扩展以 `SERModel` 契约为核心。

## 必须实现

- `model_spec`：输入 key、TensorSpec、mask/变长能力和类别数。
- `model_config`：JSON 可序列化、足以从 registry 重建模型的完整配置。
- `forward(SERBatch)`：返回 `ModelOutput`，分类 logits 形状为 `[B, C]`。

模型不能自行读取音频、manifest 或猜测输入 layout。

## Registry

自定义模型应注册 `ModelDescriptor` 和严格配置 schema。构建时必须通过模型与数据
输出的 compatibility 检查，而不是在 forward 中容忍不确定输入。

## 变长输入

支持变长序列的模型必须正确消费 lengths/mask，padding 不得改变有效序列的预测结果。
fixed/sliding/dynamic batching 的 mask 语义应在测试中分别覆盖。

## Torch adapter

TorchModelAdapter 用于把满足契约的 torch.nn.Module 接入 SERModel。状态保存/加载必须
在独立实例和嵌套 Module 场景均可 round trip。

## Hugging Face adapter

可选 HF adapter 支持本地 Wav2Vec2、HuBERT、WavLM 类音频模型。要求：

- 默认 `local_files_only=True`
- `trust_remote_code=False`
- processor/feature extractor 重建配置必须随 artifact 持久化
- 分类头与 label 数量/语义必须显式匹配
- 导出的 artifact 必须可在离线环境恢复

## 测试要求

新增模型至少覆盖：

1. 配置 validate / serialize / rebuild
2. ModelSpec 与真实 forward 输入一致
3. padding/mask 隔离
4. 一步训练和梯度更新
5. state_dict round trip
6. checkpoint restore
7. artifact export/load round trip
8. 非有限 logits 被显式拒绝

不要把只通过 shape smoke 的实现标记为稳定模型。
