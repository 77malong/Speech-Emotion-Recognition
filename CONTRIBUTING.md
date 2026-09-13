# 贡献指南

SER-lib 1.x 只维护可复用的 SER Core Python SDK。Web、Desktop、本地 HTTP 服务、
账户系统和产品 UI 应放在独立应用仓库。

## 开发环境

~~~bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[test,dev,hf]"
~~~

提交前执行：

~~~bash
python -m pip check
python -m pytest -q
python -m ruff check .
python -m mypy ser_lib
python -m build
python scripts/smoke_train_epoch.py --device cpu
~~~

CI 还会覆盖 Python 3.10–3.12、Linux/Windows/macOS、隔离 wheel 安装和固定
Transformers 版本矩阵。

## API 与兼容性

1. 新增公开 API 前先确定所属领域子包，不向根包无条件聚合导出。
2. 1.x 已公开 API 的 breaking change 必须进入下一个 major version。
3. StrictConfig 新字段必须有明确默认值/约束，禁止未知字段。
4. 不新增历史 schema migration 或 pre-1.0 compatibility shim。
5. checkpoint 是可信本地恢复格式；模型分发能力必须走 artifact。

## 数据与模型

- 新 Representation 必须声明 TensorSpec。
- 新模型必须实现 ModelSpec、model_config、ModelOutput。
- 新 importer 必须覆盖非法元数据、标签映射、路径安全、失败原子性和 split 泄漏测试。
- Dataset 不按 CNN/RNN/Transformer 或 MFCC/Mel 类型分叉。

## 测试

除正常路径外，至少覆盖边界/失败路径和序列化往返。涉及恢复逻辑时必须断言失败后对象状态
不被部分修改；涉及标签/预处理语义时不能只测试类别数或 tensor shape。

不得提交真实语料、大型权重、runs、artifacts、缓存、密钥、机器绝对路径或未经许可媒体。

历史架构计划和审计证据位于 docs/development；当前开发规则以本文件和 docs/README.md 为准。
