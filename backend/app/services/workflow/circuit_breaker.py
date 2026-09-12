"""三态熔断器 — Redis 存储，跨进程共享"""
import time
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """三态熔断器

    规则：
    - CLOSED: 正常放行，失败次数 >= threshold → OPEN
    - OPEN: 拒绝请求，等待 recovery_seconds → HALF_OPEN
    - HALF_OPEN: 放行一个探测请求，成功 → CLOSED，失败 → OPEN
    """

    def __init__(self, redis_client, threshold: int = 5, recovery_seconds: int = 60):
        self.redis = redis_client
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds

    def _key(self, tenant_id: int, flow_code: str) -> str:
        return f"wf:cb:{tenant_id}:{flow_code}"

    async def get_state(self, tenant_id: int, flow_code: str) -> CircuitState:
        key = self._key(tenant_id, flow_code)
        state = await self.redis.hget(key, "state")
        if state is None:
            return CircuitState.CLOSED
        state = state.decode() if isinstance(state, bytes) else state

        if state == CircuitState.OPEN:
            opened_at = float(await self.redis.hget(key, "opened_at") or 0)
            if time.time() - opened_at >= self.recovery_seconds:
                await self.redis.hset(key, "state", CircuitState.HALF_OPEN)
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return CircuitState(state)

    async def can_execute(self, tenant_id: int, flow_code: str) -> bool:
        """检查是否允许执行"""
        try:
            state = await self.get_state(tenant_id, flow_code)
        except Exception:
            return True  # Redis 不可用时降级放行
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # 探测请求放行
        return False  # OPEN 状态拒绝

    async def record_success(self, tenant_id: int, flow_code: str):
        """记录成功 → 重置为 CLOSED"""
        key = self._key(tenant_id, flow_code)
        try:
            await self.redis.hset(key, mapping={
                "state": CircuitState.CLOSED,
                "failure_count": "0",
            })
        except Exception:
            pass

    async def record_failure(self, tenant_id: int, flow_code: str):
        """记录失败 → 可能触发 OPEN"""
        key = self._key(tenant_id, flow_code)
        try:
            count = int(await self.redis.hget(key, "failure_count") or 0) + 1
            if count >= self.threshold:
                await self.redis.hset(key, mapping={
                    "state": CircuitState.OPEN,
                    "failure_count": str(count),
                    "opened_at": str(time.time()),
                })
            else:
                await self.redis.hset(key, "failure_count", str(count))
        except Exception:
            pass
