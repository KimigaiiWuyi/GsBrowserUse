"""代理配置与检测测试。"""

from __future__ import annotations

import pytest

from GsBrowserUse.gsbrowseruse_config.proxy import (
    resolve_proxy,
    normalize_proxy,
    parse_proxy_server,
    detect_system_proxy,
    is_local_proxy_alive,
)


def test_normalize_proxy() -> None:
    assert normalize_proxy("") == ""
    assert normalize_proxy("   ") == ""
    assert normalize_proxy("127.0.0.1:7890") == "http://127.0.0.1:7890"
    assert normalize_proxy("http://127.0.0.1:7890") == "http://127.0.0.1:7890"
    assert normalize_proxy("socks5://127.0.0.1:7890") == "socks5://127.0.0.1:7890"
    assert normalize_proxy("https://my-proxy:8080") == "https://my-proxy:8080"


def test_parse_proxy_server() -> None:
    assert parse_proxy_server("") == ""
    assert parse_proxy_server("127.0.0.1:7890") == "http://127.0.0.1:7890"
    assert parse_proxy_server("http=127.0.0.1:7890;https=127.0.0.1:7891") == "http://127.0.0.1:7890"
    assert parse_proxy_server("socks=127.0.0.1:1080") == "http://127.0.0.1:1080"


def test_is_local_proxy_alive_rejects_remote() -> None:
    # 远程主机直接返回 False，不产生网络开销
    assert not is_local_proxy_alive("http://example.com:8080")


def test_detect_system_proxy_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.test:8888")
    assert detect_system_proxy() == "http://proxy.test:8888"


def test_resolve_proxy_prefers_custom_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("GsBrowserUse.gsbrowseruse_config.config.proxy_setting", lambda: "socks5://127.0.0.1:10808")
    monkeypatch.setattr("GsBrowserUse.gsbrowseruse_config.config.auto_detect_proxy_enabled", lambda: True)
    assert resolve_proxy() == "socks5://127.0.0.1:10808"


def test_resolve_proxy_respects_auto_detect_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("GsBrowserUse.gsbrowseruse_config.config.proxy_setting", lambda: "")
    monkeypatch.setattr("GsBrowserUse.gsbrowseruse_config.config.auto_detect_proxy_enabled", lambda: False)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.test:8888")
    assert resolve_proxy() == ""
