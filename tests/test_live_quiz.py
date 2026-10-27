"""用本机浏览器走完测验页。默认不跑，避免测试去下载浏览器。"""

from __future__ import annotations

import os
import asyncio

import pytest
from quiz_walk import walk_until

from GsBrowserUse.gsbrowseruse_agent.hooks import sync_install_button
from gsuid_core.utils.plugins_config.models import GsButtonConfig
from GsBrowserUse.gsbrowseruse_config.config import CONFIG
from GsBrowserUse.gsbrowseruse_browser.service import get_pool, shutdown_pool
from GsBrowserUse.gsbrowseruse_install.install import install_browser
from GsBrowserUse.gsbrowseruse_install.manifest import install_problem
from gsuid_core.utils.plugins_config.button_action import ButtonReport

_URL = "https://aa54c359f30164d67.app.workbuddy.host/"
_NEEDLE = "灵魂重合度"

pytestmark = pytest.mark.skipif(
    os.environ.get("GSUID_OBSCURA_LIVE") != "1", reason="设置 GSUID_OBSCURA_LIVE=1 才连真浏览器"
)


def test_quiz_page_shows_the_result() -> None:
    asyncio.run(_walk())


async def _walk() -> None:
    if install_problem():
        await install_browser(ButtonReport(CONFIG, "install"))
    sync_install_button()
    stored = CONFIG.get_config("install")
    assert isinstance(stored, GsButtonConfig)
    assert stored.data.phase == "success"
    pool = get_pool()
    try:
        text = await walk_until(pool, "live", _URL, _NEEDLE)
    finally:
        await shutdown_pool()
    assert _NEEDLE in text
