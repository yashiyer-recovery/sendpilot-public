"""Shared Redis client + short-lived OAuth state storage (PKCE)."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis, from_url

from .config import settings

_redis: Redis | None = None

OAUTH_STATE_TTL = 600  # seconds


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis


async def put_oauth_state(state: str, data: dict[str, Any]) -> None:
    await get_redis().set(f"oauth:state:{state}", json.dumps(data), ex=OAUTH_STATE_TTL)


async def pop_oauth_state(state: str) -> dict[str, Any] | None:
    r = get_redis()
    key = f"oauth:state:{state}"
    val = await r.get(key)
    if val is None:
        return None
    await r.delete(key)
    return json.loads(val)
