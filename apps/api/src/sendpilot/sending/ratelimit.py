"""Per-account rate limiting + daily cap (PRD §11.6).

An atomic Redis Lua token bucket so concurrent workers never exceed the limit.
``time.time()`` here is real runtime wall-clock (worker process), not a workflow
script — it's the intended source for the bucket timestamp.
"""

from __future__ import annotations

import datetime as dt
import time

from ..cache import get_redis

TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local rate     = tonumber(ARGV[1])   -- tokens per second
local capacity = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])
local b        = redis.call('HMGET', key, 'tokens', 'ts')
local tokens   = tonumber(b[1]) or capacity
local ts       = tonumber(b[2]) or now
tokens = math.min(capacity, tokens + (now - ts) * rate)
local allowed = tokens >= 1
if allowed then tokens = tokens - 1 end
redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, 3600)
return allowed and 1 or 0
"""


async def allow_send(account_id: str, rate_per_min: int) -> bool:
    r = get_redis()
    res = await r.eval(
        TOKEN_BUCKET_LUA, 1, f"rl:{account_id}",
        rate_per_min / 60.0, max(1, rate_per_min), time.time(),
    )
    return bool(res)


async def under_daily_cap(account_id: str, cap: int) -> bool:
    r = get_redis()
    key = f"cap:{account_id}:{dt.date.today().isoformat()}"
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, 172_800)
    return n <= cap
