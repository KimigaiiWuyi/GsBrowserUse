"""会话键：同一个 bot 上的同一个用户共用一个页面，不按群拆开。"""

from __future__ import annotations

from gsuid_core.models import Event


def user_key(ev: Event | None) -> str:
    if ev is None or not ev.user_id:
        return "local"
    return f"{ev.bot_id}:{ev.user_id}"


def user_place(ev: Event | None) -> str:
    if ev is None:
        return "direct"
    return ev.user_type
