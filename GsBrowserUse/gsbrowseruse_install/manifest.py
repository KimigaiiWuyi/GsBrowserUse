"""安装结果写在 install.json。浏览器进程只认这份清单里的程序路径。"""

from __future__ import annotations

import json
from typing import TypedDict
from pathlib import Path

from gsuid_core.data_store import get_res_path

from .engines import engine_label, variant_label
from ..gsbrowseruse_config.host import host_label
from ..gsbrowseruse_config.config import ROOT, desired_engine, desired_variant

MANIFEST_PATH = ROOT / "install.json"
BIN_DIR = ROOT / "bin"
_OLD_MANIFEST = get_res_path() / "ObscuraBrowser" / "install.json"


class InstallInfo(TypedDict):
    engine: str
    version: str
    path: str
    platform: str
    variant: str
    installed_at: str


_KEYS = ("version", "path", "platform", "variant", "installed_at")


def read_manifest() -> InstallInfo | None:
    for path in _manifest_files():
        info = _read_one(path)
        if info is not None:
            return info
    return None


def write_manifest(info: InstallInfo) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def status_fields(info: InstallInfo) -> dict[str, str]:
    return {
        "host": host_label(),
        "engine": engine_label(info["engine"]),
        "version": info["version"],
        "path": info["path"],
        "platform": info["platform"],
        "variant": variant_label(info["variant"]),
        "installed_at": info["installed_at"],
    }


def install_problem() -> str:
    info = read_manifest()
    if info is None:
        return "还没安装浏览器。请主人在插件配置里点「下载并安装」。"
    if info["engine"] not in {"obscura", "lightpanda"}:
        return "已安装的引擎无法识别。请再点一次下载。"
    if info["engine"] != desired_engine():
        return "已安装的引擎和「浏览器引擎」不一致。请再点一次下载。"
    if info["platform"] != host_label():
        return f"安装包对应 {info['platform']}，当前环境是 {host_label()}。请再点一次下载。"
    if info["engine"] == "obscura" and info["variant"] != desired_variant():
        return "已安装的浏览器和「隐身模式」不一致。请在插件配置里再点一次下载。"
    return ""


def _manifest_files() -> list[Path]:
    files: list[Path] = []
    if MANIFEST_PATH.is_file():
        files.append(MANIFEST_PATH)
    if _OLD_MANIFEST.is_file() and _OLD_MANIFEST != MANIFEST_PATH:
        files.append(_OLD_MANIFEST)
    return files


def _read_one(path: Path) -> InstallInfo | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    engine = "obscura"
    if "engine" in raw:
        stored = raw["engine"]
        if not isinstance(stored, str) or not stored:
            return None
        engine = stored
    info: InstallInfo = {
        "engine": engine,
        "version": "",
        "path": "",
        "platform": "",
        "variant": "",
        "installed_at": "",
    }
    for key in _KEYS:
        if key not in raw or not isinstance(raw[key], str) or not raw[key]:
            return None
        info[key] = raw[key]
    if not Path(info["path"]).is_file():
        return None
    return info
