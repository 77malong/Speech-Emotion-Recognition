"""配置异常。"""

from ser_lib.foundation.errors.base import SERError


class ConfigurationError(SERError):
    """配置文件无法读取或内容校验失败。"""

    default_code = "configuration_error"


__all__ = ["ConfigurationError"]
