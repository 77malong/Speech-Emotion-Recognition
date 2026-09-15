# main 分支对外接口使用手册

> 源码基线：`origin/main`，提交 `8fdfdb6`（SER-lib 1.0.0）；整理日期：2026-09-15。
> 本文面向调用 SDK、编写训练程序、集成推理服务和使用命令行的开发者。路径示例需替换为实际数据、配置与模型路径。

## 1. 接口范围与阅读方法

本项目提供 Python 库和 `ser` CLI，没有内置 HTTP/REST、WebSocket 服务或麦克风采集接口。若要部署网络服务，需要在应用层封装这里的 SDK。本文以 main 源码为准，不把历史开发文档中的设想当成已实现接口。

本文后半部分逐项列出源码各模块 `__all__` 声明的导出（包括扩展子模块），为重复导出标注同一实现，展开类的字段、公开方法、构造函数、类型、默认值、返回类型、说明和显式错误条件。根包通过惰性加载提供便利入口。未公开导出的内部函数不属于稳定接口。第三方基类的通用方法（例如 PyTorch `to`、`eval`，Pydantic `model_validate`）不在此重复完整枚举。

### 接口导航

| 入口 | 具体用途 | 首选调用 |
|---|---|---|
| `ser_lib.config` | 配置解析、参数校验、预设、路径解析 | `load_experiment_config`、`build_experiment_config` |
| `ser_lib.data` | 导入外部数据、解析清单、音频解码、特征处理、批处理、统计与缓存 | `DatasetManifest`、`SERDataset`、`build_components` |
| `ser_lib.models` | CNN/GRU/Transformer，外部模型适配，模型注册与输入契约 | `model_registry`、`SERModel`、`TorchModelAdapter` |
| `ser_lib.engine` | 训练、评估、续训、指标、记录查询与兼容性预检 | `train_experiment`、`evaluate_artifact`、`Trainer` |
| `ser_lib.artifacts` | 安全模型导出、校验、加载、目录扫描 | `export_model_artifact`、`load_model_artifact` |
| `ser_lib.inference` | 单文件、批量、PCM 流式情绪识别 | `EmotionPredictor`、`BatchEmotionPredictor`、`StreamingEmotionRecognizer` |
| `ser_lib.foundation` | 公共异常、诊断、日志、进度事件、协作取消 | `SERError`、`EventContext`、`CancellationToken` |
| `ser_lib.runtime` | 当前运行环境与设备能力快照 | `get_runtime_capabilities` |
| `ser` | 无需编写 Python 的数据、训练、推理工作流 | 见第 8 节 |

### 参数与结果约定

- Python 要求 `>=3.10,<3.13`。在仓库根目录执行 `python -m pip install -e .`；HF 功能使用 `python -m pip install -e ".[hf]"`。Torch/TorchAudio 使用项目声明的配套版本。
- 签名中 `*` 后的参数必须写参数名；没有默认值的参数必填。`None` 的意义由接口决定，并不等于自动选择所有资源。
- `Path | str` 接收路径对象或字符串；`AudioRecord.audio_path` 则要求 `Path`。配置文件加载器会相对配置文件目录解析路径；直接在 Python 创建配置时，应自行使用明确路径。
- 配置使用严格 schema，拼错或多余字段会校验失败。`Field(..., ge=..., le=...)` 表示必填和边界，`default_factory` 表示每次创建独立默认对象；详见字段表。
- Pydantic 配置可用 `model_validate(dict)` 创建，`model_dump(mode="json")` 转成 JSON 兼容结构。提供 `to_dict()` 的结果对象可直接转字典；普通 dataclass（例如 `PredictionResult`）使用 `dataclasses.asdict()`。
- 标签 id 从 0 连续编号。训练/评估会核对标签语义，不能只保证类别数相同。概率列表的下标就是标签 id；概率和置信度为 0–1 数值。

## 2. 从数据到训练

### 2.1 数据导入与检查

```python
from ser_lib.data import default_registry, DatasetManifest, summarize_manifest

print(default_registry.names("importer"))
importer = default_registry.create("importer", "folder")
preview = importer.scan("data/raw", {})
print(preview.summary())
# 检查 preview 后再转换；不同数据集的参数见对应 ImportConfig 字段。
manifest = importer.convert("data/raw", "data/standard", {})
print(manifest.stats())
manifest = DatasetManifest.load("data/standard/dataset.yaml")
records = manifest.resolved_records("train")
summary = summarize_manifest("data/standard/dataset.yaml")
```

`scan(source, params)` 只扫描和给出预览，不生成标准数据；`convert(source, destination, params)` 写标准 manifest 并返回 `DatasetManifest`。内置 importer 的准确名字可从 registry 查询；各格式的标签映射、划分和源路径要求见本文对应配置字段及 [数据格式说明](DATA_FORMAT.md)。`get_records(split=None)` 返回原始全部记录；需要解码音频时使用 `resolved_records()`，以免相对路径被错误地当成工作目录路径。

`summarize_manifest` 用于轻量统计；`profile_manifest_audio` 进一步探测音频信息，耗时随文件量增加，可通过 `fail_fast` 控制遇到损坏音频后是否终止。`fingerprint_manifest` 返回数据清单指纹，用于训练 lineage、恢复与导出的一致性核对；它不是对每个音频文件内容的完整哈希校验。

### 2.2 高层训练

```python
from ser_lib.config import load_experiment_config
from ser_lib.engine import train_experiment

config = load_experiment_config("configs/cnn_logmel.yaml")
result = train_experiment(config, split="train", batch_size=16, workers=0)
print(result.to_dict())
print(result.last_checkpoint, result.best_checkpoint)
# 续训：使用原训练配置和可信 checkpoint
# result = train_experiment(config, resume=result.last_checkpoint)
```

运行前先修改配置的 manifest、类别数、标签和输出目录。`config` 也可以直接传 YAML 文件路径。`split="train"` 选择训练划分，`batch_size=16` 控制每批样本数，`workers=0` 表示当前进程加载，`resume=None` 表示新训练。Windows 自定义多进程脚本应在 `if __name__ == "__main__":` 内启动。

返回 `TrainingExperimentResult`：`training` 是本次训练段的 `TrainingResult`，`run` 是完整训练资源记录，`run_record`、`metrics_log`、`history_path` 指向落盘记录，`last_checkpoint`/`best_checkpoint` 在没有相应产物时可为空。新训练会重建对应日志；续训保留并合并历史。请为不同实验使用不同 `output_dir`。`TrainingResult.epochs` 只描述本次 fit 段，跨续训历史应读取 `load_training_history()`。

### 2.3 自定义训练循环与预检

`build_experiment_components(config, train=True)` 构建模型、音频 loader、pipeline 和 collator，并先检查特征规格、采样率、类别数等兼容性。`train=False` 用于推理/验证的数据链。`validate_experiment` 用于实验预检；`inspect_compatibility` 返回诊断报告，`validate_compatibility` 在不兼容时抛错。

```python
from torch.utils.data import DataLoader
from ser_lib.data import DatasetManifest, SERDataset
from ser_lib.engine import Trainer, build_experiment_components

components = build_experiment_components(config, train=True)
manifest = DatasetManifest.load(config.data.manifest)
dataset = SERDataset(manifest.resolved_records("train"),
                     components.audio_loader, components.pipeline)
batches = DataLoader(dataset, batch_size=16, shuffle=True,
                     collate_fn=components.collator)
trainer = Trainer.from_experiment(components.model, config)
training = trainer.fit(lambda: batches)
```

传入可重新迭代的批次工厂，使每个 epoch 都能获取数据。低层 Trainer 便于接入自定义回调、取消、优化器与验证循环；如果需要高层工作流的完整 run/history 落盘管理，优先使用 `train_experiment`。

## 3. 导出、验证与加载模型

```python
from ser_lib.artifacts import (
    export_model_artifact, inspect_model_artifact,
    verify_model_artifact, load_model_artifact,
)

# model 必须是已训练的 SERModel；名称和参数须与实例/注册表一致。
# target = export_model_artifact(
#     "artifacts/demo", model, model_name=config.model.type,
#     data_config=config.data, labels={0: "angry", 1: "happy"},
# )
info = inspect_model_artifact("artifacts/demo")
verified = verify_model_artifact("artifacts/demo")
loaded = load_model_artifact("artifacts/demo", map_location="cpu")
```

导出所需 `directory` 是不存在的目标目录，`model` 是模型实例，`model_name` 是注册 id，`data_config` 是训练一致的预处理配置，`labels` 是完整标签名映射。可选 `model_params` 必须与实际模型配置一致；`metrics`、`metadata`、`model_card` 提供指标、来源信息和模型说明。返回导出目录 `Path`。先写临时目录，成功后发布；已存在目标会拒绝覆盖。

`inspect_model_artifact` 返回 manifest 结构，不代表权重内容已完整验证；`verify_model_artifact` 完整校验 SHA-256 后返回 manifest；`load_model_artifact` 校验后重建模型与预处理，返回 `LoadedArtifact`（model、manifest、audio_loader、pipeline、collator 等字段见后文）。分发权重固定为 `weights.safetensors`。checkpoint 用于可信本地训练恢复；不要把不可信 `.pt` 当作安全分发模型。CLI 可把带完整训练来源信息的可信 checkpoint 导出成 artifact。

## 4. 单文件与批量推理

```python
from dataclasses import asdict
from ser_lib.inference import EmotionPredictor, BatchEmotionPredictor

predictor = EmotionPredictor.from_loaded_artifact(
    loaded, device="cpu", window_aggregation="mean_logits")
prediction = predictor.predict_file("audio/example.wav", uid="sample-001")
print(asdict(prediction))
batch = BatchEmotionPredictor(predictor)
results = batch.predict_directory("audio", batch_size=16, fail_fast=False)
print(results.to_dict())
```

`predict_file(path, uid=None)` 解码单个文件，省略 uid 使用文件名 stem。`predict_record(record)` 支持记录的片段起止范围，并保留 uid；路径必须已解析。`predict_audio(audio, uid="stream")` 接收内存 `AudioData`。`predict_records(records)` 一次 forward 处理多条记录并聚合各自窗口，空列表返回空列表。

返回 `PredictionResult`：

| 字段 | 含义 |
|---|---|
| `uid: str` | 对应输入记录的标识 |
| `label_id: int` | 概率最大类别的下标 |
| `emotion: str` | labels 映射的情绪名称；缺少映射时使用 id 字符串 |
| `confidence: float` | 预测类别对应概率 |
| `probabilities: list[float]` | 每个类别的 softmax 概率 |

多窗口必须指定 `window_aggregation`：`mean_logits` 先平均 logits 再 softmax；`mean_probabilities` 平均各窗口概率；`max_confidence` 选取最自信窗口的整组概率。未指定且实际产生多个窗口时抛错。NaN/Inf 模型输出也会拒绝生成预测。

批量来源接口为 `predict_files`、`predict_directory`、`predict_manifest`、`predict_records`。目录可递归扫描；manifest 支持选择 split；完整参数见后文。核心批量参数包括 `batch_size>=1`、`fail_fast=True`、`total=None`、`result_sink=None`、`retain_results=True`、事件与取消参数。`fail_fast=False` 把坏样本记录为 `PredictionFailure` 后继续；返回总计、成功计数、失败计数及保留的明细。

大数据量采用 sink 避免结果全部常驻内存：

```python
from ser_lib.inference import JsonlBatchPredictionSink

with JsonlBatchPredictionSink("outputs/predictions.jsonl") as sink:
    summary = batch.predict_records(
        records, batch_size=16, fail_fast=False,
        result_sink=sink, retain_results=False)
print(summary.total, summary.succeeded, summary.failed)
```

此时明细在 sink，返回对象仍有真实计数。未知长度迭代器不会被预先全部转成列表；进度 total 可为空。`write_batch_predictions` 用于将已保留的批量结果写出，不能用它从只剩计数的对象恢复明细。sink 使用 `with` 负责关闭文件。

## 5. PCM 流式推理

```python
from ser_lib.inference import StreamingConfig, StreamingEmotionRecognizer

stream = StreamingEmotionRecognizer(predictor, StreamingConfig(
    input_sample_rate=16000, window_ms=2000, hop_ms=500))
# pcm_chunk 是调用方采集/解码的浮点 PCM，形状 [T] 或 [C,T]。
# for item in stream.push_pcm(pcm_chunk):
#     print(item.sequence, item.start_ms, item.end_ms, item.prediction)
tail = stream.flush(pad_final=True)
stream.close()
```

每次 `push_pcm` 返回零个或多个 `StreamingPrediction`；不足一个窗口时为空列表。输入必须有限浮点数，二维输入按通道平均。`input_sample_rate` 是输入真实采样率，核心负责重采样到模型采样率。`window_ms` 决定识别窗口，`hop_ms` 决定更新间隔且不得大于窗口；`max_chunk_ms=10000` 限制单次提交长度。

`silence_rms_threshold=0.0` 控制静音判定，`suppress_silence=True` 时静音窗口可不执行模型预测，结果的 `prediction=None`；`smoothing_alpha=1.0` 不混入历史概率，小于 1 时做平滑。结果包含序号、开始/结束毫秒、静音标记、RMS 和可空预测。`latency` 给出窗口、步长、重采样前瞻及首个结果的算法延迟，不是实际机器耗时保证。

`flush(pad_final=False)` 默认不补齐尾部，`True` 时补零处理剩余音频；flush 后再次输入需要 reset。`reset()` 清空会话状态，`close()` 关闭会话并丢弃待交付结果。预测失败可能已经接收 PCM，应以空 chunk 重试而不能重复送原 chunk；flush 失败应重试 flush。流式不支持 `audio.normalize_peak=True`，因为全局峰值需要完整音频。

## 6. 评估与结果查询

```python
from ser_lib.engine import evaluate_artifact

result = evaluate_artifact(
    "artifacts/demo", manifest_path="data/standard/dataset.yaml",
    split="test", batch_size=16, workers=0, device="cpu",
    output="runs/eval-demo")
print(result.to_dict())
```

`artifact` 和 `output` 必填；省略 `manifest_path` 使用 artifact 预处理记录的 manifest 路径（换机器时通常应显式覆盖）。输出为 `EvaluationExperimentResult`，含 `evaluation` 指标对象、`run` 来源记录、`metrics_path`、`run_record` 和可空的 `predictions_path`。`retain_predictions=True` 默认保留预测；大规模评估可传 `JsonlPredictionSink` 并设为 False。

主要指标：accuracy 为正确率；macro_f1 为各类 F1 平均；UAR/balanced_accuracy 为各类召回均值；WAR 为加权召回；weighted_precision/recall/f1 按类别支持数加权；confusion_matrix 是混淆矩阵；per_class 含各类 precision、recall、f1、support；另有 loss、MCC 和 Cohen kappa。不要把滑窗评估当作文件级指标：高层返回 `metric_unit` 明确区分 `window` 与 `sample`。

低层 `evaluate(model, batches, ...)` 接收已经构建的批次，返回 `EvaluationResult`，适合自定义程序；`write_evaluation_report` 写报告。评估预测记录使用 `target`、`predicted` 字段，与无标签推理的 `PredictionResult` 不同。

```python
from itertools import islice
from ser_lib.engine import (
    load_training_record, load_training_history, scan_checkpoints,
    load_evaluation_record, inspect_evaluation_report,
    inspect_evaluation_prediction_file, iter_evaluation_predictions,
)

run = load_training_record("runs/demo")
history = load_training_history("runs/demo")
catalog = scan_checkpoints("runs/demo/checkpoints")
evaluation_run = load_evaluation_record("runs/eval-demo")
report = inspect_evaluation_report("runs/eval-demo")
file_info = inspect_evaluation_prediction_file(evaluation_run)
first_100 = list(islice(iter_evaluation_predictions("runs/eval-demo"), 100))
```

扫描 checkpoint 只检查目录与文件信息，不隐式反序列化训练状态。训练记录、历史、checkpoint、评估报告是独立资源。预测 JSONL 使用迭代器流式读取，应用可以用 `islice` 取页；库没有 Web 分页 DTO，也不会为总数预扫整份预测文件。

## 7. 扩展与可观测性

数据链是 `AudioRecord → AudioLoader → AudioData → SamplePipeline → SERSample → SERCollator → SERBatch → SERModel → ModelOutput`。音频标准形状为 `[C,T]`、float32。TensorSpec 的单样本布局包括 `T`、`FT`、`TD`、`D`、`CFT`；批处理在前面增加 B 维，按规格维护长度、padding 和窗口映射。模型输出 logits，概率转换由预测/评估执行。

使用 `default_registry` 查询/注册 importer、representation、waveform_transform、feature_transform；使用 `model_registry` 查询/注册模型。descriptor 提供配置 schema 和组件说明，适合应用动态生成配置界面。注册名称、schema、输入输出规格必须一致；自定义 `SERModel` 应实现模型契约与可重建配置。`TorchModelAdapter` 用于包装既有 torch 模型并映射输入输出，`HFAudioClassifier` 对接 HF 模型与 processor；完整构造和恢复要求见后文及 [模型开发说明](MODEL_DEVELOPMENT.md)。

有 `event_callback` 的接口同步发送生命周期、进度或指标事件；`event_context` 关联 run/split 等上下文，`cancellation` 接收取消检查。取消是协作式，发生在实现检查点，不保证立刻中断正在进行的算子。回调和 sink 的异常不要当作普通坏音频吞掉。通过 `SERError` 的 code 和上下文字段区分领域失败；配置也可能抛 Pydantic `ValidationError` 或 `ValueError`。附录列出的显式抛错不是所有传递异常的穷尽清单。

`get_runtime_capabilities()` 返回一次性的 Python/PyTorch/设备能力快照，可 `.to_dict()`，适合任务启动前选择设备；它不提供持续的 GPU 利用率监控。

## 8. 全部 CLI 命令

安装后执行 `ser --help`，也可 `python -m ser_lib.cli --help`。下表中尖括号表示需要替换的路径或值；`--json` 输出机器可读 JSON，省略时输出可读键值/列表。`--help` 可在各层使用，`ser --version` 输出库版本。

| 命令 | 输入参数、默认值与作用 | 输出 |
|---|---|---|
| `ser components list` | `--kind` 为 importer/representation/waveform_transform/feature_transform/model/all，默认 all；`--json` | 按 kind 分组的 descriptor |
| `ser dataset scan` | 必填 `--importer <id> --source <路径>`；`--params <JSON对象>` 与 `--params-file <JSON/YAML>` 互斥；`--json` | 导入预览 summary，不写入标准数据 |
| `ser dataset import` | scan 同样参数，额外必填 `--destination <目录>` | manifest 路径、dataset_id、stats，并落盘标准数据 |
| `ser dataset validate <manifest>` | `--split` 默认不筛选；`--check-files` 检查音频存在性；`--json` | valid、selected_count、missing_files、stats；不是完整音频解码测试 |
| `ser dataset stats <manifest>` | `--split`；`--probe-audio` 探测音频；`--fail-fast` 探测失败即停；`--json` | 统计；探测时额外 audio_profile |
| `ser train <config>` | `--split train`、`--batch-size 16`、`--workers 0`、`--resume <checkpoint>` 可选；`--json` | 训练结果及 run/history/checkpoint 路径 |
| `ser evaluate <artifact>` | `--manifest <路径>` 可选；`--split test`、`--batch-size 16`、`--workers 0`、`--device cpu`；必填 `--output <目录>`；`--json` | 评估指标、记录及报告路径 |
| `ser predict <artifact> <source>` | source 为音频、目录或 dataset.yaml；`--split`、`--batch-size 16`、`--device cpu`；必填 `--output <文件>`；`--keep-going` 继续坏样本；`--no-recursive` 禁止递归；`--window-aggregation` 可选 mean_logits/mean_probabilities/max_confidence；`--json` | output、total、succeeded、failed；明细写输出文件 |
| `ser artifact inspect <artifact>` | `--json` | artifact manifest 结构 |
| `ser artifact verify <artifact>` | `--json` | 完整校验通过后的 manifest |
| `ser artifact export` | 必填 `--config <YAML> --checkpoint <可信文件> --destination <新目录>`；`--model-card <JSON/YAML对象>` 可选；`--json` | artifact 路径、model、labels、source_run_id |

```shell
ser components list --kind importer --json
ser dataset scan --importer folder --source data/raw --json
ser dataset import --importer folder --source data/raw --destination data/standard --json
ser dataset validate data/standard/dataset.yaml --check-files --json
ser train configs/cnn_logmel.yaml --batch-size 16 --workers 0 --json
ser artifact export --config configs/cnn_logmel.yaml --checkpoint runs/demo/checkpoints/last.pt --destination artifacts/demo --json
ser artifact verify artifacts/demo --json
ser predict artifacts/demo audio/example.wav --output outputs/predictions.jsonl --window-aggregation mean_logits --json
ser evaluate artifacts/demo --manifest data/standard/dataset.yaml --output runs/eval-demo --json
```

上面训练输出目录由配置决定，导出示例 checkpoint 路径需换成训练实际返回的 `last_checkpoint` 或 `best_checkpoint`。退出码：0 正常完成；2 为 argparse 参数用法错误；3 配置错误；4 领域/数据错误或数据检查未通过；5 捕获的 ValueError/OSError。未被 main 捕获的异常仍可能输出 traceback。`predict --keep-going` 允许部分失败但 CLI 仍可返回 0，因此自动化必须检查 `failed` 计数。

## 9. 逐项接口字典

以下内容从上述 main 提交的语法树提取，不导入或执行模型。每个实现只展开一次，重复导出使用链接；配置继承字段以基类为准。函数签名直接展示每个输入的类型与默认值，箭头后为输出类型；类字段表同时描述构造输入和结果成员。未注解的返回值明确标为未声明，不推测类型。`self`/`cls` 由 Python 自动传入。属性只读取，不按函数传参；`__call__` 表示实例可以直接调用。

<!-- GENERATED API DICTIONARY -->

本字典覆盖 **94 个声明公开导出的模块、645 个导出路径、293 个去重实现**（包括 CLI main）。

### 9.1 全部导出路径索引

#### `ser_lib`

- [`SERDataset`](#ser_lib-data-dataset-serdataset)
- [`SERBatch`](#ser_lib-data-types-serbatch)
- [`SERModel`](#ser_lib-models-base-sermodel)
- [`Trainer`](#ser_lib-engine-training-trainer-trainer)
- [`TrainingResult`](#ser_lib-engine-training-results-trainingresult)
- [`evaluate`](#ser_lib-engine-evaluator-evaluate)
- [`train_experiment`](#ser_lib-engine-experiment-train_experiment)
- [`evaluate_artifact`](#ser_lib-engine-experiment-evaluate_artifact)
- [`EmotionPredictor`](#ser_lib-inference-offline-emotionpredictor)
- [`PredictionResult`](#ser_lib-inference-offline-predictionresult)
- [`export_model_artifact`](#ser_lib-artifacts-exporter-export_model_artifact)
- [`load_model_artifact`](#ser_lib-artifacts-loader-load_model_artifact)

#### `ser_lib._version`

- [`__version__`](#ser_lib-_version-__version__)

#### `ser_lib.artifacts`

- [`ModelCard`](#ser_lib-artifacts-manifest-modelcard)
- [`ModelArtifactManifest`](#ser_lib-artifacts-manifest-modelartifactmanifest)
- [`LoadedArtifact`](#ser_lib-artifacts-loader-loadedartifact)
- [`ArtifactEntry`](#ser_lib-artifacts-catalog-artifactentry)
- [`ArtifactScanFailure`](#ser_lib-artifacts-catalog-artifactscanfailure)
- [`ArtifactCatalog`](#ser_lib-artifacts-catalog-artifactcatalog)
- [`scan_model_artifacts`](#ser_lib-artifacts-catalog-scan_model_artifacts)
- [`export_model_artifact`](#ser_lib-artifacts-exporter-export_model_artifact)
- [`inspect_model_artifact`](#ser_lib-artifacts-loader-inspect_model_artifact)
- [`verify_model_artifact`](#ser_lib-artifacts-loader-verify_model_artifact)
- [`load_model_artifact`](#ser_lib-artifacts-loader-load_model_artifact)

#### `ser_lib.artifacts._compatibility`

- [`validate_artifact_compatibility`](#ser_lib-artifacts-_compatibility-validate_artifact_compatibility)

#### `ser_lib.artifacts.catalog`

- [`ArtifactEntry`](#ser_lib-artifacts-catalog-artifactentry)
- [`ArtifactScanFailure`](#ser_lib-artifacts-catalog-artifactscanfailure)
- [`ArtifactCatalog`](#ser_lib-artifacts-catalog-artifactcatalog)
- [`scan_model_artifacts`](#ser_lib-artifacts-catalog-scan_model_artifacts)

#### `ser_lib.artifacts.exporter`

- [`export_model_artifact`](#ser_lib-artifacts-exporter-export_model_artifact)

#### `ser_lib.artifacts.loader`

- [`LoadedArtifact`](#ser_lib-artifacts-loader-loadedartifact)
- [`inspect_model_artifact`](#ser_lib-artifacts-loader-inspect_model_artifact)
- [`verify_model_artifact`](#ser_lib-artifacts-loader-verify_model_artifact)
- [`load_model_artifact`](#ser_lib-artifacts-loader-load_model_artifact)

#### `ser_lib.artifacts.manifest`

- [`ModelCard`](#ser_lib-artifacts-manifest-modelcard)
- [`ModelArtifactManifest`](#ser_lib-artifacts-manifest-modelartifactmanifest)

#### `ser_lib.cli`

- [`main`](#ser_lib-cli-main-main)

#### `ser_lib.cli.main`

- [`main`](#ser_lib-cli-main-main)

#### `ser_lib.cli.workflows`

- [`train_experiment`](#ser_lib-cli-workflows-train_experiment)
- [`evaluate_artifact`](#ser_lib-cli-workflows-evaluate_artifact)
- [`predict_artifact`](#ser_lib-cli-workflows-predict_artifact)
- [`export_checkpoint_artifact`](#ser_lib-cli-workflows-export_checkpoint_artifact)
- [`inspect_artifact`](#ser_lib-cli-workflows-inspect_artifact)

#### `ser_lib.config`

- [`StrictConfig`](#ser_lib-config-base-strictconfig)
- [`resolve_config_path`](#ser_lib-config-loader-resolve_config_path)
- [`load_yaml_mapping`](#ser_lib-config-loader-load_yaml_mapping)
- [`AudioBackend`](#ser_lib-config-data-audiobackend)
- [`BatchingType`](#ser_lib-config-data-batchingtype)
- [`ComponentConfig`](#ser_lib-config-data-componentconfig)
- [`AudioConfig`](#ser_lib-config-data-audioconfig)
- [`CacheConfig`](#ser_lib-config-data-cacheconfig)
- [`FixedBatching`](#ser_lib-config-data-fixedbatching)
- [`SlidingBatching`](#ser_lib-config-data-slidingbatching)
- [`BatchingConfig`](#ser_lib-config-data-batchingconfig)
- [`DataConfig`](#ser_lib-config-data-dataconfig)
- [`load_data_config`](#ser_lib-config-data-load_data_config)
- [`ModelConfig`](#ser_lib-config-model-modelconfig)
- [`CNNBaselineConfig`](#ser_lib-config-model-cnnbaselineconfig)
- [`GRUBaselineConfig`](#ser_lib-config-model-grubaselineconfig)
- [`TransformerBaselineConfig`](#ser_lib-config-model-transformerbaselineconfig)
- [`HFProcessorConfig`](#ser_lib-config-model-hfprocessorconfig)
- [`HFAudioClassifierConfig`](#ser_lib-config-model-hfaudioclassifierconfig)
- [`TorchDTypeName`](#ser_lib-config-model-torchdtypename)
- [`TorchLayoutName`](#ser_lib-config-model-torchlayoutname)
- [`TorchTensorSpecConfig`](#ser_lib-config-model-torchtensorspecconfig)
- [`TorchOutputMappingConfig`](#ser_lib-config-model-torchoutputmappingconfig)
- [`TorchModelAdapterConfig`](#ser_lib-config-model-torchmodeladapterconfig)
- [`ObservabilityConfig`](#ser_lib-config-training-observabilityconfig)
- [`TrainerConfig`](#ser_lib-config-training-trainerconfig)
- [`LossConfig`](#ser_lib-config-training-lossconfig)
- [`SamplingConfig`](#ser_lib-config-training-samplingconfig)
- [`AdamWConfig`](#ser_lib-config-optimizer-adamwconfig)
- [`AdamConfig`](#ser_lib-config-optimizer-adamconfig)
- [`SGDConfig`](#ser_lib-config-optimizer-sgdconfig)
- [`OptimizerConfig`](#ser_lib-config-optimizer-optimizerconfig)
- [`parse_optimizer_config`](#ser_lib-config-optimizer-parse_optimizer_config)
- [`StepSchedulerConfig`](#ser_lib-config-scheduler-stepschedulerconfig)
- [`CosineSchedulerConfig`](#ser_lib-config-scheduler-cosineschedulerconfig)
- [`SchedulerConfig`](#ser_lib-config-scheduler-schedulerconfig)
- [`parse_scheduler_config`](#ser_lib-config-scheduler-parse_scheduler_config)
- [`ExperimentConfig`](#ser_lib-config-experiment-experimentconfig)
- [`load_experiment_config`](#ser_lib-config-experiment-load_experiment_config)
- [`StreamingConfig`](#ser_lib-config-inference-streamingconfig)
- [`DEFAULT_AUDIO_EXTENSIONS`](#ser_lib-config-importers-default_audio_extensions)
- [`CasiaImportConfig`](#ser_lib-config-importers-casiaimportconfig)
- [`CsvImportConfig`](#ser_lib-config-importers-csvimportconfig)
- [`CsemotionsImportConfig`](#ser_lib-config-importers-csemotionsimportconfig)
- [`CremaDImportConfig`](#ser_lib-config-importers-cremadimportconfig)
- [`EmotionTalkImportConfig`](#ser_lib-config-importers-emotiontalkimportconfig)
- [`EsdImportConfig`](#ser_lib-config-importers-esdimportconfig)
- [`FolderImportConfig`](#ser_lib-config-importers-folderimportconfig)
- [`JsonlImportConfig`](#ser_lib-config-importers-jsonlimportconfig)
- [`RavdessImportConfig`](#ser_lib-config-importers-ravdessimportconfig)
- [`RawWaveformConfig`](#ser_lib-config-representations-rawwaveformconfig)
- [`SpectralConfigBase`](#ser_lib-config-representations-spectralconfigbase)
- [`SpectrogramConfig`](#ser_lib-config-representations-spectrogramconfig)
- [`MelConfig`](#ser_lib-config-representations-melconfig)
- [`LogMelConfig`](#ser_lib-config-representations-logmelconfig)
- [`MFCCConfig`](#ser_lib-config-representations-mfccconfig)
- [`AcousticFeatureName`](#ser_lib-config-representations-acousticfeaturename)
- [`AcousticFeaturesConfig`](#ser_lib-config-representations-acousticfeaturesconfig)
- [`CompositeConfig`](#ser_lib-config-representations-compositeconfig)
- [`NormalizeConfig`](#ser_lib-config-transforms-normalizeconfig)
- [`GaussianNoiseConfig`](#ser_lib-config-transforms-gaussiannoiseconfig)
- [`TimeShiftConfig`](#ser_lib-config-transforms-timeshiftconfig)
- [`VolumeScaleConfig`](#ser_lib-config-transforms-volumescaleconfig)
- [`PitchShiftConfig`](#ser_lib-config-transforms-pitchshiftconfig)
- [`TimeStretchConfig`](#ser_lib-config-transforms-timestretchconfig)
- [`SpecMaskingConfig`](#ser_lib-config-transforms-specmaskingconfig)
- [`list_experiment_preset_ids`](#ser_lib-config-presets-list_experiment_preset_ids)
- [`get_experiment_preset_payload`](#ser_lib-config-presets-get_experiment_preset_payload)
- [`build_experiment_config`](#ser_lib-config-presets-build_experiment_config)

#### `ser_lib.config.base`

- [`StrictConfig`](#ser_lib-config-base-strictconfig)

#### `ser_lib.config.data`

- [`AudioBackend`](#ser_lib-config-data-audiobackend)
- [`BatchingType`](#ser_lib-config-data-batchingtype)
- [`ComponentConfig`](#ser_lib-config-data-componentconfig)
- [`AudioConfig`](#ser_lib-config-data-audioconfig)
- [`CacheConfig`](#ser_lib-config-data-cacheconfig)
- [`FixedBatching`](#ser_lib-config-data-fixedbatching)
- [`SlidingBatching`](#ser_lib-config-data-slidingbatching)
- [`BatchingConfig`](#ser_lib-config-data-batchingconfig)
- [`DataConfig`](#ser_lib-config-data-dataconfig)
- [`load_data_config`](#ser_lib-config-data-load_data_config)

#### `ser_lib.config.experiment`

- [`ExperimentConfig`](#ser_lib-config-experiment-experimentconfig)
- [`load_experiment_config`](#ser_lib-config-experiment-load_experiment_config)

#### `ser_lib.config.importers`

- [`DEFAULT_AUDIO_EXTENSIONS`](#ser_lib-config-importers-default_audio_extensions)
- [`CasiaImportConfig`](#ser_lib-config-importers-casiaimportconfig)
- [`CsvImportConfig`](#ser_lib-config-importers-csvimportconfig)
- [`CsemotionsImportConfig`](#ser_lib-config-importers-csemotionsimportconfig)
- [`CremaDImportConfig`](#ser_lib-config-importers-cremadimportconfig)
- [`EmotionTalkImportConfig`](#ser_lib-config-importers-emotiontalkimportconfig)
- [`EsdImportConfig`](#ser_lib-config-importers-esdimportconfig)
- [`FolderImportConfig`](#ser_lib-config-importers-folderimportconfig)
- [`JsonlImportConfig`](#ser_lib-config-importers-jsonlimportconfig)
- [`RavdessImportConfig`](#ser_lib-config-importers-ravdessimportconfig)

#### `ser_lib.config.inference`

- [`StreamingConfig`](#ser_lib-config-inference-streamingconfig)

#### `ser_lib.config.loader`

- [`resolve_config_path`](#ser_lib-config-loader-resolve_config_path)
- [`load_yaml_mapping`](#ser_lib-config-loader-load_yaml_mapping)

#### `ser_lib.config.model`

- [`ModelConfig`](#ser_lib-config-model-modelconfig)
- [`CNNBaselineConfig`](#ser_lib-config-model-cnnbaselineconfig)
- [`GRUBaselineConfig`](#ser_lib-config-model-grubaselineconfig)
- [`TransformerBaselineConfig`](#ser_lib-config-model-transformerbaselineconfig)
- [`HFProcessorConfig`](#ser_lib-config-model-hfprocessorconfig)
- [`HFAudioClassifierConfig`](#ser_lib-config-model-hfaudioclassifierconfig)
- [`TorchDTypeName`](#ser_lib-config-model-torchdtypename)
- [`TorchLayoutName`](#ser_lib-config-model-torchlayoutname)
- [`TorchTensorSpecConfig`](#ser_lib-config-model-torchtensorspecconfig)
- [`TorchOutputMappingConfig`](#ser_lib-config-model-torchoutputmappingconfig)
- [`TorchModelAdapterConfig`](#ser_lib-config-model-torchmodeladapterconfig)

#### `ser_lib.config.optimizer`

- [`AdamWConfig`](#ser_lib-config-optimizer-adamwconfig)
- [`AdamConfig`](#ser_lib-config-optimizer-adamconfig)
- [`SGDConfig`](#ser_lib-config-optimizer-sgdconfig)
- [`OptimizerConfig`](#ser_lib-config-optimizer-optimizerconfig)
- [`parse_optimizer_config`](#ser_lib-config-optimizer-parse_optimizer_config)

#### `ser_lib.config.presets`

- [`list_experiment_preset_ids`](#ser_lib-config-presets-list_experiment_preset_ids)
- [`get_experiment_preset_payload`](#ser_lib-config-presets-get_experiment_preset_payload)
- [`build_experiment_config`](#ser_lib-config-presets-build_experiment_config)

#### `ser_lib.config.representations`

- [`RawWaveformConfig`](#ser_lib-config-representations-rawwaveformconfig)
- [`SpectralConfigBase`](#ser_lib-config-representations-spectralconfigbase)
- [`SpectrogramConfig`](#ser_lib-config-representations-spectrogramconfig)
- [`MelConfig`](#ser_lib-config-representations-melconfig)
- [`LogMelConfig`](#ser_lib-config-representations-logmelconfig)
- [`MFCCConfig`](#ser_lib-config-representations-mfccconfig)
- [`AcousticFeatureName`](#ser_lib-config-representations-acousticfeaturename)
- [`AcousticFeaturesConfig`](#ser_lib-config-representations-acousticfeaturesconfig)
- [`CompositeConfig`](#ser_lib-config-representations-compositeconfig)

#### `ser_lib.config.scheduler`

- [`StepSchedulerConfig`](#ser_lib-config-scheduler-stepschedulerconfig)
- [`CosineSchedulerConfig`](#ser_lib-config-scheduler-cosineschedulerconfig)
- [`SchedulerConfig`](#ser_lib-config-scheduler-schedulerconfig)
- [`parse_scheduler_config`](#ser_lib-config-scheduler-parse_scheduler_config)

#### `ser_lib.config.training`

- [`ObservabilityConfig`](#ser_lib-config-training-observabilityconfig)
- [`TrainerConfig`](#ser_lib-config-training-trainerconfig)
- [`LossConfig`](#ser_lib-config-training-lossconfig)
- [`SamplingConfig`](#ser_lib-config-training-samplingconfig)

#### `ser_lib.config.transforms`

- [`NormalizeConfig`](#ser_lib-config-transforms-normalizeconfig)
- [`GaussianNoiseConfig`](#ser_lib-config-transforms-gaussiannoiseconfig)
- [`TimeShiftConfig`](#ser_lib-config-transforms-timeshiftconfig)
- [`VolumeScaleConfig`](#ser_lib-config-transforms-volumescaleconfig)
- [`PitchShiftConfig`](#ser_lib-config-transforms-pitchshiftconfig)
- [`TimeStretchConfig`](#ser_lib-config-transforms-timestretchconfig)
- [`SpecMaskingConfig`](#ser_lib-config-transforms-specmaskingconfig)

#### `ser_lib.data`

- [`AudioRecord`](#ser_lib-data-types-audiorecord)
- [`AudioData`](#ser_lib-data-types-audiodata)
- [`TensorSpec`](#ser_lib-data-types-tensorspec)
- [`RepresentationOutput`](#ser_lib-data-types-representationoutput)
- [`SERSample`](#ser_lib-data-types-sersample)
- [`SERBatch`](#ser_lib-data-types-serbatch)
- [`validate_sample_contract`](#ser_lib-data-types-validate_sample_contract)
- [`SERDataError`](#ser_lib-foundation-errors-data-serdataerror)
- [`ManifestError`](#ser_lib-foundation-errors-data-manifesterror)
- [`AudioNotFoundError`](#ser_lib-foundation-errors-data-audionotfounderror)
- [`AudioDecodeError`](#ser_lib-foundation-errors-data-audiodecodeerror)
- [`InvalidAudioSegmentError`](#ser_lib-foundation-errors-data-invalidaudiosegmenterror)
- [`RepresentationError`](#ser_lib-foundation-errors-data-representationerror)
- [`TransformError`](#ser_lib-foundation-errors-data-transformerror)
- [`CollationError`](#ser_lib-foundation-errors-data-collationerror)
- [`CompatibilityError`](#ser_lib-foundation-errors-engine-compatibilityerror)
- [`RegistryError`](#ser_lib-foundation-errors-base-registryerror)
- [`DatasetManifest`](#ser_lib-data-manifest-datasetmanifest)
- [`ManifestMeta`](#ser_lib-data-manifest-manifestmeta)
- [`read_jsonl`](#ser_lib-data-manifest-read_jsonl)
- [`write_jsonl`](#ser_lib-data-manifest-write_jsonl)
- [`AudioLoader`](#ser_lib-data-audio-audioloader)
- [`AudioLoaderConfig`](#ser_lib-data-audio-audioloaderconfig)
- [`FolderImporter`](#ser_lib-data-importers-folder-folderimporter)
- [`CsvImporter`](#ser_lib-data-importers-csv_importer-csvimporter)
- [`JsonlImporter`](#ser_lib-data-importers-jsonl_importer-jsonlimporter)
- [`CasiaImporter`](#ser_lib-data-importers-casia-casiaimporter)
- [`ImportPreview`](#ser_lib-data-importers-base-importpreview)
- [`RavdessImporter`](#ser_lib-data-importers-ravdess-ravdessimporter)
- [`register_importers`](#ser_lib-data-importers-register_importers)
- [`SamplePipeline`](#ser_lib-data-pipeline-samplepipeline)
- [`SERDataset`](#ser_lib-data-dataset-serdataset)
- [`build_pipeline`](#ser_lib-data-pipeline-build_pipeline)
- [`build_components`](#ser_lib-data-pipeline-build_components)
- [`SERCollator`](#ser_lib-data-collate-sercollator)
- [`CollateStrategy`](#ser_lib-data-collate-collatestrategy)
- [`build_collator`](#ser_lib-data-collate-build_collator)
- [`CachedRepresentation`](#ser_lib-data-cache-cachedrepresentation)
- [`Registry`](#ser_lib-data-registry-registry)
- [`default_registry`](#ser_lib-data-registry-default_registry)
- [`ComponentDescriptor`](#ser_lib-data-registry-componentdescriptor)
- [`register_representations`](#ser_lib-data-representations-register_representations)
- [`register_transforms`](#ser_lib-data-transforms-register_transforms)
- [`AudioProbeFailure`](#ser_lib-data-profiling-audioprobefailure)
- [`DurationHistogramBin`](#ser_lib-data-profiling-durationhistogrambin)
- [`DatasetAudioProfile`](#ser_lib-data-profiling-datasetaudioprofile)
- [`DatasetSummary`](#ser_lib-data-profiling-datasetsummary)
- [`DatasetProfile`](#ser_lib-data-profiling-datasetprofile)
- [`profile_manifest_audio`](#ser_lib-data-profiling-profile_manifest_audio)
- [`summarize_manifest`](#ser_lib-data-profiling-summarize_manifest)
- [`profile_dataset`](#ser_lib-data-profiling-profile_dataset)
- [`DatasetFingerprint`](#ser_lib-data-fingerprint-datasetfingerprint)
- [`fingerprint_manifest`](#ser_lib-data-fingerprint-fingerprint_manifest)

#### `ser_lib.data.audio`

- [`AudioBackend`](#ser_lib-config-data-audiobackend)
- [`AudioFileInfo`](#ser_lib-data-audio-audiofileinfo)
- [`AudioLoaderConfig`](#ser_lib-data-audio-audioloaderconfig)
- [`AudioLoader`](#ser_lib-data-audio-audioloader)
- [`probe_audio`](#ser_lib-data-audio-probe_audio)
- [`decode_audio`](#ser_lib-data-audio-decode_audio)

#### `ser_lib.data.fingerprint`

- [`DatasetFingerprint`](#ser_lib-data-fingerprint-datasetfingerprint)
- [`fingerprint_manifest`](#ser_lib-data-fingerprint-fingerprint_manifest)

#### `ser_lib.data.importers`

- [`DatasetImporter`](#ser_lib-data-importers-base-datasetimporter)
- [`ImportPreview`](#ser_lib-data-importers-base-importpreview)
- [`CasiaImporter`](#ser_lib-data-importers-casia-casiaimporter)
- [`CasiaImportConfig`](#ser_lib-config-importers-casiaimportconfig)
- [`CsvImporter`](#ser_lib-data-importers-csv_importer-csvimporter)
- [`CsvImportConfig`](#ser_lib-config-importers-csvimportconfig)
- [`CsemotionsImporter`](#ser_lib-data-importers-csemotions-csemotionsimporter)
- [`CsemotionsImportConfig`](#ser_lib-config-importers-csemotionsimportconfig)
- [`CremaDImporter`](#ser_lib-data-importers-crema_d-cremadimporter)
- [`CremaDImportConfig`](#ser_lib-config-importers-cremadimportconfig)
- [`EsdImporter`](#ser_lib-data-importers-esd-esdimporter)
- [`EsdImportConfig`](#ser_lib-config-importers-esdimportconfig)
- [`EmotionTalkImporter`](#ser_lib-data-importers-emotiontalk-emotiontalkimporter)
- [`EmotionTalkImportConfig`](#ser_lib-config-importers-emotiontalkimportconfig)
- [`FolderImporter`](#ser_lib-data-importers-folder-folderimporter)
- [`FolderImportConfig`](#ser_lib-config-importers-folderimportconfig)
- [`JsonlImporter`](#ser_lib-data-importers-jsonl_importer-jsonlimporter)
- [`JsonlImportConfig`](#ser_lib-config-importers-jsonlimportconfig)
- [`RavdessImporter`](#ser_lib-data-importers-ravdess-ravdessimporter)
- [`RavdessImportConfig`](#ser_lib-config-importers-ravdessimportconfig)
- [`normalize_raw_record`](#ser_lib-data-importers-jsonl_importer-normalize_raw_record)
- [`normalize_raw_records`](#ser_lib-data-importers-jsonl_importer-normalize_raw_records)
- [`register_importers`](#ser_lib-data-importers-register_importers)

#### `ser_lib.data.importers._conversion`

- [`run_manifest_conversion`](#ser_lib-data-importers-_conversion-run_manifest_conversion)
- [`run_single_manifest_conversion`](#ser_lib-data-importers-_conversion-run_single_manifest_conversion)
- [`write_partitioned_manifest`](#ser_lib-data-importers-_conversion-write_partitioned_manifest)

#### `ser_lib.data.importers.base`

- [`DatasetImporter`](#ser_lib-data-importers-base-datasetimporter)
- [`ImportPreview`](#ser_lib-data-importers-base-importpreview)
- [`ImportTask`](#ser_lib-data-importers-base-importtask)
- [`ImportOperation`](#ser_lib-data-importers-base-importoperation)

#### `ser_lib.data.importers.casia`

- [`CasiaImportConfig`](#ser_lib-config-importers-casiaimportconfig)
- [`CasiaImporter`](#ser_lib-data-importers-casia-casiaimporter)
- [`CASIA_EMOTION_MAPPING`](#ser_lib-data-importers-casia-casia_emotion_mapping)
- [`CASIA_EMOTION_ZH`](#ser_lib-data-importers-casia-casia_emotion_zh)

#### `ser_lib.data.importers.crema_d`

- [`CREMA_D_EMOTIONS`](#ser_lib-data-importers-crema_d-crema_d_emotions)
- [`CremaDImportConfig`](#ser_lib-config-importers-cremadimportconfig)
- [`CremaDImporter`](#ser_lib-data-importers-crema_d-cremadimporter)

#### `ser_lib.data.importers.csemotions`

- [`CSEMOTIONS_LABELS`](#ser_lib-data-importers-csemotions-csemotions_labels)
- [`CSEMOTIONS_ZH`](#ser_lib-data-importers-csemotions-csemotions_zh)
- [`CsemotionsImportConfig`](#ser_lib-config-importers-csemotionsimportconfig)
- [`CsemotionsImporter`](#ser_lib-data-importers-csemotions-csemotionsimporter)

#### `ser_lib.data.importers.csv_importer`

- [`CsvImportConfig`](#ser_lib-config-importers-csvimportconfig)
- [`CsvImporter`](#ser_lib-data-importers-csv_importer-csvimporter)

#### `ser_lib.data.importers.emotiontalk`

- [`EMOTIONTALK_LABELS`](#ser_lib-data-importers-emotiontalk-emotiontalk_labels)
- [`EmotionTalkImportConfig`](#ser_lib-config-importers-emotiontalkimportconfig)
- [`EmotionTalkImporter`](#ser_lib-data-importers-emotiontalk-emotiontalkimporter)

#### `ser_lib.data.importers.esd`

- [`ESD_LABELS`](#ser_lib-data-importers-esd-esd_labels)
- [`ESD_ZH`](#ser_lib-data-importers-esd-esd_zh)
- [`EsdImportConfig`](#ser_lib-config-importers-esdimportconfig)
- [`EsdImporter`](#ser_lib-data-importers-esd-esdimporter)

#### `ser_lib.data.importers.folder`

- [`FolderImportConfig`](#ser_lib-config-importers-folderimportconfig)
- [`FolderImporter`](#ser_lib-data-importers-folder-folderimporter)
- [`DEFAULT_AUDIO_EXTENSIONS`](#ser_lib-config-importers-default_audio_extensions)

#### `ser_lib.data.importers.jsonl_importer`

- [`JsonlImportConfig`](#ser_lib-config-importers-jsonlimportconfig)
- [`JsonlImporter`](#ser_lib-data-importers-jsonl_importer-jsonlimporter)
- [`normalize_raw_record`](#ser_lib-data-importers-jsonl_importer-normalize_raw_record)
- [`normalize_raw_records`](#ser_lib-data-importers-jsonl_importer-normalize_raw_records)
- [`STANDARD_FIELDS`](#ser_lib-data-importers-jsonl_importer-standard_fields)

#### `ser_lib.data.importers.ravdess`

- [`RavdessImporter`](#ser_lib-data-importers-ravdess-ravdessimporter)
- [`RavdessImportConfig`](#ser_lib-config-importers-ravdessimportconfig)
- [`RAVDESS_EMOTIONS`](#ser_lib-data-importers-ravdess-ravdess_emotions)

#### `ser_lib.data.profiling`

- [`AudioProbeFailure`](#ser_lib-data-profiling-audioprobefailure)
- [`DurationHistogramBin`](#ser_lib-data-profiling-durationhistogrambin)
- [`DatasetAudioProfile`](#ser_lib-data-profiling-datasetaudioprofile)
- [`DatasetSummary`](#ser_lib-data-profiling-datasetsummary)
- [`DatasetProfile`](#ser_lib-data-profiling-datasetprofile)
- [`profile_manifest_audio`](#ser_lib-data-profiling-profile_manifest_audio)
- [`summarize_manifest`](#ser_lib-data-profiling-summarize_manifest)
- [`profile_dataset`](#ser_lib-data-profiling-profile_dataset)

#### `ser_lib.data.representations`

- [`Representation`](#ser_lib-data-representations-base-representation)
- [`RawWaveform`](#ser_lib-data-representations-waveform-rawwaveform)
- [`RawWaveformConfig`](#ser_lib-config-representations-rawwaveformconfig)
- [`SpectrogramRepresentation`](#ser_lib-data-representations-spectral-spectrogramrepresentation)
- [`SpectrogramConfig`](#ser_lib-config-representations-spectrogramconfig)
- [`MelSpectrogramRepresentation`](#ser_lib-data-representations-spectral-melspectrogramrepresentation)
- [`MelConfig`](#ser_lib-config-representations-melconfig)
- [`LogMelRepresentation`](#ser_lib-data-representations-spectral-logmelrepresentation)
- [`LogMelConfig`](#ser_lib-config-representations-logmelconfig)
- [`MFCCRepresentation`](#ser_lib-data-representations-spectral-mfccrepresentation)
- [`MFCCConfig`](#ser_lib-config-representations-mfccconfig)
- [`AcousticFeatures`](#ser_lib-data-representations-acoustic-acousticfeatures)
- [`AcousticFeaturesConfig`](#ser_lib-config-representations-acousticfeaturesconfig)
- [`CompositeRepresentation`](#ser_lib-data-representations-composite-compositerepresentation)
- [`CompositeConfig`](#ser_lib-config-representations-compositeconfig)
- [`register_representations`](#ser_lib-data-representations-register_representations)

#### `ser_lib.data.representations.spectral`

- [`SpectrogramConfig`](#ser_lib-config-representations-spectrogramconfig)
- [`MelConfig`](#ser_lib-config-representations-melconfig)
- [`LogMelConfig`](#ser_lib-config-representations-logmelconfig)
- [`MFCCConfig`](#ser_lib-config-representations-mfccconfig)
- [`SpectrogramRepresentation`](#ser_lib-data-representations-spectral-spectrogramrepresentation)
- [`MelSpectrogramRepresentation`](#ser_lib-data-representations-spectral-melspectrogramrepresentation)
- [`LogMelRepresentation`](#ser_lib-data-representations-spectral-logmelrepresentation)
- [`MFCCRepresentation`](#ser_lib-data-representations-spectral-mfccrepresentation)

#### `ser_lib.data.transforms`

- [`RandomApply`](#ser_lib-data-transforms-base-randomapply)
- [`WaveformTransformPipeline`](#ser_lib-data-transforms-base-waveformtransformpipeline)
- [`FeatureTransformPipeline`](#ser_lib-data-transforms-base-featuretransformpipeline)
- [`validate_feature_transform_layouts`](#ser_lib-data-transforms-base-validate_feature_transform_layouts)
- [`SpecMasking`](#ser_lib-data-transforms-feature-specmasking)
- [`SpecMaskingConfig`](#ser_lib-config-transforms-specmaskingconfig)
- [`SPEC_MASKING_DESCRIPTOR`](#ser_lib-data-transforms-feature-spec_masking_descriptor)
- [`register_transforms`](#ser_lib-data-transforms-register_transforms)

#### `ser_lib.data.transforms.feature`

- [`SpecMasking`](#ser_lib-data-transforms-feature-specmasking)
- [`SpecMaskingConfig`](#ser_lib-config-transforms-specmaskingconfig)
- [`SPEC_MASKING_DESCRIPTOR`](#ser_lib-data-transforms-feature-spec_masking_descriptor)

#### `ser_lib.data.transforms.waveform`

- [`Normalize`](#ser_lib-data-transforms-waveform-normalize)
- [`NormalizeConfig`](#ser_lib-config-transforms-normalizeconfig)
- [`AddGaussianNoise`](#ser_lib-data-transforms-waveform-addgaussiannoise)
- [`GaussianNoiseConfig`](#ser_lib-config-transforms-gaussiannoiseconfig)
- [`TimeShift`](#ser_lib-data-transforms-waveform-timeshift)
- [`TimeShiftConfig`](#ser_lib-config-transforms-timeshiftconfig)
- [`VolumeScale`](#ser_lib-data-transforms-waveform-volumescale)
- [`VolumeScaleConfig`](#ser_lib-config-transforms-volumescaleconfig)
- [`PitchShift`](#ser_lib-data-transforms-waveform-pitchshift)
- [`PitchShiftConfig`](#ser_lib-config-transforms-pitchshiftconfig)
- [`TimeStretch`](#ser_lib-data-transforms-waveform-timestretch)
- [`TimeStretchConfig`](#ser_lib-config-transforms-timestretchconfig)
- [`RandomApply`](#ser_lib-data-transforms-base-randomapply)
- [`WAVEFORM_TRANSFORM_SPECS`](#ser_lib-data-transforms-waveform-waveform_transform_specs)

#### `ser_lib.engine`

- [`ModelConfig`](#ser_lib-config-model-modelconfig)
- [`ObservabilityConfig`](#ser_lib-config-training-observabilityconfig)
- [`TrainerConfig`](#ser_lib-config-training-trainerconfig)
- [`ExperimentConfig`](#ser_lib-config-experiment-experimentconfig)
- [`ExperimentComponents`](#ser_lib-engine-experiment-experimentcomponents)
- [`load_experiment_config`](#ser_lib-config-experiment-load_experiment_config)
- [`build_experiment_components`](#ser_lib-engine-experiment-build_experiment_components)
- [`CompatibilityReport`](#ser_lib-engine-compatibility-compatibilityreport)
- [`inspect_compatibility`](#ser_lib-engine-compatibility-inspect_compatibility)
- [`validate_compatibility`](#ser_lib-engine-compatibility-validate_compatibility)
- [`EtaSnapshot`](#ser_lib-engine-eta-etasnapshot)
- [`EtaEstimator`](#ser_lib-engine-eta-etaestimator)
- [`ExperimentValidationResult`](#ser_lib-engine-validation-experimentvalidationresult)
- [`validate_experiment`](#ser_lib-engine-validation-validate_experiment)
- [`TrainingExperimentResult`](#ser_lib-engine-experiment-trainingexperimentresult)
- [`EvaluationExperimentResult`](#ser_lib-engine-experiment-evaluationexperimentresult)
- [`train_experiment`](#ser_lib-engine-experiment-train_experiment)
- [`evaluate_artifact`](#ser_lib-engine-experiment-evaluate_artifact)
- [`TrainingMetadata`](#ser_lib-engine-lineage-trainingmetadata)
- [`build_training_metadata`](#ser_lib-engine-lineage-build_training_metadata)
- [`TrainingRecord`](#ser_lib-engine-training_records-trainingrecord)
- [`write_training_record`](#ser_lib-engine-training_records-write_training_record)
- [`load_training_record`](#ser_lib-engine-training_records-load_training_record)
- [`TrainingHistory`](#ser_lib-engine-training_history-traininghistory)
- [`load_training_history`](#ser_lib-engine-training_history-load_training_history)
- [`EvaluationMetadata`](#ser_lib-engine-evaluation_records-evaluationmetadata)
- [`EvaluationRecord`](#ser_lib-engine-evaluation_records-evaluationrecord)
- [`EvaluationPredictionFileInfo`](#ser_lib-engine-evaluation_reports-evaluationpredictionfileinfo)
- [`inspect_evaluation_prediction_file`](#ser_lib-engine-evaluation_reports-inspect_evaluation_prediction_file)
- [`build_evaluation_metadata`](#ser_lib-engine-evaluation_records-build_evaluation_metadata)
- [`write_evaluation_record`](#ser_lib-engine-evaluation_records-write_evaluation_record)
- [`load_evaluation_record`](#ser_lib-engine-evaluation_records-load_evaluation_record)
- [`AdamWConfig`](#ser_lib-config-optimizer-adamwconfig)
- [`AdamConfig`](#ser_lib-config-optimizer-adamconfig)
- [`SGDConfig`](#ser_lib-config-optimizer-sgdconfig)
- [`StepSchedulerConfig`](#ser_lib-config-scheduler-stepschedulerconfig)
- [`CosineSchedulerConfig`](#ser_lib-config-scheduler-cosineschedulerconfig)
- [`parse_optimizer_config`](#ser_lib-config-optimizer-parse_optimizer_config)
- [`build_optimizer`](#ser_lib-engine-optim-build_optimizer)
- [`parse_scheduler_config`](#ser_lib-config-scheduler-parse_scheduler_config)
- [`build_scheduler`](#ser_lib-engine-optim-build_scheduler)
- [`LossConfig`](#ser_lib-config-training-lossconfig)
- [`SamplingConfig`](#ser_lib-config-training-samplingconfig)
- [`ClassificationLoss`](#ser_lib-engine-objectives-classificationloss)
- [`build_weighted_sampler`](#ser_lib-engine-objectives-build_weighted_sampler)
- [`Trainer`](#ser_lib-engine-training-trainer-trainer)
- [`EpochResult`](#ser_lib-engine-training-results-epochresult)
- [`TrainingResult`](#ser_lib-engine-training-results-trainingresult)
- [`TrainingStatus`](#ser_lib-engine-training-results-trainingstatus)
- [`seed_everything`](#ser_lib-engine-training-trainer-seed_everything)
- [`ClassMetrics`](#ser_lib-engine-evaluator-classmetrics)
- [`PredictionRecord`](#ser_lib-engine-evaluator-predictionrecord)
- [`PredictionSink`](#ser_lib-engine-evaluator-predictionsink)
- [`JsonlPredictionSink`](#ser_lib-engine-evaluator-jsonlpredictionsink)
- [`EvaluationResult`](#ser_lib-engine-evaluator-evaluationresult)
- [`EvaluationReportInfo`](#ser_lib-engine-evaluation_reports-evaluationreportinfo)
- [`inspect_evaluation_report`](#ser_lib-engine-evaluation_reports-inspect_evaluation_report)
- [`iter_evaluation_predictions`](#ser_lib-engine-evaluation_reports-iter_evaluation_predictions)
- [`evaluate`](#ser_lib-engine-evaluator-evaluate)
- [`write_evaluation_report`](#ser_lib-engine-evaluator-write_evaluation_report)
- [`CheckpointKind`](#ser_lib-engine-checkpoint_catalog-checkpointkind)
- [`CheckpointInfo`](#ser_lib-engine-checkpoint_catalog-checkpointinfo)
- [`CheckpointScanFailure`](#ser_lib-engine-checkpoint_catalog-checkpointscanfailure)
- [`CheckpointCatalog`](#ser_lib-engine-checkpoint_catalog-checkpointcatalog)
- [`inspect_checkpoint_file`](#ser_lib-engine-checkpoint_catalog-inspect_checkpoint_file)
- [`scan_checkpoints`](#ser_lib-engine-checkpoint_catalog-scan_checkpoints)
- [`save_checkpoint`](#ser_lib-engine-checkpoint-save_checkpoint)
- [`load_checkpoint`](#ser_lib-engine-checkpoint-load_checkpoint)

#### `ser_lib.engine._seed`

- [`seed_experiment_rng`](#ser_lib-engine-_seed-seed_experiment_rng)

#### `ser_lib.engine.checkpoint`

- [`save_checkpoint`](#ser_lib-engine-checkpoint-save_checkpoint)
- [`load_checkpoint`](#ser_lib-engine-checkpoint-load_checkpoint)

#### `ser_lib.engine.checkpoint_catalog`

- [`CheckpointKind`](#ser_lib-engine-checkpoint_catalog-checkpointkind)
- [`CheckpointInfo`](#ser_lib-engine-checkpoint_catalog-checkpointinfo)
- [`CheckpointScanFailure`](#ser_lib-engine-checkpoint_catalog-checkpointscanfailure)
- [`CheckpointCatalog`](#ser_lib-engine-checkpoint_catalog-checkpointcatalog)
- [`inspect_checkpoint_file`](#ser_lib-engine-checkpoint_catalog-inspect_checkpoint_file)
- [`scan_checkpoints`](#ser_lib-engine-checkpoint_catalog-scan_checkpoints)

#### `ser_lib.engine.compatibility`

- [`CompatibilityReport`](#ser_lib-engine-compatibility-compatibilityreport)
- [`inspect_compatibility`](#ser_lib-engine-compatibility-inspect_compatibility)
- [`validate_compatibility`](#ser_lib-engine-compatibility-validate_compatibility)

#### `ser_lib.engine.eta`

- [`EtaSnapshot`](#ser_lib-engine-eta-etasnapshot)
- [`EtaEstimator`](#ser_lib-engine-eta-etaestimator)

#### `ser_lib.engine.evaluation_records`

- [`EvaluationMetadata`](#ser_lib-engine-evaluation_records-evaluationmetadata)
- [`EvaluationRecord`](#ser_lib-engine-evaluation_records-evaluationrecord)
- [`build_evaluation_metadata`](#ser_lib-engine-evaluation_records-build_evaluation_metadata)
- [`write_evaluation_record`](#ser_lib-engine-evaluation_records-write_evaluation_record)
- [`load_evaluation_record`](#ser_lib-engine-evaluation_records-load_evaluation_record)

#### `ser_lib.engine.evaluation_reports`

- [`EvaluationReportInfo`](#ser_lib-engine-evaluation_reports-evaluationreportinfo)
- [`EvaluationPredictionFileInfo`](#ser_lib-engine-evaluation_reports-evaluationpredictionfileinfo)
- [`inspect_evaluation_report`](#ser_lib-engine-evaluation_reports-inspect_evaluation_report)
- [`inspect_evaluation_prediction_file`](#ser_lib-engine-evaluation_reports-inspect_evaluation_prediction_file)
- [`iter_evaluation_predictions`](#ser_lib-engine-evaluation_reports-iter_evaluation_predictions)

#### `ser_lib.engine.evaluator`

- [`ClassMetrics`](#ser_lib-engine-evaluator-classmetrics)
- [`PredictionRecord`](#ser_lib-engine-evaluator-predictionrecord)
- [`PredictionSink`](#ser_lib-engine-evaluator-predictionsink)
- [`JsonlPredictionSink`](#ser_lib-engine-evaluator-jsonlpredictionsink)
- [`EvaluationResult`](#ser_lib-engine-evaluator-evaluationresult)
- [`evaluate`](#ser_lib-engine-evaluator-evaluate)
- [`write_evaluation_report`](#ser_lib-engine-evaluator-write_evaluation_report)

#### `ser_lib.engine.experiment`

- [`ExperimentComponents`](#ser_lib-engine-experiment-experimentcomponents)
- [`TrainingExperimentResult`](#ser_lib-engine-experiment-trainingexperimentresult)
- [`EvaluationExperimentResult`](#ser_lib-engine-experiment-evaluationexperimentresult)
- [`build_experiment_components`](#ser_lib-engine-experiment-build_experiment_components)
- [`train_experiment`](#ser_lib-engine-experiment-train_experiment)
- [`evaluate_artifact`](#ser_lib-engine-experiment-evaluate_artifact)

#### `ser_lib.engine.lineage`

- [`TrainingMetadata`](#ser_lib-engine-lineage-trainingmetadata)
- [`build_training_metadata`](#ser_lib-engine-lineage-build_training_metadata)
- [`artifact_provenance_from_training_run`](#ser_lib-engine-lineage-artifact_provenance_from_training_run)

#### `ser_lib.engine.objectives`

- [`LossConfig`](#ser_lib-config-training-lossconfig)
- [`SamplingConfig`](#ser_lib-config-training-samplingconfig)
- [`ClassificationLoss`](#ser_lib-engine-objectives-classificationloss)
- [`build_weighted_sampler`](#ser_lib-engine-objectives-build_weighted_sampler)

#### `ser_lib.engine.optim`

- [`AdamWConfig`](#ser_lib-config-optimizer-adamwconfig)
- [`AdamConfig`](#ser_lib-config-optimizer-adamconfig)
- [`SGDConfig`](#ser_lib-config-optimizer-sgdconfig)
- [`OptimizerConfig`](#ser_lib-config-optimizer-optimizerconfig)
- [`StepSchedulerConfig`](#ser_lib-config-scheduler-stepschedulerconfig)
- [`CosineSchedulerConfig`](#ser_lib-config-scheduler-cosineschedulerconfig)
- [`SchedulerConfig`](#ser_lib-config-scheduler-schedulerconfig)
- [`parse_optimizer_config`](#ser_lib-config-optimizer-parse_optimizer_config)
- [`build_optimizer`](#ser_lib-engine-optim-build_optimizer)
- [`parse_scheduler_config`](#ser_lib-config-scheduler-parse_scheduler_config)
- [`build_scheduler`](#ser_lib-engine-optim-build_scheduler)

#### `ser_lib.engine.training`

- [`TrainerConfig`](#ser_lib-config-training-trainerconfig)
- [`ObservabilityConfig`](#ser_lib-config-training-observabilityconfig)
- [`EpochResult`](#ser_lib-engine-training-results-epochresult)
- [`TrainingResult`](#ser_lib-engine-training-results-trainingresult)
- [`TrainingStatus`](#ser_lib-engine-training-results-trainingstatus)
- [`Trainer`](#ser_lib-engine-training-trainer-trainer)
- [`move_batch_to_device`](#ser_lib-data-types-move_batch_to_device)
- [`seed_everything`](#ser_lib-engine-training-trainer-seed_everything)

#### `ser_lib.engine.training.accumulation`

- [`_AccumulationState`](#ser_lib-engine-training-accumulation-_accumulationstate)
- [`_AccumulationAwareLoss`](#ser_lib-engine-training-accumulation-_accumulationawareloss)

#### `ser_lib.engine.training.results`

- [`TrainingStatus`](#ser_lib-engine-training-results-trainingstatus)
- [`EpochResult`](#ser_lib-engine-training-results-epochresult)
- [`TrainingResult`](#ser_lib-engine-training-results-trainingresult)

#### `ser_lib.engine.training.trainer`

- [`TrainerConfig`](#ser_lib-config-training-trainerconfig)
- [`ObservabilityConfig`](#ser_lib-config-training-observabilityconfig)
- [`EpochResult`](#ser_lib-engine-training-results-epochresult)
- [`TrainingResult`](#ser_lib-engine-training-results-trainingresult)
- [`TrainingStatus`](#ser_lib-engine-training-results-trainingstatus)
- [`Trainer`](#ser_lib-engine-training-trainer-trainer)
- [`move_batch_to_device`](#ser_lib-data-types-move_batch_to_device)
- [`seed_everything`](#ser_lib-engine-training-trainer-seed_everything)

#### `ser_lib.engine.training_history`

- [`TrainingHistory`](#ser_lib-engine-training_history-traininghistory)
- [`load_training_history`](#ser_lib-engine-training_history-load_training_history)

#### `ser_lib.engine.training_records`

- [`TrainingRecord`](#ser_lib-engine-training_records-trainingrecord)
- [`write_training_record`](#ser_lib-engine-training_records-write_training_record)
- [`load_training_record`](#ser_lib-engine-training_records-load_training_record)

#### `ser_lib.engine.validation`

- [`ExperimentValidationResult`](#ser_lib-engine-validation-experimentvalidationresult)
- [`validate_experiment`](#ser_lib-engine-validation-validate_experiment)

#### `ser_lib.foundation`

- [`SERError`](#ser_lib-foundation-errors-base-sererror)
- [`ConfigurationError`](#ser_lib-foundation-errors-config-configurationerror)
- [`OperationCancelled`](#ser_lib-foundation-errors-base-operationcancelled)
- [`RegistryError`](#ser_lib-foundation-errors-base-registryerror)
- [`CompatibilityError`](#ser_lib-foundation-errors-engine-compatibilityerror)
- [`Diagnostic`](#ser_lib-foundation-diagnostics-diagnostic)
- [`DiagnosticSeverity`](#ser_lib-foundation-diagnostics-diagnosticseverity)
- [`EventContext`](#ser_lib-foundation-events-base-eventcontext)
- [`ProgressEvent`](#ser_lib-foundation-events-lifecycle-progressevent)
- [`MetricEvent`](#ser_lib-foundation-events-lifecycle-metricevent)
- [`LogEvent`](#ser_lib-foundation-events-lifecycle-logevent)
- [`LifecycleEvent`](#ser_lib-foundation-events-lifecycle-lifecycleevent)
- [`EventLike`](#ser_lib-foundation-events-base-eventlike)
- [`LibraryEvent`](#ser_lib-foundation-events-libraryevent)
- [`EventCallback`](#ser_lib-foundation-events-base-eventcallback)
- [`CancellationCheck`](#ser_lib-foundation-events-base-cancellationcheck)
- [`CancellationToken`](#ser_lib-foundation-events-base-cancellationtoken)
- [`get_logger`](#ser_lib-foundation-logging-get_logger)
- [`configure_library_logging`](#ser_lib-foundation-logging-configure_library_logging)

#### `ser_lib.foundation.diagnostics`

- [`Diagnostic`](#ser_lib-foundation-diagnostics-diagnostic)
- [`DiagnosticSeverity`](#ser_lib-foundation-diagnostics-diagnosticseverity)

#### `ser_lib.foundation.errors`

- [`SERError`](#ser_lib-foundation-errors-base-sererror)
- [`OperationCancelled`](#ser_lib-foundation-errors-base-operationcancelled)
- [`RegistryError`](#ser_lib-foundation-errors-base-registryerror)
- [`ConfigurationError`](#ser_lib-foundation-errors-config-configurationerror)
- [`SERDataError`](#ser_lib-foundation-errors-data-serdataerror)
- [`ManifestError`](#ser_lib-foundation-errors-data-manifesterror)
- [`AudioNotFoundError`](#ser_lib-foundation-errors-data-audionotfounderror)
- [`AudioDecodeError`](#ser_lib-foundation-errors-data-audiodecodeerror)
- [`InvalidAudioSegmentError`](#ser_lib-foundation-errors-data-invalidaudiosegmenterror)
- [`RepresentationError`](#ser_lib-foundation-errors-data-representationerror)
- [`TransformError`](#ser_lib-foundation-errors-data-transformerror)
- [`CollationError`](#ser_lib-foundation-errors-data-collationerror)
- [`wrap_error`](#ser_lib-foundation-errors-data-wrap_error)
- [`CompatibilityError`](#ser_lib-foundation-errors-engine-compatibilityerror)

#### `ser_lib.foundation.errors.artifacts`


#### `ser_lib.foundation.errors.base`

- [`SERError`](#ser_lib-foundation-errors-base-sererror)
- [`OperationCancelled`](#ser_lib-foundation-errors-base-operationcancelled)
- [`RegistryError`](#ser_lib-foundation-errors-base-registryerror)

#### `ser_lib.foundation.errors.config`

- [`ConfigurationError`](#ser_lib-foundation-errors-config-configurationerror)

#### `ser_lib.foundation.errors.data`

- [`SERDataError`](#ser_lib-foundation-errors-data-serdataerror)
- [`ManifestError`](#ser_lib-foundation-errors-data-manifesterror)
- [`AudioNotFoundError`](#ser_lib-foundation-errors-data-audionotfounderror)
- [`AudioDecodeError`](#ser_lib-foundation-errors-data-audiodecodeerror)
- [`InvalidAudioSegmentError`](#ser_lib-foundation-errors-data-invalidaudiosegmenterror)
- [`RepresentationError`](#ser_lib-foundation-errors-data-representationerror)
- [`TransformError`](#ser_lib-foundation-errors-data-transformerror)
- [`CollationError`](#ser_lib-foundation-errors-data-collationerror)
- [`wrap_error`](#ser_lib-foundation-errors-data-wrap_error)

#### `ser_lib.foundation.errors.engine`

- [`CompatibilityError`](#ser_lib-foundation-errors-engine-compatibilityerror)

#### `ser_lib.foundation.errors.inference`


#### `ser_lib.foundation.events`

- [`EventContext`](#ser_lib-foundation-events-base-eventcontext)
- [`ProgressEvent`](#ser_lib-foundation-events-lifecycle-progressevent)
- [`MetricEvent`](#ser_lib-foundation-events-lifecycle-metricevent)
- [`LogEvent`](#ser_lib-foundation-events-lifecycle-logevent)
- [`LifecycleEvent`](#ser_lib-foundation-events-lifecycle-lifecycleevent)
- [`CheckpointEvent`](#ser_lib-foundation-events-training-checkpointevent)
- [`PredictionEvent`](#ser_lib-foundation-events-inference-predictionevent)
- [`EventLike`](#ser_lib-foundation-events-base-eventlike)
- [`LibraryEvent`](#ser_lib-foundation-events-libraryevent)
- [`EventCallback`](#ser_lib-foundation-events-base-eventcallback)
- [`CancellationCheck`](#ser_lib-foundation-events-base-cancellationcheck)
- [`CancellationToken`](#ser_lib-foundation-events-base-cancellationtoken)

#### `ser_lib.foundation.events.base`

- [`EventContext`](#ser_lib-foundation-events-base-eventcontext)
- [`EventLike`](#ser_lib-foundation-events-base-eventlike)
- [`EventCallback`](#ser_lib-foundation-events-base-eventcallback)
- [`CancellationCheck`](#ser_lib-foundation-events-base-cancellationcheck)
- [`CancellationToken`](#ser_lib-foundation-events-base-cancellationtoken)

#### `ser_lib.foundation.events.inference`

- [`PredictionEvent`](#ser_lib-foundation-events-inference-predictionevent)

#### `ser_lib.foundation.events.lifecycle`

- [`ProgressEvent`](#ser_lib-foundation-events-lifecycle-progressevent)
- [`MetricEvent`](#ser_lib-foundation-events-lifecycle-metricevent)
- [`LogEvent`](#ser_lib-foundation-events-lifecycle-logevent)
- [`LifecycleEvent`](#ser_lib-foundation-events-lifecycle-lifecycleevent)

#### `ser_lib.foundation.events.training`

- [`CheckpointEvent`](#ser_lib-foundation-events-training-checkpointevent)

#### `ser_lib.foundation.logging`

- [`LOGGER_NAME`](#ser_lib-foundation-logging-logger_name)
- [`get_logger`](#ser_lib-foundation-logging-get_logger)
- [`configure_library_logging`](#ser_lib-foundation-logging-configure_library_logging)

#### `ser_lib.inference`

- [`EmotionPredictor`](#ser_lib-inference-offline-emotionpredictor)
- [`PredictionResult`](#ser_lib-inference-offline-predictionresult)
- [`PredictionFailure`](#ser_lib-inference-batch-predictionfailure)
- [`BatchPredictionSink`](#ser_lib-inference-batch-batchpredictionsink)
- [`JsonlBatchPredictionSink`](#ser_lib-inference-batch-jsonlbatchpredictionsink)
- [`BatchPredictionResult`](#ser_lib-inference-batch-batchpredictionresult)
- [`BatchEmotionPredictor`](#ser_lib-inference-batch-batchemotionpredictor)
- [`write_batch_predictions`](#ser_lib-inference-batch-write_batch_predictions)
- [`StreamingConfig`](#ser_lib-config-inference-streamingconfig)
- [`StreamingPrediction`](#ser_lib-inference-streaming-streamingprediction)
- [`StreamingLatency`](#ser_lib-inference-streaming-streaminglatency)
- [`StreamingEmotionRecognizer`](#ser_lib-inference-streaming-streamingemotionrecognizer)

#### `ser_lib.inference.batch`

- [`PredictionFailure`](#ser_lib-inference-batch-predictionfailure)
- [`BatchPredictionSink`](#ser_lib-inference-batch-batchpredictionsink)
- [`JsonlBatchPredictionSink`](#ser_lib-inference-batch-jsonlbatchpredictionsink)
- [`BatchPredictionResult`](#ser_lib-inference-batch-batchpredictionresult)
- [`BatchEmotionPredictor`](#ser_lib-inference-batch-batchemotionpredictor)
- [`write_batch_predictions`](#ser_lib-inference-batch-write_batch_predictions)

#### `ser_lib.inference.offline`

- [`EmotionPredictor`](#ser_lib-inference-offline-emotionpredictor)
- [`PredictionResult`](#ser_lib-inference-offline-predictionresult)

#### `ser_lib.inference.streaming`

- [`StreamingConfig`](#ser_lib-config-inference-streamingconfig)
- [`StreamingPrediction`](#ser_lib-inference-streaming-streamingprediction)
- [`StreamingLatency`](#ser_lib-inference-streaming-streaminglatency)
- [`StreamingEmotionRecognizer`](#ser_lib-inference-streaming-streamingemotionrecognizer)

#### `ser_lib.models`

- [`SERModel`](#ser_lib-models-base-sermodel)
- [`ModelOutput`](#ser_lib-models-base-modeloutput)
- [`ModelSpec`](#ser_lib-models-specs-modelspec)
- [`TorchModelAdapter`](#ser_lib-models-adapters-torch-torchmodeladapter)
- [`TORCH_ADAPTER_MODEL_ID`](#ser_lib-models-adapters-torch-torch_adapter_model_id)
- [`CNNBaseline`](#ser_lib-models-cnn_models-cnnbaseline)
- [`CNNBaselineConfig`](#ser_lib-config-model-cnnbaselineconfig)
- [`GRUBaseline`](#ser_lib-models-rnn_models-grubaseline)
- [`GRUBaselineConfig`](#ser_lib-config-model-grubaselineconfig)
- [`TransformerBaseline`](#ser_lib-models-transformer_models-transformerbaseline)
- [`TransformerBaselineConfig`](#ser_lib-config-model-transformerbaselineconfig)
- [`HFAudioClassifier`](#ser_lib-models-adapters-huggingface-hfaudioclassifier)
- [`HFAudioClassifierConfig`](#ser_lib-config-model-hfaudioclassifierconfig)
- [`HFProcessorConfig`](#ser_lib-config-model-hfprocessorconfig)
- [`ModelDescriptor`](#ser_lib-models-registry-modeldescriptor)
- [`ModelRegistry`](#ser_lib-models-registry-modelregistry)
- [`model_registry`](#ser_lib-models-registry-model_registry)

#### `ser_lib.models.adapters`

- [`HFAudioClassifier`](#ser_lib-models-adapters-huggingface-hfaudioclassifier)
- [`TORCH_ADAPTER_MODEL_ID`](#ser_lib-models-adapters-torch-torch_adapter_model_id)
- [`TorchModelAdapter`](#ser_lib-models-adapters-torch-torchmodeladapter)

#### `ser_lib.models.adapters.huggingface`

- [`HFAudioClassifier`](#ser_lib-models-adapters-huggingface-hfaudioclassifier)
- [`HFAudioClassifierConfig`](#ser_lib-config-model-hfaudioclassifierconfig)
- [`HFProcessorConfig`](#ser_lib-config-model-hfprocessorconfig)

#### `ser_lib.models.adapters.torch`

- [`TORCH_ADAPTER_MODEL_ID`](#ser_lib-models-adapters-torch-torch_adapter_model_id)
- [`TorchModelAdapter`](#ser_lib-models-adapters-torch-torchmodeladapter)

#### `ser_lib.models.cnn_models`

- [`CNNBaseline`](#ser_lib-models-cnn_models-cnnbaseline)
- [`CNNBaselineConfig`](#ser_lib-config-model-cnnbaselineconfig)

#### `ser_lib.models.rnn_models`

- [`GRUBaseline`](#ser_lib-models-rnn_models-grubaseline)
- [`GRUBaselineConfig`](#ser_lib-config-model-grubaselineconfig)

#### `ser_lib.models.specs`

- [`ModelSpec`](#ser_lib-models-specs-modelspec)

#### `ser_lib.models.transformer_models`

- [`TransformerBaseline`](#ser_lib-models-transformer_models-transformerbaseline)
- [`TransformerBaselineConfig`](#ser_lib-config-model-transformerbaselineconfig)

#### `ser_lib.runtime`

- [`RuntimeDevice`](#ser_lib-runtime-runtimedevice)
- [`RuntimeCapabilities`](#ser_lib-runtime-runtimecapabilities)
- [`get_runtime_capabilities`](#ser_lib-runtime-get_runtime_capabilities)

### 9.2 定义、参数、返回值与约束

<a id="ser_lib-_version-__version__"></a>

#### `ser_lib._version.__version__`

公开导入：`ser_lib._version.__version__`。

源码：[ser_lib/_version.py:3](../ser_lib/_version.py#L3)。

类型别名、常量或共享实例定义：

```python
__version__ = '1.0.0'
```

<a id="ser_lib-artifacts-_compatibility-validate_artifact_compatibility"></a>

#### `ser_lib.artifacts._compatibility.validate_artifact_compatibility`

公开导入：`ser_lib.artifacts._compatibility.validate_artifact_compatibility`。

源码：[ser_lib/artifacts/_compatibility.py:11](../ser_lib/artifacts/_compatibility.py#L11)。

```python
validate_artifact_compatibility(model: SERModel, data_config: DataConfig, *, num_classes: int) -> None
```

Reject artifact combinations that cannot satisfy the model input contract.

<a id="ser_lib-artifacts-catalog-artifactcatalog"></a>

#### `ser_lib.artifacts.catalog.ArtifactCatalog`

公开导入：`ser_lib.artifacts.catalog.ArtifactCatalog`、`ser_lib.artifacts.ArtifactCatalog`。

源码：[ser_lib/artifacts/catalog.py:45](../ser_lib/artifacts/catalog.py#L45)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `root` | `str` | `必填（无默认值）` |
| `artifacts` | `tuple[ArtifactEntry, ...]` | `必填（无默认值）` |
| `failures` | `tuple[ArtifactScanFailure, ...]` | `必填（无默认值）` |

##### `total`

调用方式：只读属性。

```python
total(self) -> int
```

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'root': self.root, 'total': self.total, 'artifacts': [artifact.to_dict() for artifact in self.artifacts], 'failures': [failure.to_dict() for failure in self.failures]}
```

<a id="ser_lib-artifacts-catalog-artifactentry"></a>

#### `ser_lib.artifacts.catalog.ArtifactEntry`

公开导入：`ser_lib.artifacts.catalog.ArtifactEntry`、`ser_lib.artifacts.ArtifactEntry`。

源码：[ser_lib/artifacts/catalog.py:15](../ser_lib/artifacts/catalog.py#L15)。

Artifact 扫描的最小资源条目；manifest 保持领域原始结构。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `path` | `str` | `必填（无默认值）` |
| `manifest` | `ModelArtifactManifest` | `必填（无默认值）` |
| `weights_bytes` | `int` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'path': self.path, 'manifest': self.manifest.model_dump(mode='json'), 'weights_bytes': self.weights_bytes}
```

<a id="ser_lib-artifacts-catalog-artifactscanfailure"></a>

#### `ser_lib.artifacts.catalog.ArtifactScanFailure`

公开导入：`ser_lib.artifacts.catalog.ArtifactScanFailure`、`ser_lib.artifacts.ArtifactScanFailure`。

源码：[ser_lib/artifacts/catalog.py:31](../ser_lib/artifacts/catalog.py#L31)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `directory` | `str` | `必填（无默认值）` |
| `error_type` | `str` | `必填（无默认值）` |
| `message` | `str` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, str]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'directory': self.directory, 'error_type': self.error_type, 'message': self.message}
```

<a id="ser_lib-artifacts-catalog-scan_model_artifacts"></a>

#### `ser_lib.artifacts.catalog.scan_model_artifacts`

公开导入：`ser_lib.artifacts.catalog.scan_model_artifacts`、`ser_lib.artifacts.scan_model_artifacts`。

源码：[ser_lib/artifacts/catalog.py:91](../ser_lib/artifacts/catalog.py#L91)。

```python
scan_model_artifacts(root: Path | str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None) -> ArtifactCatalog
```

扫描 Artifact 根目录；只调用轻量 inspect/stat，绝不计算文件 SHA256。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'Artifact Catalog 根目录不存在或不是目录: {root_path}')`

<a id="ser_lib-artifacts-exporter-export_model_artifact"></a>

#### `ser_lib.artifacts.exporter.export_model_artifact`

公开导入：`ser_lib.export_model_artifact`、`ser_lib.artifacts.exporter.export_model_artifact`、`ser_lib.artifacts.export_model_artifact`。

源码：[ser_lib/artifacts/exporter.py:99](../ser_lib/artifacts/exporter.py#L99)。

```python
export_model_artifact(directory: Path | str, model: SERModel, *, model_name: str, model_params: Mapping[str, Any] | None=None, data_config: DataConfig, labels: Mapping[int, str], metrics: Mapping[str, float] | None=None, metadata: Mapping[str, Any] | None=None, model_card: ModelCard | Mapping[str, Any] | None=None, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> Path
```

导出 schema v2 artifact，并暴露阶段/字节级进度与协作式取消。

权重序列化由 safetensors 一次完成，因此该阶段只能提供生命周期事件；随后
SHA256 阶段按 1 MiB chunk 提供真实字节进度。所有内容先写 sibling staging
目录，取消或失败时 staging 会删除，最终目标目录不会留下半成品。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'model_name={model_name!r} 与模型声明 {model.model_spec.model_id!r} 不一致')`
- `ValueError('model_params 与模型实例的实际配置不一致')`
- `ValueError(f'labels 数量与模型 num_classes 不一致: {len(normalized_labels)} != {declared_num_classes}')`
- `FileExistsError(f'artifact 目标已存在，拒绝覆盖: {target}')`

<a id="ser_lib-artifacts-loader-loadedartifact"></a>

#### `ser_lib.artifacts.loader.LoadedArtifact`

公开导入：`ser_lib.artifacts.loader.LoadedArtifact`、`ser_lib.artifacts.LoadedArtifact`。

源码：[ser_lib/artifacts/loader.py:33](../ser_lib/artifacts/loader.py#L33)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `manifest` | `ModelArtifactManifest` | `必填（无默认值）` |
| `model` | `SERModel` | `必填（无默认值）` |
| `audio_loader` | `AudioLoader` | `必填（无默认值）` |
| `pipeline` | `SamplePipeline` | `必填（无默认值）` |
| `collator` | `SERCollator` | `必填（无默认值）` |

<a id="ser_lib-artifacts-loader-inspect_model_artifact"></a>

#### `ser_lib.artifacts.loader.inspect_model_artifact`

公开导入：`ser_lib.artifacts.loader.inspect_model_artifact`、`ser_lib.artifacts.inspect_model_artifact`。

源码：[ser_lib/artifacts/loader.py:115](../ser_lib/artifacts/loader.py#L115)。

```python
inspect_model_artifact(directory: Path | str) -> ModelArtifactManifest
```

快速检查 artifact 结构和轻量 metadata，不计算任何文件 SHA256。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'模型权重不存在: {weights}')`
- `ValueError('artifact 缺少 files_sha256')`
- `ValueError('artifact files_sha256 缺少必需元数据文件')`
- `ValueError('weights_sha256 与 files_sha256 不一致')`
- `ValueError('包含 processor 的 artifact 必须哈希 processor_config.json')`
- `FileNotFoundError(f'artifact 组成文件不存在: {path}')`

<a id="ser_lib-artifacts-loader-load_model_artifact"></a>

#### `ser_lib.artifacts.loader.load_model_artifact`

公开导入：`ser_lib.load_model_artifact`、`ser_lib.artifacts.loader.load_model_artifact`、`ser_lib.artifacts.load_model_artifact`。

源码：[ser_lib/artifacts/loader.py:279](../ser_lib/artifacts/loader.py#L279)。

```python
load_model_artifact(directory: Path | str, *, map_location: str | torch.device='cpu') -> LoadedArtifact
```

完整验证并加载当前 safetensors artifact。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('artifact 加载请求 CUDA，但当前环境不可用')`
- `ValueError('重建模型的 processor snapshot 与 artifact manifest 不一致')`
- `ValueError('artifact 权重不是合法 tensor state_dict')`

<a id="ser_lib-artifacts-loader-verify_model_artifact"></a>

#### `ser_lib.artifacts.loader.verify_model_artifact`

公开导入：`ser_lib.artifacts.loader.verify_model_artifact`、`ser_lib.artifacts.verify_model_artifact`。

源码：[ser_lib/artifacts/loader.py:145](../ser_lib/artifacts/loader.py#L145)。

```python
verify_model_artifact(directory: Path | str, *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ModelArtifactManifest
```

完整校验全部 SHA256，并以读取字节数暴露进度。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'artifact 文件 SHA-256 校验失败: {name}')`
- `ValueError('模型权重 SHA-256 校验失败，文件可能损坏或被修改')`

<a id="ser_lib-artifacts-manifest-modelartifactmanifest"></a>

#### `ser_lib.artifacts.manifest.ModelArtifactManifest`

公开导入：`ser_lib.artifacts.manifest.ModelArtifactManifest`、`ser_lib.artifacts.ModelArtifactManifest`。

源码：[ser_lib/artifacts/manifest.py:23](../ser_lib/artifacts/manifest.py#L23)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `library_version` | `str` | `必填（无默认值）` |
| `model_name` | `str` | `必填（无默认值）` |
| `model_params` | `dict[str, Any]` | `必填（无默认值）` |
| `input_specs` | `dict[str, dict[str, Any]]` | `Field(default_factory=dict)` |
| `weights_file` | `Literal['weights.safetensors']` | `'weights.safetensors'` |
| `weights_sha256` | `str` | `必填（无默认值）` |
| `files_sha256` | `dict[str, str]` | `必填（无默认值）` |
| `preprocessing` | `dict[str, Any]` | `必填（无默认值）` |
| `processor` | `dict[str, Any] &#124; None` | `None` |
| `labels` | `dict[int, str]` | `必填（无默认值）` |
| `metrics` | `dict[str, float]` | `Field(default_factory=dict)` |
| `model_card` | `ModelCard` | `Field(default_factory=ModelCard)` |
| `metadata` | `dict[str, Any]` | `Field(default_factory=dict)` |

<a id="ser_lib-artifacts-manifest-modelcard"></a>

#### `ser_lib.artifacts.manifest.ModelCard`

公开导入：`ser_lib.artifacts.manifest.ModelCard`、`ser_lib.artifacts.ModelCard`。

源码：[ser_lib/artifacts/manifest.py:12](../ser_lib/artifacts/manifest.py#L12)。

最小模型卡；未知信息允许留空，但字段不可隐式发明。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `description` | `str` | `''` |
| `intended_use` | `str` | `''` |
| `dataset` | `str` | `''` |
| `language` | `list[str]` | `Field(default_factory=list)` |
| `license` | `str` | `''` |
| `limitations` | `list[str]` | `Field(default_factory=list)` |

<a id="ser_lib-cli-main-main"></a>

#### `ser_lib.cli.main.main`

公开导入：`ser_lib.cli.main`、`ser_lib.cli.main.main`。

源码：[ser_lib/cli/main.py:312](../ser_lib/cli/main.py#L312)。

```python
main(argv: Sequence[str] | None=None) -> int
```

<a id="ser_lib-cli-workflows-evaluate_artifact"></a>

#### `ser_lib.cli.workflows.evaluate_artifact`

公开导入：`ser_lib.cli.workflows.evaluate_artifact`。

源码：[ser_lib/cli/workflows.py:128](../ser_lib/cli/workflows.py#L128)。

```python
evaluate_artifact(artifact: Path, *, manifest_path: Path | None, split: str, batch_size: int, workers: int, device: str, output: Path) -> dict[str, Any]
```

CLI 兼容入口；评估业务逻辑由 ``ser_lib.engine`` 提供。

<a id="ser_lib-cli-workflows-export_checkpoint_artifact"></a>

#### `ser_lib.cli.workflows.export_checkpoint_artifact`

公开导入：`ser_lib.cli.workflows.export_checkpoint_artifact`。

源码：[ser_lib/cli/workflows.py:200](../ser_lib/cli/workflows.py#L200)。

```python
export_checkpoint_artifact(config_path: Path, checkpoint: Path, destination: Path, *, model_card: dict[str, Any] | None=None) -> dict[str, Any]
```

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'artifact': str(target), 'model': config.model.type, 'labels': labels, 'source_run_id': source_run.run_id if source_run is not None else None}
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'标签数 {len(labels)} 与模型 num_classes={expected_classes} 不一致')`
- `ValueError('checkpoint 缺少训练 lineage，无法验证导出标签与预处理')`
- `ValueError('checkpoint 缺少标签及 fingerprint，无法验证导出语义')`
- `ValueError('导出预处理与 checkpoint 训练配置不一致')`

<a id="ser_lib-cli-workflows-inspect_artifact"></a>

#### `ser_lib.cli.workflows.inspect_artifact`

公开导入：`ser_lib.cli.workflows.inspect_artifact`。

源码：[ser_lib/cli/workflows.py:267](../ser_lib/cli/workflows.py#L267)。

```python
inspect_artifact(path: Path, *, verify: bool) -> dict[str, Any]
```

<a id="ser_lib-cli-workflows-predict_artifact"></a>

#### `ser_lib.cli.workflows.predict_artifact`

公开导入：`ser_lib.cli.workflows.predict_artifact`。

源码：[ser_lib/cli/workflows.py:150](../ser_lib/cli/workflows.py#L150)。

```python
predict_artifact(artifact: Path, *, source: Path, split: str | None, batch_size: int, device: str, output: Path, keep_going: bool, recursive: bool, window_aggregation: Literal['mean_logits', 'mean_probabilities', 'max_confidence'] | None) -> dict[str, Any]
```

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'output': str(output), 'total': result.total, 'succeeded': result.succeeded, 'failed': result.failed}
```

<a id="ser_lib-cli-workflows-train_experiment"></a>

#### `ser_lib.cli.workflows.train_experiment`

公开导入：`ser_lib.cli.workflows.train_experiment`。

源码：[ser_lib/cli/workflows.py:110](../ser_lib/cli/workflows.py#L110)。

```python
train_experiment(config_path: Path, *, split: str, batch_size: int, workers: int, resume: Path | None) -> dict[str, Any]
```

CLI 兼容入口；训练业务逻辑由 ``ser_lib.engine`` 提供。

<a id="ser_lib-config-base-strictconfig"></a>

#### `ser_lib.config.base.StrictConfig`

公开导入：`ser_lib.config.base.StrictConfig`、`ser_lib.config.StrictConfig`。

源码：[ser_lib/config/base.py:8](../ser_lib/config/base.py#L8)。

公共配置基类：拒绝未知字段，校验赋值并禁止意外修改。

基类：`BaseModel`。继承的字段/方法继续适用。

<a id="ser_lib-config-data-audiobackend"></a>

#### `ser_lib.config.data.AudioBackend`

公开导入：`ser_lib.config.data.AudioBackend`、`ser_lib.config.AudioBackend`、`ser_lib.data.audio.AudioBackend`。

源码：[ser_lib/config/data.py:15](../ser_lib/config/data.py#L15)。

类型别名、常量或共享实例定义：

```python
AudioBackend = Literal['soundfile', 'torchaudio']
```

<a id="ser_lib-config-data-audioconfig"></a>

#### `ser_lib.config.data.AudioConfig`

公开导入：`ser_lib.config.data.AudioConfig`、`ser_lib.config.AudioConfig`。

源码：[ser_lib/config/data.py:28](../ser_lib/config/data.py#L28)。

音频解码与标准化的唯一正式用户配置。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `target_sample_rate` | `int` | `Field(default=16000, ge=1000, le=192000)` |
| `mono` | `bool` | `True` |
| `normalize_peak` | `bool` | `False` |
| `backend` | `AudioBackend` | `'soundfile'` |

<a id="ser_lib-config-data-batchingconfig"></a>

#### `ser_lib.config.data.BatchingConfig`

公开导入：`ser_lib.config.data.BatchingConfig`、`ser_lib.config.BatchingConfig`。

源码：[ser_lib/config/data.py:73](../ser_lib/config/data.py#L73)。

dynamic/fixed/sliding 三种批处理策略的用户配置。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `BatchingType` | `'dynamic'` |
| `fixed` | `FixedBatching &#124; None` | `None` |
| `sliding` | `SlidingBatching &#124; None` | `None` |
| `primary_key` | `str &#124; None` | `None` |

##### `is_dynamic`

调用方式：只读属性。

```python
is_dynamic(self) -> bool
```

##### `validate_completeness`

```python
validate_completeness(self) -> None
```

校验策略与参数节点的一致性，在任务启动前失败。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError("batching.type='fixed' 时必须提供 fixed.max_lengths （例如 {features: 300}）")`
- `ValueError("batching.type='sliding' 时必须提供 sliding.window_size 与 sliding.stride")`
- `ValueError("仅 batching.type='fixed' 允许提供 fixed 节点")`
- `ValueError("仅 batching.type='sliding' 允许提供 sliding 节点")`

<a id="ser_lib-config-data-batchingtype"></a>

#### `ser_lib.config.data.BatchingType`

公开导入：`ser_lib.config.data.BatchingType`、`ser_lib.config.BatchingType`。

源码：[ser_lib/config/data.py:14](../ser_lib/config/data.py#L14)。

类型别名、常量或共享实例定义：

```python
BatchingType = Literal['dynamic', 'fixed', 'sliding']
```

<a id="ser_lib-config-data-cacheconfig"></a>

#### `ser_lib.config.data.CacheConfig`

公开导入：`ser_lib.config.data.CacheConfig`、`ser_lib.config.CacheConfig`。

源码：[ser_lib/config/data.py:37](../ser_lib/config/data.py#L37)。

确定性 Representation 磁盘缓存配置。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `enabled` | `bool` | `False` |
| `directory` | `Path` | `Path('.ser-cache/features')` |

<a id="ser_lib-config-data-componentconfig"></a>

#### `ser_lib.config.data.ComponentConfig`

公开导入：`ser_lib.config.data.ComponentConfig`、`ser_lib.config.ComponentConfig`。

源码：[ser_lib/config/data.py:18](../ser_lib/config/data.py#L18)。

通用组件引用：``{type, params, probability}``。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `str` | `Field(..., min_length=1, description='注册表中的组件名')` |
| `params` | `dict[str, Any]` | `Field(default_factory=dict, description='组件参数')` |
| `probability` | `float &#124; None` | `Field(default=None, ge=0.0, le=1.0, description='随机 transform 的触发概率')` |

<a id="ser_lib-config-data-dataconfig"></a>

#### `ser_lib.config.data.DataConfig`

公开导入：`ser_lib.config.data.DataConfig`、`ser_lib.config.DataConfig`。

源码：[ser_lib/config/data.py:107](../ser_lib/config/data.py#L107)。

数据模块顶层配置；从 YAML 加载时所有路径均相对配置文件目录解析。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `manifest` | `Path` | `必填（无默认值）` |
| `dataset_id` | `str &#124; None` | `None` |
| `labels` | `dict[int, dict[str, Any]] &#124; None` | `None` |
| `audio` | `AudioConfig` | `Field(default_factory=AudioConfig)` |
| `cache` | `CacheConfig` | `Field(default_factory=CacheConfig)` |
| `representation` | `ComponentConfig` | `必填（无默认值）` |
| `waveform_transforms` | `list[ComponentConfig]` | `Field(default_factory=list)` |
| `feature_transforms` | `list[ComponentConfig]` | `Field(default_factory=list)` |
| `batching` | `BatchingConfig` | `Field(default_factory=BatchingConfig)` |

##### `num_classes`

调用方式：只读属性。

```python
num_classes(self) -> int | None
```

<a id="ser_lib-config-data-fixedbatching"></a>

#### `ser_lib.config.data.FixedBatching`

公开导入：`ser_lib.config.data.FixedBatching`、`ser_lib.config.FixedBatching`。

源码：[ser_lib/config/data.py:44](../ser_lib/config/data.py#L44)。

固定长度批处理参数：按 key 配置最大长度。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `max_lengths` | `dict[str, int]` | `Field(..., min_length=1)` |

<a id="ser_lib-config-data-slidingbatching"></a>

#### `ser_lib.config.data.SlidingBatching`

公开导入：`ser_lib.config.data.SlidingBatching`、`ser_lib.config.SlidingBatching`。

源码：[ser_lib/config/data.py:58](../ser_lib/config/data.py#L58)。

滑动窗口批处理参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `window_size` | `int` | `Field(..., ge=1)` |
| `stride` | `int` | `Field(..., ge=1)` |

<a id="ser_lib-config-data-load_data_config"></a>

#### `ser_lib.config.data.load_data_config`

公开导入：`ser_lib.config.data.load_data_config`、`ser_lib.config.load_data_config`。

源码：[ser_lib/config/data.py:143](../ser_lib/config/data.py#L143)。

```python
load_data_config(path: Path | str) -> DataConfig
```

加载当前 DataConfig schema，并相对配置文件目录解析路径。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ConfigurationError(f'配置内容校验失败: {source}: {exc}')`

<a id="ser_lib-config-experiment-experimentconfig"></a>

#### `ser_lib.config.experiment.ExperimentConfig`

公开导入：`ser_lib.config.experiment.ExperimentConfig`、`ser_lib.config.ExperimentConfig`、`ser_lib.engine.ExperimentConfig`。

源码：[ser_lib/config/experiment.py:20](../ser_lib/config/experiment.py#L20)。

一次可复现实验的完整、可序列化配置快照。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `data` | `DataConfig` | `必填（无默认值）` |
| `model` | `ModelConfig` | `必填（无默认值）` |
| `trainer` | `TrainerConfig` | `Field(default_factory=TrainerConfig)` |
| `optimizer` | `dict[str, Any]` | `Field(default_factory=lambda: {'type': 'adamw', 'params': {}})` |
| `scheduler` | `dict[str, Any] &#124; None` | `None` |
| `loss` | `LossConfig` | `Field(default_factory=LossConfig)` |
| `sampling` | `SamplingConfig` | `Field(default_factory=SamplingConfig)` |
| `output_dir` | `Path` | `Path('runs/default')` |

<a id="ser_lib-config-experiment-load_experiment_config"></a>

#### `ser_lib.config.experiment.load_experiment_config`

公开导入：`ser_lib.config.experiment.load_experiment_config`、`ser_lib.config.load_experiment_config`、`ser_lib.engine.load_experiment_config`。

源码：[ser_lib/config/experiment.py:47](../ser_lib/config/experiment.py#L47)。

```python
load_experiment_config(path: Path | str) -> ExperimentConfig
```

严格读取当前实验配置，并基于配置文件目录解析所有相对路径。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ConfigurationError(f'配置内容校验失败: {source}: {exc}')`

<a id="ser_lib-config-importers-casiaimportconfig"></a>

#### `ser_lib.config.importers.CasiaImportConfig`

公开导入：`ser_lib.config.importers.CasiaImportConfig`、`ser_lib.config.CasiaImportConfig`、`ser_lib.data.importers.casia.CasiaImportConfig`、`ser_lib.data.importers.CasiaImportConfig`。

源码：[ser_lib/config/importers.py:23](../ser_lib/config/importers.py#L23)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `audio_extensions` | `list[str]` | `Field(default_factory=lambda: list(DEFAULT_AUDIO_EXTENSIONS))` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |

<a id="ser_lib-config-importers-cremadimportconfig"></a>

#### `ser_lib.config.importers.CremaDImportConfig`

公开导入：`ser_lib.config.importers.CremaDImportConfig`、`ser_lib.config.CremaDImportConfig`、`ser_lib.data.importers.crema_d.CremaDImportConfig`、`ser_lib.data.importers.CremaDImportConfig`。

源码：[ser_lib/config/importers.py:49](../ser_lib/config/importers.py#L49)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `audio_directory` | `str` | `'AudioWAV'` |
| `demographics_file` | `str &#124; None` | `'VideoDemographics.csv'` |
| `encoding` | `str` | `'utf-8-sig'` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |
| `speaker_splits` | `dict[str, list[str]] &#124; None` | `None` |

<a id="ser_lib-config-importers-csemotionsimportconfig"></a>

#### `ser_lib.config.importers.CsemotionsImportConfig`

公开导入：`ser_lib.config.importers.CsemotionsImportConfig`、`ser_lib.config.CsemotionsImportConfig`、`ser_lib.data.importers.csemotions.CsemotionsImportConfig`、`ser_lib.data.importers.CsemotionsImportConfig`。

源码：[ser_lib/config/importers.py:41](../ser_lib/config/importers.py#L41)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `metadata_file` | `str` | `'csemotions_metadata.csv'` |
| `audio_directory` | `str` | `'wav_data'` |
| `encoding` | `str` | `'utf-8-sig'` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |
| `speaker_splits` | `dict[str, list[str]] &#124; None` | `None` |

<a id="ser_lib-config-importers-csvimportconfig"></a>

#### `ser_lib.config.importers.CsvImportConfig`

公开导入：`ser_lib.config.importers.CsvImportConfig`、`ser_lib.config.CsvImportConfig`、`ser_lib.data.importers.csv_importer.CsvImportConfig`、`ser_lib.data.importers.CsvImportConfig`。

源码：[ser_lib/config/importers.py:28](../ser_lib/config/importers.py#L28)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `audio_path_column` | `str` | `Field(default='audio_path', min_length=1)` |
| `label_column` | `str &#124; None` | `Field(default='label')` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |
| `speaker_column` | `str &#124; None` | `None` |
| `metadata_columns` | `list[str]` | `Field(default_factory=list)` |
| `uid_column` | `str &#124; None` | `None` |
| `uid_prefix` | `str` | `Field(default='audio', min_length=1)` |
| `delimiter` | `str` | `Field(default=',', min_length=1, max_length=1)` |
| `encoding` | `str` | `'utf-8-sig'` |
| `root` | `Path &#124; None` | `None` |

<a id="ser_lib-config-importers-default_audio_extensions"></a>

#### `ser_lib.config.importers.DEFAULT_AUDIO_EXTENSIONS`

公开导入：`ser_lib.config.importers.DEFAULT_AUDIO_EXTENSIONS`、`ser_lib.config.DEFAULT_AUDIO_EXTENSIONS`、`ser_lib.data.importers.folder.DEFAULT_AUDIO_EXTENSIONS`。

源码：[ser_lib/config/importers.py:12](../ser_lib/config/importers.py#L12)。

类型别名、常量或共享实例定义：

```python
DEFAULT_AUDIO_EXTENSIONS = ('.wav', '.flac', '.mp3', '.ogg', '.m4a', '.wv', '.aiff')
```

<a id="ser_lib-config-importers-emotiontalkimportconfig"></a>

#### `ser_lib.config.importers.EmotionTalkImportConfig`

公开导入：`ser_lib.config.importers.EmotionTalkImportConfig`、`ser_lib.config.EmotionTalkImportConfig`、`ser_lib.data.importers.emotiontalk.EmotionTalkImportConfig`、`ser_lib.data.importers.EmotionTalkImportConfig`。

源码：[ser_lib/config/importers.py:57](../ser_lib/config/importers.py#L57)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `json_directory` | `str` | `'json'` |
| `audio_directory` | `str` | `'wav'` |
| `encoding` | `str` | `'utf-8'` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |
| `split_strategy` | `Literal['speaker_independent', 'official_dialogue']` | `'speaker_independent'` |
| `speaker_splits` | `dict[str, list[str]] &#124; None` | `None` |

<a id="ser_lib-config-importers-esdimportconfig"></a>

#### `ser_lib.config.importers.EsdImportConfig`

公开导入：`ser_lib.config.importers.EsdImportConfig`、`ser_lib.config.EsdImportConfig`、`ser_lib.data.importers.esd.EsdImportConfig`、`ser_lib.data.importers.EsdImportConfig`。

源码：[ser_lib/config/importers.py:70](../ser_lib/config/importers.py#L70)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `languages` | `list[Literal['zh', 'en']]` | `Field(default_factory=_default_esd_languages)` |
| `encoding` | `str` | `'utf-8-sig'` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |
| `speaker_splits` | `dict[str, list[str]] &#124; None` | `None` |

<a id="ser_lib-config-importers-folderimportconfig"></a>

#### `ser_lib.config.importers.FolderImportConfig`

公开导入：`ser_lib.config.importers.FolderImportConfig`、`ser_lib.config.FolderImportConfig`、`ser_lib.data.importers.folder.FolderImportConfig`、`ser_lib.data.importers.FolderImportConfig`。

源码：[ser_lib/config/importers.py:77](../ser_lib/config/importers.py#L77)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `audio_extensions` | `list[str]` | `Field(default_factory=lambda: list(DEFAULT_AUDIO_EXTENSIONS))` |
| `label_dir_level` | `int` | `Field(default=0, ge=0, le=2)` |
| `speaker_dir_level` | `int &#124; None` | `Field(default=None, ge=0, le=3)` |
| `label_mapping` | `dict[str, int] &#124; None` | `None` |
| `uid_prefix` | `str` | `Field(default='audio', min_length=1)` |
| `relative_paths` | `bool` | `True` |

<a id="ser_lib-config-importers-jsonlimportconfig"></a>

#### `ser_lib.config.importers.JsonlImportConfig`

公开导入：`ser_lib.config.importers.JsonlImportConfig`、`ser_lib.config.JsonlImportConfig`、`ser_lib.data.importers.jsonl_importer.JsonlImportConfig`、`ser_lib.data.importers.JsonlImportConfig`。

源码：[ser_lib/config/importers.py:97](../ser_lib/config/importers.py#L97)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid_prefix` | `str` | `Field(default='audio', min_length=1)` |
| `root` | `Path &#124; None` | `None` |

<a id="ser_lib-config-importers-ravdessimportconfig"></a>

#### `ser_lib.config.importers.RavdessImportConfig`

公开导入：`ser_lib.config.importers.RavdessImportConfig`、`ser_lib.config.RavdessImportConfig`、`ser_lib.data.importers.ravdess.RavdessImportConfig`、`ser_lib.data.importers.RavdessImportConfig`。

源码：[ser_lib/config/importers.py:102](../ser_lib/config/importers.py#L102)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `vocal_channel` | `Literal['speech', 'song', 'all']` | `'speech'` |
| `relative_paths` | `bool` | `True` |

<a id="ser_lib-config-inference-streamingconfig"></a>

#### `ser_lib.config.inference.StreamingConfig`

公开导入：`ser_lib.config.inference.StreamingConfig`、`ser_lib.config.StreamingConfig`、`ser_lib.inference.streaming.StreamingConfig`、`ser_lib.inference.StreamingConfig`。

源码：[ser_lib/config/inference.py:9](../ser_lib/config/inference.py#L9)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `input_sample_rate` | `int` | `16000` |
| `window_ms` | `int` | `2000` |
| `hop_ms` | `int` | `500` |
| `silence_rms_threshold` | `float` | `0.0` |
| `suppress_silence` | `bool` | `True` |
| `smoothing_alpha` | `float` | `1.0` |
| `max_chunk_ms` | `int` | `10000` |

构造时的字段约束：

- `ValueError('input_sample_rate 必须 > 0')`
- `ValueError('window_ms 和 hop_ms 必须 > 0')`
- `ValueError('hop_ms 不能大于 window_ms')`
- `ValueError('silence_rms_threshold 必须 >= 0')`
- `ValueError('smoothing_alpha 必须在 (0, 1] 内')`
- `ValueError('max_chunk_ms 必须 > 0')`

<a id="ser_lib-config-loader-load_yaml_mapping"></a>

#### `ser_lib.config.loader.load_yaml_mapping`

公开导入：`ser_lib.config.loader.load_yaml_mapping`、`ser_lib.config.load_yaml_mapping`。

源码：[ser_lib/config/loader.py:20](../ser_lib/config/loader.py#L20)。

```python
load_yaml_mapping(path: Path | str) -> tuple[dict[str, Any], Path]
```

安全读取 YAML 映射，并返回内容与规范化文件路径。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ConfigurationError(f'配置文件必须是 YAML 映射: {source}')`
- `ConfigurationError(f'无法读取 YAML 配置: {source}')`

<a id="ser_lib-config-loader-resolve_config_path"></a>

#### `ser_lib.config.loader.resolve_config_path`

公开导入：`ser_lib.config.loader.resolve_config_path`、`ser_lib.config.resolve_config_path`。

源码：[ser_lib/config/loader.py:13](../ser_lib/config/loader.py#L13)。

```python
resolve_config_path(value: Path | str, *, base_dir: Path | str) -> Path
```

相对 ``base_dir`` 解析路径，不依赖当前工作目录。

<a id="ser_lib-config-model-cnnbaselineconfig"></a>

#### `ser_lib.config.model.CNNBaselineConfig`

公开导入：`ser_lib.config.model.CNNBaselineConfig`、`ser_lib.config.CNNBaselineConfig`、`ser_lib.models.cnn_models.CNNBaselineConfig`、`ser_lib.models.CNNBaselineConfig`。

源码：[ser_lib/config/model.py:23](../ser_lib/config/model.py#L23)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `feature_dim` | `int` | `Field(ge=1)` |
| `num_classes` | `int` | `Field(ge=2)` |
| `hidden_dim` | `int` | `Field(default=128, ge=1)` |
| `dropout` | `float` | `Field(default=0.2, ge=0, lt=1)` |

<a id="ser_lib-config-model-grubaselineconfig"></a>

#### `ser_lib.config.model.GRUBaselineConfig`

公开导入：`ser_lib.config.model.GRUBaselineConfig`、`ser_lib.config.GRUBaselineConfig`、`ser_lib.models.rnn_models.GRUBaselineConfig`、`ser_lib.models.GRUBaselineConfig`。

源码：[ser_lib/config/model.py:30](../ser_lib/config/model.py#L30)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `feature_dim` | `int` | `Field(ge=1)` |
| `num_classes` | `int` | `Field(ge=2)` |
| `hidden_dim` | `int` | `Field(default=128, ge=1)` |
| `num_layers` | `int` | `Field(default=1, ge=1)` |
| `bidirectional` | `bool` | `True` |
| `dropout` | `float` | `Field(default=0.0, ge=0, lt=1)` |

<a id="ser_lib-config-model-hfaudioclassifierconfig"></a>

#### `ser_lib.config.model.HFAudioClassifierConfig`

公开导入：`ser_lib.config.model.HFAudioClassifierConfig`、`ser_lib.config.HFAudioClassifierConfig`、`ser_lib.models.HFAudioClassifierConfig`、`ser_lib.models.adapters.huggingface.HFAudioClassifierConfig`。

源码：[ser_lib/config/model.py:86](../ser_lib/config/model.py#L86)。

Hugging Face 音频模型配置；定义本身不依赖 transformers。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `num_classes` | `int` | `Field(ge=2)` |
| `pretrained_model_name_or_path` | `str &#124; None` | `None` |
| `encoder_config` | `dict[str, Any] &#124; None` | `None` |
| `local_files_only` | `bool` | `True` |
| `revision` | `str &#124; None` | `None` |
| `freeze_encoder` | `bool` | `False` |
| `dropout` | `float` | `Field(default=0.1, ge=0, lt=1)` |
| `pooling` | `Literal['mean', 'max']` | `'mean'` |
| `expected_sample_rate` | `int` | `Field(default=16000, ge=1000, le=192000)` |
| `strategy` | `Literal['encoder_head', 'audio_classification']` | `'encoder_head'` |
| `reset_classifier_head` | `bool` | `False` |
| `label_names` | `dict[int, str] &#124; None` | `None` |
| `processor_name_or_path` | `str &#124; None` | `None` |
| `processor_config` | `HFProcessorConfig &#124; None` | `None` |
| `processor_revision` | `str &#124; None` | `None` |

<a id="ser_lib-config-model-hfprocessorconfig"></a>

#### `ser_lib.config.model.HFProcessorConfig`

公开导入：`ser_lib.config.model.HFProcessorConfig`、`ser_lib.config.HFProcessorConfig`、`ser_lib.models.HFProcessorConfig`、`ser_lib.models.adapters.huggingface.HFProcessorConfig`。

源码：[ser_lib/config/model.py:65](../ser_lib/config/model.py#L65)。

可离线重建的 HF waveform feature extractor 快照。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `class_name` | `Literal['Wav2Vec2FeatureExtractor']` | `必填（无默认值）` |
| `config` | `dict[str, Any]` | `必填（无默认值）` |

<a id="ser_lib-config-model-modelconfig"></a>

#### `ser_lib.config.model.ModelConfig`

公开导入：`ser_lib.config.model.ModelConfig`、`ser_lib.config.ModelConfig`、`ser_lib.engine.ModelConfig`。

源码：[ser_lib/config/model.py:16](../ser_lib/config/model.py#L16)。

注册表模型及其构造参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `str` | `Field(min_length=1)` |
| `params` | `dict[str, Any]` | `Field(default_factory=dict)` |

<a id="ser_lib-config-model-torchdtypename"></a>

#### `ser_lib.config.model.TorchDTypeName`

公开导入：`ser_lib.config.model.TorchDTypeName`、`ser_lib.config.TorchDTypeName`。

源码：[ser_lib/config/model.py:150](../ser_lib/config/model.py#L150)。

类型别名、常量或共享实例定义：

```python
TorchDTypeName = Literal['float16', 'float32', 'float64', 'bfloat16', 'int8', 'int16', 'int32', 'int64', 'uint8', 'bool']
```

<a id="ser_lib-config-model-torchlayoutname"></a>

#### `ser_lib.config.model.TorchLayoutName`

公开导入：`ser_lib.config.model.TorchLayoutName`、`ser_lib.config.TorchLayoutName`。

源码：[ser_lib/config/model.py:162](../ser_lib/config/model.py#L162)。

类型别名、常量或共享实例定义：

```python
TorchLayoutName = Literal['T', 'FT', 'TD', 'D', 'CFT']
```

<a id="ser_lib-config-model-torchmodeladapterconfig"></a>

#### `ser_lib.config.model.TorchModelAdapterConfig`

公开导入：`ser_lib.config.model.TorchModelAdapterConfig`、`ser_lib.config.TorchModelAdapterConfig`。

源码：[ser_lib/config/model.py:192](../ser_lib/config/model.py#L192)。

普通 ``torch.nn.Module`` 的可移植 SER adapter 配置。

``factory_id=None`` 只允许进程内手工包装，可用于训练、评估、推理与可信
checkpoint；可分发 artifact 必须提供已注册 factory ID。配置中不接受 callable，
artifact 只保存 JSON 数据与注册 ID。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `factory_id` | `str &#124; None` | `Field(default=None, min_length=1)` |
| `factory_params` | `dict[str, Any]` | `Field(default_factory=dict)` |
| `input_map` | `dict[str, str]` | `Field(min_length=1)` |
| `output` | `TorchOutputMappingConfig` | `Field(default_factory=TorchOutputMappingConfig)` |
| `required_inputs` | `dict[str, TorchTensorSpecConfig]` | `Field(min_length=1)` |
| `supports_masks` | `bool` | `False` |
| `supports_variable_length` | `bool` | `False` |
| `num_classes` | `int` | `Field(ge=2)` |
| `expected_sample_rate` | `int &#124; None` | `Field(default=None, ge=1000, le=192000)` |
| `freeze_module` | `bool` | `False` |

<a id="ser_lib-config-model-torchoutputmappingconfig"></a>

#### `ser_lib.config.model.TorchOutputMappingConfig`

公开导入：`ser_lib.config.model.TorchOutputMappingConfig`、`ser_lib.config.TorchOutputMappingConfig`。

源码：[ser_lib/config/model.py:180](../ser_lib/config/model.py#L180)。

普通 nn.Module 输出到 ModelOutput 的显式选择器。

``logits=None`` 表示模块本身直接返回 logits tensor；字符串选择器可读取
mapping key、tuple/list 索引或对象属性，并支持 ``a.b.0`` 形式的嵌套路径。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `logits` | `str &#124; None` | `Field(default=None, min_length=1)` |
| `embeddings` | `str &#124; None` | `Field(default=None, min_length=1)` |
| `loss` | `str &#124; None` | `Field(default=None, min_length=1)` |

<a id="ser_lib-config-model-torchtensorspecconfig"></a>

#### `ser_lib.config.model.TorchTensorSpecConfig`

公开导入：`ser_lib.config.model.TorchTensorSpecConfig`、`ser_lib.config.TorchTensorSpecConfig`。

源码：[ser_lib/config/model.py:165](../ser_lib/config/model.py#L165)。

Torch adapter 所需 TensorSpec 的 JSON-safe 表示。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `layout` | `TorchLayoutName` | `必填（无默认值）` |
| `dtype` | `TorchDTypeName` | `'float32'` |
| `feature_dim` | `int &#124; None` | `Field(default=None, ge=1)` |
| `pad_value` | `float` | `0.0` |

<a id="ser_lib-config-model-transformerbaselineconfig"></a>

#### `ser_lib.config.model.TransformerBaselineConfig`

公开导入：`ser_lib.config.model.TransformerBaselineConfig`、`ser_lib.config.TransformerBaselineConfig`、`ser_lib.models.transformer_models.TransformerBaselineConfig`、`ser_lib.models.TransformerBaselineConfig`。

源码：[ser_lib/config/model.py:45](../ser_lib/config/model.py#L45)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `feature_dim` | `int` | `Field(ge=1)` |
| `num_classes` | `int` | `Field(ge=2)` |
| `d_model` | `int` | `Field(default=128, ge=4)` |
| `num_heads` | `int` | `Field(default=4, ge=1)` |
| `num_layers` | `int` | `Field(default=2, ge=1)` |
| `feedforward_dim` | `int` | `Field(default=256, ge=1)` |
| `dropout` | `float` | `Field(default=0.1, ge=0, lt=1)` |
| `activation` | `Literal['relu', 'gelu']` | `'gelu'` |
| `norm_first` | `bool` | `False` |

<a id="ser_lib-config-optimizer-adamconfig"></a>

#### `ser_lib.config.optimizer.AdamConfig`

公开导入：`ser_lib.config.optimizer.AdamConfig`、`ser_lib.config.AdamConfig`、`ser_lib.engine.optim.AdamConfig`、`ser_lib.engine.AdamConfig`。

源码：[ser_lib/config/optimizer.py:21](../ser_lib/config/optimizer.py#L21)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['adam']` | `'adam'` |
| `learning_rate` | `float` | `Field(default=0.001, gt=0, allow_inf_nan=False)` |
| `weight_decay` | `float` | `Field(default=0.0, ge=0, allow_inf_nan=False)` |
| `beta1` | `float` | `Field(default=0.9, ge=0, lt=1, allow_inf_nan=False)` |
| `beta2` | `float` | `Field(default=0.999, ge=0, lt=1, allow_inf_nan=False)` |
| `eps` | `float` | `Field(default=1e-08, gt=0, allow_inf_nan=False)` |

<a id="ser_lib-config-optimizer-adamwconfig"></a>

#### `ser_lib.config.optimizer.AdamWConfig`

公开导入：`ser_lib.config.optimizer.AdamWConfig`、`ser_lib.config.AdamWConfig`、`ser_lib.engine.optim.AdamWConfig`、`ser_lib.engine.AdamWConfig`。

源码：[ser_lib/config/optimizer.py:12](../ser_lib/config/optimizer.py#L12)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['adamw']` | `'adamw'` |
| `learning_rate` | `float` | `Field(default=0.001, gt=0, allow_inf_nan=False)` |
| `weight_decay` | `float` | `Field(default=0.0, ge=0, allow_inf_nan=False)` |
| `beta1` | `float` | `Field(default=0.9, ge=0, lt=1, allow_inf_nan=False)` |
| `beta2` | `float` | `Field(default=0.999, ge=0, lt=1, allow_inf_nan=False)` |
| `eps` | `float` | `Field(default=1e-08, gt=0, allow_inf_nan=False)` |

<a id="ser_lib-config-optimizer-optimizerconfig"></a>

#### `ser_lib.config.optimizer.OptimizerConfig`

公开导入：`ser_lib.config.optimizer.OptimizerConfig`、`ser_lib.config.OptimizerConfig`、`ser_lib.engine.optim.OptimizerConfig`。

源码：[ser_lib/config/optimizer.py:44](../ser_lib/config/optimizer.py#L44)。

类型别名、常量或共享实例定义：

```python
OptimizerConfig = AdamWConfig | AdamConfig | SGDConfig
```

<a id="ser_lib-config-optimizer-sgdconfig"></a>

#### `ser_lib.config.optimizer.SGDConfig`

公开导入：`ser_lib.config.optimizer.SGDConfig`、`ser_lib.config.SGDConfig`、`ser_lib.engine.optim.SGDConfig`、`ser_lib.engine.SGDConfig`。

源码：[ser_lib/config/optimizer.py:30](../ser_lib/config/optimizer.py#L30)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['sgd']` | `'sgd'` |
| `learning_rate` | `float` | `Field(default=0.01, gt=0, allow_inf_nan=False)` |
| `weight_decay` | `float` | `Field(default=0.0, ge=0, allow_inf_nan=False)` |
| `momentum` | `float` | `Field(default=0.0, ge=0, lt=1)` |
| `nesterov` | `bool` | `False` |

<a id="ser_lib-config-optimizer-parse_optimizer_config"></a>

#### `ser_lib.config.optimizer.parse_optimizer_config`

公开导入：`ser_lib.config.optimizer.parse_optimizer_config`、`ser_lib.config.parse_optimizer_config`、`ser_lib.engine.optim.parse_optimizer_config`、`ser_lib.engine.parse_optimizer_config`。

源码：[ser_lib/config/optimizer.py:47](../ser_lib/config/optimizer.py#L47)。

```python
parse_optimizer_config(raw: dict[str, Any]) -> OptimizerConfig
```

解析白名单 optimizer payload；这是 schema 解析，不构建 Torch optimizer。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f"optimizer 包含未知字段: {sorted(set(raw) - {'type', 'params'})}")`
- `ValueError('optimizer.params 必须是映射')`
- `ValueError(f'未知 optimizer.type={kind!r}，可用: {sorted(models)}')`

<a id="ser_lib-config-presets-build_experiment_config"></a>

#### `ser_lib.config.presets.build_experiment_config`

公开导入：`ser_lib.config.presets.build_experiment_config`、`ser_lib.config.build_experiment_config`。

源码：[ser_lib/config/presets.py:213](../ser_lib/config/presets.py#L213)。

```python
build_experiment_config(preset_id: str, overrides: Mapping[str, Any] | None=None) -> ExperimentConfig
```

从 preset 构造 ExperimentConfig；override 后重新执行严格校验。

<a id="ser_lib-config-presets-get_experiment_preset_payload"></a>

#### `ser_lib.config.presets.get_experiment_preset_payload`

公开导入：`ser_lib.config.presets.get_experiment_preset_payload`、`ser_lib.config.get_experiment_preset_payload`。

源码：[ser_lib/config/presets.py:205](../ser_lib/config/presets.py#L205)。

```python
get_experiment_preset_payload(preset_id: str) -> dict[str, Any]
```

返回 preset payload 的深拷贝，调用方修改不会污染内置模板。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `KeyError(f'未知 experiment preset: {preset_id}')`

<a id="ser_lib-config-presets-list_experiment_preset_ids"></a>

#### `ser_lib.config.presets.list_experiment_preset_ids`

公开导入：`ser_lib.config.presets.list_experiment_preset_ids`、`ser_lib.config.list_experiment_preset_ids`。

源码：[ser_lib/config/presets.py:200](../ser_lib/config/presets.py#L200)。

```python
list_experiment_preset_ids() -> tuple[str, ...]
```

返回稳定、排序后的内置 preset ID，不构造运行时组件。

<a id="ser_lib-config-representations-acousticfeaturename"></a>

#### `ser_lib.config.representations.AcousticFeatureName`

公开导入：`ser_lib.config.representations.AcousticFeatureName`、`ser_lib.config.AcousticFeatureName`。

源码：[ser_lib/config/representations.py:80](../ser_lib/config/representations.py#L80)。

类型别名、常量或共享实例定义：

```python
AcousticFeatureName = Literal['f0', 'rms', 'zcr', 'spectral_centroid', 'spectral_rolloff', 'spectral_flatness', 'spectral_flux', 'delta', 'jitter_shimmer_hnr']
```

<a id="ser_lib-config-representations-acousticfeaturesconfig"></a>

#### `ser_lib.config.representations.AcousticFeaturesConfig`

公开导入：`ser_lib.config.representations.AcousticFeaturesConfig`、`ser_lib.config.AcousticFeaturesConfig`、`ser_lib.data.representations.AcousticFeaturesConfig`。

源码：[ser_lib/config/representations.py:93](../ser_lib/config/representations.py#L93)。

AcousticFeatures 参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `features` | `list[AcousticFeatureName]` | `Field(..., min_length=1)` |
| `sample_rate` | `int` | `Field(default=16000, ge=1000, le=192000)` |
| `hop_length` | `int` | `Field(default=256, ge=1, le=4096)` |
| `win_length` | `int` | `Field(default=400, ge=2, le=8192)` |
| `n_fft` | `int` | `Field(default=1024, ge=32, le=8192)` |
| `roll_percent` | `float` | `Field(default=0.85, gt=0.0, lt=1.0)` |
| `delta_win_length` | `int` | `Field(default=5, ge=3, le=21)` |

<a id="ser_lib-config-representations-compositeconfig"></a>

#### `ser_lib.config.representations.CompositeConfig`

公开导入：`ser_lib.config.representations.CompositeConfig`、`ser_lib.config.CompositeConfig`、`ser_lib.data.representations.CompositeConfig`。

源码：[ser_lib/config/representations.py:124](../ser_lib/config/representations.py#L124)。

组合表示参数：``{key: 组件配置}``。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `outputs` | `dict[str, dict[str, Any]]` | `Field(..., min_length=1)` |

<a id="ser_lib-config-representations-logmelconfig"></a>

#### `ser_lib.config.representations.LogMelConfig`

公开导入：`ser_lib.config.representations.LogMelConfig`、`ser_lib.config.LogMelConfig`、`ser_lib.data.representations.spectral.LogMelConfig`、`ser_lib.data.representations.LogMelConfig`。

源码：[ser_lib/config/representations.py:51](../ser_lib/config/representations.py#L51)。

Log-Mel 参数。

基类：`MelConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `power` | `float` | `Field(default=2.0, ge=1.0, le=2.0)` |
| `top_db` | `float` | `Field(default=80.0, ge=10.0, le=120.0)` |

<a id="ser_lib-config-representations-mfccconfig"></a>

#### `ser_lib.config.representations.MFCCConfig`

公开导入：`ser_lib.config.representations.MFCCConfig`、`ser_lib.config.MFCCConfig`、`ser_lib.data.representations.spectral.MFCCConfig`、`ser_lib.data.representations.MFCCConfig`。

源码：[ser_lib/config/representations.py:64](../ser_lib/config/representations.py#L64)。

MFCC 参数；Mel 参数封装在组件内部。

基类：`SpectralConfigBase`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `n_mels` | `int` | `Field(default=80, ge=16, le=512)` |
| `n_mfcc` | `int` | `Field(default=40, ge=10, le=128)` |
| `dct_norm` | `Literal['ortho'] &#124; None` | `'ortho'` |
| `mel_norm` | `Literal['slaney'] &#124; None` | `'slaney'` |
| `mel_scale` | `Literal['htk', 'slaney']` | `'htk'` |

<a id="ser_lib-config-representations-melconfig"></a>

#### `ser_lib.config.representations.MelConfig`

公开导入：`ser_lib.config.representations.MelConfig`、`ser_lib.config.MelConfig`、`ser_lib.data.representations.spectral.MelConfig`、`ser_lib.data.representations.MelConfig`。

源码：[ser_lib/config/representations.py:44](../ser_lib/config/representations.py#L44)。

Mel 谱公共参数。

基类：`SpectralConfigBase`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `n_mels` | `int` | `Field(default=80, ge=16, le=512)` |
| `power` | `float` | `Field(default=2.0, ge=1.0, le=3.0)` |

<a id="ser_lib-config-representations-rawwaveformconfig"></a>

#### `ser_lib.config.representations.RawWaveformConfig`

公开导入：`ser_lib.config.representations.RawWaveformConfig`、`ser_lib.config.RawWaveformConfig`、`ser_lib.data.representations.RawWaveformConfig`。

源码：[ser_lib/config/representations.py:12](../ser_lib/config/representations.py#L12)。

RawWaveform 无参数；保留空模型用于 schema 生成与未知参数报错。

基类：`StrictConfig`。继承的字段/方法继续适用。

<a id="ser_lib-config-representations-spectralconfigbase"></a>

#### `ser_lib.config.representations.SpectralConfigBase`

公开导入：`ser_lib.config.representations.SpectralConfigBase`、`ser_lib.config.SpectralConfigBase`。

源码：[ser_lib/config/representations.py:16](../ser_lib/config/representations.py#L16)。

谱图类表示的公共参数（对齐 torchaudio 默认值）。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `sample_rate` | `int` | `Field(default=16000, ge=1000, le=192000)` |
| `n_fft` | `int` | `Field(default=400, ge=32, le=8192)` |
| `win_length` | `int &#124; None` | `Field(default=None, ge=32, le=8192)` |
| `hop_length` | `int` | `Field(default=200, ge=1, le=4096)` |
| `f_min` | `float` | `Field(default=0.0, ge=0.0)` |
| `f_max` | `float &#124; None` | `Field(default=None, ge=0.0)` |
| `center` | `bool` | `True` |
| `pad_mode` | `str` | `'reflect'` |

<a id="ser_lib-config-representations-spectrogramconfig"></a>

#### `ser_lib.config.representations.SpectrogramConfig`

公开导入：`ser_lib.config.representations.SpectrogramConfig`、`ser_lib.config.SpectrogramConfig`、`ser_lib.data.representations.spectral.SpectrogramConfig`、`ser_lib.data.representations.SpectrogramConfig`。

源码：[ser_lib/config/representations.py:38](../ser_lib/config/representations.py#L38)。

线性谱图参数。

基类：`SpectralConfigBase`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `power` | `float` | `Field(default=2.0, ge=0.0, le=3.0)` |

<a id="ser_lib-config-scheduler-cosineschedulerconfig"></a>

#### `ser_lib.config.scheduler.CosineSchedulerConfig`

公开导入：`ser_lib.config.scheduler.CosineSchedulerConfig`、`ser_lib.config.CosineSchedulerConfig`、`ser_lib.engine.optim.CosineSchedulerConfig`、`ser_lib.engine.CosineSchedulerConfig`。

源码：[ser_lib/config/scheduler.py:18](../ser_lib/config/scheduler.py#L18)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['cosine']` | `'cosine'` |
| `t_max` | `int` | `Field(ge=1)` |
| `eta_min` | `float` | `Field(default=0.0, ge=0)` |

<a id="ser_lib-config-scheduler-schedulerconfig"></a>

#### `ser_lib.config.scheduler.SchedulerConfig`

公开导入：`ser_lib.config.scheduler.SchedulerConfig`、`ser_lib.config.SchedulerConfig`、`ser_lib.engine.optim.SchedulerConfig`。

源码：[ser_lib/config/scheduler.py:24](../ser_lib/config/scheduler.py#L24)。

类型别名、常量或共享实例定义：

```python
SchedulerConfig = StepSchedulerConfig | CosineSchedulerConfig
```

<a id="ser_lib-config-scheduler-stepschedulerconfig"></a>

#### `ser_lib.config.scheduler.StepSchedulerConfig`

公开导入：`ser_lib.config.scheduler.StepSchedulerConfig`、`ser_lib.config.StepSchedulerConfig`、`ser_lib.engine.optim.StepSchedulerConfig`、`ser_lib.engine.StepSchedulerConfig`。

源码：[ser_lib/config/scheduler.py:12](../ser_lib/config/scheduler.py#L12)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['step']` | `'step'` |
| `step_size` | `int` | `Field(default=10, ge=1)` |
| `gamma` | `float` | `Field(default=0.1, gt=0, le=1)` |

<a id="ser_lib-config-scheduler-parse_scheduler_config"></a>

#### `ser_lib.config.scheduler.parse_scheduler_config`

公开导入：`ser_lib.config.scheduler.parse_scheduler_config`、`ser_lib.config.parse_scheduler_config`、`ser_lib.engine.optim.parse_scheduler_config`、`ser_lib.engine.parse_scheduler_config`。

源码：[ser_lib/config/scheduler.py:27](../ser_lib/config/scheduler.py#L27)。

```python
parse_scheduler_config(raw: dict[str, Any] | None) -> SchedulerConfig | None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f"scheduler 包含未知字段: {sorted(set(raw) - {'type', 'params'})}")`
- `ValueError('scheduler.params 必须是映射')`
- `ValueError(f'未知 scheduler.type={kind!r}，可用: {sorted(models)}')`

<a id="ser_lib-config-training-lossconfig"></a>

#### `ser_lib.config.training.LossConfig`

公开导入：`ser_lib.config.training.LossConfig`、`ser_lib.config.LossConfig`、`ser_lib.engine.objectives.LossConfig`、`ser_lib.engine.LossConfig`。

源码：[ser_lib/config/training.py:49](../ser_lib/config/training.py#L49)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['cross_entropy', 'focal']` | `'cross_entropy'` |
| `class_weights` | `list[float] &#124; None` | `None` |
| `label_smoothing` | `float` | `Field(default=0.0, ge=0.0, lt=1.0)` |
| `focal_gamma` | `float` | `Field(default=2.0, ge=0.0)` |

<a id="ser_lib-config-training-observabilityconfig"></a>

#### `ser_lib.config.training.ObservabilityConfig`

公开导入：`ser_lib.config.training.ObservabilityConfig`、`ser_lib.config.ObservabilityConfig`、`ser_lib.engine.ObservabilityConfig`、`ser_lib.engine.training.trainer.ObservabilityConfig`、`ser_lib.engine.training.ObservabilityConfig`。

源码：[ser_lib/config/training.py:13](../ser_lib/config/training.py#L13)。

训练运行时事件频率与轻量 ETA 参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `progress_interval_batches` | `int` | `Field(default=1, ge=1)` |
| `metric_interval_batches` | `int` | `Field(default=10, ge=1)` |
| `eta_window_batches` | `int` | `Field(default=20, ge=1)` |
| `eta_warmup_batches` | `int` | `Field(default=3, ge=1)` |

<a id="ser_lib-config-training-samplingconfig"></a>

#### `ser_lib.config.training.SamplingConfig`

公开导入：`ser_lib.config.training.SamplingConfig`、`ser_lib.config.SamplingConfig`、`ser_lib.engine.objectives.SamplingConfig`、`ser_lib.engine.SamplingConfig`。

源码：[ser_lib/config/training.py:64](../ser_lib/config/training.py#L64)。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `type` | `Literal['shuffle', 'weighted']` | `'shuffle'` |
| `class_weights` | `list[float] &#124; None` | `None` |
| `replacement` | `bool` | `True` |
| `num_samples` | `int &#124; None` | `Field(default=None, ge=1)` |

<a id="ser_lib-config-training-trainerconfig"></a>

#### `ser_lib.config.training.TrainerConfig`

公开导入：`ser_lib.config.training.TrainerConfig`、`ser_lib.config.TrainerConfig`、`ser_lib.engine.TrainerConfig`、`ser_lib.engine.training.trainer.TrainerConfig`、`ser_lib.engine.training.TrainerConfig`。

源码：[ser_lib/config/training.py:28](../ser_lib/config/training.py#L28)。

表示无关的训练循环配置；optimizer 参数不属于本节点。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `epochs` | `int` | `Field(default=10, ge=1)` |
| `device` | `str` | `'cpu'` |
| `seed` | `int` | `Field(default=42, ge=0)` |
| `deterministic` | `bool` | `True` |
| `amp` | `bool` | `False` |
| `gradient_clip_norm` | `float &#124; None` | `Field(default=None, gt=0)` |
| `gradient_accumulation_steps` | `int` | `Field(default=1, ge=1)` |
| `checkpoint_dir` | `Path &#124; None` | `None` |
| `validation_interval` | `int` | `Field(default=1, ge=1)` |
| `monitor` | `Literal['val_loss', 'val_accuracy', 'val_uar', 'val_macro_f1']` | `'val_loss'` |
| `early_stopping_patience` | `int &#124; None` | `Field(default=None, ge=1)` |
| `early_stopping_min_delta` | `float` | `Field(default=0.0, ge=0.0)` |
| `save_best` | `bool` | `True` |
| `save_last` | `bool` | `True` |

<a id="ser_lib-config-transforms-gaussiannoiseconfig"></a>

#### `ser_lib.config.transforms.GaussianNoiseConfig`

公开导入：`ser_lib.config.transforms.GaussianNoiseConfig`、`ser_lib.config.GaussianNoiseConfig`、`ser_lib.data.transforms.waveform.GaussianNoiseConfig`。

源码：[ser_lib/config/transforms.py:14](../ser_lib/config/transforms.py#L14)。

高斯噪声参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `snr_db` | `float` | `Field(default=15.0, gt=0.0, le=120.0, description='信噪比 (dB)')` |

<a id="ser_lib-config-transforms-normalizeconfig"></a>

#### `ser_lib.config.transforms.NormalizeConfig`

公开导入：`ser_lib.config.transforms.NormalizeConfig`、`ser_lib.config.NormalizeConfig`、`ser_lib.data.transforms.waveform.NormalizeConfig`。

源码：[ser_lib/config/transforms.py:10](../ser_lib/config/transforms.py#L10)。

Normalize 无参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

<a id="ser_lib-config-transforms-pitchshiftconfig"></a>

#### `ser_lib.config.transforms.PitchShiftConfig`

公开导入：`ser_lib.config.transforms.PitchShiftConfig`、`ser_lib.config.PitchShiftConfig`、`ser_lib.data.transforms.waveform.PitchShiftConfig`。

源码：[ser_lib/config/transforms.py:39](../ser_lib/config/transforms.py#L39)。

音高偏移参数。sample_rate 由 pipeline 构建时按 AudioLoader 配置注入。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `sample_rate` | `int` | `Field(default=16000, ge=1000, le=192000)` |
| `n_steps` | `int` | `Field(default=4, ge=-24, le=24)` |

<a id="ser_lib-config-transforms-specmaskingconfig"></a>

#### `ser_lib.config.transforms.SpecMaskingConfig`

公开导入：`ser_lib.config.transforms.SpecMaskingConfig`、`ser_lib.config.SpecMaskingConfig`、`ser_lib.data.transforms.feature.SpecMaskingConfig`、`ser_lib.data.transforms.SpecMaskingConfig`。

源码：[ser_lib/config/transforms.py:52](../ser_lib/config/transforms.py#L52)。

SpecAugment 掩码参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `time_mask_param` | `int` | `Field(default=30, ge=1, description='时间掩码最大宽度')` |
| `freq_mask_param` | `int` | `Field(default=15, ge=1, description='频率掩码最大宽度')` |

<a id="ser_lib-config-transforms-timeshiftconfig"></a>

#### `ser_lib.config.transforms.TimeShiftConfig`

公开导入：`ser_lib.config.transforms.TimeShiftConfig`、`ser_lib.config.TimeShiftConfig`、`ser_lib.data.transforms.waveform.TimeShiftConfig`。

源码：[ser_lib/config/transforms.py:20](../ser_lib/config/transforms.py#L20)。

时间平移参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `max_ratio` | `float` | `Field(default=0.2, ge=0.0, le=1.0, description='最大平移比例')` |

<a id="ser_lib-config-transforms-timestretchconfig"></a>

#### `ser_lib.config.transforms.TimeStretchConfig`

公开导入：`ser_lib.config.transforms.TimeStretchConfig`、`ser_lib.config.TimeStretchConfig`、`ser_lib.data.transforms.waveform.TimeStretchConfig`。

源码：[ser_lib/config/transforms.py:46](../ser_lib/config/transforms.py#L46)。

时间拉伸参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `rate` | `float` | `Field(default=1.2, gt=0.1, le=4.0)` |

<a id="ser_lib-config-transforms-volumescaleconfig"></a>

#### `ser_lib.config.transforms.VolumeScaleConfig`

公开导入：`ser_lib.config.transforms.VolumeScaleConfig`、`ser_lib.config.VolumeScaleConfig`、`ser_lib.data.transforms.waveform.VolumeScaleConfig`。

源码：[ser_lib/config/transforms.py:26](../ser_lib/config/transforms.py#L26)。

音量缩放参数。

基类：`StrictConfig`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `gain_min` | `float` | `Field(default=0.5, gt=0.0)` |
| `gain_max` | `float` | `Field(default=1.5, gt=0.0)` |

<a id="ser_lib-data-audio-audiofileinfo"></a>

#### `ser_lib.data.audio.AudioFileInfo`

公开导入：`ser_lib.data.audio.AudioFileInfo`。

源码：[ser_lib/data/audio.py:39](../ser_lib/data/audio.py#L39)。

与具体解码库无关的稳定音频 header 信息。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `sample_rate` | `int` | `必填（无默认值）` |
| `num_frames` | `int` | `必填（无默认值）` |
| `num_channels` | `int` | `必填（无默认值）` |
| `backend` | `AudioBackend` | `必填（无默认值）` |

<a id="ser_lib-data-audio-audioloader"></a>

#### `ser_lib.data.audio.AudioLoader`

公开导入：`ser_lib.data.audio.AudioLoader`、`ser_lib.data.AudioLoader`。

源码：[ser_lib/data/audio.py:159](../ser_lib/data/audio.py#L159)。

从 :class:`AudioRecord` 加载音频并输出标准化的 :class:`AudioData`。

##### `__init__`

```python
__init__(self, config: AudioConfig | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `SERDataError(f"不支持的音频后端: {config.backend!r}，当前支持 'soundfile' 与 'torchaudio'")`
- `SERDataError(f'target_sample_rate 必须为正，实际: {config.target_sample_rate}')`

##### `load`

```python
load(self, record: AudioRecord, *, base_dir: Path | None=None) -> AudioData
```

加载一条记录对应的音频。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `AudioNotFoundError('音频文件不存在', uid=uid, path=path, component='audio_loader', stage='resolve')`
- `AudioDecodeError('音频路径不是文件', uid=uid, path=path, component='audio_loader', stage='resolve')`
- `InvalidAudioSegmentError('解码结果为空音频（0 帧）', uid=uid, path=path, component='audio_loader', stage='decode')`
- `AudioDecodeError('音频包含 NaN/Inf，拒绝加载（不做自动替换）', uid=uid, path=path, component='audio_loader', stage='validate')`
- `InvalidAudioSegmentError('重采样后音频为空', uid=uid, path=path, component='audio_loader', stage='resample')`
- `AudioDecodeError('读取音频元信息失败', uid=uid, path=path, component='audio_loader', stage='probe')`
- `AudioDecodeError('音频解码失败', uid=uid, path=path, component='audio_loader', stage='decode')`

##### `resolve_path`

调用方式：静态方法。

```python
resolve_path(audio_path: Path, base_dir: Path | None) -> Path
```

解析音频路径：绝对路径直接规范化，相对路径基于 base_dir。

<a id="ser_lib-data-audio-audioloaderconfig"></a>

#### `ser_lib.data.audio.AudioLoaderConfig`

公开导入：`ser_lib.data.audio.AudioLoaderConfig`、`ser_lib.data.AudioLoaderConfig`。

源码：[ser_lib/data/audio.py:156](../ser_lib/data/audio.py#L156)。

类型别名、常量或共享实例定义：

```python
AudioLoaderConfig = AudioConfig
```

<a id="ser_lib-data-audio-decode_audio"></a>

#### `ser_lib.data.audio.decode_audio`

公开导入：`ser_lib.data.audio.decode_audio`。

源码：[ser_lib/data/audio.py:124](../ser_lib/data/audio.py#L124)。

```python
decode_audio(path: Path | str, *, frame_offset: int=0, num_frames: int=-1, preferred_backend: AudioBackend='soundfile') -> tuple[torch.Tensor, int]
```

按 frame 范围解码音频并返回 ``([C,T], sample_rate)``。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'不支持的音频后端: {preferred_backend!r}')`
- `RuntimeError(f'TorchAudio 与 SoundFile 均无法解码音频；torchaudio={torchaudio_exc}; soundfile={soundfile_exc}')`

<a id="ser_lib-data-audio-probe_audio"></a>

#### `ser_lib.data.audio.probe_audio`

公开导入：`ser_lib.data.audio.probe_audio`。

源码：[ser_lib/data/audio.py:68](../ser_lib/data/audio.py#L68)。

```python
probe_audio(path: Path | str, *, preferred_backend: AudioBackend='soundfile') -> AudioFileInfo
```

读取音频 header；TorchAudio 不可用时透明回退到 SoundFile。

该函数只读取元信息，不解码整段音频，可供数据扫描和 profiling 共用。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'不支持的音频后端: {preferred_backend!r}')`
- `RuntimeError(f'TorchAudio 与 SoundFile 均无法读取音频元信息；torchaudio={torchaudio_exc}; soundfile={soundfile_exc}')`

<a id="ser_lib-data-cache-cachedrepresentation"></a>

#### `ser_lib.data.cache.CachedRepresentation`

公开导入：`ser_lib.data.CachedRepresentation`。

源码：[ser_lib/data/cache.py:31](../ser_lib/data/cache.py#L31)。

缓存任意确定性 Representation 的输出。

为保证片段和上游确定性处理不会碰撞，缓存键包含 waveform 内容哈希。
不建议包装随机增强后的表示；即使内容哈希保证正确，也会制造大量低命中缓存。

基类：`Representation`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, representation: Representation, directory: Path | str) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `output_specs`

调用方式：只读属性。

```python
output_specs(self) -> dict[str, TensorSpec]
```

##### `cache_key`

```python
cache_key(self, audio: AudioData) -> str
```

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('缓存 schema 版本不匹配')`

##### `entry_count`

```python
entry_count(self) -> int
```

##### `size_bytes`

```python
size_bytes(self) -> int
```

<a id="ser_lib-data-collate-collatestrategy"></a>

#### `ser_lib.data.collate.CollateStrategy`

公开导入：`ser_lib.data.CollateStrategy`。

源码：[ser_lib/data/collate.py:36](../ser_lib/data/collate.py#L36)。

批处理策略（与 BatchingConfig.type 对齐）。

基类：`str`、`Enum`。继承的字段/方法继续适用。

<a id="ser_lib-data-collate-sercollator"></a>

#### `ser_lib.data.collate.SERCollator`

公开导入：`ser_lib.data.SERCollator`。

源码：[ser_lib/data/collate.py:44](../ser_lib/data/collate.py#L44)。

基于输入规格的通用 Collator。

Args:
    specs: ``{key: TensorSpec}``，通常来自 ``pipeline.output_specs``。
    batching: 批处理配置。

##### `__init__`

```python
__init__(self, specs: dict[str, TensorSpec], batching: BatchingConfig) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `CollationError(f'fixed 策略要求为每个时序 key 配置 max_lengths，缺失: {missing}；时序 keys: {temporal_keys}', component='collator', stage='collator_build')`
- `CollationError(f'sliding 策略第一版仅支持一个主时序输入，实际时序 keys: {temporal_keys}。多输入滑窗需要先定义同步切窗语义', component='collator', stage='collator_build')`
- `CollationError(f'batching.primary_key ({batching.primary_key!r}) 与唯一的时序 key ({temporal_keys[0]!r}) 不一致', component='collator', stage='collator_build')`

##### `__call__`

```python
__call__(self, samples: Sequence[SERSample]) -> SERBatch
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `CollationError('batch 为空，无法处理', component='collator', stage='collate')`
- `CollationError(f"样本 '{sample.uid}' 输入 key 与 collator specs 不一致: 实际 {sorted(sample.inputs)}，期望 {sorted(expected_keys)}", uid=sample.uid, component='collator', stage='collate')`
- `CollationError(f'一个 batch 内不允许部分样本有标签、部分没有；无标签样本: {bad}', component='collator', stage='collate')`

<a id="ser_lib-data-collate-build_collator"></a>

#### `ser_lib.data.collate.build_collator`

公开导入：`ser_lib.data.build_collator`。

源码：[ser_lib/data/collate.py:297](../ser_lib/data/collate.py#L297)。

```python
build_collator(specs: dict[str, TensorSpec], batching: BatchingConfig) -> SERCollator
```

便捷构造函数。

<a id="ser_lib-data-dataset-serdataset"></a>

#### `ser_lib.data.dataset.SERDataset`

公开导入：`ser_lib.SERDataset`、`ser_lib.data.SERDataset`。

源码：[ser_lib/data/dataset.py:22](../ser_lib/data/dataset.py#L22)。

核心 SER 数据集。

Args:
    records: 音频记录序列（音频路径通常应已解析为绝对路径；相对路径
        需提供 ``base_dir``）。
    audio_loader: 共享的 AudioLoader。
    pipeline: 共享的 SamplePipeline。
    base_dir: 可选的相对路径解析基准目录（通常是 manifest root）。
    strict: 是否做运行时样本契约校验（§10.1；测试与开发默认开启）。

基类：`Dataset[SERSample]`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, records: Sequence[AudioRecord], audio_loader: AudioLoader, pipeline: SamplePipeline, *, base_dir: Path | None=None, strict: bool=True) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `SERDataError('SERDataset 需要至少一条记录；空数据集应在任务启动前失败')`

##### `__len__`

```python
__len__(self) -> int
```

##### `__getitem__`

```python
__getitem__(self, index: int) -> SERSample
```

##### `records`

调用方式：只读属性。

```python
records(self) -> tuple[AudioRecord, ...]
```

数据集内的记录（只读视图）。

##### `get_labels`

```python
get_labels(self) -> list[int | None]
```

返回全部标签列表，用于计算类别权重或平衡采样。

<a id="ser_lib-data-fingerprint-datasetfingerprint"></a>

#### `ser_lib.data.fingerprint.DatasetFingerprint`

公开导入：`ser_lib.data.fingerprint.DatasetFingerprint`、`ser_lib.data.DatasetFingerprint`。

源码：[ser_lib/data/fingerprint.py:17](../ser_lib/data/fingerprint.py#L17)。

由 dataset.yaml 与 split manifests 生成的稳定内容指纹。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `dataset_id` | `str` | `必填（无默认值）` |
| `algorithm` | `str` | `必填（无默认值）` |
| `digest` | `str` | `必填（无默认值）` |
| `files` | `dict[str, str]` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-data-fingerprint-fingerprint_manifest"></a>

#### `ser_lib.data.fingerprint.fingerprint_manifest`

公开导入：`ser_lib.data.fingerprint.fingerprint_manifest`、`ser_lib.data.fingerprint_manifest`。

源码：[ser_lib/data/fingerprint.py:29](../ser_lib/data/fingerprint.py#L29)。

```python
fingerprint_manifest(manifest: DatasetManifest | Path | str, *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None) -> DatasetFingerprint
```

计算 dataset.yaml + 所有声明 split 文件的 SHA256 指纹。

音频文件本体不会参与 hash，因此该操作适合频繁用于缓存键、运行记录和
Artifact 元数据。combined digest 同时包含逻辑文件名与各文件 digest，避免
split 内容互换时得到相同结果。

<a id="ser_lib-data-importers-register_importers"></a>

#### `ser_lib.data.importers.register_importers`

公开导入：`ser_lib.data.register_importers`、`ser_lib.data.importers.register_importers`。

源码：[ser_lib/data/importers/__init__.py:33](../ser_lib/data/importers/__init__.py#L33)。

```python
register_importers(registry=default_registry) -> None
```

<a id="ser_lib-data-importers-_conversion-run_manifest_conversion"></a>

#### `ser_lib.data.importers._conversion.run_manifest_conversion`

公开导入：`ser_lib.data.importers._conversion.run_manifest_conversion`。

源码：[ser_lib/data/importers/_conversion.py:29](../ser_lib/data/importers/_conversion.py#L29)。

```python
run_manifest_conversion(*, importer_id: str, scan: ScanCallable, source: Path, destination: Path, config: Mapping[str, Any], build_manifest: BuildManifest, failure_message: FailureFormatter | None=None, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

统一 convert 生命周期、scan 调用、preview 门禁和终态统计。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f"{importer_id} 扫描失败: {preview.format_errors() or '没有记录'}")`
- `ValueError(failure_message(preview))`

<a id="ser_lib-data-importers-_conversion-run_single_manifest_conversion"></a>

#### `ser_lib.data.importers._conversion.run_single_manifest_conversion`

公开导入：`ser_lib.data.importers._conversion.run_single_manifest_conversion`。

源码：[ser_lib/data/importers/_conversion.py:111](../ser_lib/data/importers/_conversion.py#L111)。

```python
run_single_manifest_conversion(*, importer_id: str, scan: ScanCallable, source: Path, destination: Path, config: Mapping[str, Any], dataset_id: str, root: Path | str, labels: LabelResolver | None=None, records: RecordResolver | None=None, failure_message: FailureFormatter | None=None, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

执行单 JSONL manifest importer 的标准 convert 流程。

所有输出先写到目标同级 staging 目录，并在那里完成 ``DatasetManifest.load``
验证。只有 staging 完整有效后才替换正式目标；提交阶段发生异常时恢复原目录，
避免“导入失败但旧数据集已经被覆盖”。

<a id="ser_lib-data-importers-_conversion-write_partitioned_manifest"></a>

#### `ser_lib.data.importers._conversion.write_partitioned_manifest`

公开导入：`ser_lib.data.importers._conversion.write_partitioned_manifest`。

源码：[ser_lib/data/importers/_conversion.py:186](../ser_lib/data/importers/_conversion.py#L186)。

```python
write_partitioned_manifest(*, destination: Path, dataset_id: str, root: Path | str, split_names: Sequence[str], labels: Mapping[int, Mapping[str, str]], records: Sequence[AudioRecord], assignments: Mapping[str, str], task: ImportTask) -> DatasetManifest
```

统一写入带显式 record→split 映射的标准 DatasetManifest。

<a id="ser_lib-data-importers-base-datasetimporter"></a>

#### `ser_lib.data.importers.base.DatasetImporter`

公开导入：`ser_lib.data.importers.base.DatasetImporter`、`ser_lib.data.importers.DatasetImporter`。

源码：[ser_lib/data/importers/base.py:196](../ser_lib/data/importers/base.py#L196)。

基类：`Protocol`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `descriptor` | `ComponentDescriptor` | `必填（无默认值）` |

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-base-importoperation"></a>

#### `ser_lib.data.importers.base.ImportOperation`

公开导入：`ser_lib.data.importers.base.ImportOperation`。

源码：[ser_lib/data/importers/base.py:28](../ser_lib/data/importers/base.py#L28)。

类型别名、常量或共享实例定义：

```python
ImportOperation = Literal['scan', 'convert']
```

<a id="ser_lib-data-importers-base-importpreview"></a>

#### `ser_lib.data.importers.base.ImportPreview`

公开导入：`ser_lib.data.ImportPreview`、`ser_lib.data.importers.base.ImportPreview`、`ser_lib.data.importers.ImportPreview`。

源码：[ser_lib/data/importers/base.py:32](../ser_lib/data/importers/base.py#L32)。

``scan()`` 结果；所有问题只通过统一 Diagnostic 表达。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `importer_id` | `str` | `必填（无默认值）` |
| `records` | `list[AudioRecord]` | `field(default_factory=list)` |
| `label_mapping` | `dict[str, int]` | `field(default_factory=dict)` |
| `diagnostics` | `list[Diagnostic]` | `field(default_factory=list)` |

##### `error_count`

调用方式：只读属性。

```python
error_count(self) -> int
```

##### `warning_count`

调用方式：只读属性。

```python
warning_count(self) -> int
```

##### `info_count`

调用方式：只读属性。

```python
info_count(self) -> int
```

##### `ok`

调用方式：只读属性。

```python
ok(self) -> bool
```

##### `format_errors`

```python
format_errors(self, *, limit: int=10) -> str
```

为异常消息生成紧凑的人类可读错误摘要。

##### `summary`

```python
summary(self) -> dict[str, Any]
```

返回单轨、JSON-safe 的预览摘要。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'importer': self.importer_id, 'num_records': len(self.records), 'label_mapping': dict(self.label_mapping), 'num_errors': self.error_count, 'num_warnings': self.warning_count, 'num_info': self.info_count, 'num_diagnostics': len(self.diagnostics), 'diagnostics': [diagnostic.to_dict() for diagnostic in self.diagnostics]}
```

<a id="ser_lib-data-importers-base-importtask"></a>

#### `ser_lib.data.importers.base.ImportTask`

公开导入：`ser_lib.data.importers.base.ImportTask`。

源码：[ser_lib/data/importers/base.py:80](../ser_lib/data/importers/base.py#L80)。

Importer ``scan``/``convert`` 的共享生命周期、进度和取消适配器。

##### `__init__`

```python
__init__(self, importer_id: str, operation: ImportOperation, *, source: Path, destination: Path | None=None, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `stage`

调用方式：只读属性。

```python
stage(self) -> str
```

##### `__enter__`

```python
__enter__(self) -> 'ImportTask'
```

##### `__exit__`

```python
__exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: object) -> Literal[False]
```

##### `check`

```python
check(self) -> None
```

##### `update_details`

```python
update_details(self, **details: Any) -> None
```

##### `progress`

```python
progress(self, completed: int, total: int | None, *, message: str='', details: Mapping[str, Any] | None=None) -> None
```

<a id="ser_lib-data-importers-casia-casia_emotion_mapping"></a>

#### `ser_lib.data.importers.casia.CASIA_EMOTION_MAPPING`

公开导入：`ser_lib.data.importers.casia.CASIA_EMOTION_MAPPING`。

源码：[ser_lib/data/importers/casia.py:17](../ser_lib/data/importers/casia.py#L17)。

类型别名、常量或共享实例定义：

```python
CASIA_EMOTION_MAPPING: dict[str, int] = {'neutral': 0, 'happy': 1, 'angry': 2, 'sad': 3, 'surprise': 4, 'fear': 5}
```

<a id="ser_lib-data-importers-casia-casia_emotion_zh"></a>

#### `ser_lib.data.importers.casia.CASIA_EMOTION_ZH`

公开导入：`ser_lib.data.importers.casia.CASIA_EMOTION_ZH`。

源码：[ser_lib/data/importers/casia.py:25](../ser_lib/data/importers/casia.py#L25)。

类型别名、常量或共享实例定义：

```python
CASIA_EMOTION_ZH: dict[str, str] = {'neutral': '平静', 'happy': '高兴', 'angry': '愤怒', 'sad': '悲伤', 'surprise': '惊吓', 'fear': '恐惧'}
```

<a id="ser_lib-data-importers-casia-casiaimporter"></a>

#### `ser_lib.data.importers.casia.CasiaImporter`

公开导入：`ser_lib.data.CasiaImporter`、`ser_lib.data.importers.casia.CasiaImporter`、`ser_lib.data.importers.CasiaImporter`。

源码：[ser_lib/data/importers/casia.py:35](../ser_lib/data/importers/casia.py#L35)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'导入源不是目录: {source}')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-crema_d-crema_d_emotions"></a>

#### `ser_lib.data.importers.crema_d.CREMA_D_EMOTIONS`

公开导入：`ser_lib.data.importers.crema_d.CREMA_D_EMOTIONS`。

源码：[ser_lib/data/importers/crema_d.py:19](../ser_lib/data/importers/crema_d.py#L19)。

类型别名、常量或共享实例定义：

```python
CREMA_D_EMOTIONS = {'NEU': (0, 'neutral'), 'HAP': (1, 'happy'), 'ANG': (2, 'angry'), 'SAD': (3, 'sad'), 'FEA': (4, 'fearful'), 'DIS': (5, 'disgust')}
```

<a id="ser_lib-data-importers-crema_d-cremadimporter"></a>

#### `ser_lib.data.importers.crema_d.CremaDImporter`

公开导入：`ser_lib.data.importers.crema_d.CremaDImporter`、`ser_lib.data.importers.CremaDImporter`。

源码：[ser_lib/data/importers/crema_d.py:84](../ser_lib/data/importers/crema_d.py#L84)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'CREMA-D 目录不存在: {source}')`
- `NotADirectoryError(f'CREMA-D 音频目录不存在: {audio_root}')`
- `ValueError('CREMA-D label_mapping 必须覆盖且只能包含 NEU/HAP/ANG/SAD/FEA/DIS')`
- `ValueError('CREMA-D label_mapping 的整数标签不能重复')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-csemotions-csemotions_labels"></a>

#### `ser_lib.data.importers.csemotions.CSEMOTIONS_LABELS`

公开导入：`ser_lib.data.importers.csemotions.CSEMOTIONS_LABELS`。

源码：[ser_lib/data/importers/csemotions.py:18](../ser_lib/data/importers/csemotions.py#L18)。

类型别名、常量或共享实例定义：

```python
CSEMOTIONS_LABELS = {'neutral': 0, 'happy': 1, 'angry': 2, 'sad': 3, 'surprise': 4, 'fearful': 5, 'playfulness': 6}
```

<a id="ser_lib-data-importers-csemotions-csemotions_zh"></a>

#### `ser_lib.data.importers.csemotions.CSEMOTIONS_ZH`

公开导入：`ser_lib.data.importers.csemotions.CSEMOTIONS_ZH`。

源码：[ser_lib/data/importers/csemotions.py:27](../ser_lib/data/importers/csemotions.py#L27)。

类型别名、常量或共享实例定义：

```python
CSEMOTIONS_ZH = {'neutral': '中性', 'happy': '快乐', 'angry': '愤怒', 'sad': '悲伤', 'surprise': '惊讶', 'fearful': '恐惧', 'playfulness': '俏皮'}
```

<a id="ser_lib-data-importers-csemotions-csemotionsimporter"></a>

#### `ser_lib.data.importers.csemotions.CsemotionsImporter`

公开导入：`ser_lib.data.importers.csemotions.CsemotionsImporter`、`ser_lib.data.importers.CsemotionsImporter`。

源码：[ser_lib/data/importers/csemotions.py:90](../ser_lib/data/importers/csemotions.py#L90)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'CSEMOTIONS 目录不存在: {source}')`
- `FileNotFoundError(f'CSEMOTIONS metadata 不存在: {metadata_path}')`
- `NotADirectoryError(f'CSEMOTIONS 音频目录不存在: {audio_root}')`
- `ValueError`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-csv_importer-csvimporter"></a>

#### `ser_lib.data.importers.csv_importer.CsvImporter`

公开导入：`ser_lib.data.CsvImporter`、`ser_lib.data.importers.csv_importer.CsvImporter`、`ser_lib.data.importers.CsvImporter`。

源码：[ser_lib/data/importers/csv_importer.py:24](../ser_lib/data/importers/csv_importer.py#L24)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'CSV 文件不存在: {source}')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-emotiontalk-emotiontalk_labels"></a>

#### `ser_lib.data.importers.emotiontalk.EMOTIONTALK_LABELS`

公开导入：`ser_lib.data.importers.emotiontalk.EMOTIONTALK_LABELS`。

源码：[ser_lib/data/importers/emotiontalk.py:19](../ser_lib/data/importers/emotiontalk.py#L19)。

类型别名、常量或共享实例定义：

```python
EMOTIONTALK_LABELS = {'neutral': 0, 'happy': 1, 'angry': 2, 'sad': 3, 'surprised': 4, 'fearful': 5, 'disgusted': 6}
```

<a id="ser_lib-data-importers-emotiontalk-emotiontalkimporter"></a>

#### `ser_lib.data.importers.emotiontalk.EmotionTalkImporter`

公开导入：`ser_lib.data.importers.emotiontalk.EmotionTalkImporter`、`ser_lib.data.importers.EmotionTalkImporter`。

源码：[ser_lib/data/importers/emotiontalk.py:53](../ser_lib/data/importers/emotiontalk.py#L53)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'EmotionTalk 目录不存在: {source}')`
- `NotADirectoryError('EmotionTalk 必须包含 json 和 wav 目录')`
- `ValueError('EmotionTalk label_mapping 必须完整覆盖七类情感且标签不能重复')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('official_dialogue 策略不能同时配置 speaker_splits')`

<a id="ser_lib-data-importers-esd-esd_labels"></a>

#### `ser_lib.data.importers.esd.ESD_LABELS`

公开导入：`ser_lib.data.importers.esd.ESD_LABELS`。

源码：[ser_lib/data/importers/esd.py:18](../ser_lib/data/importers/esd.py#L18)。

类型别名、常量或共享实例定义：

```python
ESD_LABELS = {'Neutral': 0, 'Happy': 1, 'Angry': 2, 'Sad': 3, 'Surprise': 4}
```

<a id="ser_lib-data-importers-esd-esd_zh"></a>

#### `ser_lib.data.importers.esd.ESD_ZH`

公开导入：`ser_lib.data.importers.esd.ESD_ZH`。

源码：[ser_lib/data/importers/esd.py:19](../ser_lib/data/importers/esd.py#L19)。

类型别名、常量或共享实例定义：

```python
ESD_ZH = {'Neutral': '中性', 'Happy': '快乐', 'Angry': '愤怒', 'Sad': '悲伤', 'Surprise': '惊讶'}
```

<a id="ser_lib-data-importers-esd-esdimporter"></a>

#### `ser_lib.data.importers.esd.EsdImporter`

公开导入：`ser_lib.data.importers.esd.EsdImporter`、`ser_lib.data.importers.EsdImporter`。

源码：[ser_lib/data/importers/esd.py:76](../ser_lib/data/importers/esd.py#L76)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'ESD 目录不存在: {source}')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-folder-folderimporter"></a>

#### `ser_lib.data.importers.folder.FolderImporter`

公开导入：`ser_lib.data.FolderImporter`、`ser_lib.data.importers.folder.FolderImporter`、`ser_lib.data.importers.FolderImporter`。

源码：[ser_lib/data/importers/folder.py:18](../ser_lib/data/importers/folder.py#L18)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'导入源不是目录: {source}')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-jsonl_importer-jsonlimporter"></a>

#### `ser_lib.data.importers.jsonl_importer.JsonlImporter`

公开导入：`ser_lib.data.JsonlImporter`、`ser_lib.data.importers.jsonl_importer.JsonlImporter`、`ser_lib.data.importers.JsonlImporter`。

源码：[ser_lib/data/importers/jsonl_importer.py:68](../ser_lib/data/importers/jsonl_importer.py#L68)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-importers-jsonl_importer-standard_fields"></a>

#### `ser_lib.data.importers.jsonl_importer.STANDARD_FIELDS`

公开导入：`ser_lib.data.importers.jsonl_importer.STANDARD_FIELDS`。

源码：[ser_lib/data/importers/jsonl_importer.py:19](../ser_lib/data/importers/jsonl_importer.py#L19)。

类型别名、常量或共享实例定义：

```python
STANDARD_FIELDS = frozenset({'uid', 'audio_path', 'label', 'start_ms', 'end_ms', 'speaker_id', 'sample_rate_hint', 'metadata'})
```

<a id="ser_lib-data-importers-jsonl_importer-normalize_raw_record"></a>

#### `ser_lib.data.importers.jsonl_importer.normalize_raw_record`

公开导入：`ser_lib.data.importers.jsonl_importer.normalize_raw_record`、`ser_lib.data.importers.normalize_raw_record`。

源码：[ser_lib/data/importers/jsonl_importer.py:30](../ser_lib/data/importers/jsonl_importer.py#L30)。

```python
normalize_raw_record(raw: Mapping[str, Any], *, index: int, uid_prefix: str) -> dict[str, Any]
```

<a id="ser_lib-data-importers-jsonl_importer-normalize_raw_records"></a>

#### `ser_lib.data.importers.jsonl_importer.normalize_raw_records`

公开导入：`ser_lib.data.importers.jsonl_importer.normalize_raw_records`、`ser_lib.data.importers.normalize_raw_records`。

源码：[ser_lib/data/importers/jsonl_importer.py:55](../ser_lib/data/importers/jsonl_importer.py#L55)。

```python
normalize_raw_records(raw_records: list[Mapping[str, Any]], *, uid_prefix: str) -> list[AudioRecord]
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ManifestError(f"UID 重复: '{record.uid}'（第 {index + 1} 条）", uid=record.uid)`

<a id="ser_lib-data-importers-ravdess-ravdess_emotions"></a>

#### `ser_lib.data.importers.ravdess.RAVDESS_EMOTIONS`

公开导入：`ser_lib.data.importers.ravdess.RAVDESS_EMOTIONS`。

源码：[ser_lib/data/importers/ravdess.py:17](../ser_lib/data/importers/ravdess.py#L17)。

类型别名、常量或共享实例定义：

```python
RAVDESS_EMOTIONS = {'01': (0, 'neutral'), '02': (1, 'calm'), '03': (2, 'happy'), '04': (3, 'sad'), '05': (4, 'angry'), '06': (5, 'fearful'), '07': (6, 'disgust'), '08': (7, 'surprised')}
```

<a id="ser_lib-data-importers-ravdess-ravdessimporter"></a>

#### `ser_lib.data.importers.ravdess.RavdessImporter`

公开导入：`ser_lib.data.RavdessImporter`、`ser_lib.data.importers.ravdess.RavdessImporter`、`ser_lib.data.importers.RavdessImporter`。

源码：[ser_lib/data/importers/ravdess.py:29](../ser_lib/data/importers/ravdess.py#L29)。

##### `scan`

```python
scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> ImportPreview
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'导入源不是目录: {source}')`

##### `convert`

```python
convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> DatasetManifest
```

<a id="ser_lib-data-manifest-datasetmanifest"></a>

#### `ser_lib.data.manifest.DatasetManifest`

公开导入：`ser_lib.data.DatasetManifest`。

源码：[ser_lib/data/manifest.py:258](../ser_lib/data/manifest.py#L258)。

标准数据集 manifest：迭代记录、按 split 获取、轻量统计。

##### `__init__`

```python
__init__(self, meta: ManifestMeta, records: list[AudioRecord], record_splits: dict[str, str] | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `load`

调用方式：类方法，可直接通过类名调用。

```python
load(cls, yaml_path: Path | str) -> 'DatasetManifest'
```

加载 dataset.yaml 及其全部 splits，并拒绝无歧义的跨 split 音频泄漏。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ManifestError(f"UID 跨 split 重复: '{record.uid}' 同时出现在 '{record_splits[record.uid]}' 与 '{split_name}'", uid=record.uid, path=yaml_path)`

##### `resolve_audio_path`

```python
resolve_audio_path(self, record: AudioRecord) -> Path
```

##### `get_records`

```python
get_records(self, split: str | None=None) -> list[AudioRecord]
```

##### `resolved_records`

```python
resolved_records(self, split: str | None=None) -> list[AudioRecord]
```

##### `stats`

```python
stats(self) -> dict[str, Any]
```

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'dataset_id': self.meta.dataset_id, 'total': len(self.records), 'splits': split_counts, 'labels': label_counts, 'num_classes': self.meta.num_classes or None}
```

##### `write`

```python
write(self, yaml_path: Path | None=None) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ManifestError('未分配记录与已有 unassigned split 冲突，拒绝覆盖', path=yaml_path)`
- `ManifestError(f"split '{split_name}' 的写入路径越出 dataset 目录: {relative}", path=yaml_path)`
- `ManifestError(f"split 写入路径冲突: '{previous}' 与 '{split_name}' 都指向 {relative}", path=yaml_path)`

<a id="ser_lib-data-manifest-manifestmeta"></a>

#### `ser_lib.data.manifest.ManifestMeta`

公开导入：`ser_lib.data.ManifestMeta`。

源码：[ser_lib/data/manifest.py:36](../ser_lib/data/manifest.py#L36)。

dataset.yaml 元信息。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `dataset_id` | `str` | `必填（无默认值）` |
| `root` | `Path` | `必填（无默认值）` |
| `yaml_path` | `Path` | `必填（无默认值）` |
| `splits` | `dict[str, Path]` | `field(default_factory=dict)` |
| `labels` | `dict[int, dict[str, Any]]` | `field(default_factory=dict)` |

##### `num_classes`

调用方式：只读属性。

```python
num_classes(self) -> int
```

<a id="ser_lib-data-manifest-read_jsonl"></a>

#### `ser_lib.data.manifest.read_jsonl`

公开导入：`ser_lib.data.read_jsonl`。

源码：[ser_lib/data/manifest.py:127](../ser_lib/data/manifest.py#L127)。

```python
read_jsonl(path: Path) -> list[AudioRecord]
```

读取标准 JSONL manifest。文件内 uid 必须唯一。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ManifestError(f'manifest 文件不存在: {path}', path=path)`
- `ManifestError(f"UID 重复: '{record.uid}' 出现于第 {seen[record.uid]} 行和第 {line_number} 行 ({path})", path=path, uid=record.uid)`
- `ManifestError(f'JSONL 解析失败 ({path.name}:{line_number}): {exc}', path=path)`

<a id="ser_lib-data-manifest-write_jsonl"></a>

#### `ser_lib.data.manifest.write_jsonl`

公开导入：`ser_lib.data.write_jsonl`。

源码：[ser_lib/data/manifest.py:100](../ser_lib/data/manifest.py#L100)。

```python
write_jsonl(records: list[AudioRecord], path: Path) -> None
```

把记录写入标准 JSONL（音频路径保留为给定形式）。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ManifestError(f'写入 manifest 失败: {path}', path=path)`

<a id="ser_lib-data-pipeline-samplepipeline"></a>

#### `ser_lib.data.pipeline.SamplePipeline`

公开导入：`ser_lib.data.SamplePipeline`。

源码：[ser_lib/data/pipeline.py:38](../ser_lib/data/pipeline.py#L38)。

单样本处理流水线。

- ``waveform_transforms`` 可为 ``None``（验证/测试/推理：无随机增强）；
- ``representation`` 必填；
- ``feature_transforms`` 可为 ``None``；
- ``validate_contract`` 开启时对每个输出做契约校验（测试与开发默认开启，
  生产可关闭以提升吞吐）。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, representation: Representation, waveform_transforms: nn.Module | None=None, feature_transforms: nn.Module | None=None, *, validate_contract: bool=True) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `output_specs`

调用方式：只读属性。

```python
output_specs(self) -> dict[str, TensorSpec]
```

输出形状契约（与 representation 一致）。

##### `forward`

```python
forward(self, audio: AudioData, record: AudioRecord, *, validate_contract: bool | None=None) -> SERSample
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TransformError(f'波形 transform 输出必须是 [C, T]，实际 {waveform.dim()}D {tuple(waveform.shape)}', uid=record.uid, path=audio.source_path, component='waveform_transforms', stage='transform')`
- `RepresentationError(f'表示计算失败: {exc}', uid=record.uid, path=audio.source_path, component=self.representation.descriptor.id, stage='representation')`
- `TransformError(f'波形 transform 失败: {exc}', uid=record.uid, path=audio.source_path, component='waveform_transforms', stage='transform')`
- `TransformError(f'特征 transform 失败: {exc}', uid=record.uid, path=audio.source_path, component='feature_transforms', stage='transform')`

##### `__call__`

```python
__call__(self, audio: AudioData, record: AudioRecord, *, validate_contract: bool | None=None) -> SERSample
```

<a id="ser_lib-data-pipeline-build_components"></a>

#### `ser_lib.data.pipeline.build_components`

公开导入：`ser_lib.data.build_components`。

源码：[ser_lib/data/pipeline.py:288](../ser_lib/data/pipeline.py#L288)。

```python
build_components(data_config: DataConfig, *, train: bool, validate_contract: bool=True) -> tuple['AudioLoader', SamplePipeline]
```

构建 (AudioLoader, SamplePipeline) 组件对。

<a id="ser_lib-data-pipeline-build_pipeline"></a>

#### `ser_lib.data.pipeline.build_pipeline`

公开导入：`ser_lib.data.build_pipeline`。

源码：[ser_lib/data/pipeline.py:244](../ser_lib/data/pipeline.py#L244)。

```python
build_pipeline(data_config: DataConfig, *, train: bool, validate_contract: bool=True) -> SamplePipeline
```

从 DataConfig 构建 SamplePipeline（训练与推理共享同一入口）。

Args:
    data_config: 数据配置。
    train: True 时启用配置中的随机增强；False（验证/测试/推理）默认
        禁用随机增强（设计文档 §8.3）。
    validate_contract: 是否做运行时输出契约校验。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('训练随机波形增强之后默认禁止 Representation 缓存；请关闭 data.cache 或移除训练 waveform_transforms')`

<a id="ser_lib-data-profiling-audioprobefailure"></a>

#### `ser_lib.data.profiling.AudioProbeFailure`

公开导入：`ser_lib.data.profiling.AudioProbeFailure`、`ser_lib.data.AudioProbeFailure`。

源码：[ser_lib/data/profiling.py:15](../ser_lib/data/profiling.py#L15)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `path` | `str` | `必填（无默认值）` |
| `error_type` | `str` | `必填（无默认值）` |
| `message` | `str` | `必填（无默认值）` |

<a id="ser_lib-data-profiling-datasetaudioprofile"></a>

#### `ser_lib.data.profiling.DatasetAudioProfile`

公开导入：`ser_lib.data.profiling.DatasetAudioProfile`、`ser_lib.data.DatasetAudioProfile`。

源码：[ser_lib/data/profiling.py:33](../ser_lib/data/profiling.py#L33)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `dataset_id` | `str` | `必填（无默认值）` |
| `split` | `str &#124; None` | `必填（无默认值）` |
| `total_records` | `int` | `必填（无默认值）` |
| `probed_records` | `int` | `必填（无默认值）` |
| `failed_records` | `int` | `必填（无默认值）` |
| `total_duration_seconds` | `float` | `必填（无默认值）` |
| `min_duration_seconds` | `float &#124; None` | `必填（无默认值）` |
| `max_duration_seconds` | `float &#124; None` | `必填（无默认值）` |
| `mean_duration_seconds` | `float &#124; None` | `必填（无默认值）` |
| `sample_rates` | `dict[str, int]` | `必填（无默认值）` |
| `channels` | `dict[str, int]` | `必填（无默认值）` |
| `failures` | `tuple[AudioProbeFailure, ...]` | `必填（无默认值）` |
| `median_duration_seconds` | `float &#124; None` | `None` |
| `p90_duration_seconds` | `float &#124; None` | `None` |
| `p95_duration_seconds` | `float &#124; None` | `None` |
| `p99_duration_seconds` | `float &#124; None` | `None` |
| `duration_histogram` | `tuple[DurationHistogramBin, ...]` | `()` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-data-profiling-datasetprofile"></a>

#### `ser_lib.data.profiling.DatasetProfile`

公开导入：`ser_lib.data.profiling.DatasetProfile`、`ser_lib.data.DatasetProfile`。

源码：[ser_lib/data/profiling.py:83](../ser_lib/data/profiling.py#L83)。

供可视化数据集分析页使用的详细、JSON-safe profile。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `dataset_id` | `str` | `必填（无默认值）` |
| `name` | `str` | `必填（无默认值）` |
| `total_records` | `int` | `必填（无默认值）` |
| `num_classes` | `int &#124; None` | `必填（无默认值）` |
| `num_speakers` | `int` | `必填（无默认值）` |
| `unlabeled_records` | `int` | `必填（无默认值）` |
| `records_without_speaker` | `int` | `必填（无默认值）` |
| `splits` | `dict[str, int]` | `必填（无默认值）` |
| `labels` | `dict[str, int]` | `必填（无默认值）` |
| `label_display_names` | `dict[str, str]` | `必填（无默认值）` |
| `split_labels` | `dict[str, dict[str, int]]` | `必填（无默认值）` |
| `speaker_counts` | `dict[str, int]` | `必填（无默认值）` |
| `audio_profile` | `DatasetAudioProfile &#124; None` | `None` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'dataset_id': self.dataset_id, 'name': self.name, 'total_records': self.total_records, 'num_classes': self.num_classes, 'num_speakers': self.num_speakers, 'unlabeled_records': self.unlabeled_records, 'records_without_speaker': self.records_without_speaker, 'splits': dict(self.splits), 'labels': dict(self.labels), 'label_display_names': dict(self.label_display_names), 'split_labels': {split: dict(counts) for split, counts in self.split_labels.items()}, 'speaker_counts': dict(self.speaker_counts), 'audio_profile': self.audio_profile.to_dict() if self.audio_profile is not None else None}
```

<a id="ser_lib-data-profiling-datasetsummary"></a>

#### `ser_lib.data.profiling.DatasetSummary`

公开导入：`ser_lib.data.profiling.DatasetSummary`、`ser_lib.data.DatasetSummary`。

源码：[ser_lib/data/profiling.py:57](../ser_lib/data/profiling.py#L57)。

供 CLI/Web 列表和详情首屏直接消费的数据集摘要。

默认摘要只扫描 manifest，不打开音频文件；只有显式请求音频 profiling 时，
才填充时长、采样率、声道和失败记录统计。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `dataset_id` | `str` | `必填（无默认值）` |
| `name` | `str` | `必填（无默认值）` |
| `total_records` | `int` | `必填（无默认值）` |
| `num_classes` | `int &#124; None` | `必填（无默认值）` |
| `num_speakers` | `int` | `必填（无默认值）` |
| `splits` | `dict[str, int]` | `必填（无默认值）` |
| `labels` | `dict[str, int]` | `必填（无默认值）` |
| `total_duration_seconds` | `float &#124; None` | `None` |
| `audio_profiled` | `bool` | `False` |
| `profiled_records` | `int` | `0` |
| `failed_audio_records` | `int` | `0` |
| `sample_rates` | `dict[str, int]` | `field(default_factory=dict)` |
| `channels` | `dict[str, int]` | `field(default_factory=dict)` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-data-profiling-durationhistogrambin"></a>

#### `ser_lib.data.profiling.DurationHistogramBin`

公开导入：`ser_lib.data.profiling.DurationHistogramBin`、`ser_lib.data.DurationHistogramBin`。

源码：[ser_lib/data/profiling.py:23](../ser_lib/data/profiling.py#L23)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `lower_seconds` | `float` | `必填（无默认值）` |
| `upper_seconds` | `float` | `必填（无默认值）` |
| `count` | `int` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-data-profiling-profile_dataset"></a>

#### `ser_lib.data.profiling.profile_dataset`

公开导入：`ser_lib.data.profiling.profile_dataset`、`ser_lib.data.profile_dataset`。

源码：[ser_lib/data/profiling.py:331](../ser_lib/data/profiling.py#L331)。

```python
profile_dataset(manifest: DatasetManifest | Path | str, *, include_audio: bool=False, fail_fast: bool=False, histogram_bins: int=10, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None) -> DatasetProfile
```

构建数据集分析页所需的详细 profile。

manifest 扫描提供 split×label、speaker 和缺失字段统计；``include_audio=True``
时额外进行 header profiling，并附带时长分位数与 histogram。不会解码完整波形。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('histogram_bins 必须 >= 1')`

<a id="ser_lib-data-profiling-profile_manifest_audio"></a>

#### `ser_lib.data.profiling.profile_manifest_audio`

公开导入：`ser_lib.data.profiling.profile_manifest_audio`、`ser_lib.data.profile_manifest_audio`。

源码：[ser_lib/data/profiling.py:173](../ser_lib/data/profiling.py#L173)。

```python
profile_manifest_audio(manifest: DatasetManifest | Path | str, *, split: str | None=None, fail_fast: bool=False, histogram_bins: int=10, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None) -> DatasetAudioProfile
```

使用音频 header 统计时长、分位数、采样率、声道和损坏/缺失文件。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('histogram_bins 必须 >= 1')`
- `ValueError('音频 header 包含非正采样率、帧数或声道数')`
- `ValueError('记录片段没有有效时长')`

<a id="ser_lib-data-profiling-summarize_manifest"></a>

#### `ser_lib.data.profiling.summarize_manifest`

公开导入：`ser_lib.data.profiling.summarize_manifest`、`ser_lib.data.summarize_manifest`。

源码：[ser_lib/data/profiling.py:260](../ser_lib/data/profiling.py#L260)。

```python
summarize_manifest(manifest: DatasetManifest | Path | str, *, include_audio_profile: bool=False, fail_fast: bool=False, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None) -> DatasetSummary
```

构建稳定、JSON-safe 的轻量数据集摘要。

``include_audio_profile=False`` 时只遍历 manifest，适合数据集列表和详情页首屏。
开启后复用 :func:`profile_manifest_audio`，仅读取音频 header，不解码整段音频。

<a id="ser_lib-data-registry-componentdescriptor"></a>

#### `ser_lib.data.registry.ComponentDescriptor`

公开导入：`ser_lib.data.ComponentDescriptor`。

源码：[ser_lib/data/registry.py:32](../ser_lib/data/registry.py#L32)。

统一的公开组件描述信息。

``config_schema`` 来自 Pydantic JSON Schema，Web 可据此动态生成参数表单；
``capabilities`` 只保存机器可读能力声明，不要求前端从描述文本推断行为。
``input_specs`` / ``output_specs`` 为数据组件的兼容字段，后续新组件优先把
额外能力放入 ``capabilities``。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `id` | `str` | `必填（无默认值）` |
| `display_name` | `str` | `必填（无默认值）` |
| `category` | `str` | `必填（无默认值）` |
| `version` | `str` | `'1.0'` |
| `status` | `str` | `STATUS_STABLE` |
| `description` | `str` | `''` |
| `config_schema` | `dict[str, Any]` | `field(default_factory=dict)` |
| `capabilities` | `dict[str, Any]` | `field(default_factory=dict)` |
| `input_specs` | `dict[str, TensorSpec] &#124; None` | `None` |
| `output_specs` | `dict[str, TensorSpec] &#124; None` | `None` |

##### `to_json_safe`

```python
to_json_safe(self) -> dict[str, Any]
```

序列化为 JSON 安全结构；``torch.dtype`` 转换为稳定字符串。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'id': self.id, 'display_name': self.display_name, 'category': self.category, 'version': self.version, 'status': self.status, 'description': self.description, 'config_schema': self.config_schema, 'capabilities': dict(self.capabilities), 'input_specs': _specs_to_json_safe(self.input_specs), 'output_specs': _specs_to_json_safe(self.output_specs)}
```

<a id="ser_lib-data-registry-registry"></a>

#### `ser_lib.data.registry.Registry`

公开导入：`ser_lib.data.Registry`。

源码：[ser_lib/data/registry.py:109](../ser_lib/data/registry.py#L109)。

命名空间隔离的组件注册表。

##### `__init__`

```python
__init__(self) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `register`

```python
register(self, *, namespace: str, name: str, factory: Callable[..., Any], config_model: type[BaseModel] | None=None, descriptor: ComponentDescriptor | None=None, replace: bool=False) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'namespace 与 name 不能为空: {namespace!r}/{name!r}')`
- `RegistryError(f'组件重复注册: namespace={namespace!r}, name={name!r}。如需覆盖请显式传入 replace=True')`
- `RegistryError(f'descriptor.id ({descriptor.id!r}) 必须与注册名称 ({name!r}) 一致')`
- `RegistryError(f'组件 {namespace}.{name} 的 config_model 无法实例化: {exc}')`

##### `get_entry`

```python
get_entry(self, namespace: str, name: str) -> ComponentEntry
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f"未知组件: namespace={namespace!r}, name={name!r}。可用组件: {available or '（空）'}")`

##### `create`

```python
create(self, namespace: str, component: Mapping[str, Any] | str, **overrides: Any) -> Any
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'组件配置必须是 Mapping 或 str，实际: {type(component)!r}')`
- `RegistryError(f"组件配置包含未知字段 {sorted(unknown_keys)}，仅允许 'type' 与 'params'")`
- `RegistryError(f"组件 'type' 必须是非空字符串，实际: {raw_type!r}")`
- `RegistryError(f"组件 'params' 必须是字典，实际: {type(params)!r}")`
- `RegistryError(f'组件 {namespace}.{comp_type} 构建失败: {exc}', component=comp_type, stage='component_build')`
- `RegistryError(f'组件 {namespace}.{comp_type} 参数校验失败: {exc}', component=comp_type, stage='config_validation')`

##### `names`

```python
names(self, namespace: str) -> list[str]
```

##### `descriptors`

```python
descriptors(self, namespace: str, *, statuses: tuple[str, ...] | None=PUBLIC_STATUSES) -> list[ComponentDescriptor]
```

枚举组件；``statuses=None`` 时返回包括 optional/unavailable 在内的全部项。

##### `json_safe_descriptors`

```python
json_safe_descriptors(self, namespace: str, *, statuses: tuple[str, ...] | None=PUBLIC_STATUSES) -> list[dict[str, Any]]
```

<a id="ser_lib-data-registry-default_registry"></a>

#### `ser_lib.data.registry.default_registry`

公开导入：`ser_lib.data.default_registry`。

源码：[ser_lib/data/registry.py:244](../ser_lib/data/registry.py#L244)。

类型别名、常量或共享实例定义：

```python
default_registry = Registry()
```

<a id="ser_lib-data-representations-register_representations"></a>

#### `ser_lib.data.representations.register_representations`

公开导入：`ser_lib.data.register_representations`、`ser_lib.data.representations.register_representations`。

源码：[ser_lib/data/representations/__init__.py:47](../ser_lib/data/representations/__init__.py#L47)。

```python
register_representations(registry: Registry | None=None) -> None
```

把全部表示注册到注册表（默认注册到 default_registry）。

<a id="ser_lib-data-representations-acoustic-acousticfeatures"></a>

#### `ser_lib.data.representations.acoustic.AcousticFeatures`

公开导入：`ser_lib.data.representations.AcousticFeatures`。

源码：[ser_lib/data/representations/acoustic.py:211](../ser_lib/data/representations/acoustic.py#L211)。

声学帧级特征表示（详见模块 docstring 的输出协议）。

基类：`Representation`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, **params) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `output_specs`

调用方式：只读属性。

```python
output_specs(self) -> dict[str, TensorSpec]
```

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RepresentationError(f'帧级特征时间长度不一致: {mismatched}（参考帧数 {ref}）。禁止自动插值或裁剪对齐；如需不等长时间轴，请将各特征拆分为独立的 AcousticFeatures 子表示并通过 CompositeRepresentation 组合', path=audio.source_path, component=self.descriptor.id, stage='representation')`

<a id="ser_lib-data-representations-base-representation"></a>

#### `ser_lib.data.representations.base.Representation`

公开导入：`ser_lib.data.representations.Representation`。

源码：[ser_lib/data/representations/base.py:19](../ser_lib/data/representations/base.py#L19)。

输入表示的抽象基类。

子类必须：

- 声明类属性 ``descriptor``（供调用方枚举）；
- 实现 ``output_specs``，返回 ``{key: TensorSpec}``；
- 实现 ``forward(audio)`` 并保证输出满足自己声明的 specs。

基类：`nn.Module`、`ABC`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `descriptor` | `ComponentDescriptor` | `必填（无默认值）` |

##### `output_specs`

调用方式：只读属性。

```python
output_specs(self) -> dict[str, TensorSpec]
```

声明输出 tensor 的形状契约。

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

把 AudioData 转换为标准表示输出。

<a id="ser_lib-data-representations-composite-compositerepresentation"></a>

#### `ser_lib.data.representations.composite.CompositeRepresentation`

公开导入：`ser_lib.data.representations.CompositeRepresentation`。

源码：[ser_lib/data/representations/composite.py:21](../ser_lib/data/representations/composite.py#L21)。

组合多个子表示。

基类：`Representation`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, **params: Any) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RepresentationError(f'组合表示的子组件必须是 Representation，实际: {type(sub_rep)!r}', component=self.descriptor.id, stage='component_build')`
- `RepresentationError(f"组合表示输出 key 冲突: '{new_key}' 被多个子表示占用", component=self.descriptor.id, stage='component_build')`

##### `output_specs`

调用方式：只读属性。

```python
output_specs(self) -> dict[str, TensorSpec]
```

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

<a id="ser_lib-data-representations-spectral-logmelrepresentation"></a>

#### `ser_lib.data.representations.spectral.LogMelRepresentation`

公开导入：`ser_lib.data.representations.spectral.LogMelRepresentation`、`ser_lib.data.representations.LogMelRepresentation`。

源码：[ser_lib/data/representations/spectral.py:140](../ser_lib/data/representations/spectral.py#L140)。

Log-Mel 谱：Mel 谱后接 AmplitudeToDB。

基类：`_SpectralRepresentationBase`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `config` | `LogMelConfig` | `必填（无默认值）` |

##### `__init__`

```python
__init__(self, **params) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

<a id="ser_lib-data-representations-spectral-mfccrepresentation"></a>

#### `ser_lib.data.representations.spectral.MFCCRepresentation`

公开导入：`ser_lib.data.representations.spectral.MFCCRepresentation`、`ser_lib.data.representations.MFCCRepresentation`。

源码：[ser_lib/data/representations/spectral.py:184](../ser_lib/data/representations/spectral.py#L184)。

MFCC：Mel 参数转换逻辑封装在组件内部。

基类：`_SpectralRepresentationBase`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `config` | `MFCCConfig` | `必填（无默认值）` |

##### `__init__`

```python
__init__(self, **params) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

<a id="ser_lib-data-representations-spectral-melspectrogramrepresentation"></a>

#### `ser_lib.data.representations.spectral.MelSpectrogramRepresentation`

公开导入：`ser_lib.data.representations.spectral.MelSpectrogramRepresentation`、`ser_lib.data.representations.MelSpectrogramRepresentation`。

源码：[ser_lib/data/representations/spectral.py:101](../ser_lib/data/representations/spectral.py#L101)。

Mel 谱。

基类：`_SpectralRepresentationBase`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `config` | `MelConfig` | `必填（无默认值）` |

##### `__init__`

```python
__init__(self, **params) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

<a id="ser_lib-data-representations-spectral-spectrogramrepresentation"></a>

#### `ser_lib.data.representations.spectral.SpectrogramRepresentation`

公开导入：`ser_lib.data.representations.spectral.SpectrogramRepresentation`、`ser_lib.data.representations.SpectrogramRepresentation`。

源码：[ser_lib/data/representations/spectral.py:66](../ser_lib/data/representations/spectral.py#L66)。

线性幅度谱（power 谱）。

基类：`_SpectralRepresentationBase`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, **params) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

<a id="ser_lib-data-representations-waveform-rawwaveform"></a>

#### `ser_lib.data.representations.waveform.RawWaveform`

公开导入：`ser_lib.data.representations.RawWaveform`。

源码：[ser_lib/data/representations/waveform.py:16](../ser_lib/data/representations/waveform.py#L16)。

原始波形表示。

输入 ``AudioData.waveform [1, T]``，输出 ``inputs["waveform"] [T]``，
layout ``T``，length ``{"waveform": T}``。

基类：`Representation`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `output_specs`

调用方式：只读属性。

```python
output_specs(self) -> dict[str, TensorSpec]
```

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'waveform': TensorSpec(layout=LAYOUT_T)}
```

##### `forward`

```python
forward(self, audio: AudioData) -> RepresentationOutput
```

<a id="ser_lib-data-transforms-register_transforms"></a>

#### `ser_lib.data.transforms.register_transforms`

公开导入：`ser_lib.data.register_transforms`、`ser_lib.data.transforms.register_transforms`。

源码：[ser_lib/data/transforms/__init__.py:31](../ser_lib/data/transforms/__init__.py#L31)。

```python
register_transforms(registry: Registry | None=None) -> None
```

注册波形级与特征级 transform（默认注册到 default_registry）。

<a id="ser_lib-data-transforms-base-featuretransformpipeline"></a>

#### `ser_lib.data.transforms.base.FeatureTransformPipeline`

公开导入：`ser_lib.data.transforms.FeatureTransformPipeline`。

源码：[ser_lib/data/transforms/base.py:68](../ser_lib/data/transforms/base.py#L68)。

特征级 transform 流水线：对每个输入 key 应用全部 transform。

构建（而不是运行）阶段已完成 layout 兼容性校验；运行时对每个
temporal key 依次应用。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, transforms: Sequence[nn.Module] | None=None, *, keys: Sequence[str] | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, inputs: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TransformError(f"特征 transform '{type(transform).__name__}' 处理输入 '{key}' 失败: {exc}", component=type(transform).__name__, stage='feature_transform')`

<a id="ser_lib-data-transforms-base-randomapply"></a>

#### `ser_lib.data.transforms.base.RandomApply`

公开导入：`ser_lib.data.transforms.waveform.RandomApply`、`ser_lib.data.transforms.RandomApply`。

源码：[ser_lib/data/transforms/base.py:18](../ser_lib/data/transforms/base.py#L18)。

以概率 ``probability`` 应用内部 transform，否则原样返回。

- 概率必须落在 ``[0, 1]``；
- ``p=0`` 永不执行、``p=1`` 必定执行；
- 使用 torch 全局 RNG 抽样，固定 seed 下可复现。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, transform: nn.Module, probability: float) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TransformError(f'RandomApply 概率必须在 [0, 1]，实际: {probability}', component=type(transform).__name__, stage='transform_build')`

##### `forward`

```python
forward(self, *args, **kwargs) -> 未声明返回类型
```

##### `extra_repr`

```python
extra_repr(self) -> str
```

<a id="ser_lib-data-transforms-base-waveformtransformpipeline"></a>

#### `ser_lib.data.transforms.base.WaveformTransformPipeline`

公开导入：`ser_lib.data.transforms.WaveformTransformPipeline`。

源码：[ser_lib/data/transforms/base.py:46](../ser_lib/data/transforms/base.py#L46)。

波形级 transform 流水线：``[C, T] -> [C, T]``。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, transforms: Sequence[nn.Module] | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TransformError(f"波形 transform '{type(transform).__name__}' 执行失败: {exc}", component=type(transform).__name__, stage='waveform_transform')`

<a id="ser_lib-data-transforms-base-validate_feature_transform_layouts"></a>

#### `ser_lib.data.transforms.base.validate_feature_transform_layouts`

公开导入：`ser_lib.data.transforms.validate_feature_transform_layouts`。

源码：[ser_lib/data/transforms/base.py:110](../ser_lib/data/transforms/base.py#L110)。

```python
validate_feature_transform_layouts(transform: nn.Module, specs: dict[str, TensorSpec]) -> None
```

构建期校验特征 transform 与输入 layout 兼容（验证优先于运行）。

transform 需要声明 ``compatible_layouts: tuple[str, ...]``；
对所有时序输入 key 逐一检查。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TransformError(f"特征 transform '{type(transform).__name__}' 不兼容输入 layout {incompatible}，支持的 layout: {compatible}", component=type(transform).__name__, stage='transform_build')`

<a id="ser_lib-data-transforms-feature-spec_masking_descriptor"></a>

#### `ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR`

公开导入：`ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR`、`ser_lib.data.transforms.SPEC_MASKING_DESCRIPTOR`。

源码：[ser_lib/data/transforms/feature.py:33](../ser_lib/data/transforms/feature.py#L33)。

类型别名、常量或共享实例定义：

```python
SPEC_MASKING_DESCRIPTOR = ComponentDescriptor(id='spec_masking', display_name='SpecAugment 掩码', category='feature_transform', description='对 [F, T] 或 [C, F, T] 输入应用时间与频率掩码。', config_schema=SpecMaskingConfig.model_json_schema())
```

<a id="ser_lib-data-transforms-feature-specmasking"></a>

#### `ser_lib.data.transforms.feature.SpecMasking`

公开导入：`ser_lib.data.transforms.feature.SpecMasking`、`ser_lib.data.transforms.SpecMasking`。

源码：[ser_lib/data/transforms/feature.py:17](../ser_lib/data/transforms/feature.py#L17)。

时间掩码 + 频率掩码（分别评估触发概率由 RandomApply 包装器决定）。

基类：`torch.nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, time_mask_param: int=30, freq_mask_param: int=15) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, features: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-addgaussiannoise"></a>

#### `ser_lib.data.transforms.waveform.AddGaussianNoise`

公开导入：`ser_lib.data.transforms.waveform.AddGaussianNoise`。

源码：[ser_lib/data/transforms/waveform.py:41](../ser_lib/data/transforms/waveform.py#L41)。

按目标信噪比注入高斯白噪声。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, snr_db: float=15.0) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-normalize"></a>

#### `ser_lib.data.transforms.waveform.Normalize`

公开导入：`ser_lib.data.transforms.waveform.Normalize`。

源码：[ser_lib/data/transforms/waveform.py:30](../ser_lib/data/transforms/waveform.py#L30)。

逐条 waveform 归一化（确定性，零均值单位方差）。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-pitchshift"></a>

#### `ser_lib.data.transforms.waveform.PitchShift`

公开导入：`ser_lib.data.transforms.waveform.PitchShift`。

源码：[ser_lib/data/transforms/waveform.py:92](../ser_lib/data/transforms/waveform.py#L92)。

音高偏移（半音）。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, sample_rate: int=16000, n_steps: int=4) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-timeshift"></a>

#### `ser_lib.data.transforms.waveform.TimeShift`

公开导入：`ser_lib.data.transforms.waveform.TimeShift`。

源码：[ser_lib/data/transforms/waveform.py:59](../ser_lib/data/transforms/waveform.py#L59)。

时间平移，越界部分用零填充（输出长度不变）。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, max_ratio: float=0.2) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-timestretch"></a>

#### `ser_lib.data.transforms.waveform.TimeStretch`

公开导入：`ser_lib.data.transforms.waveform.TimeStretch`。

源码：[ser_lib/data/transforms/waveform.py:105](../ser_lib/data/transforms/waveform.py#L105)。

时间拉伸（相位声码器；输出长度随 rate 变化）。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, rate: float=1.2, n_fft: int=1024, hop_length: int=256) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-volumescale"></a>

#### `ser_lib.data.transforms.waveform.VolumeScale`

公开导入：`ser_lib.data.transforms.waveform.VolumeScale`。

源码：[ser_lib/data/transforms/waveform.py:79](../ser_lib/data/transforms/waveform.py#L79)。

随机音量缩放，模拟麦克风远近波动。

基类：`nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, gain_min: float=0.5, gain_max: float=1.5) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `forward`

```python
forward(self, waveform: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-data-transforms-waveform-waveform_transform_specs"></a>

#### `ser_lib.data.transforms.waveform.WAVEFORM_TRANSFORM_SPECS`

公开导入：`ser_lib.data.transforms.waveform.WAVEFORM_TRANSFORM_SPECS`。

源码：[ser_lib/data/transforms/waveform.py:135](../ser_lib/data/transforms/waveform.py#L135)。

类型别名、常量或共享实例定义：

```python
WAVEFORM_TRANSFORM_SPECS: dict[str, tuple[type[nn.Module], type[BaseModel], ComponentDescriptor]] = {'normalize': (Normalize, NormalizeConfig, ComponentDescriptor(id='normalize', display_name='波形归一化', category='waveform_transform', description='零均值单位方差归一化（确定性）。', config_schema=NormalizeConfig.model_json_schema())), 'gaussian_noise': (AddGaussianNoise, GaussianNoiseConfig, ComponentDescriptor(id='gaussian_noise', display_name='高斯噪声', category='waveform_transform', description='按目标信噪比 (dB) 注入高斯白噪声。', config_schema=GaussianNoiseConfig.model_json_schema())), 'time_shift': (TimeShift, TimeShiftConfig, ComponentDescriptor(id='time_shift', display_name='时间平移', category='waveform_transform', description='随机左右平移波形，零填充，输出长度不变。', config_schema=TimeShiftConfig.model_json_schema())), 'volume_scale': (VolumeScale, VolumeScaleConfig, ComponentDescriptor(id='volume_scale', display_name='音量缩放', category='waveform_transform', description='在 [gain_min, gain_max] 内随机缩放音量。', config_schema=VolumeScaleConfig.model_json_schema())), 'pitch_shift': (PitchShift, PitchShiftConfig, ComponentDescriptor(id='pitch_shift', display_name='音高偏移', category='waveform_transform', status='experimental', description='按半音数偏移音高（experimental）。', config_schema=PitchShiftConfig.model_json_schema())), 'time_stretch': (TimeStretch, TimeStretchConfig, ComponentDescriptor(id='time_stretch', display_name='时间拉伸', category='waveform_transform', status='experimental', description='相位声码器时间拉伸，输出长度随 rate 变化（experimental）。', config_schema=TimeStretchConfig.model_json_schema()))}
```

<a id="ser_lib-data-types-audiodata"></a>

#### `ser_lib.data.types.AudioData`

公开导入：`ser_lib.data.AudioData`。

源码：[ser_lib/data/types.py:137](../ser_lib/data/types.py#L137)。

AudioLoader 的输出。

约束（设计文档 §5.2）：

- ``waveform`` 始终是二维 ``[C, T]``；单声道策略下 ``C == 1``，仍保留 channel 维。
- 默认 dtype 为 ``torch.float32``。
- Loader 不做 ``squeeze()``。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `waveform` | `torch.Tensor` | `必填（无默认值）` |
| `sample_rate` | `int` | `必填（无默认值）` |
| `source_path` | `Path` | `必填（无默认值）` |
| `original_sample_rate` | `int` | `必填（无默认值）` |
| `num_frames` | `int` | `必填（无默认值）` |

构造时的字段约束：

- `ValueError(f'AudioData.waveform 必须是 [C, T] 二维张量，实际 {self.waveform.dim()}D {tuple(self.waveform.shape)}')`
- `ValueError(f'AudioData.waveform 不允许空音频，实际 shape {tuple(self.waveform.shape)}')`
- `ValueError(f'AudioData.waveform dtype 必须是 float32，实际: {self.waveform.dtype}')`
- `ValueError(f'AudioData 采样率必须为正，实际 sample_rate={self.sample_rate}, original_sample_rate={self.original_sample_rate}')`
- `ValueError('AudioData.waveform 包含 NaN/Inf')`

<a id="ser_lib-data-types-audiorecord"></a>

#### `ser_lib.data.types.AudioRecord`

公开导入：`ser_lib.data.AudioRecord`。

源码：[ser_lib/data/types.py:69](../ser_lib/data/types.py#L69)。

Manifest 中的一条音频记录。

Attributes:
    uid: 记录唯一 ID，在一个 manifest 中必须唯一。
    audio_path: 音频路径；可以是相对路径，解析由 Manifest/Resolver 完成。
    label: 类别标签；``None`` 表示无标签推理数据。
    start_ms: 片段起始毫秒（含），必须 ``>= 0``。
    end_ms: 片段结束毫秒（不含），与 ``start_ms`` 同时存在时必须 ``end_ms > start_ms``。
    speaker_id: 说话人 ID。
    sample_rate_hint: 数据源声明的原始采样率提示，可省去 probing。
    metadata: 附加业务字段；下游组件不得原地修改。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `audio_path` | `Path` | `必填（无默认值）` |
| `label` | `int &#124; None` | `None` |
| `start_ms` | `int &#124; None` | `None` |
| `end_ms` | `int &#124; None` | `None` |
| `speaker_id` | `str &#124; None` | `None` |
| `sample_rate_hint` | `int &#124; None` | `None` |
| `metadata` | `Mapping[str, Any]` | `field(default_factory=dict)` |

构造时的字段约束：

- `ValueError(f'AudioRecord.uid 必须是非空字符串，实际: {self.uid!r}')`
- `ValueError(f'AudioRecord.audio_path 必须是 pathlib.Path，实际: {type(self.audio_path)!r}')`
- `ValueError(f'AudioRecord.label 必须是 int 或 None，实际: {self.label!r}')`
- `ValueError(f'AudioRecord.start_ms 必须是整数或 None，实际: {self.start_ms!r}')`
- `ValueError(f'AudioRecord.start_ms 必须 >= 0，实际: {self.start_ms} (uid={self.uid})')`
- `ValueError(f'AudioRecord.end_ms 必须是整数或 None，实际: {self.end_ms!r}')`
- `ValueError(f'AudioRecord 要求 end_ms > start_ms（省略 start_ms 时按 0 处理），实际 start_ms={self.start_ms}, end_ms={self.end_ms} (uid={self.uid})')`
- `ValueError(f'AudioRecord.sample_rate_hint 必须为正整数，实际: {self.sample_rate_hint!r}')`

<a id="ser_lib-data-types-representationoutput"></a>

#### `ser_lib.data.types.RepresentationOutput`

公开导入：`ser_lib.data.RepresentationOutput`。

源码：[ser_lib/data/types.py:337](../ser_lib/data/types.py#L337)。

Representation 的输出。

约束：

- 单一波形表示统一使用 key ``waveform``；单一声学表示统一使用 key ``features``；
  多分支表示使用有语义的稳定 key。
- 只有时序输入需要出现在 ``lengths``。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `inputs` | `dict[str, torch.Tensor]` | `必填（无默认值）` |
| `lengths` | `dict[str, int]` | `必填（无默认值）` |

<a id="ser_lib-data-types-serbatch"></a>

#### `ser_lib.data.types.SERBatch`

公开导入：`ser_lib.SERBatch`、`ser_lib.data.SERBatch`。

源码：[ser_lib/data/types.py:372](../ser_lib/data/types.py#L372)。

Collator 的批次输出（设计文档 §5.6）。

约束：

- 分类标签 dtype 为 ``torch.long``。
- 无标签推理 batch 的 ``labels`` 为 ``None``。
- mask 使用 ``True`` 表示有效位置，``False`` 表示 padding。
- ``window_map[i]`` 表示第 i 个滑窗来自原始 batch 的哪个样本。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `inputs` | `dict[str, torch.Tensor]` | `必填（无默认值）` |
| `lengths` | `dict[str, torch.Tensor]` | `必填（无默认值）` |
| `masks` | `dict[str, torch.Tensor]` | `必填（无默认值）` |
| `labels` | `torch.Tensor &#124; None` | `必填（无默认值）` |
| `uids` | `list[str]` | `必填（无默认值）` |
| `metadata` | `list[dict[str, Any]]` | `必填（无默认值）` |
| `window_map` | `torch.Tensor &#124; None` | `None` |

构造时的字段约束：

- `ValueError(f'SERBatch.labels dtype 必须是 torch.long，实际: {self.labels.dtype}')`
- `ValueError(f'SERBatch.lengths 中的 key 必须属于 inputs，未知 key: {sorted(unknown_lengths)}')`
- `ValueError(f'SERBatch.masks 中的 key 必须属于 inputs，未知 key: {sorted(unknown_masks)}')`
- `ValueError(f'SERBatch.inputs 的 batch size 不一致: {batch_sizes}')`
- `ValueError(f'SERBatch.labels 必须是 [B]，期望 ({batch_size},)，实际 {tuple(self.labels.shape)}')`
- `ValueError(f'SERBatch.uids/metadata 必须与 batch 对齐: B={batch_size}, uids={len(self.uids)}, metadata={len(self.metadata)}')`
- `ValueError(f'window_map 行数 ({self.window_map.shape[0]}) 必须与 labels 数量 ({self.labels.shape[0]}) 一致')`
- `ValueError(f"SERBatch.lengths['{key}'] 必须是 shape=[B] 的 long tensor，实际 dtype={value.dtype}, shape={tuple(value.shape)}")`
- `ValueError(f"SERBatch.masks['{key}'] 必须是 shape=[B,T] 的 bool tensor，实际 dtype={value.dtype}, shape={tuple(value.shape)}")`
- `ValueError(f"SERBatch.lengths['{key}'] 超过 mask 的时间长度")`
- `ValueError(f'window_map 必须是 shape=[B] 的 long tensor，实际 dtype={self.window_map.dtype}, shape={tuple(self.window_map.shape)}')`
- `ValueError('window_map 不允许包含负索引')`

<a id="ser_lib-data-types-sersample"></a>

#### `ser_lib.data.types.SERSample`

公开导入：`ser_lib.data.SERSample`。

源码：[ser_lib/data/types.py:352](../ser_lib/data/types.py#L352)。

Dataset 的单样本输出。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `inputs` | `dict[str, torch.Tensor]` | `必填（无默认值）` |
| `lengths` | `dict[str, int]` | `必填（无默认值）` |
| `label` | `int &#124; None` | `必填（无默认值）` |
| `metadata` | `dict[str, Any]` | `必填（无默认值）` |

构造时的字段约束：

- `ValueError('SERSample.uid 不能为空')`
- `ValueError(f'SERSample.lengths 中的 key 必须属于 inputs，未知 key: {sorted(unknown_lengths)}')`

<a id="ser_lib-data-types-tensorspec"></a>

#### `ser_lib.data.types.TensorSpec`

公开导入：`ser_lib.data.TensorSpec`。

源码：[ser_lib/data/types.py:177](../ser_lib/data/types.py#L177)。

单个输入 tensor 的形状契约。

Attributes:
    layout: 白名单 layout（``T`` / ``FT`` / ``TD`` / ``D`` / ``CFT``）。
    dtype: 期望 dtype。
    feature_dim: 固定特征维度（如 n_mels）；``None`` 表示不固定。
    time_axis: 时间轴索引；``None`` 表示非时序输入（如 ``D``）。
    pad_value: collate 时使用的 padding 值。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `layout` | `str` | `必填（无默认值）` |
| `dtype` | `torch.dtype` | `torch.float32` |
| `feature_dim` | `int &#124; None` | `None` |
| `time_axis` | `int &#124; None` | `None` |
| `pad_value` | `float` | `0.0` |

构造时的字段约束：

- `ValueError(f'TensorSpec.feature_dim 必须为正，实际: {self.feature_dim}')`
- `ValueError("layout='T' 表示纯时间轴，不允许配置 feature_dim")`
- `ValueError(f'TensorSpec.time_axis={self.time_axis} 与 layout={self.layout} 的标准时间轴 {expected_axis} 不一致；time_axis=None 表示非时序输入')`

##### `temporal`

调用方式：只读属性。

```python
temporal(self) -> bool
```

是否为时序输入。

##### `validate_tensor`

```python
validate_tensor(self, tensor: torch.Tensor, *, key: str, uid: str | None=None, error_cls: type[SERDataError]=RepresentationError) -> None
```

校验单个 tensor 是否满足本 spec。

Args:
    tensor: 待校验张量。
    key: 输入 key 名称。
    uid: 样本 uid（批处理上下文传 ``None``）。
    error_cls: 使用的异常类型；Dataset/Pipeline 上下文用 ``RepresentationError``，
        Collator 上下文用 ``CollationError``。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `error_cls(f"输入 '{key}' 不满足 layout '{self.layout}': 期望 {_LAYOUT_SHAPE_TABLE[self.layout][0]}D，实际 {tensor.dim()}D {tuple(tensor.shape)}", uid=uid, component=key, stage='spec_validation')`
- `error_cls(f"输入 '{key}' dtype 不匹配: 期望 {self.dtype}，实际 {tensor.dtype}", uid=uid, component=key, stage='spec_validation')`
- `error_cls(f"输入 '{key}' feature_dim 不匹配: 期望 {self.feature_dim}，实际 {tensor.shape[dim]} (shape {tuple(tensor.shape)})", uid=uid, component=key, stage='spec_validation')`

<a id="ser_lib-data-types-move_batch_to_device"></a>

#### `ser_lib.data.types.move_batch_to_device`

公开导入：`ser_lib.engine.training.trainer.move_batch_to_device`、`ser_lib.engine.training.move_batch_to_device`。

源码：[ser_lib/data/types.py:447](../ser_lib/data/types.py#L447)。

```python
move_batch_to_device(batch: SERBatch, device: torch.device) -> SERBatch
```

将 batch 中的 tensor 移动到目标设备，保留元数据。

<a id="ser_lib-data-types-validate_sample_contract"></a>

#### `ser_lib.data.types.validate_sample_contract`

公开导入：`ser_lib.data.validate_sample_contract`。

源码：[ser_lib/data/types.py:459](../ser_lib/data/types.py#L459)。

```python
validate_sample_contract(sample: SERSample, specs: Mapping[str, TensorSpec]) -> None
```

运行时样本契约校验（debug/strict 模式调用，见设计文档 T3.4）。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RepresentationError(f"样本 '{sample.uid}' 输入 key 与 specs 不一致: 实际 {sorted(sample.inputs)}，期望 {sorted(specs)}", uid=sample.uid, component='pipeline', stage='contract_validation')`
- `RepresentationError(f"样本 '{sample.uid}' 非时序输入 '{key}' 不允许出现在 lengths", uid=sample.uid, component='pipeline', stage='contract_validation')`
- `RepresentationError(f"样本 '{sample.uid}' lengths['{key}']={length} 与时间轴长度 {sample.inputs[key].shape[time_axis]} 不一致", uid=sample.uid, component='pipeline', stage='contract_validation')`

<a id="ser_lib-engine-_seed-seed_experiment_rng"></a>

#### `ser_lib.engine._seed.seed_experiment_rng`

公开导入：`ser_lib.engine._seed.seed_experiment_rng`。

源码：[ser_lib/engine/_seed.py:15](../ser_lib/engine/_seed.py#L15)。

```python
seed_experiment_rng(seed: int, *, deterministic: bool=True) -> None
```

Seed Python, NumPy and Torch before any experiment component is constructed.

<a id="ser_lib-engine-checkpoint-load_checkpoint"></a>

#### `ser_lib.engine.checkpoint.load_checkpoint`

公开导入：`ser_lib.engine.checkpoint.load_checkpoint`、`ser_lib.engine.load_checkpoint`。

源码：[ser_lib/engine/checkpoint.py:163](../ser_lib/engine/checkpoint.py#L163)。

```python
load_checkpoint(path: Path | str, model: SERModel, optimizer: torch.optim.Optimizer | None=None, *, scheduler: torch.optim.lr_scheduler.LRScheduler | None=None, scaler: torch.cuda.amp.GradScaler | None=None, map_location: str | torch.device='cpu', restore_rng: bool=True, expected_trainer_config: dict[str, Any] | None=None, metadata_validator: Callable[[dict[str, Any]], None] | None=None) -> dict[str, Any]
```

严格加载当前结构的可信本地 checkpoint。

``metadata_validator`` 在任何 model/optimizer/scheduler/scaler 状态应用之前执行，
用于高层实验入口检查 lineage、数据指纹和完整实验配置兼容性，避免“不兼容后
才报错但当前对象已被部分恢复”的半状态。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'checkpoint 不存在: {source}')`
- `ValueError('checkpoint 顶层结构必须是映射')`
- `ValueError('checkpoint rng_state 字段不完整或包含未知字段')`
- `ValueError('checkpoint 与当前模型类型不一致')`
- `ValueError('checkpoint 与当前模型配置不一致')`
- `ValueError('checkpoint 缺少合法 model_state')`
- `ValueError('checkpoint trainer_config 与当前训练配置不一致')`
- `ValueError('checkpoint metadata 必须是映射')`

<a id="ser_lib-engine-checkpoint-save_checkpoint"></a>

#### `ser_lib.engine.checkpoint.save_checkpoint`

公开导入：`ser_lib.engine.checkpoint.save_checkpoint`、`ser_lib.engine.save_checkpoint`。

源码：[ser_lib/engine/checkpoint.py:117](../ser_lib/engine/checkpoint.py#L117)。

```python
save_checkpoint(path: Path | str, model: SERModel, optimizer: torch.optim.Optimizer | None, *, epoch: int, scheduler: torch.optim.lr_scheduler.LRScheduler | None=None, scaler: torch.cuda.amp.GradScaler | None=None, metrics: dict[str, float] | None=None, metadata: dict[str, Any] | None=None, trainer_config: dict[str, Any] | None=None) -> Path
```

原子保存继续训练所需状态。

Checkpoint 使用 pickle，只能加载由本库在可信本地环境生成的文件；用于分发
的模型必须使用 artifact。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('checkpoint epoch 不能为负数')`

<a id="ser_lib-engine-checkpoint_catalog-checkpointcatalog"></a>

#### `ser_lib.engine.checkpoint_catalog.CheckpointCatalog`

公开导入：`ser_lib.engine.checkpoint_catalog.CheckpointCatalog`、`ser_lib.engine.CheckpointCatalog`。

源码：[ser_lib/engine/checkpoint_catalog.py:54](../ser_lib/engine/checkpoint_catalog.py#L54)。

Checkpoint 列表；扫描不会调用 `torch.load()`。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `root` | `str` | `必填（无默认值）` |
| `checkpoints` | `tuple[CheckpointInfo, ...]` | `必填（无默认值）` |
| `failures` | `tuple[CheckpointScanFailure, ...]` | `必填（无默认值）` |

##### `total`

调用方式：只读属性。

```python
total(self) -> int
```

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'root': self.root, 'total': self.total, 'checkpoints': [item.to_dict() for item in self.checkpoints], 'failures': [failure.to_dict() for failure in self.failures]}
```

<a id="ser_lib-engine-checkpoint_catalog-checkpointinfo"></a>

#### `ser_lib.engine.checkpoint_catalog.CheckpointInfo`

公开导入：`ser_lib.engine.checkpoint_catalog.CheckpointInfo`、`ser_lib.engine.CheckpointInfo`。

源码：[ser_lib/engine/checkpoint_catalog.py:18](../ser_lib/engine/checkpoint_catalog.py#L18)。

不反序列化 `.pt` 内容即可获得的 checkpoint 文件信息。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `path` | `str` | `必填（无默认值）` |
| `name` | `str` | `必填（无默认值）` |
| `kind` | `CheckpointKind` | `必填（无默认值）` |
| `epoch` | `int &#124; None` | `必填（无默认值）` |
| `size_bytes` | `int` | `必填（无默认值）` |
| `modified_at` | `datetime` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'path': self.path, 'name': self.name, 'kind': self.kind, 'epoch': self.epoch, 'size_bytes': self.size_bytes, 'modified_at': self.modified_at.isoformat()}
```

<a id="ser_lib-engine-checkpoint_catalog-checkpointkind"></a>

#### `ser_lib.engine.checkpoint_catalog.CheckpointKind`

公开导入：`ser_lib.engine.checkpoint_catalog.CheckpointKind`、`ser_lib.engine.CheckpointKind`。

源码：[ser_lib/engine/checkpoint_catalog.py:13](../ser_lib/engine/checkpoint_catalog.py#L13)。

类型别名、常量或共享实例定义：

```python
CheckpointKind = Literal['best', 'last', 'epoch', 'other']
```

<a id="ser_lib-engine-checkpoint_catalog-checkpointscanfailure"></a>

#### `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure`

公开导入：`ser_lib.engine.checkpoint_catalog.CheckpointScanFailure`、`ser_lib.engine.CheckpointScanFailure`。

源码：[ser_lib/engine/checkpoint_catalog.py:40](../ser_lib/engine/checkpoint_catalog.py#L40)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `path` | `str` | `必填（无默认值）` |
| `error_type` | `str` | `必填（无默认值）` |
| `message` | `str` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, str]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'path': self.path, 'error_type': self.error_type, 'message': self.message}
```

<a id="ser_lib-engine-checkpoint_catalog-inspect_checkpoint_file"></a>

#### `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file`

公开导入：`ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file`、`ser_lib.engine.inspect_checkpoint_file`。

源码：[ser_lib/engine/checkpoint_catalog.py:74](../ser_lib/engine/checkpoint_catalog.py#L74)。

```python
inspect_checkpoint_file(path: Path | str) -> CheckpointInfo
```

只读取一个 `.pt` 文件的 stat 信息，不解析 pickle payload。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'checkpoint 文件不存在: {source}')`
- `ValueError(f'checkpoint 文件必须使用 .pt 后缀: {source}')`

<a id="ser_lib-engine-checkpoint_catalog-scan_checkpoints"></a>

#### `ser_lib.engine.checkpoint_catalog.scan_checkpoints`

公开导入：`ser_lib.engine.checkpoint_catalog.scan_checkpoints`、`ser_lib.engine.scan_checkpoints`。

源码：[ser_lib/engine/checkpoint_catalog.py:93](../ser_lib/engine/checkpoint_catalog.py#L93)。

```python
scan_checkpoints(root: Path | str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None) -> CheckpointCatalog
```

扫描 `.pt` checkpoint；不读取模型、optimizer 或 RNG state。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'checkpoint 根目录不存在或不是目录: {root_path}')`

<a id="ser_lib-engine-compatibility-compatibilityreport"></a>

#### `ser_lib.engine.compatibility.CompatibilityReport`

公开导入：`ser_lib.engine.compatibility.CompatibilityReport`、`ser_lib.engine.CompatibilityReport`。

源码：[ser_lib/engine/compatibility.py:16](../ser_lib/engine/compatibility.py#L16)。

模型与数据流水线的非抛异常兼容性检查结果。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `compatible` | `bool` | `必填（无默认值）` |
| `diagnostics` | `tuple[Diagnostic, ...]` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'compatible': self.compatible, 'diagnostics': [diagnostic.to_dict() for diagnostic in self.diagnostics]}
```

<a id="ser_lib-engine-compatibility-inspect_compatibility"></a>

#### `ser_lib.engine.compatibility.inspect_compatibility`

公开导入：`ser_lib.engine.compatibility.inspect_compatibility`、`ser_lib.engine.inspect_compatibility`。

源码：[ser_lib/engine/compatibility.py:48](../ser_lib/engine/compatibility.py#L48)。

```python
inspect_compatibility(representation_specs: Mapping[str, TensorSpec], model_spec: ModelSpec, batching_config: BatchingConfig, *, num_classes: int | None=None, sample_rate: int | None=None) -> CompatibilityReport
```

检查兼容性并返回全部问题，不抛 ``CompatibilityError``。

<a id="ser_lib-engine-compatibility-validate_compatibility"></a>

#### `ser_lib.engine.compatibility.validate_compatibility`

公开导入：`ser_lib.engine.compatibility.validate_compatibility`、`ser_lib.engine.validate_compatibility`。

源码：[ser_lib/engine/compatibility.py:223](../ser_lib/engine/compatibility.py#L223)。

```python
validate_compatibility(representation_specs: Mapping[str, TensorSpec], model_spec: ModelSpec, batching_config: BatchingConfig, *, num_classes: int | None=None, sample_rate: int | None=None) -> None
```

保留历史 raise 接口；内部复用 ``inspect_compatibility``。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `CompatibilityError('模型兼容性校验失败:\n- ' + '\n- '.join(problems), component='compatibility_check', stage='task_startup')`

<a id="ser_lib-engine-eta-etaestimator"></a>

#### `ser_lib.engine.eta.EtaEstimator`

公开导入：`ser_lib.engine.eta.EtaEstimator`、`ser_lib.engine.EtaEstimator`。

源码：[ser_lib/engine/eta.py:44](../ser_lib/engine/eta.py#L44)。

按 phase 维护固定 recent-N 窗口的 ETA 状态。

只接收调用方已有的 batch duration/sample count，不读取系统时钟、不 sleep、
不知道 DataLoader/模型/optimizer，实现与训练关键路径解耦。

##### `__init__`

```python
__init__(self, *, window_size: int=20, warmup_batches: int=3) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('window_size 必须 >= 1')`
- `ValueError('warmup_batches 必须 >= 1')`
- `ValueError('warmup_batches 不能大于 window_size')`

##### `reset`

```python
reset(self, phase: str | None=None) -> None
```

##### `record_batch`

```python
record_batch(self, duration_seconds: float, samples: int=0, *, phase: str='train') -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('phase 不能为空')`
- `ValueError('duration_seconds 必须 >= 0')`
- `ValueError('samples 必须 >= 0')`

##### `snapshot`

```python
snapshot(self, *, phase: str='train', completed_batches: int, total_batches: int | None, future_batches: int=0) -> EtaSnapshot
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('completed_batches 必须 >= 0')`
- `ValueError('total_batches 不能小于 completed_batches')`
- `ValueError('future_batches 必须 >= 0')`

<a id="ser_lib-engine-eta-etasnapshot"></a>

#### `ser_lib.engine.eta.EtaSnapshot`

公开导入：`ser_lib.engine.eta.EtaSnapshot`、`ser_lib.engine.EtaSnapshot`。

源码：[ser_lib/engine/eta.py:11](../ser_lib/engine/eta.py#L11)。

某一阶段的稳定 ETA/吞吐快照。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `phase` | `str` | `必填（无默认值）` |
| `ready` | `bool` | `必填（无默认值）` |
| `samples_seen` | `int` | `必填（无默认值）` |
| `batches_seen` | `int` | `必填（无默认值）` |
| `average_batch_seconds` | `float &#124; None` | `必填（无默认值）` |
| `batches_per_second` | `float &#124; None` | `必填（无默认值）` |
| `samples_per_second` | `float &#124; None` | `必填（无默认值）` |
| `phase_remaining_seconds` | `float &#124; None` | `必填（无默认值）` |
| `global_remaining_seconds` | `float &#124; None` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'phase': self.phase, 'ready': self.ready, 'samples_seen': self.samples_seen, 'batches_seen': self.batches_seen, 'average_batch_seconds': self.average_batch_seconds, 'batches_per_second': self.batches_per_second, 'samples_per_second': self.samples_per_second, 'phase_remaining_seconds': self.phase_remaining_seconds, 'global_remaining_seconds': self.global_remaining_seconds}
```

<a id="ser_lib-engine-evaluation_records-evaluationmetadata"></a>

#### `ser_lib.engine.evaluation_records.EvaluationMetadata`

公开导入：`ser_lib.engine.evaluation_records.EvaluationMetadata`、`ser_lib.engine.EvaluationMetadata`。

源码：[ser_lib/engine/evaluation_records.py:97](../ser_lib/engine/evaluation_records.py#L97)。

评估开始前即可创建并用于事件上下文的稳定 lineage。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `evaluation_id` | `str` | `必填（无默认值）` |
| `created_at` | `datetime` | `必填（无默认值）` |
| `source_artifact` | `str` | `必填（无默认值）` |
| `source_run_id` | `str &#124; None` | `必填（无默认值）` |
| `dataset_id` | `str` | `必填（无默认值）` |
| `dataset_fingerprint` | `str &#124; None` | `必填（无默认值）` |
| `model_name` | `str` | `必填（无默认值）` |
| `split` | `str` | `必填（无默认值）` |
| `device` | `str` | `必填（无默认值）` |
| `library_version` | `str` | `必填（无默认值）` |

构造时的字段约束：

- `ValueError('created_at 必须包含时区')`
- `ValueError('source_run_id 不能是空字符串')`
- `ValueError('dataset_fingerprint 不能是空字符串')`
- `ValueError(f'{name} 不能为空')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'evaluation_id': self.evaluation_id, 'created_at': self.created_at.isoformat(), 'source_artifact': self.source_artifact, 'source_run_id': self.source_run_id, 'dataset_id': self.dataset_id, 'dataset_fingerprint': self.dataset_fingerprint, 'model_name': self.model_name, 'split': self.split, 'device': self.device, 'library_version': self.library_version}
```

<a id="ser_lib-engine-evaluation_records-evaluationrecord"></a>

#### `ser_lib.engine.evaluation_records.EvaluationRecord`

公开导入：`ser_lib.engine.evaluation_records.EvaluationRecord`、`ser_lib.engine.EvaluationRecord`。

源码：[ser_lib/engine/evaluation_records.py:146](../ser_lib/engine/evaluation_records.py#L146)。

严格、JSON-safe 的评估终态记录。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `evaluation_id` | `str` | `必填（无默认值）` |
| `directory` | `str` | `必填（无默认值）` |
| `created_at` | `datetime` | `必填（无默认值）` |
| `started_at` | `datetime` | `必填（无默认值）` |
| `finished_at` | `datetime` | `必填（无默认值）` |
| `duration_seconds` | `float` | `必填（无默认值）` |
| `source_artifact` | `str` | `必填（无默认值）` |
| `source_run_id` | `str &#124; None` | `必填（无默认值）` |
| `dataset_id` | `str` | `必填（无默认值）` |
| `dataset_fingerprint` | `str &#124; None` | `必填（无默认值）` |
| `model_name` | `str` | `必填（无默认值）` |
| `split` | `str` | `必填（无默认值）` |
| `device` | `str` | `必填（无默认值）` |
| `library_version` | `str` | `必填（无默认值）` |
| `sample_count` | `int` | `必填（无默认值）` |
| `metrics` | `dict[str, float]` | `必填（无默认值）` |
| `metrics_file` | `str` | `必填（无默认值）` |
| `predictions_file` | `str &#124; None` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

##### `from_evaluation`

调用方式：类方法，可直接通过类名调用。

```python
from_evaluation(cls, directory: Path | str, metadata: EvaluationMetadata, result: EvaluationResult, *, started_at: datetime, finished_at: datetime, predictions_file: str | None='predictions.jsonl') -> 'EvaluationRecord'
```

##### `from_dict`

调用方式：类方法，可直接通过类名调用。

```python
from_dict(cls, value: Mapping[str, Any], *, directory: Path | str | None=None) -> 'EvaluationRecord'
```

<a id="ser_lib-engine-evaluation_records-build_evaluation_metadata"></a>

#### `ser_lib.engine.evaluation_records.build_evaluation_metadata`

公开导入：`ser_lib.engine.evaluation_records.build_evaluation_metadata`、`ser_lib.engine.build_evaluation_metadata`。

源码：[ser_lib/engine/evaluation_records.py:225](../ser_lib/engine/evaluation_records.py#L225)。

```python
build_evaluation_metadata(*, source_artifact: Path | str, dataset_id: str, model_name: str, split: str, device: str, library_version: str | None=None, source_run_id: str | None=None, dataset_fingerprint: str | None=None, evaluation_id: str | None=None, created_at: datetime | None=None) -> EvaluationMetadata
```

构造评估 lineage；默认使用当前库版本，不执行隐藏 I/O。

<a id="ser_lib-engine-evaluation_records-load_evaluation_record"></a>

#### `ser_lib.engine.evaluation_records.load_evaluation_record`

公开导入：`ser_lib.engine.evaluation_records.load_evaluation_record`、`ser_lib.engine.load_evaluation_record`。

源码：[ser_lib/engine/evaluation_records.py:287](../ser_lib/engine/evaluation_records.py#L287)。

```python
load_evaluation_record(path: Path | str) -> EvaluationRecord
```

读取 evaluation 目录或 ``evaluation.json``；目录以实际位置为准。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'评估运行记录不存在: {record_path}')`
- `ValueError('evaluation.json 顶层必须是映射')`

<a id="ser_lib-engine-evaluation_records-write_evaluation_record"></a>

#### `ser_lib.engine.evaluation_records.write_evaluation_record`

公开导入：`ser_lib.engine.evaluation_records.write_evaluation_record`、`ser_lib.engine.write_evaluation_record`。

源码：[ser_lib/engine/evaluation_records.py:253](../ser_lib/engine/evaluation_records.py#L253)。

```python
write_evaluation_record(directory: Path | str, metadata: EvaluationMetadata, result: EvaluationResult, *, started_at: datetime, finished_at: datetime, predictions_file: str | None='predictions.jsonl') -> Path
```

把终态评估记录原子写入 ``evaluation.json``。

<a id="ser_lib-engine-evaluation_reports-evaluationpredictionfileinfo"></a>

#### `ser_lib.engine.evaluation_reports.EvaluationPredictionFileInfo`

公开导入：`ser_lib.engine.evaluation_reports.EvaluationPredictionFileInfo`、`ser_lib.engine.EvaluationPredictionFileInfo`。

源码：[ser_lib/engine/evaluation_reports.py:134](../ser_lib/engine/evaluation_reports.py#L134)。

由 evaluation metadata 与文件 stat 得到的 prediction 文件信息。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `path` | `str &#124; None` | `必填（无默认值）` |
| `exists` | `bool` | `必填（无默认值）` |
| `size_bytes` | `int &#124; None` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'path': self.path, 'exists': self.exists, 'size_bytes': self.size_bytes}
```

<a id="ser_lib-engine-evaluation_reports-evaluationreportinfo"></a>

#### `ser_lib.engine.evaluation_reports.EvaluationReportInfo`

公开导入：`ser_lib.engine.evaluation_reports.EvaluationReportInfo`、`ser_lib.engine.EvaluationReportInfo`。

源码：[ser_lib/engine/evaluation_reports.py:88](../ser_lib/engine/evaluation_reports.py#L88)。

无需读取预测明细即可使用的评估报告信息。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `directory` | `str` | `必填（无默认值）` |
| `loss` | `float` | `必填（无默认值）` |
| `accuracy` | `float` | `必填（无默认值）` |
| `war` | `float` | `必填（无默认值）` |
| `uar` | `float` | `必填（无默认值）` |
| `macro_f1` | `float` | `必填（无默认值）` |
| `weighted_precision` | `float` | `必填（无默认值）` |
| `weighted_recall` | `float` | `必填（无默认值）` |
| `weighted_f1` | `float` | `必填（无默认值）` |
| `balanced_accuracy` | `float` | `必填（无默认值）` |
| `matthews_correlation_coefficient` | `float` | `必填（无默认值）` |
| `cohen_kappa` | `float` | `必填（无默认值）` |
| `sample_count` | `int` | `必填（无默认值）` |
| `confusion_matrix` | `tuple[tuple[int, ...], ...]` | `必填（无默认值）` |
| `per_class` | `tuple[ClassMetrics, ...]` | `必填（无默认值）` |
| `predictions_file` | `str &#124; None` | `必填（无默认值）` |
| `predictions_bytes` | `int &#124; None` | `必填（无默认值）` |
| `metric_unit` | `Literal['sample', 'window']` | `'sample'` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'directory': self.directory, 'metric_unit': self.metric_unit, 'loss': self.loss, 'accuracy': self.accuracy, 'war': self.war, 'uar': self.uar, 'macro_f1': self.macro_f1, 'weighted_precision': self.weighted_precision, 'weighted_recall': self.weighted_recall, 'weighted_f1': self.weighted_f1, 'balanced_accuracy': self.balanced_accuracy, 'matthews_correlation_coefficient': self.matthews_correlation_coefficient, 'cohen_kappa': self.cohen_kappa, 'sample_count': self.sample_count, 'confusion_matrix': [list(row) for row in self.confusion_matrix], 'per_class': [metric.to_dict() for metric in self.per_class], 'predictions_file': self.predictions_file, 'predictions_bytes': self.predictions_bytes}
```

<a id="ser_lib-engine-evaluation_reports-inspect_evaluation_prediction_file"></a>

#### `ser_lib.engine.evaluation_reports.inspect_evaluation_prediction_file`

公开导入：`ser_lib.engine.evaluation_reports.inspect_evaluation_prediction_file`、`ser_lib.engine.inspect_evaluation_prediction_file`。

源码：[ser_lib/engine/evaluation_reports.py:196](../ser_lib/engine/evaluation_reports.py#L196)。

```python
inspect_evaluation_prediction_file(run: EvaluationRecord) -> EvaluationPredictionFileInfo
```

按 ``evaluation.json`` 声明的文件名做 stat，不打开 prediction 内容。

<a id="ser_lib-engine-evaluation_reports-inspect_evaluation_report"></a>

#### `ser_lib.engine.evaluation_reports.inspect_evaluation_report`

公开导入：`ser_lib.engine.evaluation_reports.inspect_evaluation_report`、`ser_lib.engine.inspect_evaluation_report`。

源码：[ser_lib/engine/evaluation_reports.py:149](../ser_lib/engine/evaluation_reports.py#L149)。

```python
inspect_evaluation_report(directory: Path | str) -> EvaluationReportInfo
```

读取并严格校验 ``metrics.json``，但不读取 ``predictions.jsonl`` 内容。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'评估报告目录不存在或不是目录: {target}')`
- `FileNotFoundError(f'评估 metrics.json 不存在: {metrics_path}')`
- `ValueError('metrics.json 顶层必须是映射')`

<a id="ser_lib-engine-evaluation_reports-iter_evaluation_predictions"></a>

#### `ser_lib.engine.evaluation_reports.iter_evaluation_predictions`

公开导入：`ser_lib.engine.evaluation_reports.iter_evaluation_predictions`、`ser_lib.engine.iter_evaluation_predictions`。

源码：[ser_lib/engine/evaluation_reports.py:217](../ser_lib/engine/evaluation_reports.py#L217)。

```python
iter_evaluation_predictions(directory: Path | str, *, incorrect_only: bool=False, target: int | None=None, predicted: int | None=None, cancellation: CancellationCheck | None=None) -> Iterator[PredictionRecord]
```

惰性校验并产出 ``predictions.jsonl`` 中满足条件的记录。

每次只解析当前行；函数不扫描总匹配数，也不提供分页元数据。调用方可使用
``itertools.islice`` 等 iterator 工具进行有界切片。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('target 必须 >= 0')`
- `ValueError('predicted 必须 >= 0')`
- `FileNotFoundError(f'评估 predictions.jsonl 不存在: {predictions_path}')`
- `ValueError(f'predictions.jsonl 第 {line_number} 行为空')`
- `ValueError(f'predictions.jsonl 第 {line_number} 行无效: {exc}')`

<a id="ser_lib-engine-evaluator-classmetrics"></a>

#### `ser_lib.engine.evaluator.ClassMetrics`

公开导入：`ser_lib.engine.evaluator.ClassMetrics`、`ser_lib.engine.ClassMetrics`。

源码：[ser_lib/engine/evaluator.py:28](../ser_lib/engine/evaluator.py#L28)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `label_id` | `int` | `必填（无默认值）` |
| `label_name` | `str` | `必填（无默认值）` |
| `precision` | `float` | `必填（无默认值）` |
| `recall` | `float` | `必填（无默认值）` |
| `f1` | `float` | `必填（无默认值）` |
| `support` | `int` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, object]
```

返回稳定、可直接 JSON 序列化的类别指标。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'label_id': self.label_id, 'label_name': self.label_name, 'precision': self.precision, 'recall': self.recall, 'f1': self.f1, 'support': self.support}
```

<a id="ser_lib-engine-evaluator-evaluationresult"></a>

#### `ser_lib.engine.evaluator.EvaluationResult`

公开导入：`ser_lib.engine.evaluator.EvaluationResult`、`ser_lib.engine.EvaluationResult`。

源码：[ser_lib/engine/evaluator.py:118](../ser_lib/engine/evaluator.py#L118)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `accuracy` | `float` | `必填（无默认值）` |
| `macro_f1` | `float` | `必填（无默认值）` |
| `uar` | `float` | `必填（无默认值）` |
| `confusion_matrix` | `torch.Tensor` | `必填（无默认值）` |
| `sample_count` | `int` | `必填（无默认值）` |
| `loss` | `float` | `必填（无默认值）` |
| `war` | `float` | `必填（无默认值）` |
| `per_class` | `tuple[ClassMetrics, ...]` | `必填（无默认值）` |
| `predictions` | `tuple[PredictionRecord, ...]` | `必填（无默认值）` |
| `weighted_precision` | `float` | `必填（无默认值）` |
| `weighted_recall` | `float` | `必填（无默认值）` |
| `weighted_f1` | `float` | `必填（无默认值）` |
| `balanced_accuracy` | `float` | `必填（无默认值）` |
| `matthews_correlation_coefficient` | `float` | `必填（无默认值）` |
| `cohen_kappa` | `float` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self, *, include_predictions: bool=True) -> dict[str, object]
```

返回公开 Result 的统一 JSON-safe 表示。

``include_predictions=False`` 适合指标摘要和 ``metrics.json``；默认保留
完整预测，方便 Web Backend 直接消费结果而无需了解内部 dataclass/Tensor。

##### `summary_dict`

```python
summary_dict(self) -> dict[str, object]
```

兼容旧 API：返回不含样本明细的 JSON-safe 聚合报告。

<a id="ser_lib-engine-evaluator-jsonlpredictionsink"></a>

#### `ser_lib.engine.evaluator.JsonlPredictionSink`

公开导入：`ser_lib.engine.evaluator.JsonlPredictionSink`、`ser_lib.engine.JsonlPredictionSink`。

源码：[ser_lib/engine/evaluator.py:75](../ser_lib/engine/evaluator.py#L75)。

把评估预测增量写入 JSONL，避免完整预测常驻内存。

Sink 生命周期由调用方管理；推荐使用 ``with``。评估器只调用 ``write()``，
不会擅自关闭外部资源。

##### `__init__`

```python
__init__(self, path: Path | str, *, append: bool=False, flush_each: bool=False) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `write`

```python
write(self, record: PredictionRecord) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('JsonlPredictionSink 已关闭')`

##### `flush`

```python
flush(self) -> None
```

##### `close`

```python
close(self) -> None
```

##### `__enter__`

```python
__enter__(self) -> 'JsonlPredictionSink'
```

##### `__exit__`

```python
__exit__(self, exc_type: object, exc: object, traceback: object) -> None
```

<a id="ser_lib-engine-evaluator-predictionrecord"></a>

#### `ser_lib.engine.evaluator.PredictionRecord`

公开导入：`ser_lib.engine.evaluator.PredictionRecord`、`ser_lib.engine.PredictionRecord`。

源码：[ser_lib/engine/evaluator.py:49](../ser_lib/engine/evaluator.py#L49)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `target` | `int` | `必填（无默认值）` |
| `predicted` | `int` | `必填（无默认值）` |
| `confidence` | `float` | `必填（无默认值）` |
| `probabilities` | `tuple[float, ...]` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, object]
```

返回单样本预测的 JSON-safe 表示。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'uid': self.uid, 'target': self.target, 'predicted': self.predicted, 'confidence': self.confidence, 'probabilities': list(self.probabilities)}
```

<a id="ser_lib-engine-evaluator-predictionsink"></a>

#### `ser_lib.engine.evaluator.PredictionSink`

公开导入：`ser_lib.engine.evaluator.PredictionSink`、`ser_lib.engine.PredictionSink`。

源码：[ser_lib/engine/evaluator.py:67](../ser_lib/engine/evaluator.py#L67)。

评估逐样本结果的增量消费者协议。

基类：`Protocol`。继承的字段/方法继续适用。

##### `write`

```python
write(self, record: PredictionRecord) -> None
```

消费一条已经完成 softmax/argmax 的预测记录。

<a id="ser_lib-engine-evaluator-evaluate"></a>

#### `ser_lib.engine.evaluator.evaluate`

公开导入：`ser_lib.evaluate`、`ser_lib.engine.evaluator.evaluate`、`ser_lib.engine.evaluate`。

源码：[ser_lib/engine/evaluator.py:248](../ser_lib/engine/evaluator.py#L248)。

```python
evaluate(model: SERModel, batches: Iterable[SERBatch], *, num_classes: int, device: str | torch.device='cpu', labels: Mapping[int, str] | None=None, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, loss_fn: torch.nn.Module | None=None, event_context: EventContext | None=None, split: str | None=None, prediction_sink: PredictionSink | None=None, retain_predictions: bool=True) -> EvaluationResult
```

评估分类模型，并可增量输出每个样本的预测。

``prediction_sink`` 会在每条预测生成后同步接收 ``PredictionRecord``；设置
``retain_predictions=False`` 后，``EvaluationResult.predictions`` 保持为空，
可将百万级评估的预测内存从 O(N) 降为 O(1)。默认值完全保持旧行为。

``loss_fn`` 的 scalar 输出默认按当前 batch 的 sample mean 解释。需要不同归约
质量的 loss 可以实现 ``reduction_denominator(targets)``；评估器会按
``Σ(loss_i × denominator_i) / Σ denominator_i`` 汇总，从而保持 batch 划分不变性。

``event_context`` 是与 Web/传输无关的运行上下文，可原生携带 ``run_id``、
``epoch``、``total_epochs``、``global_step`` 等字段；``split`` 用于 standalone
evaluation 的便捷覆盖。能获取 ``len(batches)`` 时进度事件会提供 ``total``，
否则保持 ``None``。

``event_callback`` 是同步 fail-fast hook：callback 异常会终止评估并传播给调用方；
评估器仍保证在退出前恢复模型原始 train/eval 状态。

Sliding collator 产生的窗口被视为独立行；原始样本级窗口聚合属于推理层，
评估器不会根据重复 UID 隐式猜测聚合策略。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('num_classes 必须 >= 2')`
- `ValueError('评估请求 CUDA，但当前环境不可用')`
- `ValueError(f'无效评估设备: {device!r}')`
- `ValueError('评估数据为空')`
- `ValueError('评估 batch 必须包含 labels')`
- `FloatingPointError('模型 logits 包含 NaN/Inf')`
- `ValueError(f'模型 logits 期望 [B,{num_classes}]，实际 {tuple(output.logits.shape)}')`
- `ValueError('评估标签超出 [0, num_classes) 范围')`
- `FloatingPointError('评估 loss 为 NaN/Inf')`

<a id="ser_lib-engine-evaluator-write_evaluation_report"></a>

#### `ser_lib.engine.evaluator.write_evaluation_report`

公开导入：`ser_lib.engine.evaluator.write_evaluation_report`、`ser_lib.engine.write_evaluation_report`。

源码：[ser_lib/engine/evaluator.py:527](../ser_lib/engine/evaluator.py#L527)。

```python
write_evaluation_report(directory: Path | str, result: EvaluationResult) -> Path
```

原子写入 ``metrics.json`` 与 ``predictions.jsonl``。

<a id="ser_lib-engine-experiment-evaluationexperimentresult"></a>

#### `ser_lib.engine.experiment.EvaluationExperimentResult`

公开导入：`ser_lib.engine.experiment.EvaluationExperimentResult`、`ser_lib.engine.EvaluationExperimentResult`。

源码：[ser_lib/engine/experiment.py:114](../ser_lib/engine/experiment.py#L114)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `output_dir` | `Path` | `必填（无默认值）` |
| `evaluation` | `EvaluationResult` | `必填（无默认值）` |
| `run` | `EvaluationRecord` | `必填（无默认值）` |
| `run_record` | `Path` | `必填（无默认值）` |
| `metrics_path` | `Path` | `必填（无默认值）` |
| `predictions_path` | `Path &#124; None` | `必填（无默认值）` |
| `metric_unit` | `str` | `'sample'` |

##### `to_dict`

```python
to_dict(self) -> dict[str, object]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{**summary, 'evaluation_id': self.run.evaluation_id, 'source_artifact': self.run.source_artifact, 'source_run_id': self.run.source_run_id, 'dataset_id': self.run.dataset_id, 'dataset_fingerprint': self.run.dataset_fingerprint, 'model_name': self.run.model_name, 'split': self.run.split, 'device': self.run.device, 'sample_count': self.run.sample_count, 'metrics': dict(self.run.metrics), 'output_dir': str(self.output_dir), 'evaluation': evaluation, 'run': run, 'run_record': str(self.run_record), 'metrics_path': str(self.metrics_path), 'predictions_path': str(self.predictions_path) if self.predictions_path is not None else None, 'metric_unit': self.metric_unit}
```

<a id="ser_lib-engine-experiment-experimentcomponents"></a>

#### `ser_lib.engine.experiment.ExperimentComponents`

公开导入：`ser_lib.engine.experiment.ExperimentComponents`、`ser_lib.engine.ExperimentComponents`。

源码：[ser_lib/engine/experiment.py:49](../ser_lib/engine/experiment.py#L49)。

通过完整预检后可直接交给训练代码的运行时组件。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `model` | `SERModel` | `必填（无默认值）` |
| `audio_loader` | `Any` | `必填（无默认值）` |
| `pipeline` | `SamplePipeline` | `必填（无默认值）` |
| `collator` | `SERCollator` | `必填（无默认值）` |

<a id="ser_lib-engine-experiment-trainingexperimentresult"></a>

#### `ser_lib.engine.experiment.TrainingExperimentResult`

公开导入：`ser_lib.engine.experiment.TrainingExperimentResult`、`ser_lib.engine.TrainingExperimentResult`。

源码：[ser_lib/engine/experiment.py:77](../ser_lib/engine/experiment.py#L77)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `output_dir` | `Path` | `必填（无默认值）` |
| `training` | `TrainingResult` | `必填（无默认值）` |
| `run` | `TrainingRecord` | `必填（无默认值）` |
| `run_record` | `Path` | `必填（无默认值）` |
| `metrics_log` | `Path` | `必填（无默认值）` |
| `history_path` | `Path` | `必填（无默认值）` |
| `resumed_from` | `Path &#124; None` | `必填（无默认值）` |
| `last_checkpoint` | `Path &#124; None` | `必填（无默认值）` |
| `best_checkpoint` | `Path &#124; None` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, object]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'run_id': self.training.run_id, 'status': self.training.status, 'history': training['epochs'], 'best_epoch': self.training.best_epoch, 'best_metric': self.training.best_metric, 'monitored_metric': self.training.monitored_metric, 'dataset_id': self.run.dataset_id, 'dataset_fingerprint': self.run.dataset_fingerprint, 'model_id': self.run.model_id, 'output_dir': str(self.output_dir), 'training': training, 'run': run, 'run_record': str(self.run_record), 'metrics_log': str(self.metrics_log), 'history_path': str(self.history_path), 'resumed_from': str(self.resumed_from) if self.resumed_from is not None else None, 'last_checkpoint': str(self.last_checkpoint) if self.last_checkpoint is not None else None, 'best_checkpoint': str(self.best_checkpoint) if self.best_checkpoint is not None else None}
```

<a id="ser_lib-engine-experiment-build_experiment_components"></a>

#### `ser_lib.engine.experiment.build_experiment_components`

公开导入：`ser_lib.engine.experiment.build_experiment_components`、`ser_lib.engine.build_experiment_components`。

源码：[ser_lib/engine/experiment.py:155](../ser_lib/engine/experiment.py#L155)。

```python
build_experiment_components(config: ExperimentConfig, *, train: bool=True) -> ExperimentComponents
```

构建实验组件，并在读取训练数据前完成全部静态兼容性检查。

<a id="ser_lib-engine-experiment-evaluate_artifact"></a>

#### `ser_lib.engine.experiment.evaluate_artifact`

公开导入：`ser_lib.evaluate_artifact`、`ser_lib.engine.experiment.evaluate_artifact`、`ser_lib.engine.evaluate_artifact`。

源码：[ser_lib/engine/experiment.py:479](../ser_lib/engine/experiment.py#L479)。

```python
evaluate_artifact(artifact: Path | str, *, manifest_path: Path | str | None=None, split: str='test', batch_size: int=16, workers: int=0, device: str='cpu', output: Path | str, prediction_sink: PredictionSink | None=None, retain_predictions: bool=True) -> EvaluationExperimentResult
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('artifact metadata.source_run_id 必须是非空字符串')`

<a id="ser_lib-engine-experiment-train_experiment"></a>

#### `ser_lib.engine.experiment.train_experiment`

公开导入：`ser_lib.train_experiment`、`ser_lib.engine.experiment.train_experiment`、`ser_lib.engine.train_experiment`。

源码：[ser_lib/engine/experiment.py:368](../ser_lib/engine/experiment.py#L368)。

```python
train_experiment(config: ExperimentConfig | Path | str, *, split: str='train', batch_size: int=16, workers: int=0, resume: Path | str | None=None) -> TrainingExperimentResult
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RuntimeError('Trainer.from_experiment 未生成 TrainingMetadata')`
- `ValueError('回溯续训必须使用新的 output_dir，不能覆盖未来历史')`
- `ValueError('续训输出目录属于不同 run，不能合并训练历史')`
- `ValueError('续训输出目录缺少 run.json，无法验证已有训练历史的归属')`

<a id="ser_lib-engine-lineage-trainingmetadata"></a>

#### `ser_lib.engine.lineage.TrainingMetadata`

公开导入：`ser_lib.engine.lineage.TrainingMetadata`、`ser_lib.engine.TrainingMetadata`。

源码：[ser_lib/engine/lineage.py:11](../ser_lib/engine/lineage.py#L11)。

一次训练运行的稳定、JSON-safe lineage 描述。

该对象只保存调用方已经知道的信息；它不会自行读取 manifest、扫描数据集或
计算 fingerprint，因此构造 Trainer 不会引入隐藏 I/O。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `run_id` | `str` | `必填（无默认值）` |
| `created_at` | `datetime` | `必填（无默认值）` |
| `dataset_id` | `str &#124; None` | `必填（无默认值）` |
| `dataset_fingerprint` | `str &#124; None` | `必填（无默认值）` |
| `model_id` | `str` | `必填（无默认值）` |
| `config` | `dict[str, Any]` | `必填（无默认值）` |
| `seed` | `int` | `必填（无默认值）` |
| `device` | `str` | `必填（无默认值）` |
| `library_version` | `str` | `必填（无默认值）` |

构造时的字段约束：

- `ValueError('run_id 不能为空')`
- `ValueError('model_id 不能为空')`
- `ValueError('device 不能为空')`
- `ValueError('library_version 不能为空')`
- `ValueError('seed 不能为负数')`
- `ValueError('created_at 必须包含时区')`
- `ValueError('dataset_id 不能是空字符串')`
- `ValueError('dataset_fingerprint 不能是空字符串')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'run_id': self.run_id, 'created_at': self.created_at.isoformat(), 'dataset_id': self.dataset_id, 'dataset_fingerprint': self.dataset_fingerprint, 'model_id': self.model_id, 'config': dict(self.config), 'seed': self.seed, 'device': self.device, 'library_version': self.library_version}
```

##### `from_dict`

调用方式：类方法，可直接通过类名调用。

```python
from_dict(cls, value: Mapping[str, Any]) -> 'TrainingMetadata'
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('TrainingMetadata.created_at 必须是 ISO 8601 字符串')`
- `ValueError('TrainingMetadata.config 必须是映射')`

##### `with_run_id`

```python
with_run_id(self, run_id: str) -> 'TrainingMetadata'
```

<a id="ser_lib-engine-lineage-artifact_provenance_from_training_run"></a>

#### `ser_lib.engine.lineage.artifact_provenance_from_training_run`

公开导入：`ser_lib.engine.lineage.artifact_provenance_from_training_run`。

源码：[ser_lib/engine/lineage.py:119](../ser_lib/engine/lineage.py#L119)。

```python
artifact_provenance_from_training_run(source_run: TrainingMetadata, *, metadata: Mapping[str, Any] | None=None) -> dict[str, Any]
```

把训练 lineage 转成 artifact 可接收的通用 metadata。

artifacts 层只接收 JSON-safe provenance 映射，不反向依赖 engine 类型；调用方
若已显式提供同名 metadata，则保持调用方值优先。

<a id="ser_lib-engine-lineage-build_training_metadata"></a>

#### `ser_lib.engine.lineage.build_training_metadata`

公开导入：`ser_lib.engine.lineage.build_training_metadata`、`ser_lib.engine.build_training_metadata`。

源码：[ser_lib/engine/lineage.py:93](../ser_lib/engine/lineage.py#L93)。

```python
build_training_metadata(*, run_id: str, model_id: str, config: Mapping[str, Any], seed: int, device: str, library_version: str, dataset_id: str | None=None, dataset_fingerprint: str | None=None, created_at: datetime | None=None) -> TrainingMetadata
```

构造训练 lineage；不执行任何文件系统或数据集探测。

<a id="ser_lib-engine-objectives-classificationloss"></a>

#### `ser_lib.engine.objectives.ClassificationLoss`

公开导入：`ser_lib.engine.objectives.ClassificationLoss`、`ser_lib.engine.ClassificationLoss`。

源码：[ser_lib/engine/objectives.py:15](../ser_lib/engine/objectives.py#L15)。

基类：`nn.Module`。继承的字段/方法继续适用。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `class_weights` | `torch.Tensor &#124; None` | `必填（无默认值）` |

##### `__init__`

```python
__init__(self, config: LossConfig, num_classes: int) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'loss.class_weights 长度必须等于 num_classes={num_classes}')`

##### `forward`

```python
forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor
```

##### `reduction_denominator`

```python
reduction_denominator(self, targets: torch.Tensor) -> float
```

Return the denominator used by this loss' scalar mean reduction.

Gradient accumulation must combine microbatches as one logical batch. For
weighted cross entropy, PyTorch's ``mean`` reduction divides by the sum
of target-class weights rather than by the number of samples. Focal loss
in this module explicitly calls ``mean()`` on its per-sample values, so
its denominator remains the sample count even when class weights are used.

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('loss reduction denominator 必须大于 0')`

<a id="ser_lib-engine-objectives-build_weighted_sampler"></a>

#### `ser_lib.engine.objectives.build_weighted_sampler`

公开导入：`ser_lib.engine.objectives.build_weighted_sampler`、`ser_lib.engine.build_weighted_sampler`。

源码：[ser_lib/engine/objectives.py:73](../ser_lib/engine/objectives.py#L73)。

```python
build_weighted_sampler(labels: Sequence[int | None], *, num_classes: int, config: SamplingConfig, seed: int) -> WeightedRandomSampler | None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('weighted sampling 要求所有训练样本都有标签')`
- `ValueError('训练标签超出 [0, num_classes) 范围')`
- `ValueError('replacement=False 时 num_samples 不能超过训练样本数')`
- `ValueError(f'sampling.class_weights 长度必须等于 num_classes={num_classes}')`

<a id="ser_lib-engine-optim-build_optimizer"></a>

#### `ser_lib.engine.optim.build_optimizer`

公开导入：`ser_lib.engine.optim.build_optimizer`、`ser_lib.engine.build_optimizer`。

源码：[ser_lib/engine/optim.py:22](../ser_lib/engine/optim.py#L22)。

```python
build_optimizer(parameters, config: OptimizerConfig) -> torch.optim.Optimizer
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TypeError(f'不支持的优化器配置: {type(config)!r}')`

<a id="ser_lib-engine-optim-build_scheduler"></a>

#### `ser_lib.engine.optim.build_scheduler`

公开导入：`ser_lib.engine.optim.build_scheduler`、`ser_lib.engine.build_scheduler`。

源码：[ser_lib/engine/optim.py:44](../ser_lib/engine/optim.py#L44)。

```python
build_scheduler(optimizer: torch.optim.Optimizer, config: SchedulerConfig | None) -> torch.optim.lr_scheduler.LRScheduler | None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TypeError(f'不支持的调度器配置: {type(config)!r}')`

<a id="ser_lib-engine-training-accumulation-_accumulationawareloss"></a>

#### `ser_lib.engine.training.accumulation._AccumulationAwareLoss`

公开导入：`ser_lib.engine.training.accumulation._AccumulationAwareLoss`。

源码：[ser_lib/engine/training/accumulation.py:71](../ser_lib/engine/training/accumulation.py#L71)。

Wrap an explicit scalar loss with logical-batch accumulation semantics.

基类：`torch.nn.Module`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, base_loss: torch.nn.Module, state: _AccumulationState) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `reduction_denominator`

```python
reduction_denominator(self, targets: torch.Tensor) -> float
```

Expose the wrapped loss reduction contract to validation/evaluation.

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('loss reduction denominator 必须大于 0')`

##### `forward`

```python
forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor
```

<a id="ser_lib-engine-training-accumulation-_accumulationstate"></a>

#### `ser_lib.engine.training.accumulation._AccumulationState`

公开导入：`ser_lib.engine.training.accumulation._AccumulationState`。

源码：[ser_lib/engine/training/accumulation.py:8](../ser_lib/engine/training/accumulation.py#L8)。

Track online reduction mass for gradients and epoch-level loss metrics.

##### `__init__`

```python
__init__(self, accumulation_steps: int, optimizer: torch.optim.Optimizer) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `begin_epoch`

```python
begin_epoch(self) -> None
```

##### `end_epoch`

```python
end_epoch(self) -> None
```

##### `scale_loss`

```python
scale_loss(self, loss: torch.Tensor, denominator: float) -> torch.Tensor
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('gradient accumulation denominator 必须大于 0')`

##### `finish_step`

```python
finish_step(self) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RuntimeError('optimizer step 缺少 gradient accumulation denominator')`

##### `epoch_mean_loss`

```python
epoch_mean_loss(self) -> float
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RuntimeError('epoch loss 缺少 reduction denominator')`

<a id="ser_lib-engine-training-results-epochresult"></a>

#### `ser_lib.engine.training.results.EpochResult`

公开导入：`ser_lib.engine.EpochResult`、`ser_lib.engine.training.results.EpochResult`、`ser_lib.engine.training.trainer.EpochResult`、`ser_lib.engine.training.EpochResult`。

源码：[ser_lib/engine/training/results.py:14](../ser_lib/engine/training/results.py#L14)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `epoch` | `int` | `必填（无默认值）` |
| `loss` | `float` | `必填（无默认值）` |
| `accuracy` | `float` | `必填（无默认值）` |
| `sample_count` | `int` | `必填（无默认值）` |
| `optimizer_steps` | `int` | `0` |
| `validation` | `dict[str, float] &#124; None` | `None` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'epoch': self.epoch, 'loss': self.loss, 'accuracy': self.accuracy, 'sample_count': self.sample_count, 'optimizer_steps': self.optimizer_steps, 'validation': dict(self.validation) if self.validation is not None else None}
```

<a id="ser_lib-engine-training-results-trainingresult"></a>

#### `ser_lib.engine.training.results.TrainingResult`

公开导入：`ser_lib.TrainingResult`、`ser_lib.engine.TrainingResult`、`ser_lib.engine.training.results.TrainingResult`、`ser_lib.engine.training.trainer.TrainingResult`、`ser_lib.engine.training.TrainingResult`。

源码：[ser_lib/engine/training/results.py:34](../ser_lib/engine/training/results.py#L34)。

一次 Trainer.fit 调用的稳定、JSON-safe 终态结果。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `run_id` | `str` | `必填（无默认值）` |
| `status` | `TrainingStatus` | `必填（无默认值）` |
| `epochs` | `tuple[EpochResult, ...]` | `必填（无默认值）` |
| `best_epoch` | `int &#124; None` | `必填（无默认值）` |
| `best_metric` | `float &#124; None` | `必填（无默认值）` |
| `monitored_metric` | `str` | `必填（无默认值）` |
| `started_at` | `datetime` | `必填（无默认值）` |
| `finished_at` | `datetime` | `必填（无默认值）` |
| `duration_seconds` | `float` | `必填（无默认值）` |
| `last_checkpoint` | `Path &#124; None` | `必填（无默认值）` |
| `best_checkpoint` | `Path &#124; None` | `必填（无默认值）` |
| `stop_reason` | `str &#124; None` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'run_id': self.run_id, 'status': self.status, 'epochs': [epoch.to_dict() for epoch in self.epochs], 'best_epoch': self.best_epoch, 'best_metric': self.best_metric, 'monitored_metric': self.monitored_metric, 'started_at': self.started_at.isoformat(), 'finished_at': self.finished_at.isoformat(), 'duration_seconds': self.duration_seconds, 'last_checkpoint': str(self.last_checkpoint) if self.last_checkpoint is not None else None, 'best_checkpoint': str(self.best_checkpoint) if self.best_checkpoint is not None else None, 'stop_reason': self.stop_reason}
```

<a id="ser_lib-engine-training-results-trainingstatus"></a>

#### `ser_lib.engine.training.results.TrainingStatus`

公开导入：`ser_lib.engine.TrainingStatus`、`ser_lib.engine.training.results.TrainingStatus`、`ser_lib.engine.training.trainer.TrainingStatus`、`ser_lib.engine.training.TrainingStatus`。

源码：[ser_lib/engine/training/results.py:10](../ser_lib/engine/training/results.py#L10)。

类型别名、常量或共享实例定义：

```python
TrainingStatus = Literal['completed', 'early_stopped', 'cancelled', 'failed']
```

<a id="ser_lib-engine-training-trainer-trainer"></a>

#### `ser_lib.engine.training.trainer.Trainer`

公开导入：`ser_lib.Trainer`、`ser_lib.engine.Trainer`、`ser_lib.engine.training.trainer.Trainer`、`ser_lib.engine.training.Trainer`。

源码：[ser_lib/engine/training/trainer.py:140](../ser_lib/engine/training/trainer.py#L140)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `run_metadata` | `TrainingMetadata &#124; None` | `必填（无默认值）` |

##### `__init__`

```python
__init__(self, model: SERModel, config: TrainerConfig | None=None, *, optimizer: torch.optim.Optimizer | None=None, scheduler: torch.optim.lr_scheduler.LRScheduler | None=None, loss_fn: torch.nn.Module | None=None, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, observability: ObservabilityConfig | None=None, run_id: str | None=None, run_metadata: TrainingMetadata | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('配置请求 CUDA，但当前环境不可用')`
- `ValueError('AMP 当前仅支持 CUDA 设备')`
- `ValueError('run_id 不能为空字符串')`
- `ValueError(f'无效训练设备: {self.config.device!r}')`

##### `attach_sampling_generator`

```python
attach_sampling_generator(self, generator: torch.Generator | None) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TypeError('sampling generator 必须是 torch.Generator 或 None')`

##### `from_experiment`

调用方式：类方法，可直接通过类名调用。

```python
from_experiment(cls, model: SERModel, experiment: ExperimentConfig, *, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, observability: ObservabilityConfig | None=None, run_id: str | None=None, dataset_id: str | None=None, dataset_fingerprint: str | None=None) -> 'Trainer'
```

按实验配置构造训练器，并记录当前训练 lineage。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'实验模型 {experiment.model.type!r} 与实例声明 {model.model_spec.model_id!r} 不一致')`
- `ValueError('实验 model.params 与模型实例的实际配置不一致')`
- `ValueError('分类训练要求模型声明 num_classes')`

##### `train_epoch`

```python
train_epoch(self, batches: Iterable[SERBatch], *, epoch: int) -> EpochResult
```

##### `fit`

```python
fit(self, train_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]], *, val_batches: Iterable[SERBatch] | Callable[[], Iterable[SERBatch]] | None=None, on_epoch_end: Callable[[EpochResult], None] | None=None, start_epoch: int | None=None) -> TrainingResult
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('启用 early stopping 时必须提供 val_batches')`
- `ValueError('start_epoch 必须 >= 1')`
- `RuntimeError('Trainer.fit 完成后未生成 TrainingResult')`
- `ValueError('验证要求模型声明 num_classes')`

##### `resume_from`

```python
resume_from(self, path, *, restore_rng: bool=True) -> dict[str, Any]
```

在应用训练状态前校验完整实验 lineage，并恢复可发现的 best artifact。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('checkpoint epoch 非法')`
- `ValueError('checkpoint best_metric 必须是有限数值')`
- `ValueError('checkpoint optimizer step 计数不一致')`
- `ValueError(f'checkpoint metadata.{key} 必须是非负整数')`
- `ValueError('checkpoint sampling_generator_state 必须是 Tensor')`
- `ValueError('checkpoint metadata.best_checkpoint 必须是相对文件名')`
- `FileNotFoundError(f'checkpoint 引用的 best artifact 不存在: {candidate}')`
- `ValueError('checkpoint best 引用的 epoch/run 不一致')`

<a id="ser_lib-engine-training-trainer-seed_everything"></a>

#### `ser_lib.engine.training.trainer.seed_everything`

公开导入：`ser_lib.engine.seed_everything`、`ser_lib.engine.training.trainer.seed_everything`、`ser_lib.engine.training.seed_everything`。

源码：[ser_lib/engine/training/trainer.py:53](../ser_lib/engine/training/trainer.py#L53)。

```python
seed_everything(seed: int, *, deterministic: bool=True) -> None
```

为 Python 与 PyTorch 设置可复现 seed。

<a id="ser_lib-engine-training_history-traininghistory"></a>

#### `ser_lib.engine.training_history.TrainingHistory`

公开导入：`ser_lib.engine.training_history.TrainingHistory`、`ser_lib.engine.TrainingHistory`。

源码：[ser_lib/engine/training_history.py:46](../ser_lib/engine/training_history.py#L46)。

完整、严格校验的 epoch 训练历史。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `directory` | `str` | `必填（无默认值）` |
| `history_file` | `str` | `必填（无默认值）` |
| `epochs` | `tuple[EpochResult, ...]` | `必填（无默认值）` |

##### `epoch_count`

调用方式：只读属性。

```python
epoch_count(self) -> int
```

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'directory': self.directory, 'history_file': self.history_file, 'epoch_count': self.epoch_count, 'epochs': [epoch.to_dict() for epoch in self.epochs]}
```

<a id="ser_lib-engine-training_history-load_training_history"></a>

#### `ser_lib.engine.training_history.load_training_history`

公开导入：`ser_lib.engine.training_history.load_training_history`、`ser_lib.engine.load_training_history`。

源码：[ser_lib/engine/training_history.py:66](../ser_lib/engine/training_history.py#L66)。

```python
load_training_history(path: Path | str) -> TrainingHistory
```

读取 run 目录或其 ``history.json``；不读取 checkpoint / metrics.jsonl。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'训练 history.json 不存在: {history_path}')`
- `ValueError('history.json 顶层必须是列表')`
- `ValueError('history.json epoch 必须严格递增且不能重复')`

<a id="ser_lib-engine-training_records-trainingrecord"></a>

#### `ser_lib.engine.training_records.TrainingRecord`

公开导入：`ser_lib.engine.training_records.TrainingRecord`、`ser_lib.engine.TrainingRecord`。

源码：[ser_lib/engine/training_records.py:56](../ser_lib/engine/training_records.py#L56)。

严格、JSON-safe 的训练终态记录。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `run_id` | `str` | `必填（无默认值）` |
| `directory` | `str` | `必填（无默认值）` |
| `status` | `TrainingStatus` | `必填（无默认值）` |
| `created_at` | `datetime` | `必填（无默认值）` |
| `started_at` | `datetime` | `必填（无默认值）` |
| `finished_at` | `datetime` | `必填（无默认值）` |
| `duration_seconds` | `float` | `必填（无默认值）` |
| `dataset_id` | `str &#124; None` | `必填（无默认值）` |
| `dataset_fingerprint` | `str &#124; None` | `必填（无默认值）` |
| `model_id` | `str` | `必填（无默认值）` |
| `seed` | `int` | `必填（无默认值）` |
| `device` | `str` | `必填（无默认值）` |
| `library_version` | `str` | `必填（无默认值）` |
| `config` | `dict[str, Any]` | `必填（无默认值）` |
| `epochs_completed` | `int` | `必填（无默认值）` |
| `last_epoch` | `int &#124; None` | `必填（无默认值）` |
| `best_epoch` | `int &#124; None` | `必填（无默认值）` |
| `best_metric` | `float &#124; None` | `必填（无默认值）` |
| `monitored_metric` | `str` | `必填（无默认值）` |
| `last_checkpoint` | `str &#124; None` | `必填（无默认值）` |
| `best_checkpoint` | `str &#124; None` | `必填（无默认值）` |
| `stop_reason` | `str &#124; None` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

##### `from_training`

调用方式：类方法，可直接通过类名调用。

```python
from_training(cls, directory: Path | str, metadata: TrainingMetadata, result: TrainingResult) -> 'TrainingRecord'
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('TrainingMetadata.run_id 与 TrainingResult.run_id 不一致')`

##### `from_dict`

调用方式：类方法，可直接通过类名调用。

```python
from_dict(cls, value: dict[str, Any], *, directory: Path | str | None=None) -> 'TrainingRecord'
```

<a id="ser_lib-engine-training_records-load_training_record"></a>

#### `ser_lib.engine.training_records.load_training_record`

公开导入：`ser_lib.engine.training_records.load_training_record`、`ser_lib.engine.load_training_record`。

源码：[ser_lib/engine/training_records.py:164](../ser_lib/engine/training_records.py#L164)。

```python
load_training_record(path: Path | str) -> TrainingRecord
```

读取一个 run 目录或其 ``run.json``。目录字段始终以实际位置为准。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `FileNotFoundError(f'训练运行记录不存在: {record_path}')`
- `ValueError('run.json 顶层必须是映射')`

<a id="ser_lib-engine-training_records-write_training_record"></a>

#### `ser_lib.engine.training_records.write_training_record`

公开导入：`ser_lib.engine.training_records.write_training_record`、`ser_lib.engine.write_training_record`。

源码：[ser_lib/engine/training_records.py:141](../ser_lib/engine/training_records.py#L141)。

```python
write_training_record(directory: Path | str, metadata: TrainingMetadata, result: TrainingResult) -> Path
```

把终态训练记录原子写入 ``run.json``。

<a id="ser_lib-engine-validation-experimentvalidationresult"></a>

#### `ser_lib.engine.validation.ExperimentValidationResult`

公开导入：`ser_lib.engine.validation.ExperimentValidationResult`、`ser_lib.engine.ExperimentValidationResult`。

源码：[ser_lib/engine/validation.py:22](../ser_lib/engine/validation.py#L22)。

Web/CLI 可直接消费的实验 dry-run 结果。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `valid` | `bool` | `必填（无默认值）` |
| `diagnostics` | `tuple[Diagnostic, ...]` | `必填（无默认值）` |
| `normalized_config` | `dict[str, Any]` | `必填（无默认值）` |
| `summary` | `dict[str, Any]` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'valid': self.valid, 'diagnostics': [diagnostic.to_dict() for diagnostic in self.diagnostics], 'normalized_config': dict(self.normalized_config), 'summary': dict(self.summary)}
```

<a id="ser_lib-engine-validation-validate_experiment"></a>

#### `ser_lib.engine.validation.validate_experiment`

公开导入：`ser_lib.engine.validation.validate_experiment`、`ser_lib.engine.validate_experiment`。

源码：[ser_lib/engine/validation.py:360](../ser_lib/engine/validation.py#L360)。

```python
validate_experiment(config: ExperimentConfig | Path | str) -> ExperimentValidationResult
```

执行训练前 dry-run，不加载样本、不创建模型、不分配 GPU。

``Path``/``str`` 输入同时覆盖 YAML/Pydantic Schema 校验；已经构造好的
:class:`ExperimentConfig` 则从领域级静态检查开始。

<a id="ser_lib-foundation-diagnostics-diagnostic"></a>

#### `ser_lib.foundation.diagnostics.Diagnostic`

公开导入：`ser_lib.foundation.diagnostics.Diagnostic`、`ser_lib.foundation.Diagnostic`。

源码：[ser_lib/foundation/diagnostics.py:42](../ser_lib/foundation/diagnostics.py#L42)。

一个稳定、可 JSON 序列化、供 Python 调用方消费的诊断项。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `severity` | `DiagnosticSeverity` | `必填（无默认值）` |
| `code` | `str` | `必填（无默认值）` |
| `message` | `str` | `必填（无默认值）` |
| `stage` | `str &#124; None` | `None` |
| `field` | `str &#124; None` | `None` |
| `path` | `str &#124; Path &#124; None` | `None` |
| `uid` | `str &#124; None` | `None` |
| `suggestion` | `str &#124; None` | `None` |
| `details` | `dict[str, Any]` | `dataclass_field(default_factory=dict)` |

构造时的字段约束：

- `ValueError(f'Diagnostic.severity 非法: {self.severity!r}; 支持: {allowed}')`
- `ValueError('Diagnostic.message 必须是非空字符串')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'severity': self.severity, 'code': self.code, 'message': self.message, 'stage': self.stage, 'field': self.field, 'path': self.path, 'uid': self.uid, 'suggestion': self.suggestion, 'details': _json_safe(self.details)}
```

##### `from_error`

调用方式：类方法，可直接通过类名调用。

```python
from_error(cls, error: Exception, *, severity: DiagnosticSeverity='error', suggestion: str | None=None) -> 'Diagnostic'
```

把异常转换为结构化 Diagnostic，不改变原异常的控制流语义。

<a id="ser_lib-foundation-diagnostics-diagnosticseverity"></a>

#### `ser_lib.foundation.diagnostics.DiagnosticSeverity`

公开导入：`ser_lib.foundation.diagnostics.DiagnosticSeverity`、`ser_lib.foundation.DiagnosticSeverity`。

源码：[ser_lib/foundation/diagnostics.py:14](../ser_lib/foundation/diagnostics.py#L14)。

类型别名、常量或共享实例定义：

```python
DiagnosticSeverity = Literal['info', 'warning', 'error']
```

<a id="ser_lib-foundation-errors-base-operationcancelled"></a>

#### `ser_lib.foundation.errors.base.OperationCancelled`

公开导入：`ser_lib.foundation.OperationCancelled`、`ser_lib.foundation.errors.base.OperationCancelled`、`ser_lib.foundation.errors.OperationCancelled`。

源码：[ser_lib/foundation/errors/base.py:35](../ser_lib/foundation/errors/base.py#L35)。

调用方请求取消一个可取消操作。

基类：`SERError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-base-registryerror"></a>

#### `ser_lib.foundation.errors.base.RegistryError`

公开导入：`ser_lib.data.RegistryError`、`ser_lib.foundation.RegistryError`、`ser_lib.foundation.errors.base.RegistryError`、`ser_lib.foundation.errors.RegistryError`。

源码：[ser_lib/foundation/errors/base.py:41](../ser_lib/foundation/errors/base.py#L41)。

跨 data/models 使用的注册表操作错误。

基类：`SERError`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, message: str, *, uid: str | None=None, path: Path | str | None=None, component: str | None=None, stage: str | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

<a id="ser_lib-foundation-errors-base-sererror"></a>

#### `ser_lib.foundation.errors.base.SERError`

公开导入：`ser_lib.foundation.SERError`、`ser_lib.foundation.errors.base.SERError`、`ser_lib.foundation.errors.SERError`。

源码：[ser_lib/foundation/errors/base.py:10](../ser_lib/foundation/errors/base.py#L10)。

所有可预期 SER 领域错误的根类型。

基类：`Exception`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, message: str, *, code: str | None=None, details: Mapping[str, Any] | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('异常 message 必须是非空字符串')`
- `ValueError(f'异常 code 非法: {resolved_code!r}')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'code': self.code, 'message': str(self), 'details': dict(self.details)}
```

<a id="ser_lib-foundation-errors-config-configurationerror"></a>

#### `ser_lib.foundation.errors.config.ConfigurationError`

公开导入：`ser_lib.foundation.ConfigurationError`、`ser_lib.foundation.errors.config.ConfigurationError`、`ser_lib.foundation.errors.ConfigurationError`。

源码：[ser_lib/foundation/errors/config.py:6](../ser_lib/foundation/errors/config.py#L6)。

配置文件无法读取或内容校验失败。

基类：`SERError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-audiodecodeerror"></a>

#### `ser_lib.foundation.errors.data.AudioDecodeError`

公开导入：`ser_lib.data.AudioDecodeError`、`ser_lib.foundation.errors.data.AudioDecodeError`、`ser_lib.foundation.errors.AudioDecodeError`。

源码：[ser_lib/foundation/errors/data.py:68](../ser_lib/foundation/errors/data.py#L68)。

音频解码失败或内容损坏。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-audionotfounderror"></a>

#### `ser_lib.foundation.errors.data.AudioNotFoundError`

公开导入：`ser_lib.data.AudioNotFoundError`、`ser_lib.foundation.errors.data.AudioNotFoundError`、`ser_lib.foundation.errors.AudioNotFoundError`。

源码：[ser_lib/foundation/errors/data.py:62](../ser_lib/foundation/errors/data.py#L62)。

音频文件不存在。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-collationerror"></a>

#### `ser_lib.foundation.errors.data.CollationError`

公开导入：`ser_lib.data.CollationError`、`ser_lib.foundation.errors.data.CollationError`、`ser_lib.foundation.errors.CollationError`。

源码：[ser_lib/foundation/errors/data.py:92](../ser_lib/foundation/errors/data.py#L92)。

批处理失败：key、layout 或标签契约不一致。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-invalidaudiosegmenterror"></a>

#### `ser_lib.foundation.errors.data.InvalidAudioSegmentError`

公开导入：`ser_lib.data.InvalidAudioSegmentError`、`ser_lib.foundation.errors.data.InvalidAudioSegmentError`、`ser_lib.foundation.errors.InvalidAudioSegmentError`。

源码：[ser_lib/foundation/errors/data.py:74](../ser_lib/foundation/errors/data.py#L74)。

音频片段定义非法（越界、零长度或解码结果为空）。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-manifesterror"></a>

#### `ser_lib.foundation.errors.data.ManifestError`

公开导入：`ser_lib.data.ManifestError`、`ser_lib.foundation.errors.data.ManifestError`、`ser_lib.foundation.errors.ManifestError`。

源码：[ser_lib/foundation/errors/data.py:56](../ser_lib/foundation/errors/data.py#L56)。

Manifest 读取、校验或路径解析失败。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-representationerror"></a>

#### `ser_lib.foundation.errors.data.RepresentationError`

公开导入：`ser_lib.data.RepresentationError`、`ser_lib.foundation.errors.data.RepresentationError`、`ser_lib.foundation.errors.RepresentationError`。

源码：[ser_lib/foundation/errors/data.py:80](../ser_lib/foundation/errors/data.py#L80)。

表示（Representation）计算失败或输出违反契约。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-serdataerror"></a>

#### `ser_lib.foundation.errors.data.SERDataError`

公开导入：`ser_lib.data.SERDataError`、`ser_lib.foundation.errors.data.SERDataError`、`ser_lib.foundation.errors.SERDataError`。

源码：[ser_lib/foundation/errors/data.py:11](../ser_lib/foundation/errors/data.py#L11)。

数据模块所有业务异常的基类。

基类：`SERError`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, message: str, *, uid: str | None=None, path: Path | str | None=None, component: str | None=None, stage: str | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

<a id="ser_lib-foundation-errors-data-transformerror"></a>

#### `ser_lib.foundation.errors.data.TransformError`

公开导入：`ser_lib.data.TransformError`、`ser_lib.foundation.errors.data.TransformError`、`ser_lib.foundation.errors.TransformError`。

源码：[ser_lib/foundation/errors/data.py:86](../ser_lib/foundation/errors/data.py#L86)。

Transform 构建或执行失败。

基类：`SERDataError`。继承的字段/方法继续适用。

<a id="ser_lib-foundation-errors-data-wrap_error"></a>

#### `ser_lib.foundation.errors.data.wrap_error`

公开导入：`ser_lib.foundation.errors.data.wrap_error`、`ser_lib.foundation.errors.wrap_error`。

源码：[ser_lib/foundation/errors/data.py:98](../ser_lib/foundation/errors/data.py#L98)。

```python
wrap_error(exc: Exception, target: type[SERDataError], message: str, *, uid: str | None=None, path: Any=None, component: str | None=None, stage: str | None=None) -> SERDataError
```

把底层异常包装为业务异常并保留异常链。

<a id="ser_lib-foundation-errors-engine-compatibilityerror"></a>

#### `ser_lib.foundation.errors.engine.CompatibilityError`

公开导入：`ser_lib.data.CompatibilityError`、`ser_lib.foundation.CompatibilityError`、`ser_lib.foundation.errors.engine.CompatibilityError`、`ser_lib.foundation.errors.CompatibilityError`。

源码：[ser_lib/foundation/errors/engine.py:10](../ser_lib/foundation/errors/engine.py#L10)。

跨数据与模型契约的兼容性校验失败。

基类：`SERError`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, message: str, *, uid: str | None=None, path: Path | str | None=None, component: str | None=None, stage: str | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

<a id="ser_lib-foundation-events-libraryevent"></a>

#### `ser_lib.foundation.events.LibraryEvent`

公开导入：`ser_lib.foundation.LibraryEvent`、`ser_lib.foundation.events.LibraryEvent`。

源码：[ser_lib/foundation/events/__init__.py:19](../ser_lib/foundation/events/__init__.py#L19)。

类型别名、常量或共享实例定义：

```python
LibraryEvent = ProgressEvent | MetricEvent | LogEvent | LifecycleEvent
```

<a id="ser_lib-foundation-events-base-cancellationcheck"></a>

#### `ser_lib.foundation.events.base.CancellationCheck`

公开导入：`ser_lib.foundation.CancellationCheck`、`ser_lib.foundation.events.base.CancellationCheck`、`ser_lib.foundation.events.CancellationCheck`。

源码：[ser_lib/foundation/events/base.py:92](../ser_lib/foundation/events/base.py#L92)。

长操作只依赖此协议，不依赖具体调度器。

基类：`Protocol`。继承的字段/方法继续适用。

##### `is_cancelled`

调用方式：只读属性。

```python
is_cancelled(self) -> bool
```

##### `raise_if_cancelled`

```python
raise_if_cancelled(self) -> None
```

<a id="ser_lib-foundation-events-base-cancellationtoken"></a>

#### `ser_lib.foundation.events.base.CancellationToken`

公开导入：`ser_lib.foundation.CancellationToken`、`ser_lib.foundation.events.base.CancellationToken`、`ser_lib.foundation.events.CancellationToken`。

源码：[ser_lib/foundation/events/base.py:101](../ser_lib/foundation/events/base.py#L101)。

可在线程间安全共享的协作式取消令牌。

##### `__init__`

```python
__init__(self) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `is_cancelled`

调用方式：只读属性。

```python
is_cancelled(self) -> bool
```

##### `cancel`

```python
cancel(self) -> None
```

##### `raise_if_cancelled`

```python
raise_if_cancelled(self) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `OperationCancelled('操作已取消')`

<a id="ser_lib-foundation-events-base-eventcallback"></a>

#### `ser_lib.foundation.events.base.EventCallback`

公开导入：`ser_lib.foundation.EventCallback`、`ser_lib.foundation.events.base.EventCallback`、`ser_lib.foundation.events.EventCallback`。

源码：[ser_lib/foundation/events/base.py:89](../ser_lib/foundation/events/base.py#L89)。

类型别名、常量或共享实例定义：

```python
EventCallback = Callable[[EventLike], None]
```

<a id="ser_lib-foundation-events-base-eventcontext"></a>

#### `ser_lib.foundation.events.base.EventContext`

公开导入：`ser_lib.foundation.EventContext`、`ser_lib.foundation.events.base.EventContext`、`ser_lib.foundation.events.EventContext`。

源码：[ser_lib/foundation/events/base.py:57](../ser_lib/foundation/events/base.py#L57)。

跨事件共享的运行上下文。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `run_id` | `str &#124; None` | `None` |
| `epoch` | `int &#124; None` | `None` |
| `total_epochs` | `int &#124; None` | `None` |
| `batch` | `int &#124; None` | `None` |
| `total_batches` | `int &#124; None` | `None` |
| `global_step` | `int &#124; None` | `None` |
| `split` | `str &#124; None` | `None` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'run_id': self.run_id, 'epoch': self.epoch, 'total_epochs': self.total_epochs, 'batch': self.batch, 'total_batches': self.total_batches, 'global_step': self.global_step, 'split': self.split}
```

<a id="ser_lib-foundation-events-base-eventlike"></a>

#### `ser_lib.foundation.events.base.EventLike`

公开导入：`ser_lib.foundation.EventLike`、`ser_lib.foundation.events.base.EventLike`、`ser_lib.foundation.events.EventLike`。

源码：[ser_lib/foundation/events/base.py:80](../ser_lib/foundation/events/base.py#L80)。

所有可由事件 callback 消费的只读结构化事件协议。

基类：`Protocol`。继承的字段/方法继续适用。

##### `sequence`

调用方式：只读属性。

```python
sequence(self) -> int
```

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-foundation-events-inference-predictionevent"></a>

#### `ser_lib.foundation.events.inference.PredictionEvent`

公开导入：`ser_lib.foundation.events.inference.PredictionEvent`、`ser_lib.foundation.events.PredictionEvent`。

源码：[ser_lib/foundation/events/inference.py:19](../ser_lib/foundation/events/inference.py#L19)。

单条推理结果事件。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `emotion` | `str` | `必填（无默认值）` |
| `confidence` | `float` | `必填（无默认值）` |
| `label_id` | `int &#124; None` | `None` |
| `probabilities` | `tuple[float, ...]` | `()` |
| `details` | `dict[str, Any]` | `field(default_factory=dict)` |
| `timestamp` | `datetime` | `field(default_factory=_utc_now)` |
| `context` | `EventContext` | `field(default_factory=EventContext)` |
| `sequence` | `int` | `field(default_factory=_next_event_sequence)` |
| `event_type` | `ClassVar[str]` | `'prediction'` |

构造时的字段约束：

- `ValueError('PredictionEvent.uid 不能为空')`
- `ValueError('PredictionEvent.emotion 不能为空')`
- `ValueError('PredictionEvent.confidence 必须位于 [0, 1]')`
- `ValueError('PredictionEvent.label_id 不能为负数')`
- `ValueError('PredictionEvent.probabilities 必须位于 [0, 1]')`
- `ValueError('sequence 必须为正整数')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'event_type': self.event_type, 'sequence': self.sequence, 'uid': self.uid, 'emotion': self.emotion, 'confidence': self.confidence, 'label_id': self.label_id, 'probabilities': list(self.probabilities), 'timestamp': _timestamp_to_iso(self.timestamp), 'context': self.context.to_dict(), 'details': _json_safe(self.details)}
```

<a id="ser_lib-foundation-events-lifecycle-lifecycleevent"></a>

#### `ser_lib.foundation.events.lifecycle.LifecycleEvent`

公开导入：`ser_lib.foundation.LifecycleEvent`、`ser_lib.foundation.events.lifecycle.LifecycleEvent`、`ser_lib.foundation.events.LifecycleEvent`。

源码：[ser_lib/foundation/events/lifecycle.py:141](../ser_lib/foundation/events/lifecycle.py#L141)。

描述长任务或其阶段的生命周期变化。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `stage` | `str` | `必填（无默认值）` |
| `status` | `str` | `必填（无默认值）` |
| `message` | `str` | `''` |
| `details` | `dict[str, Any]` | `field(default_factory=dict)` |
| `timestamp` | `datetime` | `field(default_factory=_utc_now)` |
| `context` | `EventContext` | `field(default_factory=EventContext)` |
| `sequence` | `int` | `field(default_factory=_next_event_sequence)` |
| `event_type` | `ClassVar[str]` | `'lifecycle'` |

构造时的字段约束：

- `ValueError('LifecycleEvent.stage 不能为空')`
- `ValueError(f'LifecycleEvent.status 非法: {self.status!r}; 支持: {allowed}')`
- `ValueError('sequence 必须为正整数')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'event_type': self.event_type, 'sequence': self.sequence, 'stage': self.stage, 'status': self.status, 'timestamp': _timestamp_to_iso(self.timestamp), 'context': self.context.to_dict(), 'message': self.message, 'details': _json_safe(self.details)}
```

<a id="ser_lib-foundation-events-lifecycle-logevent"></a>

#### `ser_lib.foundation.events.lifecycle.LogEvent`

公开导入：`ser_lib.foundation.LogEvent`、`ser_lib.foundation.events.lifecycle.LogEvent`、`ser_lib.foundation.events.LogEvent`。

源码：[ser_lib/foundation/events/lifecycle.py:108](../ser_lib/foundation/events/lifecycle.py#L108)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `level` | `str` | `必填（无默认值）` |
| `message` | `str` | `必填（无默认值）` |
| `stage` | `str &#124; None` | `None` |
| `details` | `dict[str, Any]` | `field(default_factory=dict)` |
| `timestamp` | `datetime` | `field(default_factory=_utc_now)` |
| `context` | `EventContext` | `field(default_factory=EventContext)` |
| `sequence` | `int` | `field(default_factory=_next_event_sequence)` |
| `event_type` | `ClassVar[str]` | `'log'` |

构造时的字段约束：

- `ValueError('LogEvent.level 不能为空')`
- `ValueError('LogEvent.message 不能为空')`
- `ValueError('sequence 必须为正整数')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'event_type': self.event_type, 'sequence': self.sequence, 'level': self.level, 'message': self.message, 'stage': self.stage, 'timestamp': _timestamp_to_iso(self.timestamp), 'context': self.context.to_dict(), 'details': _json_safe(self.details)}
```

<a id="ser_lib-foundation-events-lifecycle-metricevent"></a>

#### `ser_lib.foundation.events.lifecycle.MetricEvent`

公开导入：`ser_lib.foundation.MetricEvent`、`ser_lib.foundation.events.lifecycle.MetricEvent`、`ser_lib.foundation.events.MetricEvent`。

源码：[ser_lib/foundation/events/lifecycle.py:72](../ser_lib/foundation/events/lifecycle.py#L72)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `name` | `str` | `必填（无默认值）` |
| `value` | `float` | `必填（无默认值）` |
| `step` | `int &#124; None` | `None` |
| `split` | `str &#124; None` | `None` |
| `timestamp` | `datetime` | `field(default_factory=_utc_now)` |
| `context` | `EventContext` | `field(default_factory=EventContext)` |
| `sequence` | `int` | `field(default_factory=_next_event_sequence)` |
| `event_type` | `ClassVar[str]` | `'metric'` |

构造时的字段约束：

- `ValueError('MetricEvent.name 不能为空')`
- `ValueError('sequence 必须为正整数')`
- `ValueError('MetricEvent.split 与 context.split 不一致')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'event_type': self.event_type, 'sequence': self.sequence, 'name': self.name, 'value': _json_safe(self.value), 'step': self.step, 'split': self.split, 'timestamp': _timestamp_to_iso(self.timestamp), 'context': self.context.to_dict()}
```

<a id="ser_lib-foundation-events-lifecycle-progressevent"></a>

#### `ser_lib.foundation.events.lifecycle.ProgressEvent`

公开导入：`ser_lib.foundation.ProgressEvent`、`ser_lib.foundation.events.lifecycle.ProgressEvent`、`ser_lib.foundation.events.ProgressEvent`。

源码：[ser_lib/foundation/events/lifecycle.py:29](../ser_lib/foundation/events/lifecycle.py#L29)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `stage` | `str` | `必填（无默认值）` |
| `completed` | `int` | `必填（无默认值）` |
| `total` | `int &#124; None` | `None` |
| `message` | `str` | `''` |
| `timestamp` | `datetime` | `field(default_factory=_utc_now)` |
| `context` | `EventContext` | `field(default_factory=EventContext)` |
| `sequence` | `int` | `field(default_factory=_next_event_sequence)` |
| `details` | `dict[str, Any]` | `field(default_factory=dict)` |
| `event_type` | `ClassVar[str]` | `'progress'` |

构造时的字段约束：

- `ValueError('ProgressEvent.stage 不能为空')`
- `ValueError('completed/total 不能为负数')`
- `ValueError('completed 不能大于 total')`
- `ValueError('sequence 必须为正整数')`

##### `fraction`

调用方式：只读属性。

```python
fraction(self) -> float | None
```

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'event_type': self.event_type, 'sequence': self.sequence, 'stage': self.stage, 'timestamp': _timestamp_to_iso(self.timestamp), 'context': self.context.to_dict(), 'completed': self.completed, 'total': self.total, 'message': self.message, 'details': _json_safe(self.details)}
```

<a id="ser_lib-foundation-events-training-checkpointevent"></a>

#### `ser_lib.foundation.events.training.CheckpointEvent`

公开导入：`ser_lib.foundation.events.training.CheckpointEvent`、`ser_lib.foundation.events.CheckpointEvent`。

源码：[ser_lib/foundation/events/training.py:27](../ser_lib/foundation/events/training.py#L27)。

描述 checkpoint 保存生命周期。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `action` | `str` | `必填（无默认值）` |
| `kind` | `str` | `必填（无默认值）` |
| `path` | `str &#124; Path` | `必填（无默认值）` |
| `epoch` | `int` | `必填（无默认值）` |
| `metric_name` | `str &#124; None` | `None` |
| `metric_value` | `float &#124; None` | `None` |
| `message` | `str` | `''` |
| `details` | `dict[str, Any]` | `field(default_factory=dict)` |
| `timestamp` | `datetime` | `field(default_factory=_utc_now)` |
| `context` | `EventContext` | `field(default_factory=EventContext)` |
| `sequence` | `int` | `field(default_factory=_next_event_sequence)` |
| `event_type` | `ClassVar[str]` | `'checkpoint'` |

构造时的字段约束：

- `ValueError(f'CheckpointEvent.action 非法: {self.action!r}; 支持: {allowed}')`
- `ValueError('CheckpointEvent.kind 不能为空')`
- `ValueError('CheckpointEvent.path 不能为空')`
- `ValueError('CheckpointEvent.epoch 不能为负数')`
- `ValueError('sequence 必须为正整数')`

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'event_type': self.event_type, 'sequence': self.sequence, 'action': self.action, 'kind': self.kind, 'path': _json_safe(self.path), 'epoch': self.epoch, 'metric_name': self.metric_name, 'metric_value': _json_safe(self.metric_value), 'timestamp': _timestamp_to_iso(self.timestamp), 'context': self.context.to_dict(), 'message': self.message, 'details': _json_safe(self.details)}
```

<a id="ser_lib-foundation-logging-logger_name"></a>

#### `ser_lib.foundation.logging.LOGGER_NAME`

公开导入：`ser_lib.foundation.logging.LOGGER_NAME`。

源码：[ser_lib/foundation/logging.py:8](../ser_lib/foundation/logging.py#L8)。

类型别名、常量或共享实例定义：

```python
LOGGER_NAME = 'ser_lib'
```

<a id="ser_lib-foundation-logging-configure_library_logging"></a>

#### `ser_lib.foundation.logging.configure_library_logging`

公开导入：`ser_lib.foundation.logging.configure_library_logging`、`ser_lib.foundation.configure_library_logging`。

源码：[ser_lib/foundation/logging.py:20](../ser_lib/foundation/logging.py#L20)。

```python
configure_library_logging(level: int | str=logging.INFO, *, stream: TextIO | None=None) -> logging.Handler
```

显式为 ``ser_lib`` 安装一个 handler，并返回它供调用方移除。

<a id="ser_lib-foundation-logging-get_logger"></a>

#### `ser_lib.foundation.logging.get_logger`

公开导入：`ser_lib.foundation.logging.get_logger`、`ser_lib.foundation.get_logger`。

源码：[ser_lib/foundation/logging.py:11](../ser_lib/foundation/logging.py#L11)。

```python
get_logger(name: str | None=None) -> logging.Logger
```

获取库命名空间下的 logger。

<a id="ser_lib-inference-batch-batchemotionpredictor"></a>

#### `ser_lib.inference.batch.BatchEmotionPredictor`

公开导入：`ser_lib.inference.batch.BatchEmotionPredictor`、`ser_lib.inference.BatchEmotionPredictor`。

源码：[ser_lib/inference/batch.py:156](../ser_lib/inference/batch.py#L156)。

在单文件预测器之上提供来源枚举、增量事件和逐条失败策略。

##### `__init__`

```python
__init__(self, predictor: EmotionPredictor) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `predict_records`

```python
predict_records(self, records: Iterable[AudioRecord], *, fail_fast: bool=True, batch_size: int=16, total: int | None=None, result_sink: BatchPredictionSink | None=None, retain_results: bool=True, event_callback: EventCallback | None=None, cancellation: CancellationCheck | None=None, event_context: EventContext | None=None) -> BatchPredictionResult
```

批量预测，并支持流式 Iterable 与增量结果 sink。

默认 ``retain_results=True`` 保持历史行为：完整成功/失败明细都放进返回值。
超大任务可传 ``result_sink`` 并设置 ``retain_results=False``，此时返回值仅保留
总计数，逐条明细由 sink 消费。未知长度 Iterable 不会被强制 ``list()``；
progress 的 ``total`` 为 ``None``，除非调用方显式提供 ``total``。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('batch_size 必须 >= 1')`
- `ValueError('total 必须 >= 0')`
- `ValueError(f'批量推理实际处理 {completed} 条，与声明 total={known_total} 不一致')`
- `ValueError('批量预测返回数量与输入记录数不一致')`

##### `predict_files`

```python
predict_files(self, paths: Iterable[Path | str], **kwargs) -> BatchPredictionResult
```

##### `predict_directory`

```python
predict_directory(self, directory: Path | str, *, recursive: bool=True, extensions: Sequence[str] | None=None, **kwargs) -> BatchPredictionResult
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `NotADirectoryError(f'批量推理目录不存在或不是目录: {root}')`

##### `predict_manifest`

```python
predict_manifest(self, manifest: DatasetManifest | Path | str, *, split: str | None=None, **kwargs) -> BatchPredictionResult
```

<a id="ser_lib-inference-batch-batchpredictionresult"></a>

#### `ser_lib.inference.batch.BatchPredictionResult`

公开导入：`ser_lib.inference.batch.BatchPredictionResult`、`ser_lib.inference.BatchPredictionResult`。

源码：[ser_lib/inference/batch.py:98](../ser_lib/inference/batch.py#L98)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `predictions` | `tuple[PredictionResult, ...]` | `必填（无默认值）` |
| `failures` | `tuple[PredictionFailure, ...]` | `必填（无默认值）` |
| `total` | `int` | `必填（无默认值）` |
| `succeeded_count` | `int &#124; None` | `None` |
| `failed_count` | `int &#124; None` | `None` |

构造时的字段约束：

- `ValueError('BatchPredictionResult.total 不能为负数')`
- `ValueError('succeeded_count 不能小于已保留 predictions 数量')`
- `ValueError('failed_count 不能小于已保留 failures 数量')`
- `ValueError('BatchPredictionResult.total 与成功/失败数量不一致')`

##### `succeeded`

调用方式：只读属性。

```python
succeeded(self) -> int
```

##### `failed`

调用方式：只读属性。

```python
failed(self) -> int
```

##### `retained_results`

调用方式：只读属性。

```python
retained_results(self) -> int
```

##### `to_dict`

```python
to_dict(self) -> dict[str, object]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'predictions': [asdict(prediction) for prediction in self.predictions], 'failures': [failure.to_dict() for failure in self.failures], 'total': self.total, 'succeeded': self.succeeded, 'failed': self.failed, 'retained_results': self.retained_results}
```

<a id="ser_lib-inference-batch-batchpredictionsink"></a>

#### `ser_lib.inference.batch.BatchPredictionSink`

公开导入：`ser_lib.inference.batch.BatchPredictionSink`、`ser_lib.inference.BatchPredictionSink`。

源码：[ser_lib/inference/batch.py:40](../ser_lib/inference/batch.py#L40)。

批量推理逐条结果消费者；生命周期由调用方管理。

基类：`Protocol`。继承的字段/方法继续适用。

##### `write_prediction`

```python
write_prediction(self, result: PredictionResult) -> None
```

##### `write_failure`

```python
write_failure(self, failure: PredictionFailure) -> None
```

<a id="ser_lib-inference-batch-jsonlbatchpredictionsink"></a>

#### `ser_lib.inference.batch.JsonlBatchPredictionSink`

公开导入：`ser_lib.inference.batch.JsonlBatchPredictionSink`、`ser_lib.inference.JsonlBatchPredictionSink`。

源码：[ser_lib/inference/batch.py:50](../ser_lib/inference/batch.py#L50)。

把批量推理结果增量写入 JSONL，避免完整结果常驻内存。

##### `__init__`

```python
__init__(self, path: Path | str, *, append: bool=False, flush_each: bool=False) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `write_prediction`

```python
write_prediction(self, result: PredictionResult) -> None
```

##### `write_failure`

```python
write_failure(self, failure: PredictionFailure) -> None
```

##### `flush`

```python
flush(self) -> None
```

##### `close`

```python
close(self) -> None
```

##### `__enter__`

```python
__enter__(self) -> 'JsonlBatchPredictionSink'
```

##### `__exit__`

```python
__exit__(self, exc_type: object, exc: object, traceback: object) -> None
```

<a id="ser_lib-inference-batch-predictionfailure"></a>

#### `ser_lib.inference.batch.PredictionFailure`

公开导入：`ser_lib.inference.batch.PredictionFailure`、`ser_lib.inference.PredictionFailure`。

源码：[ser_lib/inference/batch.py:30](../ser_lib/inference/batch.py#L30)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `audio_path` | `str` | `必填（无默认值）` |
| `error_type` | `str` | `必填（无默认值）` |
| `message` | `str` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, object]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-inference-batch-write_batch_predictions"></a>

#### `ser_lib.inference.batch.write_batch_predictions`

公开导入：`ser_lib.inference.batch.write_batch_predictions`、`ser_lib.inference.write_batch_predictions`。

源码：[ser_lib/inference/batch.py:357](../ser_lib/inference/batch.py#L357)。

```python
write_batch_predictions(path: Path | str, result: BatchPredictionResult, *, format: Literal['jsonl', 'csv'] | None=None) -> Path
```

原子写入内存中保留的完整批量结果。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('BatchPredictionResult 未保留完整明细；请在推理时使用 result_sink 直接写出')`
- `ValueError('批量预测输出格式必须是 jsonl 或 csv')`

<a id="ser_lib-inference-offline-emotionpredictor"></a>

#### `ser_lib.inference.offline.EmotionPredictor`

公开导入：`ser_lib.EmotionPredictor`、`ser_lib.inference.offline.EmotionPredictor`、`ser_lib.inference.EmotionPredictor`。

源码：[ser_lib/inference/offline.py:25](../ser_lib/inference/offline.py#L25)。

##### `__init__`

```python
__init__(self, model: SERModel, audio_loader: AudioLoader, pipeline: SamplePipeline, collator: SERCollator, labels: Mapping[int, str] | None=None, *, device: str | torch.device='cpu', window_aggregation: Literal['mean_logits', 'mean_probabilities', 'max_confidence'] | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('推理请求 CUDA，但当前环境不可用')`

##### `from_loaded_artifact`

调用方式：类方法，可直接通过类名调用。

```python
from_loaded_artifact(cls, artifact: 'LoadedArtifact', *, device: str | torch.device='cpu', window_aggregation: Literal['mean_logits', 'mean_probabilities', 'max_confidence'] | None=None) -> 'EmotionPredictor'
```

从已加载 artifact 构造 predictor，不隐藏额外模型或 processor 加载。

##### `predict_file`

```python
predict_file(self, path: Path | str, *, uid: str | None=None) -> PredictionResult
```

##### `predict_record`

```python
predict_record(self, record: AudioRecord) -> PredictionResult
```

预测已解析路径的记录，并保留 UID 与片段范围。

##### `predict_audio`

```python
predict_audio(self, audio: AudioData, *, uid: str='stream') -> PredictionResult
```

预测已在内存中的标准 AudioData，供流式核心等调用方复用。

##### `predict_records`

```python
predict_records(self, records: Sequence[AudioRecord]) -> list[PredictionResult]
```

在一次模型 forward 中预测多个记录，并正确聚合各自的滑窗。

<a id="ser_lib-inference-offline-predictionresult"></a>

#### `ser_lib.inference.offline.PredictionResult`

公开导入：`ser_lib.PredictionResult`、`ser_lib.inference.offline.PredictionResult`、`ser_lib.inference.PredictionResult`。

源码：[ser_lib/inference/offline.py:18](../ser_lib/inference/offline.py#L18)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `uid` | `str` | `必填（无默认值）` |
| `label_id` | `int` | `必填（无默认值）` |
| `emotion` | `str` | `必填（无默认值）` |
| `confidence` | `float` | `必填（无默认值）` |
| `probabilities` | `list[float]` | `必填（无默认值）` |

<a id="ser_lib-inference-streaming-streamingemotionrecognizer"></a>

#### `ser_lib.inference.streaming.StreamingEmotionRecognizer`

公开导入：`ser_lib.inference.streaming.StreamingEmotionRecognizer`、`ser_lib.inference.StreamingEmotionRecognizer`。

源码：[ser_lib/inference/streaming.py:162](../ser_lib/inference/streaming.py#L162)。

同步消费 PCM，并为每个完整窗口返回一次预测。

离线 ``normalize_peak`` 依赖整段音频的全局峰值，无法在无界流中保持相同
语义。该配置会在会话创建时明确拒绝，而不是被静默忽略或退化成依赖 chunk
划分的局部归一化。

##### `__init__`

```python
__init__(self, predictor: EmotionPredictor, config: StreamingConfig) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('streaming 不支持 audio.normalize_peak=True：全局峰值归一化需要完整音频；请关闭该选项后使用流式推理')`
- `ValueError('window_ms/hop_ms 在目标采样率下不足一个采样点')`

##### `buffered_samples`

调用方式：只读属性。

```python
buffered_samples(self) -> int
```

##### `latency`

调用方式：只读属性。

```python
latency(self) -> StreamingLatency
```

##### `push_pcm`

```python
push_pcm(self, pcm: torch.Tensor | Sequence[float]) -> list[StreamingPrediction]
```

提交 PCM；预测失败后用空 chunk 重试，已完成结果会一并交付。

一次失败的调用可能已经接收了 PCM，不能重送同一 chunk。
flush 失败后应重试 flush；reset/close 明确丢弃待交付结果。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RuntimeError('流式会话已关闭')`
- `RuntimeError('流式会话已 flush；请 reset 后再输入')`
- `ValueError('PCM 必须是 [T] 或 [C,T]')`
- `ValueError('PCM 包含 NaN/Inf')`
- `BufferError(f'PCM chunk 超过 max_chunk_ms={self.config.max_chunk_ms}')`

##### `flush`

```python
flush(self, *, pad_final: bool=False) -> list[StreamingPrediction]
```

##### `reset`

```python
reset(self) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RuntimeError('流式会话已关闭')`

##### `close`

```python
close(self) -> None
```

<a id="ser_lib-inference-streaming-streaminglatency"></a>

#### `ser_lib.inference.streaming.StreamingLatency`

公开导入：`ser_lib.inference.streaming.StreamingLatency`、`ser_lib.inference.StreamingLatency`。

源码：[ser_lib/inference/streaming.py:29](../ser_lib/inference/streaming.py#L29)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `window_ms` | `float` | `必填（无默认值）` |
| `hop_ms` | `float` | `必填（无默认值）` |
| `resampler_lookahead_ms` | `float` | `必填（无默认值）` |
| `first_result_ms` | `float` | `必填（无默认值）` |

<a id="ser_lib-inference-streaming-streamingprediction"></a>

#### `ser_lib.inference.streaming.StreamingPrediction`

公开导入：`ser_lib.inference.streaming.StreamingPrediction`、`ser_lib.inference.StreamingPrediction`。

源码：[ser_lib/inference/streaming.py:19](../ser_lib/inference/streaming.py#L19)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `sequence` | `int` | `必填（无默认值）` |
| `start_ms` | `float` | `必填（无默认值）` |
| `end_ms` | `float` | `必填（无默认值）` |
| `silent` | `bool` | `必填（无默认值）` |
| `rms` | `float` | `必填（无默认值）` |
| `prediction` | `PredictionResult &#124; None` | `必填（无默认值）` |

<a id="ser_lib-models-adapters-huggingface-hfaudioclassifier"></a>

#### `ser_lib.models.adapters.huggingface.HFAudioClassifier`

公开导入：`ser_lib.models.HFAudioClassifier`、`ser_lib.models.adapters.huggingface.HFAudioClassifier`、`ser_lib.models.adapters.HFAudioClassifier`。

源码：[ser_lib/models/adapters/huggingface.py:199](../ser_lib/models/adapters/huggingface.py#L199)。

Hugging Face waveform encoder/classifier adapted to ``SERBatch``.

``encoder_head`` preserves the historical SER-owned classification head.
``audio_classification`` consumes logits from a native HF classification model and
therefore requires explicit label names so its head mapping can be verified.

基类：`SERModel`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, num_classes: int, pretrained_model_name_or_path: str | None=None, encoder_config: dict[str, Any] | None=None, local_files_only: bool=True, revision: str | None=None, freeze_encoder: bool=False, dropout: float=0.1, pooling: Literal['mean', 'max']='mean', expected_sample_rate: int=16000, strategy: Literal['encoder_head', 'audio_classification']='encoder_head', reset_classifier_head: bool=False, label_names: dict[int, str] | None=None, processor_name_or_path: str | None=None, processor_config: dict[str, Any] | HFProcessorConfig | None=None, processor_revision: str | None=None) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('Hugging Face model config.to_dict() 必须包含 model_type')`
- `ValueError('Hugging Face encoder 配置缺少合法 hidden_size')`

##### `model_spec`

调用方式：只读属性。

```python
model_spec(self) -> ModelSpec
```

##### `model_config`

调用方式：只读属性。

```python
model_config(self) -> dict[str, Any]
```

##### `artifact_processor_config`

调用方式：只读属性。

```python
artifact_processor_config(self) -> dict[str, Any] | None
```

##### `validate_artifact_labels`

```python
validate_artifact_labels(self, labels: Mapping[int, str]) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'artifact labels 数量与 HF num_classes 不一致: {len(labels)} != {self.num_classes}')`
- `ValueError('artifact labels 与 HF classification label2id/id2label 不一致')`

##### `train`

```python
train(self, mode: bool=True) -> 'HFAudioClassifier'
```

##### `forward`

```python
forward(self, batch: SERBatch) -> ModelOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError("HFAudioClassifier 需要 batch.inputs['waveform']")`
- `ValueError('HFAudioClassifier 期望非空 waveform [B,T]')`
- `ValueError('waveform 必须是浮点 tensor')`
- `ValueError('Hugging Face encoder 必须返回 last_hidden_state [B,T,D]')`
- `RuntimeError('encoder_head strategy 缺少 SER classifier')`
- `ValueError('HF audio-classification model 必须返回 logits [B,C]')`
- `ValueError(f'HF classification logits 类别维与 num_classes 不一致: {logits.shape[1]} != {self.num_classes}')`

<a id="ser_lib-models-adapters-torch-torch_adapter_model_id"></a>

#### `ser_lib.models.adapters.torch.TORCH_ADAPTER_MODEL_ID`

公开导入：`ser_lib.models.TORCH_ADAPTER_MODEL_ID`、`ser_lib.models.adapters.torch.TORCH_ADAPTER_MODEL_ID`、`ser_lib.models.adapters.TORCH_ADAPTER_MODEL_ID`。

源码：[ser_lib/models/adapters/torch.py:21](../ser_lib/models/adapters/torch.py#L21)。

类型别名、常量或共享实例定义：

```python
TORCH_ADAPTER_MODEL_ID = 'torch_model_adapter'
```

<a id="ser_lib-models-adapters-torch-torchmodeladapter"></a>

#### `ser_lib.models.adapters.torch.TorchModelAdapter`

公开导入：`ser_lib.models.TorchModelAdapter`、`ser_lib.models.adapters.torch.TorchModelAdapter`、`ser_lib.models.adapters.TorchModelAdapter`。

源码：[ser_lib/models/adapters/torch.py:121](../ser_lib/models/adapters/torch.py#L121)。

用显式输入/输出映射包装普通 ``nn.Module``。

adapter 作为正常子模块参与 ``parameters()``、``to()``、train/eval 模式切换；
但持久化权重直接委托给被包装 module，因此不会引入 ``module.``、``model.``
或 ``_module.`` state_dict 前缀。

基类：`SERModel`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, module: nn.Module, config: TorchModelAdapterConfig) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `TypeError(f'module 必须是 torch.nn.Module，实际 {type(module)!r}')`
- `ValueError('已有 SERModel 不应再次使用 TorchModelAdapter 包装')`

##### `wrap`

调用方式：类方法，可直接通过类名调用。

```python
wrap(cls, module: nn.Module, *, required_inputs: Mapping[str, TensorSpec], input_map: Mapping[str, str], num_classes: int, output: TorchOutputMappingConfig | Mapping[str, Any] | None=None, supports_masks: bool=False, supports_variable_length: bool=False, expected_sample_rate: int | None=None, freeze_module: bool=False, factory_id: str | None=None, factory_params: Mapping[str, Any] | None=None) -> 'TorchModelAdapter'
```

显式包装现有 module；factory 可缺省用于仅本地/checkpoint 场景。

##### `wrapped_module`

调用方式：只读属性。

```python
wrapped_module(self) -> nn.Module
```

##### `model_spec`

调用方式：只读属性。

```python
model_spec(self) -> ModelSpec
```

##### `model_config`

调用方式：只读属性。

```python
model_config(self) -> dict[str, Any]
```

##### `state_dict`

```python
state_dict(self, *args: Any, **kwargs: Any) -> 未声明返回类型
```

Standalone 保持原始 key；嵌套保存时遵守 PyTorch 子模块前缀。

##### `load_state_dict`

```python
load_state_dict(self, state_dict: Mapping[str, torch.Tensor], strict: bool=True, assign: bool=False) -> 未声明返回类型
```

##### `forward`

```python
forward(self, batch: SERBatch) -> ModelOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'TorchModelAdapter logits 类别维与 num_classes 不一致: {result.logits.shape[1]} != {self._adapter_config.num_classes}')`
- `ValueError('module 已返回 ModelOutput 时不能再配置 output selector')`
- `ValueError('module 非直接返回 logits tensor 时必须配置 output.logits 选择器')`

<a id="ser_lib-models-base-modeloutput"></a>

#### `ser_lib.models.base.ModelOutput`

公开导入：`ser_lib.models.ModelOutput`。

源码：[ser_lib/models/base.py:14](../ser_lib/models/base.py#L14)。

所有 SER 模型的标准输出。

``logits`` 必须是 ``[B, C]``；``embeddings`` 如存在必须是 ``[B, D]``；
``loss`` 如存在必须是标量。输出允许包含非有限 logits，以便训练器在统一
位置产生诊断，但形状错误必须在模型边界立即失败。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `logits` | `torch.Tensor` | `必填（无默认值）` |
| `embeddings` | `torch.Tensor &#124; None` | `None` |
| `loss` | `torch.Tensor &#124; None` | `None` |

构造时的字段约束：

- `ValueError(f'ModelOutput.logits 必须是 [B,C] tensor，实际: {shape}')`
- `ValueError(f'ModelOutput.logits 要求 B>=1、C>=2，实际 {tuple(self.logits.shape)}')`
- `ValueError('ModelOutput.loss 必须是标量 tensor')`
- `ValueError('ModelOutput.embeddings 必须是与 logits batch 对齐的 [B,D] tensor')`

<a id="ser_lib-models-base-sermodel"></a>

#### `ser_lib.models.base.SERModel`

公开导入：`ser_lib.SERModel`、`ser_lib.models.SERModel`。

源码：[ser_lib/models/base.py:43](../ser_lib/models/base.py#L43)。

所有内置及第三方适配模型必须实现的最小稳定接口。

基类：`nn.Module`、`ABC`。继承的字段/方法继续适用。

##### `model_spec`

调用方式：只读属性。

```python
model_spec(self) -> ModelSpec
```

##### `model_config`

调用方式：只读属性。

```python
model_config(self) -> dict[str, Any]
```

返回可 JSON 序列化、可用于注册表重建模型的完整配置。

##### `artifact_processor_config`

调用方式：只读属性。

```python
artifact_processor_config(self) -> dict[str, Any] | None
```

返回需要随 artifact 固化的 processor 快照；普通模型默认没有。

##### `validate_artifact_labels`

```python
validate_artifact_labels(self, labels: Mapping[int, str]) -> None
```

允许模型在 artifact 写入前校验领域标签契约。

##### `parameter_count`

```python
parameter_count(self, *, trainable_only: bool=False) -> int
```

返回模型参数量；可限制为需要梯度的参数。

##### `forward`

```python
forward(self, batch: SERBatch) -> ModelOutput
```

<a id="ser_lib-models-cnn_models-cnnbaseline"></a>

#### `ser_lib.models.cnn_models.CNNBaseline`

公开导入：`ser_lib.models.cnn_models.CNNBaseline`、`ser_lib.models.CNNBaseline`。

源码：[ser_lib/models/cnn_models.py:50](../ser_lib/models/cnn_models.py#L50)。

保持时间分辨率的一维卷积分类器。

输入 ``features`` 为 ``[B,F,T]``。优先使用显式 mask；当 collator 只提供
``lengths`` 时会据此构造连续前缀 mask。无效时间步在每个卷积块之间都被清零，
并从 BatchNorm 统计中排除，因此同一有效序列的输出不依赖右侧 padding 长度或
同 batch 中最长样本。随后根据有效位置做 masked mean pooling。

基类：`SERModel`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, feature_dim: int, num_classes: int, hidden_dim: int=128, dropout: float=0.2) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError('feature_dim/hidden_dim 必须为正，num_classes 必须 >= 2')`
- `ValueError('dropout 必须位于 [0, 1)')`

##### `model_spec`

调用方式：只读属性。

```python
model_spec(self) -> ModelSpec
```

##### `model_config`

调用方式：只读属性。

```python
model_config(self) -> dict[str, int | float]
```

##### `forward`

```python
forward(self, batch: SERBatch) -> ModelOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError(f'CNNBaseline 期望 [B,{self.feature_dim},T]，实际 {tuple(features.shape)}')`
- `ValueError('CNNBaseline 不接受空 batch 或零长度时间轴')`
- `ValueError(f'CNNBaseline features 必须是浮点 tensor，实际 {features.dtype}')`
- `ValueError("CNNBaseline 需要 batch.inputs['features']")`
- `ValueError(f'features mask 期望 {(features.shape[0], features.shape[-1])}，实际 {tuple(mask.shape)}')`
- `ValueError('CNNBaseline 的每个样本必须至少包含一个有效时间步')`

<a id="ser_lib-models-registry-modeldescriptor"></a>

#### `ser_lib.models.registry.ModelDescriptor`

公开导入：`ser_lib.models.ModelDescriptor`。

源码：[ser_lib/models/registry.py:20](../ser_lib/models/registry.py#L20)。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `id` | `str` | `必填（无默认值）` |
| `display_name` | `str` | `必填（无默认值）` |
| `description` | `str` | `必填（无默认值）` |
| `config_schema` | `dict[str, Any]` | `必填（无默认值）` |
| `input_layouts` | `dict[str, str]` | `必填（无默认值）` |
| `version` | `str` | `'1.0'` |
| `status` | `str` | `'stable'` |

##### `to_json_safe`

```python
to_json_safe(self) -> dict[str, Any]
```

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'id': self.id, 'display_name': self.display_name, 'description': self.description, 'config_schema': self.config_schema, 'input_layouts': self.input_layouts, 'version': self.version, 'status': self.status}
```

<a id="ser_lib-models-registry-modelregistry"></a>

#### `ser_lib.models.registry.ModelRegistry`

公开导入：`ser_lib.models.ModelRegistry`。

源码：[ser_lib/models/registry.py:53](../ser_lib/models/registry.py#L53)。

##### `__init__`

```python
__init__(self) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `register`

```python
register(self, name: str, factory: Callable[..., SERModel], *, config_model: type[BaseModel] | None=None, descriptor: ModelDescriptor | None=None, spec_factory: ModelSpecFactory | None=None, reconstructibility_check: ReconstructibilityCheck | None=None, replace: bool=False) -> None
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError('模型名称不能为空')`
- `RegistryError(f'模型重复注册: {name!r}')`
- `RegistryError('模型 descriptor.id 必须与注册名称一致')`

##### `create`

```python
create(self, name: str, **params: Any) -> SERModel
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'未知模型 {name!r}，可用模型: {sorted(self._entries)}')`
- `RegistryError(f'模型工厂 {name!r} 返回了非 SERModel: {type(model)!r}')`
- `RegistryError(f'模型 {name!r} 构建失败: {exc}')`

##### `validate_config`

```python
validate_config(self, name: str, params: dict[str, Any]) -> dict[str, Any]
```

严格校验模型配置，并返回带默认值的 JSON-safe 参数。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'未知模型 {name!r}，可用模型: {sorted(self._entries)}')`
- `RegistryError(f'模型 {name!r} 配置校验失败: {exc}')`

##### `validate_reconstructible`

```python
validate_reconstructible(self, name: str, params: dict[str, Any]) -> dict[str, Any]
```

验证模型配置可由注册 ID 重建，但不实例化模型或加载权重。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'模型 {name!r} 不可重建: {exc}')`

##### `inspect_spec`

```python
inspect_spec(self, name: str, params: dict[str, Any]) -> ModelSpec
```

仅根据配置生成 ModelSpec，不实例化模型、不加载权重。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'未知模型 {name!r}，可用模型: {sorted(self._entries)}')`
- `RegistryError(f'模型 {name!r} 未声明静态 ModelSpec，无法执行无实例化 dry-run')`
- `RegistryError(f'模型 {name!r} spec_factory 返回了非 ModelSpec: {type(spec)!r}')`
- `RegistryError(f'模型 {name!r} ModelSpec 生成失败: {exc}')`

##### `supports_static_spec`

```python
supports_static_spec(self, name: str) -> bool
```

模型是否支持不实例化模型的静态 ModelSpec 查询。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'未知模型 {name!r}，可用模型: {sorted(self._entries)}')`

##### `register_torch_factory`

```python
register_torch_factory(self, factory_id: str, factory: Callable[..., nn.Module], *, config_model: type[BaseModel] | None=None, replace: bool=False) -> None
```

登记普通 nn.Module 的可重建 factory。

callable 只存在于当前 Python 进程的 registry；artifact 永远只持久化
``factory_id`` 与 JSON-safe 参数，不序列化或动态导入 callable。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError('Torch factory ID 不能为空')`
- `RegistryError(f'Torch factory 重复注册: {factory_id!r}')`
- `RegistryError('Torch factory 必须可调用')`

##### `has_torch_factory`

```python
has_torch_factory(self, factory_id: str) -> bool
```

##### `torch_factory_names`

```python
torch_factory_names(self) -> list[str]
```

##### `validate_torch_factory_config`

```python
validate_torch_factory_config(self, factory_id: str, params: dict[str, Any]) -> dict[str, Any]
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'未知 Torch factory {factory_id!r}，可用: {sorted(self._torch_factories)}')`
- `RegistryError(f'Torch factory {factory_id!r} 参数必须是 JSON-safe 数据')`
- `RegistryError(f'Torch factory {factory_id!r} 配置校验失败: {exc}')`

##### `create_torch_module`

```python
create_torch_module(self, factory_id: str, **params: Any) -> nn.Module
```

由已注册 ID 重建普通 nn.Module。

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'Torch factory {factory_id!r} 返回了非 nn.Module: {type(module)!r}')`
- `RegistryError(f'Torch factory {factory_id!r} 构建失败: {exc}')`

##### `descriptor`

```python
descriptor(self, name: str) -> dict[str, Any]
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `RegistryError(f'未知模型 {name!r}，可用模型: {sorted(self._entries)}')`

##### `names`

```python
names(self) -> list[str]
```

##### `descriptors`

```python
descriptors(self) -> list[dict[str, Any]]
```

<a id="ser_lib-models-registry-model_registry"></a>

#### `ser_lib.models.registry.model_registry`

公开导入：`ser_lib.models.model_registry`。

源码：[ser_lib/models/registry.py:228](../ser_lib/models/registry.py#L228)。

类型别名、常量或共享实例定义：

```python
model_registry = ModelRegistry()
```

<a id="ser_lib-models-rnn_models-grubaseline"></a>

#### `ser_lib.models.rnn_models.GRUBaseline`

公开导入：`ser_lib.models.rnn_models.GRUBaseline`、`ser_lib.models.GRUBaseline`。

源码：[ser_lib/models/rnn_models.py:18](../ser_lib/models/rnn_models.py#L18)。

使用 packed sequence 忽略 padding 的 GRU 分类基线。

基类：`SERModel`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, feature_dim: int, num_classes: int, hidden_dim: int=128, num_layers: int=1, bidirectional: bool=True, dropout: float=0.0) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `model_spec`

调用方式：只读属性。

```python
model_spec(self) -> ModelSpec
```

##### `model_config`

调用方式：只读属性。

```python
model_config(self) -> dict[str, int | float | bool]
```

##### `forward`

```python
forward(self, batch: SERBatch) -> ModelOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError("GRUBaseline 需要 batch.inputs['features']")`
- `ValueError(f'GRUBaseline 期望 [B,{self.feature_dim},T]，实际 {tuple(features.shape)}')`
- `ValueError('GRUBaseline 不接受空 batch 或零长度时间轴')`
- `ValueError(f'GRUBaseline features 必须是浮点 tensor，实际 {features.dtype}')`

<a id="ser_lib-models-specs-modelspec"></a>

#### `ser_lib.models.specs.ModelSpec`

公开导入：`ser_lib.models.specs.ModelSpec`、`ser_lib.models.ModelSpec`。

源码：[ser_lib/models/specs.py:11](../ser_lib/models/specs.py#L11)。

模型输入规格（模型显式声明，禁止调用方猜测 tensor shape）。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `model_id` | `str` | `必填（无默认值）` |
| `required_inputs` | `dict[str, TensorSpec]` | `必填（无默认值）` |
| `supports_masks` | `bool` | `必填（无默认值）` |
| `supports_variable_length` | `bool` | `必填（无默认值）` |
| `num_classes` | `int &#124; None` | `必填（无默认值）` |
| `expected_sample_rate` | `int &#124; None` | `None` |

<a id="ser_lib-models-transformer_models-transformerbaseline"></a>

#### `ser_lib.models.transformer_models.TransformerBaseline`

公开导入：`ser_lib.models.transformer_models.TransformerBaseline`、`ser_lib.models.TransformerBaseline`。

源码：[ser_lib/models/transformer_models.py:40](../ser_lib/models/transformer_models.py#L40)。

投影声学帧、加入正弦位置编码并进行 masked mean pooling。

基类：`SERModel`。继承的字段/方法继续适用。

##### `__init__`

```python
__init__(self, feature_dim: int, num_classes: int, d_model: int=128, num_heads: int=4, num_layers: int=2, feedforward_dim: int=256, dropout: float=0.1, activation: Literal['relu', 'gelu']='gelu', norm_first: bool=False) -> None
```

作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。

##### `model_spec`

调用方式：只读属性。

```python
model_spec(self) -> ModelSpec
```

##### `model_config`

调用方式：只读属性。

```python
model_config(self) -> dict[str, int | float | bool | str]
```

##### `forward`

```python
forward(self, batch: SERBatch) -> ModelOutput
```

实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：

- `ValueError("TransformerBaseline 需要 batch.inputs['features']")`
- `ValueError(f'TransformerBaseline 期望 [B,{self.feature_dim},T]，实际 {tuple(features.shape)}')`
- `ValueError('TransformerBaseline 不接受空 batch 或零长度时间轴')`
- `ValueError('TransformerBaseline features 必须是浮点 tensor')`

<a id="ser_lib-runtime-runtimecapabilities"></a>

#### `ser_lib.runtime.RuntimeCapabilities`

公开导入：`ser_lib.runtime.RuntimeCapabilities`。

源码：[ser_lib/runtime.py:27](../ser_lib/runtime.py#L27)。

一次性环境能力快照；不承担持续资源监控。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `python_version` | `str` | `必填（无默认值）` |
| `torch_version` | `str` | `必填（无默认值）` |
| `cuda_available` | `bool` | `必填（无默认值）` |
| `devices` | `tuple[RuntimeDevice, ...]` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：

```python
{'python_version': self.python_version, 'torch_version': self.torch_version, 'cuda_available': self.cuda_available, 'devices': [device.to_dict() for device in self.devices]}
```

<a id="ser_lib-runtime-runtimedevice"></a>

#### `ser_lib.runtime.RuntimeDevice`

公开导入：`ser_lib.runtime.RuntimeDevice`。

源码：[ser_lib/runtime.py:13](../ser_lib/runtime.py#L13)。

一个可供单设备训练、评估或推理选择的运行设备。

| 字段 | 类型 | 默认值 / 校验 / 描述 |
|---|---|---|
| `id` | `str` | `必填（无默认值）` |
| `type` | `str` | `必填（无默认值）` |
| `name` | `str` | `必填（无默认值）` |
| `total_memory` | `int &#124; None` | `必填（无默认值）` |
| `amp_supported` | `bool` | `必填（无默认值）` |

##### `to_dict`

```python
to_dict(self) -> dict[str, Any]
```

作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。

<a id="ser_lib-runtime-get_runtime_capabilities"></a>

#### `ser_lib.runtime.get_runtime_capabilities`

公开导入：`ser_lib.runtime.get_runtime_capabilities`。

源码：[ser_lib/runtime.py:44](../ser_lib/runtime.py#L44)。

```python
get_runtime_capabilities() -> RuntimeCapabilities
```

返回 JSON-safe 的 Python/PyTorch 与本机可选设备信息。

