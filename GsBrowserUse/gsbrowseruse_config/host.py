"""当前机器的系统和架构。安装包按这个选择。"""

from __future__ import annotations

import sys
import platform


def system_token(system: str) -> str:
    folded = system.lower()
    if folded.startswith("win"):
        return "windows"
    if folded in {"darwin", "macos"}:
        return "macos"
    if folded == "linux":
        return "linux"
    raise RuntimeError(f"不支持的系统：{system}")


def machine_token(machine: str) -> str:
    folded = machine.lower()
    if folded in {"amd64", "x86_64", "x64"}:
        return "x86_64"
    if folded in {"arm64", "aarch64"}:
        return "aarch64"
    raise RuntimeError(f"不支持的 CPU：{machine}")


def platform_label(system: str, machine: str) -> str:
    return f"{system_token(system)}-{machine_token(machine)}"


def host_label() -> str:
    return platform_label(sys.platform, platform.machine())
