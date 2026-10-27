"""按快照里的 e 编号往下走。和代理该做的步骤一样。"""

from __future__ import annotations

from GsBrowserUse.gsbrowseruse_browser.pool import SessionPool
from GsBrowserUse.gsbrowseruse_browser.actions import click, open_url
from GsBrowserUse.gsbrowseruse_browser.snapshot import SNAPSHOT_MARK


def ref_starting(snapshot: str, prefix: str) -> str:
    if SNAPSHOT_MARK not in snapshot:
        raise AssertionError(snapshot)
    tail = snapshot.rsplit(SNAPSHOT_MARK, 1)[1]
    for line in tail.splitlines():
        piece = line.strip()
        if not piece:
            continue
        parts = piece.split(" ", 2)
        if len(parts) < 3:
            continue
        ref, _kind, name = parts
        if name.startswith(prefix):
            return ref
    raise AssertionError(prefix + "\n" + snapshot)


async def walk_until(pool: SessionPool, key: str, url: str, needle: str) -> str:
    text = await open_url(pool, key, url)
    text = await click(pool, key, ref_starting(text, "开始"))
    for _ in range(45):
        if needle in text:
            return text
        text = await click(pool, key, ref_starting(text, "A"))
    return text
