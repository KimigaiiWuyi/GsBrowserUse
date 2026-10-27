"""快照文本。Agent 只根据 e 编号操作，编号和名称在同一次快照里对齐。"""

from __future__ import annotations

from urllib.parse import urlsplit

SNAPSHOT_MARK = "--- 可操作 ---"
_BODY_LIMIT = 4000
_NAME_LIMIT = 200

Control = tuple[str, str]


def clip_name(name: str) -> str:
    text = " ".join(name.split())
    if len(text) <= _NAME_LIMIT:
        return text
    return text[:_NAME_LIMIT] + "…"


def format_snapshot(url: str, title: str, body: str, controls: list[Control]) -> str:
    clipped = body.strip()
    if len(clipped) > _BODY_LIMIT:
        clipped = clipped[:_BODY_LIMIT] + "…"
    lines = [f"URL: {url}", f"标题: {title}", "正文:", clipped, SNAPSHOT_MARK]
    for index, (kind, name) in enumerate(controls, start=1):
        lines.append(f"e{index} {kind} {name}")
    return "\n".join(lines)


def resolve_control(target: str, controls: list[Control]) -> Control | None:
    text = target.strip()
    if len(text) >= 2 and text[0] == "e" and text[1:].isdigit():
        index = int(text[1:]) - 1
        if 0 <= index < len(controls):
            return controls[index]
        return None
    for control in controls:
        if control[1] == text:
            return control
    for control in controls:
        if control[1].startswith(text):
            return control
    return None


def blocked_secret(input_type: str | None, user_type: str) -> str:
    if input_type == "password" and user_type != "direct":
        return "群聊里不能填写密码，请改走私聊。"
    return ""


def reject_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "只打开 http 或 https 链接。"
    return ""
