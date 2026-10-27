"""插件配置。按钮的 endpoint 必须和 register_config_button 用同一条路径。"""

from __future__ import annotations

from gsuid_core.data_store import get_res_path
from gsuid_core.utils.fonts.fonts import FONT_ORIGIN_PATH
from gsuid_core.utils.plugins_config.models import (
    GSC,
    ButtonState,
    GsIntConfig,
    GsStrConfig,
    GsBoolConfig,
    GsButtonConfig,
    ButtonStatusField,
)
from gsuid_core.utils.plugins_config.gs_config import StringConfig

from .host import host_label

ROOT = get_res_path("GsBrowserUse")
INSTALL_ENDPOINT = "/api/gs_browser_use/install"
_HOST = host_label()
_ENGINES = ("obscura", "lightpanda")

CONFIG_DEFAULT: dict[str, GSC] = {
    "install": GsButtonConfig(
        title="安装浏览器",
        desc="按当前环境和所选引擎下载。装好以后这里会显示版本、路径和当前环境。",
        data=ButtonState(),
        endpoint=INSTALL_ENDPOINT,
        label="下载并安装",
        level="primary",
        confirm=f"当前环境是 {_HOST}。会下载这个环境对应的安装包，约 70MB。已经安装时再点一次会换成当前引擎。",
        status_fields=[
            ButtonStatusField(key="host", label="当前环境"),
            ButtonStatusField(key="engine", label="引擎"),
            ButtonStatusField(key="version", label="版本"),
            ButtonStatusField(key="path", label="路径"),
            ButtonStatusField(key="platform", label="安装包平台"),
            ButtonStatusField(key="variant", label="安装包"),
            ButtonStatusField(key="installed_at", label="安装时间"),
        ],
        show_progress=True,
        poll_ms=800,
    ),
    "engine": GsStrConfig(
        title="浏览器引擎",
        desc="Obscura 支持 Windows、Linux、macOS。Lightpanda 只有 Linux 和 macOS 安装包。改完需要再点一次下载。",
        data="obscura",
        options=["obscura", "lightpanda"],
    ),
    "max_contexts": GsIntConfig(
        title="同时打开的页面数",
        desc="每个用户占一个页面。超过后关掉最久没用的。最多 8 个。",
        data=3,
        max_value=8,
    ),
    "idle_seconds": GsIntConfig(
        title="空闲关闭秒数",
        desc="这么久没人操作就关掉页面。少于 30 秒时按 30 秒。最后一个页面关掉后，浏览器进程也退出。",
        data=300,
        max_value=3600,
    ),
    "master_only": GsBoolConfig(
        title="仅主人可用",
        desc="打开时，只有主人能让代理操作浏览器。",
        data=True,
    ),
    "stealth": GsBoolConfig(
        title="隐身模式",
        desc="只对 Obscura 生效，会改用隐身安装包。改完需要再点一次下载。",
        data=False,
    ),
    "allow_private_network": GsBoolConfig(
        title="允许访问内网",
        desc="只对 Obscura 生效。默认关闭。打开后浏览器才能访问本机和局域网地址。",
        data=False,
    ),
    "font_dir": GsStrConfig(
        title="字体目录",
        desc="只对 Obscura 生效。截图里的中文需要这个目录下的字体。留空则不指定。",
        data=str(FONT_ORIGIN_PATH.parent),
    ),
}

CONFIG = StringConfig("GsBrowserUse", ROOT / "config.json", CONFIG_DEFAULT)


def _int_flag(key: str, default: int, low: int, high: int) -> int:
    item = CONFIG.get_config(key)
    value = item.data if isinstance(item, GsIntConfig) else default
    if value < low:
        return low
    if value > high:
        return high
    return value


def flag_bool(key: str, default: bool) -> bool:
    item = CONFIG.get_config(key)
    if isinstance(item, GsBoolConfig):
        return item.data
    return default


def max_contexts() -> int:
    return _int_flag("max_contexts", 3, 1, 8)


def idle_limit() -> int:
    return _int_flag("idle_seconds", 300, 30, 3600)


def desired_engine() -> str:
    item = CONFIG.get_config("engine")
    if isinstance(item, GsStrConfig) and item.data in _ENGINES:
        return item.data
    return "obscura"


def desired_variant() -> str:
    if flag_bool("stealth", False):
        return "stealth"
    return "render"


def font_dir() -> str:
    item = CONFIG.get_config("font_dir")
    if isinstance(item, GsStrConfig):
        return item.data.strip()
    return ""
