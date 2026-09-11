# Artifact 与安全边界

当前 artifact 包含固定名称 `weights.safetensors` 的权重、数据/模型配置、标签、指标、模型卡和
manifest。manifest 保存所有组成文件的 SHA-256；加载器先验证当前结构、路径、文件
存在性、哈希及外部元数据一致性，再构建模型。

```bash
ser artifact export --config configs/cnn_logmel.yaml \
  --checkpoint runs/cnn-logmel/checkpoints/best.pt --destination artifacts/model
ser artifact verify artifacts/model --json
ser artifact inspect artifacts/model --json
```

导出目标必须不存在，防止覆盖已有模型。artifact 是目录级原子写入，加载器没有 pickle 权重入口。
`library_version` 只用于记录创建来源，不控制加载分支；不接受 `schema_version` 或 `weights_format`。
发布模型时必须补充
模型卡中的训练数据、语言、许可、用途和限制，不得把 checkpoint 冒充 artifact。

checkpoint 仅用于可信本地续训，仍使用 Torch 序列化以保存优化器和随机状态。
它严格接受当前完整 payload，不提供历史格式回退。格式验证不使不可信 pickle 安全。
