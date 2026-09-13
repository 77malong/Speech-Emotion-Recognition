# 安装与环境

SER-lib 1.0.0 支持 Python 3.10、3.11、3.12。CI 覆盖 Linux、Windows、macOS，
并对构建后的 wheel 做源码树外隔离安装验证。

## 基础安装

建议先根据机器的 CPU/CUDA 环境安装兼容的 PyTorch 与 TorchAudio，然后安装本库：

~~~bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
~~~

运行时依赖范围：

- torch >=2.0,<2.9
- torchaudio >=2.0,<2.9
- numpy >=1.26
- soundfile >=0.12
- pydantic >=2.5
- PyYAML >=6.0
- safetensors >=0.4

Torch 与 TorchAudio 必须来自兼容版本并使用同一 CPU/CUDA 渠道。

## 可选依赖

Hugging Face 音频模型：

~~~bash
python -m pip install -e ".[hf]"
~~~

hf extra 支持 transformers >=4.38,<6；CI 固定验证 4.38.2 与 5.17.0。
基础安装不会自动安装 transformers。

测试与开发：

~~~bash
python -m pip install -e ".[test,dev]"
~~~

完整开发环境：

~~~bash
python -m pip install -e ".[test,dev,hf]"
~~~

## 验证安装

~~~bash
python -c "import ser_lib; print(ser_lib.__version__)"
ser --version
ser components list --json
python -m pip check
~~~

预期版本为 1.0.0。若 ser 命令不存在，先确认虚拟环境已经激活；也可运行：

~~~bash
python -m ser_lib.cli --version
~~~

## GPU

库本身不固定 CUDA wheel 来源。请先按 PyTorch 官方渠道安装与你驱动匹配的 torch /
torchaudio，再安装 ser-lib。训练配置中的 trainer.device 可设为 cpu 或 cuda；
AMP 当前用于 CUDA 训练。

## 源码开发检查

~~~bash
python -m pytest -q
python -m ruff check .
python -m mypy ser_lib
python -m build
python scripts/smoke_train_epoch.py --device cpu
~~~

发布基线 CI #581 已在全部支持的 Python/OS 组合通过上述自动化门禁。
