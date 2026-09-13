# 可执行示例

examples/ 只调用 SER-lib 1.0 公开 API，可从仓库根目录运行。

## 训练

~~~bash
python examples/train_from_python.py configs/cnn_logmel.yaml
~~~

配置引用的标准 manifest 必须存在。

## 推理

先从可信 checkpoint 导出 artifact，再运行：

~~~bash
python examples/predict_artifact.py artifacts/model path/to/audio.wav
~~~

## 资源检查与 preset

~~~bash
python examples/inspect_runs_and_presets.py --training-run runs/demo
~~~

示例用于展示 API 组合，不引入 Service/Page/View facade。

完整工作流：

- [训练与 CLI](../docs/TRAINING_AND_CLI.md)
- [公共 API](../docs/API_REFERENCE.md)
- [Artifact 与安全](../docs/ARTIFACTS_AND_SECURITY.md)
