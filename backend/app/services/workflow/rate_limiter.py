"""基于 Redis 的令牌桶限流器"""
import time
from typing import Optional


# Lua 脚本：原子性令牌获取
_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 120)
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 120)
    return 0
end
"""


class WorkflowRateLimiter:
    """令牌桶限流器 — 粒度: tenant_id + flow_code"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self._script_sha: Optional[str] = None

    async def acquire(self, tenant_id: int, flow_code: str,
                      max_tokens: int = 10, refill_rate: float = 0.167) -> bool:
        """尝试获取令牌。返回 True 表示允许，False 表示限流。"""
        key = f"wf:rl:{tenant_id}:{flow_code}"
        now = time.time()

        try:
            result = await self.redis.eval(
                _TOKEN_BUCKET_SCRIPT, 1, key,
                str(max_tokens), str(refill_rate), str(now)
            )
            return bool(result)
        except Exception:
            # Redis 不可用时降级为放行
            return True
