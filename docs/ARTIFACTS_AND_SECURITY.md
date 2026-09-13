# Artifact 与安全边界

SER-lib 1.0 明确区分 **training checkpoint** 与 **model artifact**。

## Model artifact

用于分发、评估和推理。目录包含：

- `weights.safetensors`
- 当前模型配置
- 当前数据/预处理配置
- 标签映射
- 指标和模型卡
- 可选 Hugging Face processor 配置
- manifest 及组成文件 SHA-256

~~~bash
ser artifact export   --config configs/cnn_logmel.yaml   --checkpoint runs/cnn-logmel/checkpoints/best.pt   --destination artifacts/model   --json

ser artifact inspect artifacts/model --json
ser artifact verify artifacts/model --json
~~~

导出目标必须不存在。写入采用目录级原子策略；verify/load 在构建模型前校验结构、
路径和哈希。artifact 只接受当前 safetensors 结构，不提供 pickle artifact 回退入口。

`library_version` 用于 provenance，不作为隐藏 migration 分支。

## Training checkpoint

checkpoint 保存继续训练所需状态，因此使用 Torch 序列化：

- model / optimizer / scheduler / scaler state
- Python / NumPy / Torch RNG
- 采样器状态
- epoch、优化器计数、最佳模型身份
- trainer config 与 run lineage

它只能加载由自己生成且来源可信的本地文件。pickle 本身不适合不可信输入。

恢复前进行结构、模型、配置、RNG、采样器和关联 checkpoint 校验；应用状态失败时执行
回滚，避免模型/优化器停留在半恢复状态。

## 标签和数据语义

从 checkpoint 导出 artifact 时，不仅比较 num_classes，还比较：

- checkpoint 训练标签
- 当前导出配置标签
- 当前 manifest 标签
- dataset id / fingerprint
- 训练/导出预处理契约

语义不一致会拒绝导出。

## 模型发布要求

发布 artifact 时模型卡至少写明：

- 训练数据与数据许可
- 标签定义
- 模型许可
- 预期用途
- 已知限制
- 评估数据与指标含义

不得把 checkpoint 改名后当作 artifact 发布。
