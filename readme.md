# Speech Emotion Recognition

[![CI](https://github.com/77malong/Speech-Emotion-Recognition/actions/workflows/ci.yml/badge.svg)](https://github.com/77malong/Speech-Emotion-Recognition/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10--3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Speech Emotion Recognition（SER）核心 Python SDK。项目覆盖外部音频数据导入、标准
manifest、特征表示、模型、训练、评估、安全模型产物和离线/流式推理；不包含 Web、
Desktop、本地 HTTP 服务或账户系统。

> 当前稳定版：**v1.0.0**。仓库不附带语料和预训练权重。

## 1.0 能力

| 领域 | 能力 |
|---|---|
| 数据 | DatasetManifest + JSONL、9 类 importer、音频属性检查、数据指纹 |
| 表示 | waveform、spectrogram、Mel/Log-Mel、MFCC、组合表示、transform、缓存 |
| 模型 | CNN、GRU/BiGRU、轻量 Transformer、可选 Hugging Face 音频模型 |
| 训练 | CPU/单 GPU、AMP、梯度累积/裁剪、scheduler、early stopping、断点续训 |
| 目标 | cross entropy、focal loss、class weights、WeightedRandomSampler |
| 评估 | loss、WAR/accuracy、UAR、macro/weighted F1、MCC、kappa、混淆矩阵 |
| Artifact | safetensors、模型卡、processor 配置、SHA-256、离线恢复 |
| 推理 | 单文件、目录、manifest 批量推理、纯 PCM streaming |
| CLI | components、dataset、train、evaluate、predict、artifact |
| 工程 | Python 3.10–3.12、Linux/Windows/macOS CI、Ruff、mypy、coverage、wheel smoke |

发布基线 495f8f5 的 CI #581 全绿：普通矩阵 518 passed / 3 skipped，质量任务
528 passed / 1 skipped，并验证 Transformers 4.38.2 与 5.17.0。

## 安装

建议先按你的 CPU/CUDA 环境安装匹配的 PyTorch 与 TorchAudio，再安装本库：

~~~bash
git clone https://github.com/77malong/Speech-Emotion-Recognition.git
cd Speech-Emotion-Recognition
python -m pip install --upgrade pip
python -m pip install -e .
~~~

需要 Hugging Face 音频模型：

~~~bash
python -m pip install -e ".[hf]"
~~~

开发环境：

~~~bash
python -m pip install -e ".[test,dev,hf]"
~~~

验证：

~~~bash
python -c "import ser_lib; print(ser_lib.__version__)"
ser --version
ser components list --json
~~~

详细环境说明见 [安装文档](docs/INSTALLATION.md)。

## 最短工作流

### 1. 导入并校验数据

~~~bash
ser dataset scan --importer folder --source path/to/audio --json
ser dataset import --importer folder --source path/to/audio --destination data/standard
ser dataset validate data/standard/dataset.yaml --check-files --json
ser dataset stats data/standard/dataset.yaml --probe-audio --json
~~~

标准数据由 dataset.yaml 和一个或多个 JSONL split 组成。路径、标签和 split 契约见
[标准数据格式](docs/DATA_FORMAT.md)。

### 2. 训练

~~~bash
ser train configs/cnn_logmel.yaml --split train --batch-size 16 --json
~~~

没有显式 checkpoint_dir 时使用 output_dir/checkpoints。fresh run 会建立新的
metrics/history；使用 --resume 才延续既有训练历史。

无需外部数据的训练冒烟：

~~~bash
python scripts/smoke_train_epoch.py --device cpu
~~~

### 3. 从 checkpoint 导出安全 artifact

~~~bash
ser artifact export   --config configs/cnn_logmel.yaml   --checkpoint runs/cnn-logmel/checkpoints/best.pt   --destination artifacts/model   --json

ser artifact verify artifacts/model --json
~~~

checkpoint 只用于可信本地续训；模型分发和推理使用 safetensors artifact。
导出时会核对训练 lineage、标签语义、manifest 身份和预处理契约。

### 4. 评估与推理

~~~bash
ser evaluate artifacts/model   --manifest data/standard/dataset.yaml   --split test   --output runs/evaluation   --json

ser predict artifacts/model path/to/audio.wav   --output runs/predictions.jsonl   --json
~~~

Python API 示例见 [examples](examples/README.md)。

## 数据与模型边界

数据管线不会根据 CNN/RNN/Transformer 类型分叉：

~~~text
外部数据
  -> Importer / DatasetManifest
  -> AudioLoader
  -> Representation + Transform
  -> SERDataset
  -> SERCollator / SERBatch
  -> ModelSpec compatibility
  -> Train / Evaluate / Inference
~~~

Representation 用 TensorSpec 声明输出；模型用 ModelSpec 声明输入需求。增加表示通常
不需要新增 Dataset，增加模型也不应把模型判断写进数据层。

## 1.0 兼容性

- 文档中列出的公开 Python API、CLI 与 artifact 契约是 1.x 兼容面。
- 未列入公开导出或标记为内部实现的模块不属于稳定 API。
- 配置、manifest、artifact 和 run records 使用严格当前结构；未知字段直接拒绝。
- checkpoint 含 Torch pickle，只加载自己生成且来源可信的文件；不要把 checkpoint
  当作公开模型包。
- artifact 固定使用 safetensors，并在加载前验证结构、路径和哈希。
- Hugging Face adapter 默认本地加载并禁用远程自定义代码。

## 当前限制

- tutorials/00–07 仍是教学提纲，不作为可执行验收。
- 核心训练目标是单机 CPU/单 GPU SER；未声明分布式训练、Web 服务或设备采集能力。
- 仓库不提供数据集下载，也不重新分发第三方模型或语料。
- 真实数据工程验收不等于论文效果、生产 SLA 或泛化能力承诺。

## 文档

从 [文档索引](docs/README.md) 开始。常用入口：

- [安装](docs/INSTALLATION.md)
- [数据格式](docs/DATA_FORMAT.md)
- [训练与 CLI](docs/TRAINING_AND_CLI.md)
- [公共 API](docs/API_REFERENCE.md)
- [模型扩展](docs/MODEL_DEVELOPMENT.md)
- [Artifact 与安全](docs/ARTIFACTS_AND_SECURITY.md)
- [教程状态](docs/TUTORIAL_STATUS.md)
- [变更记录](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)

docs/development 下保存 1.0 前的架构计划、阶段记录和严格审查证据；这些文件用于追溯，
不是当前 API 说明。

## 许可证

项目代码使用 [MIT License](LICENSE)。第三方依赖和数据集许可见
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。
