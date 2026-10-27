"""工具真正调用的动作。锁在用户会话上，同一个用户的操作排队。"""

from __future__ import annotations

from pathlib import Path

from .pool import SessionPool
from .snapshot import reject_url, blocked_secret

_WAIT_MAX = 30.0


async def open_url(pool: SessionPool, key: str, url: str) -> str:
    rejected = reject_url(url)
    if rejected:
        return rejected
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.goto(url)


async def snapshot(pool: SessionPool, key: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.snapshot()


async def click(pool: SessionPool, key: str, target: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.click(target)


async def fill(pool: SessionPool, key: str, target: str, text: str, *, user_type: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        kind = await session.driver.control_type(target)
        blocked = blocked_secret(kind, user_type)
        if blocked:
            return blocked
        return await session.driver.fill_value(target, text)


async def press(pool: SessionPool, key: str, hotkey: str, target: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.press(hotkey, target)


async def select(pool: SessionPool, key: str, target: str, value: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.select(target, value)


async def scroll(pool: SessionPool, key: str, direction: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.scroll(direction)


async def wait_text(pool: SessionPool, key: str, text: str, timeout_sec: float) -> str:
    bounded = min(_WAIT_MAX, max(1.0, timeout_sec))
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.wait_text(text, bounded)


async def back(pool: SessionPool, key: str) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.back()


async def shot(pool: SessionPool, key: str, path: Path) -> str:
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        return await session.driver.shot(path)


async def close_session(pool: SessionPool, key: str) -> str:
    if not await pool.opened(key):
        return "当前没有打开的页面。"
    session = await pool.acquire(key)
    async with session.lock:
        pool.mark(session)
        await session.driver.close()
        await pool.forget(key)
    return "页面已关闭。"
