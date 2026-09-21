"""执行主记录（agent_execution 表）写入 —— 替换原 pass 存根。

所有函数吞异常（记录 warning）：主记录失败不应中断 SSE 执行流。
超时路径：status=cancelled + finished_reason=interrupted + interrupt_reason=timeout。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def record_execution_start(
    db: Any,
    *,
    execution_id: str,
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
    execution_mode: str = "skill",
    target_id: Optional[str] = None,
    user_input: Optional[str] = None,
    metadata: Optional[dict] = None,
    trace_id: Optional[str] = None,
) -> None:
    """写入执行主记录（status=running）。"""
    from app.models.agent.agent_execution import AgentExecution

    try:
        db.add(AgentExecution(
            execution_id=execution_id,
            session_id=session_id,
            user_id=user_id,
            execution_mode=execution_mode,
            target_id=str(target_id) if target_id is not None else None,
            status="running",
            user_input=user_input,
            trace_id=trace_id,
            started_at=datetime.now(),
            metadata_json=metadata,
        ))
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_start 失败 %s: %s", execution_id, e)


def _get_row(db: Any, execution_id: str):
    from app.models.agent.agent_execution import AgentExecution
    return (
        db.query(AgentExecution)
        .filter(AgentExecution.execution_id == execution_id)
        .first()
    )


def record_execution_done(
    db: Any,
    execution_id: str,
    output: Optional[str] = None,
    latency_ms: Optional[int] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    iterations: Optional[int] = None,
) -> None:
    """标记完成并回填输出/用量。"""
    try:
        row = _get_row(db, execution_id)
        if row is None:
            logger.warning("record_execution_done：执行记录不存在 %s", execution_id)
            return
        row.status = "completed"
        row.finished_reason = "completed"
        row.output = output
        row.completed_at = datetime.now()
        if latency_ms is not None:
            row.latency_ms = latency_ms
        if input_tokens is not None:
            row.input_tokens = input_tokens
        if output_tokens is not None:
            row.output_tokens = output_tokens
        if iterations is not None:
            row.iterations = iterations
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_done 失败 %s: %s", execution_id, e)


def record_execution_failed(
    db: Any,
    execution_id: str,
    error: Optional[str] = None,
    latency_ms: Optional[int] = None,
    interrupt_reason: Optional[str] = None,
) -> None:
    """标记失败；带 interrupt_reason（如 timeout）时记为 cancelled/interrupted。"""
    try:
        row = _get_row(db, execution_id)
        if row is None:
            logger.warning("record_execution_failed：执行记录不存在 %s", execution_id)
            return
        if interrupt_reason:
            row.status = "cancelled"
            row.finished_reason = "interrupted"
            row.interrupt_reason = interrupt_reason
        else:
            row.status = "failed"
            row.finished_reason = "error"
        row.error = error
        row.completed_at = datetime.now()
        if latency_ms is not None:
            row.latency_ms = latency_ms
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_failed 失败 %s: %s", execution_id, e)
