"""TransientRetryPolicy —— 网络/基础设施瞬态错误自动重试 ×3 + 指数退避。

对齐 dsh-superagent transient.ts + dsh executor.ts。
"""
from __future__ import annotations
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import random
import asyncio

from loguru import logger

# 可注入的 sleep（测试注入 0 延迟，避免真实等待）
SleepFn = Callable[[float], Awaitable[None]]


# Transient 错误码表（对齐 dsh-superagent executor.ts）
TRANSIENT_ERRNOS = {"ECONNRESET", "ECONNREFUSED", "ETIMEDOUT", "EAI_AGAIN"}
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 15.0  # 秒
    max_delay: float = 120.0


class TransientRetryPolicy:
    """Transient retry policy —— 配置 + 判断。"""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    def is_transient(self, exc: BaseException) -> bool:
        return is_transient_error(exc)


def is_transient_error(exc: BaseException) -> bool:
    """判断是否为 Transient 错误。"""
    # HTTP 状态码
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in TRANSIENT_HTTP:
        return True
    # errno（OSError / ConnectionError）
    errno = getattr(exc, "errno", None)
    if isinstance(errno, str) and errno in TRANSIENT_ERRNOS:
        return True
    # 常见连接错误类名匹配
    name = type(exc).__name__
    if any(k in name for k in (
        "Timeout", "ConnectionReset", "ConnectionRefused",
        "ConnectionError", "OSError",
    )):
        return True
    return False


async def retry_with_backoff(coro, config: RetryConfig | None = None,
                             sleep: SleepFn | None = None):
    """异步重试 —— Transient 错误自动退避重试（15s→30s→60s，max ×3）。

    sleep 参数允许注入（测试传立即返回的 sleep 以避免真实等待）。
    """
    cfg = config or RetryConfig()
    _sleep: SleepFn = sleep or asyncio.sleep
    last_exc: BaseException | None = None
    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await coro()
        except BaseException as e:
            last_exc = e
            if not is_transient_error(e) or attempt >= cfg.max_attempts:
                raise
            delay = min(
                cfg.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 5),
                cfg.max_delay,
            )
            logger.warning(
                f"[TransientRetry] attempt {attempt}/{cfg.max_attempts} · "
                f"{type(e).__name__} · retry in {delay:.1f}s"
            )
            await _sleep(delay)
    assert last_exc is not None
    raise last_exc
