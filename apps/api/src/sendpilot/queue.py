"""Arq queue access for enqueuing jobs from the API/handlers."""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from .config import settings

_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(name: str, *args: Any, **kwargs: Any):
    pool = await get_pool()
    return await pool.enqueue_job(name, *args, **kwargs)
