"""浏览器代理。工具白名单只有页面操作，不带发消息。"""

from __future__ import annotations

from gsuid_core.ai_core.agent_node import AgentNode, register_agent_node

_PROMPT = """你操作浏览器页面。每次只调用一个工具，然后根据新的快照决定下一步。

快照里，「--- 可操作 ---」上面是页面正文，下面每行是 e编号、控件种类、名称。
点击、填写、选择都填这些 e 编号。编号过期就重新看快照。

先打开 http 或 https 链接。已经打开时看快照，不要重复打开。

多步选择题：点名称以「开始」开头的按钮。每一题只点一个选项。
选项名称通常以 A、B、C、D 开头。不要点「上一题」，除非用户明确要改上一题。
正文出现结果或结束说明后停下来，把这段正文原样作为结论返回。

用户没要截图就不要截图。要截图时把返回的文件路径写进结论。
全部做完再关闭页面。

页面上没有的按钮不要编。不要执行脚本。
"""

_BOUNDARY = """【交付】
把最后一屏的正文原样作为返回值。不要发消息给用户。若有截图，只把文件路径写进返回值。
"""

_TOOLS = [
    "browser_open",
    "browser_snapshot",
    "browser_click",
    "browser_fill",
    "browser_press",
    "browser_select",
    "browser_scroll",
    "browser_wait",
    "browser_back",
    "browser_shot",
    "browser_close",
]


def register_browser_agent() -> None:
    register_agent_node(
        AgentNode(
            node_id="browser_agent",
            display_name="浏览器代理",
            prompt=_PROMPT,
            prompt_style="plain",
            when_to_use="用户要在浏览器里打开网页、点击、填写、截图，或走完一个多步页面。只读一篇文章时不要用。",
            match_keywords=["打开网页", "浏览器操作", "网页截图"],
            tool_packs=[],
            tool_names=list(_TOOLS),
            boundary_override=_BOUNDARY,
            master_only=False,
            source="plugin",
            plugin="GsBrowserUse",
        )
    )


register_browser_agent()
