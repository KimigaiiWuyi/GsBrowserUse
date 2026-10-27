"""GsBrowserUse 插件。业务在子目录里，嵌套加载会自动导入。"""

from __future__ import annotations

import sys
from types import ModuleType

from gsuid_core.sv import Plugins


def _pin_loader_ancestors() -> None:
    """加载器没建 plugins 父包时，相对导入会失败。"""
    parts = __name__.split(".")
    if parts[0] != "plugins":
        return
    for index in range(1, len(parts)):
        qualified = ".".join(parts[:index])
        if qualified in sys.modules:
            continue
        ancestor = ModuleType(qualified)
        ancestor.__package__ = qualified
        ancestor.__path__ = []
        sys.modules[qualified] = ancestor


_pin_loader_ancestors()

Plugins(
    name="GsBrowserUse",
    force_prefix=["浏览器"],
    allow_empty_prefix=False,
)
