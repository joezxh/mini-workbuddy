"""EventBus —— 基于 Observer 模式的事件分发（spec §4.1）。

P0 范围：LOG（结构化日志）+ DB（委托 ExecutionEventService）两级 handler。
STREAM/UI 级由调用方（SSE 生成器）自行消费，不经 bus。
handler 异常相互隔离：一个 handler 失败不影响其他 handler。
"""
from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from app.schemas.agent.event_types import EventEnvelope, EventLevel


class EventBus:
    """事件总线：publish 一次，按 levels 分发到各 handler。"""

    def __init__(self, event_service: Optional[Any] = None) -> None:
        # event_service: ExecutionEventService（DB handler 目标）
        self._event_service = event_service

    def publish(self, envelope: EventEnvelope) -> None:
        """分发单个事件信封。同步、不抛出（handler 异常吞掉并记日志）。"""
        # L0：所有事件统一 debug 日志（含被降级不落库的）
        logger.bind(
            execution_id=envelope.execution_id,
            trace_id=envelope.trace_id,
            category=envelope.category,
        ).debug("event[{}] {} levels={}", envelope.execution_id[:8],
                envelope.event_type, envelope.levels)

        # L1：DB 持久化（仅 DB 级事件；service 内部会再次校验并过滤）
        if self._event_service is not None and EventLevel.DB in envelope.levels:
            try:
                self._event_service.record_envelope(envelope)
            except Exception as e:  # noqa: BLE001 —— handler 隔离
                logger.opt(exception=True).warning(
                    "DBHandler 处理事件失败 {}: {}", envelope.event_type, e,
                )
