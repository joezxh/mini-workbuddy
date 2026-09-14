"""重连退避与错误分类（差距分析 §3.4 重连）。

ReconnectBackoff: 指数退避（封顶）+ 最大重试次数。
classify_error: 将异常映射为 ErrorCode，用于决定降级/重试策略。
"""
import asyncio
from typing import Optional

from app.config import settings
from app.duplex.voice.constants import ErrorCode


class ReconnectBackoff:
    """指数退避计算器（不持有网络状态）。"""

    def __init__(
        self,
        base: float = 0.5,
        factor: float = 2.0,
        cap: float = 8.0,
        max_attempts: Optional[int] = None,
    ):
        self._base = base
        self._factor = factor
        self._cap = cap
        self._max = max_attempts if max_attempts is not None else settings.VOICE_RECONNECT_MAX
        self._attempt = 0

    def reset(self) -> None:
        self._attempt = 0

    def next_delay(self) -> float:
        """返回下一次重连延迟（秒），并推进计数。"""
        delay = min(self._base * (self._factor ** self._attempt), self._cap)
        self._attempt += 1
        return delay

    def should_retry(self) -> bool:
        return self._attempt < self._max

    @property
    def attempt(self) -> int:
        return self._attempt


def classify_error(error: BaseException) -> ErrorCode:
    """将异常归并为 ErrorCode，用于降级决策。"""
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return ErrorCode.FATAL
    if isinstance(error, (ConnectionError, OSError)):
        return ErrorCode.PROVIDER_UNAVAILABLE
    if isinstance(error, ValueError):
        return ErrorCode.OTHER
    return ErrorCode.OTHER
