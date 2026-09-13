# 安全说明

## 报告漏洞

请使用代码托管平台的私密安全报告渠道，不要在公开 issue 中披露可利用细节。维护者确认后
会评估受影响版本并协调修复与披露。

## 1.0 信任边界

- **Model artifact**：分发模型使用 safetensors；load 前校验 manifest、路径和 SHA-256。
- **Training checkpoint**：使用 Torch/pickle 保存优化器和 RNG，只能加载自己生成且来源可信的文件。
- **无 pickle artifact 回退**：1.0 artifact 只接受当前 safetensors 结构。
- **Hugging Face**：默认本地加载，禁止远程自定义代码（`trust_remote_code=False`）。
- **Importer**：不会执行数据集附带 Python 脚本，也不会自动下载受限语料。
- **路径**：artifact/manifest 写入和加载均校验路径边界，不能通过元数据逃逸目标目录。
- **恢复失败**：checkpoint restore 对已应用 runtime state 实施回滚，避免调用方继续使用半恢复对象。

本库不提供执行任意用户 Python 代码的插件入口。

## 供应链

模型、数据集和依赖各自具有独立供应链及许可风险。发布者/部署者仍需审查来源、哈希、
模型卡、数据授权和依赖版本。

安全边界的技术说明见 [docs/ARTIFACTS_AND_SECURITY.md](docs/ARTIFACTS_AND_SECURITY.md)。
