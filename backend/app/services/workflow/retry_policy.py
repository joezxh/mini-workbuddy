"""指数退避重试策略"""
import asyncio
import random
from typing import Set

import httpx
from loguru import logger


# 可重试的 HTTP 状态码
RETRIABLE_STATUS_CODES: Set[int] = {429, 502, 503, 504}


class RetriableError(Exception):
    """可重试错误"""
    pass


class NonRetriableError(Exception):
    """不可重试错误"""
    pass


class RetryPolicy:
    """指数退避重试策略"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 30.0, jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def _calc_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    @staticmethod
    def is_retriable(error: Exception) -> bool:
        if isinstance(error, RetriableError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in RETRIABLE_STATUS_CODES
        if isinstance(error, (httpx.ConnectTimeout, httpx.ReadTimeout)):
            return True
        return False

    async def execute_with_retry(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == self.max_retries or not self.is_retriable(e):
                    raise
                delay = self._calc_delay(attempt)
                logger.warning(f"重试 {attempt + 1}/{self.max_retries}，延迟 {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        raise last_error
