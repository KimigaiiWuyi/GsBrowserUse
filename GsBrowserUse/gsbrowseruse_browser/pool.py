"""按用户放页面。同时打开的数量和空闲时间由调用方传入。"""

from __future__ import annotations

import time
import asyncio
from typing import Callable
from dataclasses import dataclass

from .driver import PageDriver, BrowserBackend
from .errors import BrowserBusy


@dataclass
class LiveSession:
    driver: PageDriver
    lock: asyncio.Lock
    touched: float


class SessionPool:
    def __init__(
        self,
        backend: BrowserBackend,
        *,
        max_live: Callable[[], int],
        idle_seconds: Callable[[], int],
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._backend = backend
        self._max_live = max_live
        self._idle_seconds = idle_seconds
        self._clock = clock or time.monotonic
        self._sessions: dict[str, LiveSession] = {}
        # 开页和腾位共用这把锁，避免同时打开的页面超过上限。
        self._lock = asyncio.Lock()
        self._sweeper: asyncio.Task[None] | None = None

    def _now(self) -> float:
        return self._clock()

    def mark(self, session: LiveSession) -> None:
        session.touched = self._now()

    def _ensure_sweeper(self) -> None:
        if self._sweeper is None:
            self._sweeper = asyncio.create_task(self._sweep_loop())

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            await self.sweep_once()

    async def stop_sweeper(self) -> None:
        task = self._sweeper
        self._sweeper = None
        if task is None:
            return
        task.cancel()
        await asyncio.wait([task])

    async def opened(self, key: str) -> bool:
        async with self._lock:
            return key in self._sessions

    async def acquire(self, key: str) -> LiveSession:
        self._ensure_sweeper()
        async with self._lock:
            current = self._sessions.get(key)
            if current is not None:
                current.touched = self._now()
                return current
            await self._make_room()
            driver = await self._backend.open_page()
            session = LiveSession(driver=driver, lock=asyncio.Lock(), touched=self._now())
            self._sessions[key] = session
            return session

    async def _make_room(self) -> None:
        if len(self._sessions) < self._max_live():
            return
        unlocked = [key for key, session in self._sessions.items() if not session.lock.locked()]
        if not unlocked:
            raise BrowserBusy("浏览器正忙，请稍后再试。")
        oldest = min(unlocked, key=lambda item: self._sessions[item].touched)
        await self._drop(oldest)

    async def sweep_once(self) -> None:
        async with self._lock:
            now = self._now()
            limit = self._idle_seconds()
            stale = [
                key
                for key, session in self._sessions.items()
                if not session.lock.locked() and now - session.touched >= limit
            ]
            for key in stale:
                await self._drop(key)
            if not self._sessions:
                await self._backend.stop()

    async def _drop(self, key: str) -> None:
        if key not in self._sessions:
            return
        session = self._sessions.pop(key)
        await session.driver.close()

    async def forget(self, key: str) -> None:
        """页面已经关掉。没有剩余页面时退出浏览器进程。"""
        async with self._lock:
            if key in self._sessions:
                self._sessions.pop(key)
            if not self._sessions:
                await self._backend.stop()

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            async with session.lock:
                await session.driver.close()
        await self._backend.stop()

    async def shutdown(self) -> None:
        await self.stop_sweeper()
        await self.close_all()
