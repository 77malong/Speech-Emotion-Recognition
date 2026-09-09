"""兼容入口：Diagnostic 已迁移到 :mod:`ser_lib.foundation.diagnostics`。

该 shim 仅用于 0.2.x 过渡，计划在 Stage 05 删除。
"""

from ser_lib.foundation.diagnostics import Diagnostic, DiagnosticSeverity

__all__ = ["Diagnostic", "DiagnosticSeverity"]
