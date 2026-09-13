# 第三方许可清单

本文件列出 SER-lib 1.0 的直接运行时依赖和主要可选依赖。实际发布/部署仍应针对锁定版本
审计完整传递依赖。

| 依赖 | 用途 | 上游许可 |
|---|---|---|
| PyTorch | 张量、模型与训练 | BSD 风格许可及其第三方许可 |
| TorchAudio | 音频 I/O、重采样、特征 | BSD-2-Clause |
| NumPy | 数值计算 | BSD-3-Clause |
| SoundFile | 音频文件读取 | BSD-3-Clause（并依赖 libsndfile 的许可） |
| Pydantic | 严格配置校验 | MIT |
| PyYAML | YAML 配置与 manifest | MIT |
| safetensors | 安全权重格式 | Apache-2.0 |
| Transformers（hf extra） | 预训练音频模型适配 | Apache-2.0 |

数据集和预训练模型不会因使用本库而获得重新许可。本仓库只提供 importer，不自动下载、
打包或重新分发语料。

已知示例：RAVDESS 常见发行条款为 CC BY-NC-SA 4.0；CREMA-D 数据库与单项内容有其
独立数据库/内容许可。CASIA、CSEMOTIONS、ESD、EmotionTalk 等必须以用户实际获取副本
附带的官方许可为准。

artifact 发布者应在模型卡中写明训练数据、模型/数据许可、用途和限制。
