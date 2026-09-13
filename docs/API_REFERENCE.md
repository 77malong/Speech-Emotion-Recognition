# 公共 API 索引

SER-lib 1.0.0 的稳定 Python API 以各领域子包公开导出为准。未列入模块 `__all__`
或文档明确标记为内部实现的名称，不属于 1.x 兼容承诺。

| 子包 | 主要公开能力 |
|---|---|
| `ser_lib.foundation` | 公共异常、事件、取消、Diagnostic、日志辅助 |
| `ser_lib.config` | 严格配置 schema、配置加载、preset |
| `ser_lib.data` | Manifest、AudioLoader、SERDataset、Pipeline、Collator、importer/representation registry |
| `ser_lib.models` | SERModel、ModelSpec、CNN、GRU、Transformer、Torch/HF adapter、model registry |
| `ser_lib.engine` | Trainer、训练/评估实验、checkpoint、records、history、reports、compatibility |
| `ser_lib.artifacts` | safetensors artifact 导出、inspect、verify、load、catalog |
| `ser_lib.inference` | 单文件、批量、纯 PCM streaming 推理 |
| `ser_lib.runtime` | Python/PyTorch/CPU/CUDA/MPS 能力探测 |
| `ser_lib.cli` | `ser` 命令入口 |

## 根包便利入口

`import ser_lib` 只提供少量高层惰性入口：

- `SERDataset`、`SERBatch`、`SERModel`
- `Trainer`、`TrainingResult`、`evaluate`
- `train_experiment`、`evaluate_artifact`
- `EmotionPredictor`、`PredictionResult`
- `export_model_artifact`、`load_model_artifact`

配置、lineage、catalog、runtime、diagnostic 等能力从对应领域子包导入。

## 配置与 preset

~~~python
from ser_lib.config import (
    build_experiment_config,
    get_experiment_preset_payload,
    list_experiment_preset_ids,
)

preset_ids = list_experiment_preset_ids()
payload = get_experiment_preset_payload("gru_mfcc_baseline")
config = build_experiment_config(
    "gru_mfcc_baseline",
    overrides={"trainer": {"epochs": 20}},
)
~~~

Preset 最终生成唯一的 `ExperimentConfig`；返回 payload 是深拷贝。

## Dataset

~~~python
from ser_lib.data import DatasetManifest, fingerprint_manifest, summarize_manifest

manifest = DatasetManifest.load("data/standard/dataset.yaml")
records = manifest.get_records(split="train")
summary = summarize_manifest("data/standard/dataset.yaml")
fingerprint = fingerprint_manifest(manifest)
~~~

`get_records(split=None)` 返回全部记录；音频路径解析使用 `resolved_records()`。
核心库不提供 Web 式分页 DTO。

## Component discovery

~~~python
from ser_lib.data import default_registry
from ser_lib.models import model_registry

representations = default_registry.json_safe_descriptors("representation")
importers = default_registry.json_safe_descriptors("importer")
models = model_registry.descriptors()
~~~

CLI 的 `ser components list` 使用同一 registry。

## Training resources

~~~python
from ser_lib.engine import (
    load_training_history,
    load_training_record,
    scan_checkpoints,
)

run = load_training_record("runs/demo")
history = load_training_history("runs/demo")
checkpoints = scan_checkpoints("runs/demo/checkpoints")
~~~

TrainingRecord、history 和 checkpoint 是独立资源。扫描 checkpoint 只做目录/stat，
不会隐式反序列化权重。

## Evaluation resources

~~~python
from itertools import islice
from ser_lib.engine import (
    inspect_evaluation_prediction_file,
    inspect_evaluation_report,
    iter_evaluation_predictions,
    load_evaluation_record,
)

run = load_evaluation_record("runs/eval-demo")
report = inspect_evaluation_report("runs/eval-demo")
prediction_file = inspect_evaluation_prediction_file(run)
page = list(islice(iter_evaluation_predictions("runs/eval-demo"), 100))
~~~

Prediction JSONL 使用流式 iterator，不为了分页总数预扫完整文件。

## Artifact

~~~python
from ser_lib.artifacts import (
    export_model_artifact,
    inspect_model_artifact,
    load_model_artifact,
    scan_model_artifacts,
    verify_model_artifact,
)
~~~

`inspect_model_artifact()` 读取结构；`verify_model_artifact()` 做完整 SHA-256 校验；
`load_model_artifact()` 在验证后重建模型与预处理。分发权重固定为
`weights.safetensors`。

## Training objective

~~~python
from ser_lib.engine import (
    ClassificationLoss,
    LossConfig,
    SamplingConfig,
    build_weighted_sampler,
)
~~~

支持 cross entropy、focal loss、class weights、label smoothing 与 weighted sampling。

## Runtime

~~~python
from ser_lib.runtime import get_runtime_capabilities

runtime = get_runtime_capabilities()
~~~

Runtime API 只做一次性环境能力探测，不提供持续 CPU/GPU 进程监控。

## 1.x 兼容边界

1. 文档列出的公开导出、CLI 命令/参数和 artifact 结构遵循语义化版本。
2. 配置、dataset、artifact、run/evaluation records 使用严格当前结构。
3. `library_version` 仅记录来源，不触发兼容分支。
4. checkpoint 是可信本地训练恢复状态，不作为不可信模型交换格式。
5. 内部私有模块、历史开发脚本和 docs/development 中的审计基线路径不属于公开 API。
