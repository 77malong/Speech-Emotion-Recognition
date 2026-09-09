"""全库用户配置共享的严格 Pydantic 基础。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictConfig(BaseModel):
    """公共配置基类：拒绝未知字段，校验赋值并禁止意外修改。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=True)


__all__ = ["StrictConfig"]
