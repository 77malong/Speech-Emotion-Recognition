# 安装与环境

支持 Python 3.10–3.12。CI 在 Linux、Windows 和 macOS 上覆盖声明的 Python
版本，并在 Linux/Python 3.12 上额外验证基础安装、构建产物和源码树外隔离 wheel。

基础库安装：

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
```

开发与测试环境：

```bash
python -m pip install -e ".[test,dev]"
```

Hugging Face 预训练音频模型是可选能力，正式 extra 名称为 `hf`：

```bash
python -m pip install -e ".[hf]"
```

基础安装不会引入 `transformers`；需要 Hugging Face 能力时只使用 `hf` extra。

PyTorch/TorchAudio 必须来自兼容版本与相同 CPU/CUDA 渠道。安装后运行：

```bash
python -c "import ser_lib; print(ser_lib.__version__)"
ser components list --json
```

若命令找不到，先确认当前 shell 已激活虚拟环境，并可用
`python -m ser_lib.cli` 代替 `ser` 排查入口安装问题。
