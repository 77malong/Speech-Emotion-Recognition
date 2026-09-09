# 07 - Public API Audit

## 目标

冻结 SER-lib 进入稳定开发版前的公共 API 边界，确保应用层依赖的符号是有意公开的，internal helper 不被误导出。

## 审计范围

- `ser_lib/__init__.py`
- `ser_lib/core/__init__.py`
- `ser_lib/data/__init__.py`
- `ser_lib/engine/__init__.py`
- `ser_lib/artifacts/__init__.py`
- `ser_lib/inference/__init__.py`
- `ser_lib/services/__init__.py`
- `ser_lib/models/__init__.py`
- `tests/test_public_api.py`

## 审计维度

### 符号层

- `__all__` 与真实导出一致；
- public DTO / Service / stable helpers 可从预期路径导入；
- 下划线 internal 不被根包错误暴露；
- 同一概念不存在多个冲突公开入口。

### 命名层

统一检查：

- `*Info`、`*Result`、`*Detail`、`*Catalog`、`*Report` 的语义；
- `inspect_*` vs `scan_*` vs `load_*` vs `query_*`；
- `run_id` / `evaluation_id` / `artifact_id` 等 ID 命名；
- `path` / `*_file` / `*_dir` 的含义。

### 序列化层

对所有公开 Result/Info/Detail/Catalog：

- `to_dict()` 一致；
- Path 使用 `/` 规范；
- datetime UTC；
- enum 输出 value；
- tuple/set 等变 JSON-safe；
- 可直接 `json.dumps()`。

### 兼容层

不做大规模无兼容重命名。确实需要调整时：

- 优先 alias/deprecation；
- 文档标明迁移路径；
- 测试锁定旧入口仍可用。

## 实现步骤

1. 自动/人工列出各 `__init__` 当前导出；
2. 分类 stable / compatibility / internal；
3. 修正明显泄漏与遗漏；
4. 增强 `test_public_api.py` 为契约测试；
5. 为关键 DTO 增加统一 JSON-safe 参数化测试；
6. 更新 API_REFERENCE。

## 验收

- 根包和子包导出是显式、有测试的；
- 新增的 RunDetail、Preset、Migration public surface 已明确；
- internal helper 不要求应用层依赖；
- 公开 DTO 序列化契约有回归测试。

## 建议提交

`refactor(api): stabilize public ser-lib surface`
