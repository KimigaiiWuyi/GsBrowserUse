"""下载按钮。进度写回配置，刷新页面还能看到。"""

from __future__ import annotations

import sys
import shutil
import platform
from pathlib import Path
from datetime import datetime

import httpx

from gsuid_core.utils.plugins_config.button_action import ButtonReport, register_config_button

from .archive import assert_digest, extract_archive
from .engines import Asset, get_engine
from .manifest import BIN_DIR, InstallInfo, status_fields, write_manifest
from ..gsbrowseruse_config.config import ROOT, INSTALL_ENDPOINT, desired_engine, desired_variant

_STAGING = ROOT / "staging"
_DOWNLOADS = ROOT / "download"


def _replace_tree(src: Path, dest: Path) -> None:
    backup = dest.with_name(dest.name + ".prev")
    if backup.exists():
        shutil.rmtree(backup)
    moved = False
    if dest.exists():
        dest.rename(backup)
    try:
        src.rename(dest)
        moved = True
    finally:
        if not moved and backup.exists() and not dest.exists():
            backup.rename(dest)
    if backup.exists():
        shutil.rmtree(backup)


def _chmod_programs(dest: Path, asset: Asset) -> None:
    if sys.platform == "win32":
        return
    names = [asset.program]
    if asset.worker is not None:
        names.append(asset.worker)
    for name in names:
        path = dest / name
        if path.is_file():
            path.chmod(0o755)


def _require_programs(dest: Path, asset: Asset) -> None:
    if not (dest / asset.program).is_file():
        raise RuntimeError("安装包里没有浏览器程序。")
    if asset.worker is not None and not (dest / asset.worker).is_file():
        raise RuntimeError("安装包里没有浏览器程序。")


async def _stream(url: str, dest: Path, report: ButtonReport) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(30.0, read=600.0)
    headers = {"User-Agent": "gsuid-gs-browser-use"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = 0
            if "content-length" in resp.headers and resp.headers["content-length"].isdigit():
                total = int(resp.headers["content-length"])
            got = 0
            shown = 2
            with dest.open("wb") as handle:
                async for chunk in resp.aiter_bytes(256 * 1024):
                    handle.write(chunk)
                    got += len(chunk)
                    if total > 0:
                        progress = 5 + int(got * 80 / total)
                    else:
                        progress = min(85, 5 + got // (1024 * 1024))
                    if progress != shown:
                        shown = progress
                        report.update(phase="running", progress=progress, message=f"正在下载，已完成 {progress}%。")


async def install_browser(report: ButtonReport) -> None:
    engine = get_engine(desired_engine())
    stealth = desired_variant() == "stealth"
    asset = engine.resolve(sys.platform, platform.machine(), stealth)
    report.update(phase="running", progress=2, message=f"当前环境是 {asset.platform}，正在下载 {asset.name}。")
    archive = _DOWNLOADS / asset.name
    await _stream(asset.url, archive, report)
    report.update(phase="running", progress=88, message="正在校验安装包。")
    assert_digest(archive, asset.digest)
    if _STAGING.exists():
        shutil.rmtree(_STAGING)
    if asset.packed:
        report.update(phase="running", progress=93, message="正在解压。")
        extract_archive(archive, _STAGING)
    else:
        report.update(phase="running", progress=93, message="正在放置程序。")
        _STAGING.mkdir(parents=True)
        archive.replace(_STAGING / asset.program)
    _require_programs(_STAGING, asset)
    _chmod_programs(_STAGING, asset)
    # Windows 上正在运行的程序不能覆盖，所以先停进程再换目录。
    from ..gsbrowseruse_browser.service import close_if_started

    await close_if_started()
    report.update(phase="running", progress=97, message="正在安装。")
    _replace_tree(_STAGING, BIN_DIR)
    if archive.exists():
        archive.unlink()
    installed_at = datetime.now().isoformat(timespec="seconds")
    variant = "stealth" if asset.engine_id == "obscura" and stealth else "render"
    info: InstallInfo = {
        "engine": asset.engine_id,
        "version": asset.version,
        "path": str(BIN_DIR / asset.program),
        "platform": asset.platform,
        "variant": variant,
        "installed_at": installed_at,
    }
    write_manifest(info)
    report.update(phase="success", progress=100, message="已安装", fields=status_fields(info))


register_config_button(INSTALL_ENDPOINT, install_browser)
