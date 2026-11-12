"""Notices —— 4 类通知原语（Task 7.5）。

result_relay / followup_relay / coalescing_notice / receipt_notice。
统一经 sse_bus.sse_publish 投递（局部 import 防循环依赖），
Feishu 等真实通道由 OutboxService 接管，首期全部走 SSE Feed。
"""
from __future__ import annotations

from loguru import logger

# coalescing_notice 模块级缓存 —— 同 name 覆盖等待中的旧 notice
_PENDING_NOTICES: dict[str, dict] = {}


async def _publish(event: str, data: dict) -> None:
    """SSE 投递（局部 import 防循环），失败只 warning 不抛。"""
    try:
        from .sse_bus import sse_publish
        await sse_publish(event, data)
    except Exception as e:
        logger.warning(f"notices · publish failed · event={event}: {e}")


async def result_relay(ticket_id: str, message: str, channel: str = "sse") -> None:
    """Worker 提问 / 结果立即转发到 Channel。"""
    logger.info(
        f"notices.result_relay · ticket={ticket_id} · channel={channel} · "
        f"len={len(message or '')}"
    )
    await _publish("notice_result_relay", {
        "ticket_id": ticket_id, "message": message, "channel": channel,
    })


async def followup_relay(ticket_id: str, channel: str = "sse") -> None:
    """到期后通知有人类跟进的 Ticket。"""
    logger.info(f"notices.followup_relay · ticket={ticket_id} · channel={channel}")
    await _publish("notice_followup_relay", {
        "ticket_id": ticket_id, "channel": channel,
        "message": f"⏰ Ticket {ticket_id} 等待人类跟进",
    })


async def coalescing_notice(name: str, payload: dict) -> bool:
    """同 name payload 覆盖等待中的旧 notice（避免重复通知刷屏）。

    Returns:
        True = 覆盖了同名等待中的旧 notice；False = 全新 notice。
    """
    overrode = name in _PENDING_NOTICES
    _PENDING_NOTICES[name] = dict(payload or {})
    logger.info(f"notices.coalescing_notice · name={name} · overrode={overrode}")
    await _publish("notice_coalescing", {"name": name, "overrode": overrode, **(payload or {})})
    return overrode


async def receipt_notice(ticket_id: str, message_id: str) -> None:
    """送达回执（确认某人已读）。"""
    logger.info(f"notices.receipt_notice · ticket={ticket_id} · message_id={message_id}")
    await _publish("notice_receipt", {"ticket_id": ticket_id, "message_id": message_id})
