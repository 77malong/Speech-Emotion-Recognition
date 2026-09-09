# 08 - Service API Audit

## 目标

确保未来 Python Worker 常见业务可以只依赖 `ser_lib.services`，而不是导入多个 engine/data/artifact internal 模块拼接流程。

## Service 范围

- `DatasetService`
- `TrainingService`
- `EvaluationService`
- `InferenceService`
- `ArtifactService`
- `CatalogService`
- `RuntimeService`

## 审计方法

按用户工作流而非按文件检查。

### Dataset

Import / Summary / Profile / Query / Edit / Transaction / Fingerprint / Revision / Restore。

### Training

Dry-run / Run / Events / Cancellation / Checkpoint / Resume / History / Run Catalog / Checkpoint Catalog / Run Detail。

### Evaluation

Run / Metrics / Prediction Sink / Report / Prediction Query / Run Catalog / Run Detail。

### Inference

Single / Batch / Sink / Streaming。

### Artifact

Export / Inspect / Verify / Progress / Catalog / Lineage。

### Runtime

Capabilities / GPU metrics / CPU-RAM metrics。

### Config/Catalog

Component Catalog / Experiment Presets / compatibility validation 的合理入口。

## 重点问题

- Service 是否复制底层业务逻辑；
- 同类方法参数命名是否一致；
- Path 是否都接受 `str | Path`（按现有风格）；
- event/cancel 参数是否在长任务 facade 中完整透传；
- Result DTO 是否直接返回领域对象而非临时 dict；
- list/inspect/query 是否保持不同成本边界；
- CatalogService 是否只是有意义的聚合，而不是重复其他 Service。

## 非目标

- 不把所有底层函数都包一层 Service；
- 不隐藏需要高级用户直接使用的核心模型 API；
- 不引入 HTTP/RPC 概念。

## 测试

增强 `tests/test_services.py`，并按需要在领域测试中验证 Service delegation。特别检查 monkeypatch 底层函数时 facade 是否正确透传 options/event/cancellation。

## 验收

- 未来 Worker 的主要业务不需要 import `_internal`；
- Service 层薄、稳定、无复制业务；
- 命名和参数风格一致；
- 每个 facade 的成本语义清晰。

## 建议提交

`refactor(services): stabilize application service facade`
