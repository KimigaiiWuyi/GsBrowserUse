"""进程里的那一个页面池。测试可以自己 new SessionPool，不走这里。"""

from __future__ import annotations

from .pool import SessionPool
from ..gsbrowseruse_config.config import idle_limit, max_contexts

_pool: SessionPool | None = None


def get_pool() -> SessionPool:
    global _pool
    if _pool is None:
        from .runtime import Runtime

        _pool = SessionPool(Runtime(), max_live=max_contexts, idle_seconds=idle_limit)
    return _pool


async def close_if_started() -> None:
    pool = _pool
    if pool is not None:
        await pool.shutdown()


async def shutdown_pool() -> None:
    global _pool
    pool = _pool
    _pool = None
    if pool is not None:
        await pool.shutdown()
