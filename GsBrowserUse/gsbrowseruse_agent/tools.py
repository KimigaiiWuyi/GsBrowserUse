"""浏览器工具只挂在 browser_agent 上。主人格通过委派使用，不直接拿这些工具。"""

from __future__ import annotations

from datetime import datetime
from collections.abc import Awaitable

from pydantic_ai import RunContext

from gsuid_core.models import Event
from gsuid_core.ai_core.models import ToolContext
from gsuid_core.ai_core.register import ai_tools

from ..gsbrowseruse_browser.who import user_key, user_place
from ..gsbrowseruse_config.config import ROOT, flag_bool
from ..gsbrowseruse_browser.errors import BrowserBusy, BrowserNotReady
from ..gsbrowseruse_browser.actions import (
    back,
    fill,
    shot,
    click,
    press,
    scroll,
    select,
    open_url,
    snapshot,
    wait_text,
    close_session,
)
from ..gsbrowseruse_browser.service import get_pool


def allow_browser(ev: Event | None) -> tuple[bool, str]:
    if flag_bool("master_only", True) and (ev is None or ev.user_pm != 0):
        return False, "浏览器只对主人开放。主人可以在插件配置里关掉「仅主人可用」。"
    return True, ""


async def _guard(work: Awaitable[str]) -> str:
    try:
        return await work
    except BrowserNotReady as exc:
        return exc.message
    except BrowserBusy as exc:
        return exc.message


def _shot_path(key: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in key)[:40]
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return str(ROOT / "shots" / f"{safe}-{stamp}.png")


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["在隔离的浏览器里打开网页，并继续点击、填写、截图"],
    aliases=["浏览器·打开网页"],
    brief="打开一个 http 或 https 网页，并返回页面快照。",
    timeout=180,
    code_callable=False,
)
async def browser_open(ctx: RunContext[ToolContext], url: str) -> str:
    """打开一个 http 或 https 网页，并返回快照。

    同一个用户会沿用已经打开的页面。还没安装浏览器时，提示主人去插件配置里下载。

    Args:
        ctx: 工具上下文
        url: 以 http:// 或 https:// 开头的网址
    """
    return await _guard(open_url(get_pool(), user_key(ctx.deps.ev), url))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["查看当前浏览器页面的正文和可操作控件"],
    aliases=["浏览器·查看页面"],
    brief="读取当前页面的正文和可点击控件。",
    timeout=60,
    code_callable=False,
)
async def browser_snapshot(ctx: RunContext[ToolContext]) -> str:
    """读取当前页面。正文在分隔线上面，e 编号在下面。

    Args:
        ctx: 工具上下文
    """
    return await _guard(snapshot(get_pool(), user_key(ctx.deps.ev)))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["点击快照里的按钮或链接"],
    aliases=["浏览器·点击"],
    brief="点击快照里的控件，并返回点击之后的页面快照。",
    timeout=60,
    code_callable=False,
)
async def browser_click(ctx: RunContext[ToolContext], target: str) -> str:
    """点击快照里的 e 编号，返回点击之后的快照。

    Args:
        ctx: 工具上下文
        target: 快照里的 e 编号，例如 e2
    """
    return await _guard(click(get_pool(), user_key(ctx.deps.ev), target))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["在网页输入框里填写文字"],
    aliases=["浏览器·填写"],
    brief="把文字写入输入框。群聊里不能填写密码。",
    timeout=60,
    code_callable=False,
)
async def browser_fill(ctx: RunContext[ToolContext], target: str, text: str) -> str:
    """把文字填进快照里的输入框。群聊里不能填密码。

    Args:
        ctx: 工具上下文
        target: 快照里的 e 编号
        text: 要填入的文字
    """
    return await _guard(fill(get_pool(), user_key(ctx.deps.ev), target, text, user_type=user_place(ctx.deps.ev)))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["在网页上按键"],
    aliases=["浏览器·按键"],
    brief="在页面上按下指定按键，并返回新的快照。",
    timeout=60,
    code_callable=False,
)
async def browser_press(ctx: RunContext[ToolContext], key: str, target: str = "") -> str:
    """按下键盘。可以先把焦点放到某个 e 编号上。

    Args:
        ctx: 工具上下文
        key: 键名，例如 Enter、Tab、ArrowDown，或单个字符
        target: 可选，先聚焦的 e 编号
    """
    return await _guard(press(get_pool(), user_key(ctx.deps.ev), key, target))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["选择网页下拉框中的一项"],
    aliases=["浏览器·选择"],
    brief="选择下拉框中的一项，并返回新的快照。",
    timeout=60,
    code_callable=False,
)
async def browser_select(ctx: RunContext[ToolContext], target: str, value: str) -> str:
    """选择下拉框里的一项。

    Args:
        ctx: 工具上下文
        target: 快照里的 e 编号
        value: 选项的可见文字或值
    """
    return await _guard(select(get_pool(), user_key(ctx.deps.ev), target, value))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["滚动当前网页"],
    aliases=["浏览器·滚动"],
    brief="向上或向下滚动当前页面，并返回新的快照。",
    timeout=60,
    code_callable=False,
)
async def browser_scroll(ctx: RunContext[ToolContext], direction: str) -> str:
    """向上或向下滚动当前页面。

    Args:
        ctx: 工具上下文
        direction: up 或 down
    """
    return await _guard(scroll(get_pool(), user_key(ctx.deps.ev), direction))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["等待页面上出现某段文字"],
    aliases=["浏览器·等待"],
    brief="等待页面正文出现指定文字，然后返回快照。",
    timeout=90,
    code_callable=False,
)
async def browser_wait(ctx: RunContext[ToolContext], text: str, timeout_sec: int = 10) -> str:
    """等到正文里出现这段文字，然后返回快照。

    Args:
        ctx: 工具上下文
        text: 要等的文字
        timeout_sec: 最多等几秒，超过 30 秒按 30 秒
    """
    return await _guard(wait_text(get_pool(), user_key(ctx.deps.ev), text, float(timeout_sec)))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["浏览器后退一页"],
    aliases=["浏览器·后退"],
    brief="回到上一个网页，并读取新的页面快照。",
    timeout=60,
    code_callable=False,
)
async def browser_back(ctx: RunContext[ToolContext]) -> str:
    """回到上一个页面，并返回快照。

    Args:
        ctx: 工具上下文
    """
    return await _guard(back(get_pool(), user_key(ctx.deps.ev)))


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["截取当前浏览器画面"],
    aliases=["浏览器·截图"],
    brief="截取当前画面，并返回图片文件路径。",
    timeout=90,
    code_callable=False,
)
async def browser_shot(ctx: RunContext[ToolContext]) -> str:
    """截取当前画面，返回图片文件路径。

    Args:
        ctx: 工具上下文
    """
    from pathlib import Path
    from datetime import datetime

    from gsuid_core.ai_core.planning.models import AIAgentTask
    from gsuid_core.ai_core.planning.runtime import get_plan_context
    from gsuid_core.ai_core.planning.workspace import put_artifact

    plan_ctx = get_plan_context()
    workspace = plan_ctx.artifact_workspace if plan_ctx else None

    if workspace is not None:
        workspace.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() else "_" for ch in user_key(ctx.deps.ev))[:40]
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = workspace / f"shot_{safe}-{stamp}.png"
    else:
        path = Path(_shot_path(user_key(ctx.deps.ev)))

    result = await _guard(shot(get_pool(), user_key(ctx.deps.ev), path))

    # 在 Kanban 任务上下文中且截图成功落盘时，自动登记为真实图片 artifact
    if workspace is not None and plan_ctx is not None and path.exists() and path.is_file():
        art = await put_artifact(
            summary=f"浏览器截图: {path.name}",
            mime="image/png",
            artifact_kind="output",
            plan_ctx=plan_ctx,
            file_path=path,
        )
        if art is not None:
            await AIAgentTask.update_data_by_data(
                select_data={"id": plan_ctx.task_id},
                update_data={"output_artifact_id": art.id},
            )
            return (
                f"✅ 截图已自动登记为图片产物: {art.id}（{art.size_bytes} bytes，"
                f"文件：{path.name}，上游可直接发送）\n{result}"
            )
    return result


@ai_tools(
    category="default",
    check_func=allow_browser,
    capability_domain="浏览器",
    covers=["关闭当前用户的浏览器页面"],
    aliases=["浏览器·关闭页面"],
    brief="关闭当前用户的页面。没有其他页面时，连浏览器进程一起停掉。",
    timeout=60,
    code_callable=False,
)
async def browser_close(ctx: RunContext[ToolContext]) -> str:
    """关闭当前用户的页面。没有别的页面时，浏览器进程也退出。

    Args:
        ctx: 工具上下文
    """
    return await _guard(close_session(get_pool(), user_key(ctx.deps.ev)))
