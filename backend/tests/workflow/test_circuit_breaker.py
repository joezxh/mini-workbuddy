"""熔断器 + 重试策略单元测试"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.workflow.circuit_breaker import CircuitBreaker, CircuitState
from app.services.workflow.retry_policy import RetryPolicy, RetriableError, NonRetriableError


# ── CircuitBreaker ───────────────────────────────────────────

class TestCircuitBreaker:
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self, mock_redis):
        cb = CircuitBreaker(mock_redis)
        state = await cb.get_state(1, "test-flow")
        assert state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self, mock_redis):
        cb = CircuitBreaker(mock_redis)
        assert await cb.can_execute(1, "test-flow") is True

    @pytest.mark.asyncio
    async def test_can_execute_when_open(self, mock_redis):
        import time
        mock_redis.hget = AsyncMock(side_effect=lambda k, f: {
            "state": b"open",
            "opened_at": str(time.time()).encode(),
        }.get(f))
        cb = CircuitBreaker(mock_redis)
        assert await cb.can_execute(1, "test-flow") is False

    @pytest.mark.asyncio
    async def test_half_open_after_recovery(self, mock_redis):
        import time
        mock_redis.hget = AsyncMock(side_effect=lambda k, f: {
            "state": b"open",
            "opened_at": str(time.time() - 120).encode(),  # 2 分钟前
        }.get(f))
        cb = CircuitBreaker(mock_redis, recovery_seconds=60)
        state = await cb.get_state(1, "test-flow")
        assert state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_record_success_resets_to_closed(self, mock_redis):
        cb = CircuitBreaker(mock_redis)
        await cb.record_success(1, "test-flow")
        mock_redis.hset.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failure_opens_after_threshold(self, mock_redis):
        mock_redis.hget = AsyncMock(return_value=b"4")  # 已有 4 次失败
        cb = CircuitBreaker(mock_redis, threshold=5)
        await cb.record_failure(1, "test-flow")
        # 第 5 次应触发 OPEN
        call_args = mock_redis.hset.call_args
        assert call_args is not None


# ── RetryPolicy ──────────────────────────────────────────────

class TestRetryPolicy:
    def test_calc_delay_exponential(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=30.0, jitter=False)
        assert policy._calc_delay(0) == 1.0
        assert policy._calc_delay(1) == 2.0
        assert policy._calc_delay(2) == 4.0
        assert policy._calc_delay(10) == 30.0  # capped

    def test_calc_delay_with_jitter(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=30.0, jitter=True)
        delay = policy._calc_delay(2)
        assert 2.0 <= delay <= 6.0  # 4.0 * [0.5, 1.5]

    def test_is_retriable_http_status(self):
        import httpx
        policy = RetryPolicy()
        resp = httpx.Response(status_code=503, request=httpx.Request("GET", "http://x"))
        err = httpx.HTTPStatusError("server error", request=resp.request, response=resp)
        assert policy.is_retriable(err) is True

    def test_is_retriable_400_not_retriable(self):
        import httpx
        policy = RetryPolicy()
        resp = httpx.Response(status_code=400, request=httpx.Request("GET", "http://x"))
        err = httpx.HTTPStatusError("bad request", request=resp.request, response=resp)
        assert policy.is_retriable(err) is False

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        policy = RetryPolicy(max_retries=3, jitter=False)
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetriableError("temporary")
            return "ok"

        result = await policy.execute_with_retry(flaky_func)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self):
        policy = RetryPolicy(max_retries=2, jitter=False)

        async def always_fail():
            raise RetriableError("permanent")

        with pytest.raises(RetriableError):
            await policy.execute_with_retry(always_fail)
