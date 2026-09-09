# 05 - CPU / RAM Runtime Metrics

## 目标

在已有 `RuntimeCapabilities`、CUDA `RuntimeMetrics` 基础上补充按需 CPU/RAM snapshot：

- process RSS；
- system RAM used；
- system RAM available；
- system RAM total；
- system CPU utilization；
- process CPU utilization。

继续坚持按需查询，不塞进 Trainer 每 batch 热路径。

## 主要代码

- `ser_lib/runtime.py`
- `ser_lib/services/runtime.py`
- `tests/test_runtime_metrics.py`
- `tests/test_runtime_capabilities.py`
- `pyproject.toml`（只有确认需要新依赖时才修改）

## 依赖策略

先检查项目是否已有 `psutil`。如果没有，需要评估：

1. 是否用标准库实现可移植的最小指标；
2. 如果跨平台 CPU/RAM 准确度要求使标准库明显不足，再显式加入 psutil。

不能使用 Linux `/proc` 作为唯一实现，因为 CI 要覆盖 Windows/macOS。

## DTO

优先在现有 RuntimeMetrics 中扩展结构，或增加嵌套：

```text
RuntimeMetrics
├── system
├── process
└── devices / cuda
```

但必须考虑已有 public DTO 兼容性。若直接改字段会破坏序列化契约，应增加新的可选字段而非重构旧字段。

所有字节值字段命名统一以 `_bytes` 结尾，百分比命名统一以 `_percent` 结尾。

## 采样语义

CPU utilization 的第一次调用可能有平台/库特定语义，必须在文档中说明。不要为了得到“准确一秒平均”而在 API 内 sleep 阻塞。snapshot 应快速返回。

## 测试

- 所有字节值非负且关系合理；
- available <= total；
- process RSS 非负；
- CPU 百分比范围合理；
- 无 CUDA 环境也正常；
- monkeypatch provider 可得到确定性 DTO；
- `json.dumps(metrics.to_dict())` 成功；
- Windows/macOS 不依赖 `/proc`。

## 验收

- `RuntimeService` 一次 snapshot 可提供 CPU/RAM + 现有 GPU 指标；
- 无训练热路径采样；
- 无阻塞等待；
- 跨平台 CI 可运行。

## 建议提交

`feat(runtime): add cpu and memory metrics`
