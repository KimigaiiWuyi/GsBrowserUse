"""代理配置与检测。支持自定义代理及自动读取本地代理环境（环境变量、Windows 注册表等）。"""

from __future__ import annotations

import os
import sys
import socket
import urllib.request
from urllib.parse import urlparse


def normalize_proxy(url: str) -> str:
    """规范化代理地址，自动补全协议前缀。"""
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        return f"http://{url}"
    return url


def parse_proxy_server(server: str) -> str:
    """解析 Windows 注册表中的 ProxyServer 字段。

    可能为单个地址 '127.0.0.1:7890' 或复合形式 'http=127.0.0.1:7890;https=127.0.0.1:7890'。
    """
    server = server.strip()
    if not server:
        return ""
    if ";" in server or "=" in server:
        pairs = dict(item.split("=", 1) for item in server.split(";") if "=" in item)
        for proto in ("http", "https", "all", "socks"):
            if proto in pairs:
                return normalize_proxy(pairs[proto])
    return normalize_proxy(server)


def is_local_proxy_alive(proxy_url: str, timeout: float = 0.1) -> bool:
    """探测本机代理端口是否处于监听状态，避免挂起到失效端口。"""
    try:
        p = urlparse(proxy_url)
        host = p.hostname or "127.0.0.1"
        if host in ("127.0.0.1", "localhost", "::1"):
            port = p.port or 80
            with socket.create_connection((host, port), timeout=timeout):
                return True
    except OSError:
        pass
    return False


def detect_system_proxy() -> str:
    """自动检测操作系统与环境中的代理。"""
    # 1. 常见标准环境变量
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
        val = os.environ.get(key, "").strip()
        if val:
            return normalize_proxy(val)

    # 2. urllib 标准库检测
    try:
        proxies = urllib.request.getproxies()
        for proto in ("https", "http", "all"):
            if proto in proxies and proxies[proto]:
                return normalize_proxy(proxies[proto])
    except Exception:
        pass

    # 3. Windows 平台注册表检测
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:
                try:
                    enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                except FileNotFoundError:
                    enabled = 0
                try:
                    server, _ = winreg.QueryValueEx(key, "ProxyServer")
                except FileNotFoundError:
                    server = ""
                parsed = parse_proxy_server(server)
                if parsed:
                    # 如果系统代理处于启用状态，直接返回
                    if enabled:
                        return parsed
                    # 如果处于关闭状态但本地代理端口处于存活状态，作为 fallback 采用
                    if is_local_proxy_alive(parsed):
                        return parsed
        except Exception:
            pass

    return ""


def resolve_proxy() -> str:
    """综合配置项与环境自动解析最终使用的代理地址。"""
    from .config import proxy_setting, auto_detect_proxy_enabled

    custom = proxy_setting()
    if custom:
        return normalize_proxy(custom)
    if auto_detect_proxy_enabled():
        return detect_system_proxy()
    return ""
