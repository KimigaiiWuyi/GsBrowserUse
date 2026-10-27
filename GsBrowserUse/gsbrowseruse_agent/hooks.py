"""启动时把磁盘上的安装结果同步到按钮。退出时关掉浏览器进程。"""

from __future__ import annotations

from gsuid_core.server import on_core_start, on_core_shutdown
from gsuid_core.utils.plugins_config.models import ButtonState, GsButtonConfig

from ..gsbrowseruse_config.host import host_label
from ..gsbrowseruse_config.config import CONFIG, desired_engine
from ..gsbrowseruse_browser.service import shutdown_pool
from ..gsbrowseruse_install.engines import engine_label
from ..gsbrowseruse_install.manifest import read_manifest, status_fields, install_problem


def sync_install_button() -> None:
    item = CONFIG.get_config("install")
    if not isinstance(item, GsButtonConfig):
        return
    if item.data.phase == "running":
        fields = dict(item.data.fields)
        fields["host"] = host_label()
        fields["engine"] = engine_label(desired_engine())
        CONFIG.set_button_state(
            "install",
            ButtonState(
                phase="error",
                progress=item.data.progress,
                message="任务已中断",
                fields=fields,
            ),
        )
        return
    info = read_manifest()
    if info is None:
        _show_host(item)
        return
    fields = status_fields(info)
    problem = install_problem()
    if problem:
        phase = "error"
        message = problem
    else:
        phase = "success"
        message = "已安装"
    if item.data.phase == phase and item.data.message == message and dict(item.data.fields) == fields:
        return
    CONFIG.set_button_state(
        "install",
        ButtonState(phase=phase, progress=100, message=message, fields=fields),
    )


def _show_host(item: GsButtonConfig) -> None:
    fields = dict(item.data.fields)
    fields["host"] = host_label()
    fields["engine"] = engine_label(desired_engine())
    if item.data.phase == "success":
        phase = "error"
        message = "安装文件不在了，请重新下载。"
        progress = 0
    else:
        phase = item.data.phase
        message = item.data.message or f"当前环境是 {host_label()}。"
        progress = item.data.progress
    if item.data.phase == phase and item.data.message == message and dict(item.data.fields) == fields:
        return
    CONFIG.set_button_state(
        "install",
        ButtonState(phase=phase, progress=progress, message=message, fields=fields),
    )


@on_core_start
async def _sync_browser_install() -> None:
    sync_install_button()


@on_core_shutdown
async def _stop_browser() -> None:
    await shutdown_pool()
