"""一个本机浏览器进程。每个用户再开自己的浏览器上下文，不共用 cookie。"""

from __future__ import annotations

import os
import sys
import signal
import socket
import asyncio
import platform
from pathlib import Path

import httpx
from playwright.async_api import Error as PlaywrightError, Browser, Playwright, async_playwright

from gsuid_core.logger import logger

from .page import PlaywrightPage
from .driver import PageDriver
from .errors import BrowserNotReady
from ..gsbrowseruse_config.proxy import resolve_proxy
from ..gsbrowseruse_config.config import font_dir, flag_bool
from ..gsbrowseruse_install.engines import Asset, BrowserEngine, get_engine
from ..gsbrowseruse_install.manifest import read_manifest, install_problem

_VIEWPORT_WIDTH = 1280
_VIEWPORT_HEIGHT = 900


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        allocated = sock.getsockname()[1]
    if not isinstance(allocated, int):
        raise BrowserNotReady("没有拿到空闲端口。")
    return allocated


class Runtime:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._proc: asyncio.subprocess.Process | None = None
        self._port = 0
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._drains: list[asyncio.Task[None]] = []
        self._tail = bytearray()

    async def open_page(self) -> PageDriver:
        browser = await self._ensure()
        try:
            context = await browser.new_context(viewport={"width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT})
            page = await context.new_page()
        except PlaywrightError as exc:
            raise BrowserNotReady(f"没能打开新的浏览器页面：{exc}") from exc
        return PlaywrightPage(page)

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _ensure(self) -> Browser:
        async with self._lock:
            if self._alive():
                browser = self._browser
                if browser is not None:
                    return browser
            await self._stop_locked()
            problem = install_problem()
            if problem:
                raise BrowserNotReady(problem)
            info = read_manifest()
            if info is None:
                raise BrowserNotReady("还没安装浏览器。请主人在插件配置里点「下载并安装」。")
            binary = Path(info["path"])
            port = _free_port()
            engine = get_engine(info["engine"])
            stealth = info["variant"] == "stealth"
            try:
                asset = engine.resolve(sys.platform, platform.machine(), stealth)
            except RuntimeError as exc:
                raise BrowserNotReady(str(exc)) from exc
            proxy = resolve_proxy()
            proc = await _spawn(binary, port, engine, asset, stealth, proxy=proxy)
            self._proc = proc
            self._port = port
            self._remember_streams(proc)
            await self._wait_ready(proc, port)
            playwright = await async_playwright().start()
            try:
                browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            except PlaywrightError as exc:
                await playwright.stop()
                await self._stop_process()
                raise BrowserNotReady(f"连不上浏览器：{exc}") from exc
            self._playwright = playwright
            self._browser = browser
            proxy_hint = f"，代理 {proxy}" if proxy else ""
            logger.info(f"[GsBrowserUse] 已在 127.0.0.1:{port} 启动，引擎 {engine.engine_id}{proxy_hint}")
            return browser

    def _alive(self) -> bool:
        if self._proc is None or self._proc.returncode is not None:
            return False
        if self._browser is None:
            return False
        return self._browser.is_connected()

    def _remember_streams(self, proc: asyncio.subprocess.Process) -> None:
        if proc.stdout is not None:
            self._drains.append(asyncio.create_task(self._drain(proc.stdout)))
        if proc.stderr is not None:
            self._drains.append(asyncio.create_task(self._drain(proc.stderr)))

    async def _drain(self, stream: asyncio.StreamReader) -> None:
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                return
            self._tail.extend(chunk)
            if len(self._tail) > 4000:
                del self._tail[:-4000]

    async def _wait_ready(self, proc: asyncio.subprocess.Process, port: int) -> None:
        url = f"http://127.0.0.1:{port}/json/version"
        deadline = asyncio.get_running_loop().time() + 20
        async with httpx.AsyncClient(trust_env=False) as client:
            while asyncio.get_running_loop().time() < deadline:
                if proc.returncode is not None:
                    raise BrowserNotReady(self._exit_message(proc.returncode))
                try:
                    resp = await client.get(url, timeout=1.0)
                except httpx.HTTPError:
                    await asyncio.sleep(0.2)
                    continue
                if resp.status_code == 200:
                    return
                await asyncio.sleep(0.2)
        raise BrowserNotReady(self._exit_message(None))

    def _exit_message(self, code: int | None) -> str:
        tail = self._tail.decode("utf-8", errors="replace").strip()
        if code is None:
            head = "浏览器没有在时限内打开调试端口。"
        else:
            head = f"浏览器进程已退出（{code}）。"
        if not tail:
            return head
        return f"{head}\n{tail[-800:]}"

    async def _stop_locked(self) -> None:
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        if browser is not None:
            try:
                await browser.close()
            except PlaywrightError:
                pass
        if playwright is not None:
            await playwright.stop()
        await self._stop_process()
        drains = list(self._drains)
        self._drains.clear()
        for task in drains:
            task.cancel()
        if drains:
            await asyncio.wait(drains)
        self._tail.clear()

    async def _stop_process(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.returncode is not None:
            return
        if sys.platform == "win32":
            proc.terminate()
        else:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            proc.kill()
            await proc.wait()


async def _spawn(
    binary: Path,
    port: int,
    engine: BrowserEngine,
    asset: Asset,
    stealth: bool,
    proxy: str = "",
) -> asyncio.subprocess.Process:
    worker_ready = asset.worker is None or (binary.parent / asset.worker).is_file()
    if binary.name != asset.program or not worker_ready:
        raise BrowserNotReady("安装目录里缺少浏览器程序，请重新下载。")
    cmd = engine.serve_args(
        binary,
        port,
        stealth=stealth,
        private_network=flag_bool("allow_private_network", False),
        fonts=font_dir(),
        proxy=proxy,
    )
    if sys.platform == "win32":
        # 0x08000000 = CREATE_NO_WINDOW，避免弹出黑色控制台。
        return await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(binary.parent),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=0x08000000,
        )
    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(binary.parent),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
