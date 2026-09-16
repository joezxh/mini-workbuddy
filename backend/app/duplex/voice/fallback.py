"""语音降级策略。

降级决策树：
1. Provider 不可用 → 尝试备用 Provider（ProviderRegistry.resolve_backup）
2. 无备用 → 降级为文字模式（input_mode="text"）
3. 麦克风不可用 → 直接文字模式
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, List, Optional

from loguru import logger

from app.duplex.voice.constants import ErrorCode
from app.duplex.voice.reconnect_backoff import ReconnectBackoff, classify_error


class VoiceFallback:
    """语音降级策略。

    两种用法：
    1) 实例用法 `with_fallback`：Provider 链降级（主 → 备用 → 文字模式）。
    2) 静态用法 `try_fallback`：基于 EngineRequest 的既有降级（M1 沿用）。
    """

    def __init__(
        self,
        providers: Optional[List[Any]] = None,
        max_text_mode: bool = True,
    ):
        self.providers = providers or []
        self.backoff = ReconnectBackoff()
        self.max_text_mode = max_text_mode

    async def with_fallback(
        self,
        primary: Any,
        action: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """在主 Provider 上执行 action，失败则沿备用链降级。

        - Provider 不可用类错误 → 依次尝试备用 Provider
        - 全部失败（或非 Provider 错误）→ 降级为文字模式（max_text_mode）
        """
        try:
            return await action(primary)
        except Exception as e:  # noqa: BLE001 - 降级需捕获全部异常
            code = classify_error(e)
            if code == ErrorCode.PROVIDER_UNAVAILABLE:
                for alt in self.providers[1:]:
                    try:
                        return await action(alt)
                    except Exception:  # noqa: BLE001 - 继续尝试下一个备用
                        continue
                self.backoff.next_delay()
            if self.max_text_mode:
                logger.warning(f"VoiceFallback: 降级为文字模式: {e}")
                return {"type": "text_only", "message": "语音服务暂不可用，已切换文字模式"}
            raise

    @staticmethod
    def try_fallback(
        request,
        error: Exception,
        available_providers: Optional[list[str]] = None,
    ):
        """尝试降级。

        Args:
            request: EngineRequest
            error: 触发的异常
            available_providers: 当前可用 Provider 列表

        Returns:
            修改后的 request（降级后 input_mode 或 provider 已变更）
        """
        error_msg = str(error).lower()
        current_provider = request.context.get("provider", "dashscope")

        # 1. Provider 相关错误 → 尝试备用
        if any(kw in error_msg for kw in ("provider", "connection", "websocket")):
            backup = _find_backup(current_provider, available_providers or [])
            if backup:
                request.context["provider"] = backup
                logger.info(
                    f"VoiceFallback: 切换 Provider "
                    f"{current_provider} → {backup}"
                )
                return request

        # 2. 无法恢复 → 降级为文字模式
        logger.warning(f"VoiceFallback: 语音降级为文字模式: {error}")
        request.context["input_mode"] = "text"
        request.context["fallback_reason"] = str(error)
        return request


def _find_backup(current: str, available: list[str]) -> Optional[str]:
    """从可用列表中找非 current 的备用 Provider。"""
    for provider in available:
        if provider != current:
            return provider
    return None
