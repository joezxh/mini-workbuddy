"""AI Team 错误渲染工具。

把团队运行中抛出的异常统一转换为**面向用户/落库**的简短中文文案，供端点层写入
运行记录（``mark_failed``）、事件流（``emit_team_error``）与 HTTP 响应。

设计约束：
1. 绝不抛异常——渲染发生在 ``except`` 分支中，二次抛错会掩盖真实故障；
2. 绝不返回空串——落库与前端展示都依赖可读文案，兜底退回异常类型名；
3. 业务性异常（参数/校验类）直接使用异常自带文案，技术性异常附加类型名便于排障。
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

#: 展示文案最大长度（防御性截断，避免超长堆栈文本撑爆事件负载 / HTTP 响应）
_MAX_MESSAGE_LENGTH = 2000

#: 业务性异常：自带文案已足够人类可读，不再附加类型名
_BUSINESS_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    NotImplementedError,
)


def render_team_error(
    exc: BaseException,
    *,
    max_length: int = _MAX_MESSAGE_LENGTH,
) -> str:
    """将异常渲染为可展示的错误文案。

    Args:
        exc: 捕获到的异常（含 ``BaseException``，如 ``CancelledError``）。
        max_length: 文案最大长度，超出部分做截断（``<=0`` 表示不截断）。

    Returns:
        str: 非空的错误描述文案。
    """
    try:
        if isinstance(exc, asyncio.CancelledError):
            return "运行已被取消"

        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            detail = str(exc).strip()
            return _truncate(f"执行超时: {detail}", max_length) if detail else "执行超时"

        # FastAPI HTTPException：优先返回其业务语义的 detail
        detail = getattr(exc, "detail", None)
        status_code = getattr(exc, "status_code", None)
        if detail is not None and status_code is not None:
            return _truncate(str(detail), max_length)

        message = str(exc).strip()
        if not message:
            return type(exc).__name__

        if isinstance(exc, _BUSINESS_EXCEPTIONS):
            return _truncate(message, max_length)

        return _truncate(f"{type(exc).__name__}: {message}", max_length)
    except Exception:  # noqa: BLE001  渲染失败绝不能掩盖原始异常
        logger.warning("渲染团队错误文案失败: %r", exc)
        return type(exc).__name__ or "团队运行失败"


def _truncate(text: str, max_length: int) -> str:
    """超长文案截断，保证落库与传输可控。"""
    if max_length <= 0 or len(text) <= max_length:
        return text
    return text[:max_length] + "…（已截断）"


__all__ = ["render_team_error"]
