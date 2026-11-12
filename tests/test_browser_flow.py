"""页面池、快照编号，以及群聊不能填密码。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from quiz_walk import walk_until
from fastapi.routing import APIRoute

from gsuid_core.models import Event
from GsBrowserUse.gsbrowseruse_agent.tools import allow_browser
from GsBrowserUse.gsbrowseruse_browser.who import user_key
from GsBrowserUse.gsbrowseruse_browser.pool import SessionPool
from gsuid_core.utils.plugins_config.models import GsBoolConfig
from GsBrowserUse.gsbrowseruse_config.config import CONFIG, INSTALL_ENDPOINT
from GsBrowserUse.gsbrowseruse_browser.driver import PageDriver
from GsBrowserUse.gsbrowseruse_browser.errors import BrowserBusy
from GsBrowserUse.gsbrowseruse_browser.actions import fill, open_url
from GsBrowserUse.gsbrowseruse_browser.snapshot import Control, format_snapshot, resolve_control

_NEEDLE = "灵魂重合度"


class _Backend:
    def __init__(self, page: PageDriver) -> None:
        self.page = page
        self.opens = 0
        self.stopped = False

    async def open_page(self) -> PageDriver:
        self.opens += 1
        return self.page

    async def stop(self) -> None:
        self.stopped = True


class _Quiz:
    def __init__(self) -> None:
        self.step = -1
        self.controls: list[Control] = []
        self.closed = False

    async def goto(self, url: str) -> str:
        self.step = -1
        return await self.snapshot()

    async def snapshot(self) -> str:
        body, controls = self._view()
        self.controls = controls
        return format_snapshot("https://example.test/quiz", "测验", body, controls)

    async def click(self, target: str) -> str:
        found = resolve_control(target, self.controls)
        if found is None:
            return f"页面上没有「{target}」"
        name = found[1]
        if name.startswith("开始"):
            self.step = 0
        elif name.startswith("上一题") and self.step > 0:
            self.step -= 1
        elif name.startswith("A") and 0 <= self.step < 40:
            self.step += 1
        return await self.snapshot()

    async def close(self) -> None:
        self.closed = True

    def _view(self) -> tuple[str, list[Control]]:
        if self.step < 0:
            return "准备开始", [("button", "开始测试")]
        if self.step >= 40:
            return "你的动漫灵魂角色是\n测试角色\n灵魂重合度 80%", []
        body = f"{self.step + 1} / 40\n这是第 {self.step + 1} 题"
        return body, [
            ("button", "上一题"),
            ("button", "A. 先看情况"),
            ("button", "B. 直接问"),
            ("button", "C. 换个话题"),
            ("button", "D. 先离开"),
        ]


class _Secret:
    def __init__(self) -> None:
        self.filled: list[str] = []
        self.controls: list[Control] = [("textbox", "密码")]

    async def control_type(self, target: str) -> str | None:
        found = resolve_control(target, self.controls)
        if found is None:
            return None
        if found[1] == "密码":
            return "password"
        return "text"

    async def fill_value(self, target: str, text: str) -> str:
        self.filled.append(text)
        return "已填写"

    async def close(self) -> None:
        return None


def _pool(page: PageDriver, *, live: int = 2, idle: int = 30, now: dict[str, float] | None = None) -> SessionPool:
    clock = (lambda: now["t"]) if now is not None else None
    return SessionPool(_Backend(page), max_live=lambda: live, idle_seconds=lambda: idle, clock=clock)


def test_same_user_shares_a_page_across_rooms() -> None:
    group = Event(bot_id="bot", user_id="u1", user_type="group")
    private = Event(bot_id="bot", user_id="u1", user_type="direct")
    other = Event(bot_id="bot", user_id="u2", user_type="group")
    assert user_key(group) == user_key(private)
    assert user_key(group) != user_key(other)


def test_master_switch() -> None:
    item = CONFIG.get_config("master_only")
    assert isinstance(item, GsBoolConfig)
    previous = item.data
    owner = Event(user_id="owner", user_pm=0)
    guest = Event(user_id="guest", user_pm=6)
    CONFIG.set_config("master_only", True)
    try:
        assert allow_browser(owner)[0] is True
        allowed, message = allow_browser(guest)
        assert allowed is False
        assert "主人" in message
        CONFIG.set_config("master_only", False)
        assert allow_browser(guest)[0] is True
    finally:
        CONFIG.set_config("master_only", previous)


def test_install_button_requires_admin() -> None:
    import GsBrowserUse.gsbrowseruse_install  # noqa: F401
    from gsuid_core.webconsole.app_app import app
    from gsuid_core.webconsole.web_api import require_admin

    matched = [route for route in app.routes if isinstance(route, APIRoute) and route.path == INSTALL_ENDPOINT]
    methods = {method for route in matched for method in route.methods}
    assert methods == {"GET", "POST"}

    def calls(route: APIRoute) -> list[object]:
        found: list[object] = []
        stack = list(route.dependant.dependencies)
        while stack:
            dep = stack.pop()
            found.append(dep.call)
            stack.extend(dep.dependencies)
        return found

    for route in matched:
        assert require_admin in calls(route)


def test_file_url_is_refused_before_open() -> None:
    page = _Quiz()

    async def _run() -> str:
        pool = _pool(page)
        try:
            return await open_url(pool, "u", "file:///tmp/secret")
        finally:
            await pool.shutdown()

    assert asyncio.run(_run()) == "只打开 http 或 https 链接。"
    assert page.closed is False


def test_group_cannot_fill_password() -> None:
    page = _Secret()

    async def _run() -> tuple[str, str]:
        pool = _pool(page)
        try:
            private = await fill(pool, "u", "e1", "secret", user_type="direct")
            group = await fill(pool, "u", "e1", "secret", user_type="group")
            return private, group
        finally:
            await pool.shutdown()

    private, group = asyncio.run(_run())
    assert private == "已填写"
    assert page.filled == ["secret"]
    assert "私聊" in group


def test_choice_page_reaches_the_result() -> None:
    page = _Quiz()

    async def _run() -> str:
        pool = _pool(page)
        try:
            return await walk_until(pool, "u", "https://example.test/quiz", _NEEDLE)
        finally:
            await pool.shutdown()

    text = asyncio.run(_run())
    assert _NEEDLE in text
    assert page.step == 40


def test_idle_page_is_closed_and_process_stops() -> None:
    page = _Quiz()
    now = {"t": 0.0}

    async def _run() -> _Backend:
        backend = _Backend(page)
        pool = SessionPool(backend, max_live=lambda: 2, idle_seconds=lambda: 10, clock=lambda: now["t"])
        try:
            await pool.acquire("u")
            now["t"] = 10
            await pool.sweep_once()
            return backend
        finally:
            await pool.shutdown()

    backend = asyncio.run(_run())
    assert page.closed is True
    assert backend.stopped is True


def test_busy_when_every_page_is_in_use() -> None:
    async def _run() -> None:
        pool = _pool(_Quiz(), live=1)
        try:
            held = await pool.acquire("a")
            async with held.lock:
                with pytest.raises(BrowserBusy):
                    await pool.acquire("b")
        finally:
            await pool.shutdown()

    asyncio.run(_run())


def test_same_user_reuses_the_open_page() -> None:
    async def _run() -> int:
        backend = _Backend(_Quiz())
        pool = SessionPool(backend, max_live=lambda: 2, idle_seconds=lambda: 30)
        try:
            await pool.acquire("u")
            await pool.acquire("u")
            return backend.opens
        finally:
            await pool.shutdown()

    assert asyncio.run(_run()) == 1


def test_browser_shot_auto_registers_in_kanban(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from sqlmodel import SQLModel
    from pydantic_ai import RunContext
    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import gsuid_core.utils.database.base_models as base_models
    from gsuid_core.ai_core.models import ToolContext
    from gsuid_core.ai_core.planning.models import AIAgentTask, AIAgentArtifact  # noqa: F401
    from gsuid_core.ai_core.planning.runtime import (
        PlanRunContext,
        bind_plan_context,
        reset_plan_context,
    )
    from GsBrowserUse.gsbrowseruse_agent.tools import browser_shot

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'artifacts.db').as_posix()}",
        poolclass=NullPool,
    )
    monkeypatch.setattr(
        base_models,
        "async_maker",
        async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession),
    )
    monkeypatch.setattr(base_models, "sqlite_read_semaphore", None)
    monkeypatch.setattr(base_models, "_db_type", "sqlite")

    async def _init_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.run(_init_tables())

    ws = tmp_path / "browser_ws"
    ws.mkdir()
    plan_ctx = PlanRunContext(
        root_task_id="root_shot_test",
        task_id="task_shot_test",
        agent_profile="browser_agent",
        artifact_workspace=ws,
    )
    token = bind_plan_context(plan_ctx)

    try:
        ev = Event(user_id="test_user_42", user_pm=0)
        tool_ctx = ToolContext(ev=ev)
        run_ctx = MagicMock(spec=RunContext)
        run_ctx.deps = tool_ctx

        async def fake_shot(pool: object, key: str, path: Path) -> str:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"FAKE_BROWSER_SHOT_BYTES")
            return f"截图文件：{path}\n正文内容..."

        monkeypatch.setattr("GsBrowserUse.gsbrowseruse_agent.tools.shot", fake_shot)

        result = asyncio.run(browser_shot(run_ctx))
        assert "✅ 截图已自动登记为图片产物:" in result
        assert "上游可直接发送" in result

        shot_files = list(ws.glob("shot_*.png"))
        assert len(shot_files) == 1
        assert shot_files[0].read_bytes() == b"FAKE_BROWSER_SHOT_BYTES"
    finally:
        reset_plan_context(token)
