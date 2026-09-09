# 09 - Documentation and Examples Sync

## 目标

在 API 稳定化后同步文档，确保 README、API reference、训练文档、示例代码与真实 public API 一致。

## 主要文件

- `readme.md`
- `docs/API_REFERENCE.md`
- `docs/TRAINING_AND_CLI.md`
- `docs/SER_STUDIO_FOUNDATION.md`
- `configs/README.md`
- `examples/README.md`
- `examples/train_from_python.py`
- `examples/predict_artifact.py`
- 必要时新增 run detail / preset 示例
- `tests/test_release_examples.py`

## 必须补充

1. TrainingRunDetail 示例；
2. EvaluationRunDetail 示例；
3. Experiment Preset 枚举与生成配置；
4. Schema migration 的兼容承诺与 future-version error；
5. Runtime CPU/RAM snapshot；
6. ETA 新语义；
7. Service-first 推荐调用方式；
8. 大文件成本说明：checkpoint list 不 load、prediction detail 不整文件读、dataset summary 不扫音频、artifact list 不 hash 权重。

## 文档原则

- 不把未来 SER-Studio UI 当成已实现；
- 可以说明 Worker 将调用 Service，但不要添加 UI 代码；
- 示例必须可测试或至少被 import/compile 检查；
- 不复制一整套与源码易漂移的参数表；参数详情优先指向 schema/catalog。

## 测试

- release examples 继续通过；
- 文档示例中的 import 路径真实存在；
- 配置文件与 preset 关键语义一致；
- 文档中不再引用被审计为 internal 的 API。

## 验收

用户从 README/API_REFERENCE 能完成 Dataset→Train→Run Detail→Artifact→Evaluation→Evaluation Detail 的核心路径，并能理解各接口的读取成本。

## 建议提交

`docs(api): sync ser-lib stabilization documentation`
