"""用 Playwright 当 CDP 客户端。不调用 playwright install。"""

from __future__ import annotations

import time
import asyncio
from pathlib import Path

from playwright.async_api import Page, Error as PlaywrightError, Locator, TimeoutError as PlaywrightTimeout

from .snapshot import Control, clip_name, format_snapshot, resolve_control

_KINDS: tuple[tuple[str, str], ...] = (
    ("button", "button, [role=button]"),
    ("link", "a[href]"),
    ("textbox", "input, textarea"),
    ("select", "select"),
)
_KEYS = frozenset(
    {
        "Enter",
        "Tab",
        "Escape",
        "Backspace",
        "Space",
        "Delete",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
    }
)
_CONTROL_CAP = 40


class PlaywrightPage:
    def __init__(self, page: Page) -> None:
        self._page = page
        self._controls: list[Control] = []

    async def close(self) -> None:
        context = self._page.context
        await self._page.close()
        await context.close()

    async def goto(self, url: str) -> str:
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await self._page.locator("button").first.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeout:
            pass
        except PlaywrightError as exc:
            return f"打不开这个页面：{exc}"
        return await self.snapshot()

    async def snapshot(self) -> str:
        self._controls = await self._collect()
        return format_snapshot(self._page.url, await self._title(), await self._body(), self._controls)

    async def click(self, target: str) -> str:
        loc = await self._locate(target)
        if loc is None:
            return f"页面上没有「{target}」。先看快照里的 e 编号。"
        before = await self._body()
        try:
            await loc.scroll_into_view_if_needed(timeout=3000)
            await loc.click(timeout=8000)
        except PlaywrightTimeout:
            return "点击超时。"
        except PlaywrightError as exc:
            return f"点击失败：{exc}"
        await self._wait_change(before)
        return await self.snapshot()

    async def control_type(self, target: str) -> str | None:
        loc = await self._locate(target)
        if loc is None:
            return None
        return await loc.get_attribute("type")

    async def fill_value(self, target: str, text: str) -> str:
        loc = await self._locate(target)
        if loc is None:
            return f"页面上没有「{target}」。先看快照里的 e 编号。"
        try:
            await loc.fill(text, timeout=8000)
        except PlaywrightError as exc:
            return f"填写失败：{exc}"
        return await self.snapshot()

    async def press(self, key: str, target: str) -> str:
        if key not in _KEYS and len(key) != 1:
            return "这个按键不支持。"
        if target:
            loc = await self._locate(target)
            if loc is None:
                return f"页面上没有「{target}」。"
            try:
                await loc.focus(timeout=3000)
            except PlaywrightError as exc:
                return f"无法聚焦：{exc}"
        try:
            await self._page.keyboard.press(key)
        except PlaywrightError as exc:
            return f"按键失败：{exc}"
        return await self.snapshot()

    async def select(self, target: str, value: str) -> str:
        loc = await self._locate(target)
        if loc is None:
            return f"页面上没有「{target}」。"
        try:
            await loc.select_option(label=value, timeout=8000)
        except PlaywrightError:
            try:
                await loc.select_option(value=value, timeout=8000)
            except PlaywrightError as exc:
                return f"选择失败：{exc}"
        return await self.snapshot()

    async def scroll(self, direction: str) -> str:
        if direction == "down":
            delta = 480
        elif direction == "up":
            delta = -480
        else:
            return "方向只接受 up 或 down。"
        try:
            await self._page.mouse.wheel(0, delta)
        except PlaywrightError as exc:
            return f"滚动失败：{exc}"
        return await self.snapshot()

    async def wait_text(self, text: str, timeout_sec: float) -> str:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            if text and text in await self._body():
                return await self.snapshot()
            await asyncio.sleep(0.2)
        return "等待超时，页面上还没有这段文字。"

    async def back(self) -> str:
        try:
            await self._page.go_back(wait_until="domcontentloaded", timeout=15000)
        except PlaywrightError as exc:
            return f"无法返回：{exc}"
        return await self.snapshot()

    async def shot(self, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            await self._page.screenshot(path=str(path), full_page=False)
        except PlaywrightError as exc:
            return f"截图失败：{exc}"
        body = await self._body()
        if len(body) > 500:
            body = body[:500] + "…"
        return f"截图文件：{path}\n{body}"

    async def _locate(self, target: str) -> Locator | None:
        if not self._controls:
            self._controls = await self._collect()
        found = resolve_control(target, self._controls)
        if found is None:
            return None
        kind, name = found
        selector = ""
        for item_kind, item_selector in _KINDS:
            if item_kind == kind:
                selector = item_selector
                break
        if not selector:
            return None
        loc = self._page.locator(selector)
        count = await loc.count()
        for index in range(count):
            item = loc.nth(index)
            if not await item.is_visible():
                continue
            if await self._label(item) == name:
                return item
        return None

    async def _collect(self) -> list[Control]:
        found: list[Control] = []
        for kind, selector in _KINDS:
            loc = self._page.locator(selector)
            count = await loc.count()
            for index in range(count):
                item = loc.nth(index)
                if not await item.is_visible():
                    continue
                name = await self._label(item)
                if not name:
                    continue
                found.append((kind, name))
                if len(found) >= _CONTROL_CAP:
                    return found
        return found

    async def _label(self, loc: Locator) -> str:
        text = clip_name(await loc.inner_text())
        if text:
            return text
        for attr in ("aria-label", "placeholder", "name", "value"):
            raw = await loc.get_attribute(attr)
            if raw:
                text = clip_name(raw)
                if text:
                    return text
        return ""

    async def _body(self) -> str:
        try:
            return await self._page.locator("body").inner_text()
        except PlaywrightError:
            return ""

    async def _title(self) -> str:
        try:
            return await self._page.title()
        except PlaywrightError:
            return ""

    async def _wait_change(self, before: str) -> None:
        # 题目按钮有过渡动画，点完立刻读正文还会停在上一题。
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            await asyncio.sleep(0.2)
            if await self._body() != before:
                return
