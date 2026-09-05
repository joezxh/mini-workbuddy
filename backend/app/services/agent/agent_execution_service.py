"""AgentExecution 查询业务逻辑层。

所有聚合查询 / JOIN 在此实现，router 仅做参数校验 + 调用 + 组装响应。
"""
from __future__ import annotations

from typing import Optional, Tuple, List
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.models.agent.agent_execution import AgentExecution
from app.models.ai.ai_chat import AiChatSession
from app.models.agent.agent_trace import AgentTrace
from app.models.agent.agent_execution_event import AgentExecutionEvent
# TODO: 域特定模型已移除
# from app.models.agent_hitl_pause import AgentHitlPause
from app.schemas.agent.agent_execution import (
    AgentExecutionItem,
    AgentExecutionDetail,
    AgentExecutionStats,
    AgentExecutionEventItem,
    AgentHitlPauseItem,
    AgentExecutionEventListResp,
    AgentTraceSummary,
)


# 列表展示时的文本截断长度
_PREVIEW_LIMIT = 500


def _truncate(text: Optional[str], limit: int = _PREVIEW_LIMIT) -> Optional[str]:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "..."


def _item_from_row(exec_row, session_title: Optional[str] = None) -> AgentExecutionItem:
    """由 (AgentExecution, session_title) 元组构造列表项。"""
    return AgentExecutionItem(
        execution_id=exec_row.execution_id,
        session_id=exec_row.session_id,
        session_title=session_title,
        user_id=exec_row.user_id,
        execution_mode=exec_row.execution_mode,
        target_id=exec_row.target_id,
        status=exec_row.status,
        user_input=_truncate(exec_row.user_input),
        output=_truncate(exec_row.output),
        error=_truncate(exec_row.error),
        latency_ms=exec_row.latency_ms,
        started_at=exec_row.started_at,
        completed_at=exec_row.completed_at,
    )


def list_executions(
    db: Session,
    *,
    session_id: Optional[int] = None,
    execution_mode: Optional[str] = None,
    status: Optional[str] = None,
    target_id: Optional[str] = None,
    keyword: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[AgentExecutionItem], int]:
    """分页 + 筛选查询 agent_execution，JOIN ai_chat_session 取标题。

    Returns:
        (items, total)
    """
    SessionAlias = aliased(AiChatSession)

    base = db.query(AgentExecution, SessionAlias.session_title).outerjoin(
        SessionAlias, AgentExecution.session_id == SessionAlias.session_id
    )

    if session_id is not None:
        base = base.filter(AgentExecution.session_id == session_id)
    if execution_mode is not None:
        base = base.filter(AgentExecution.execution_mode == execution_mode)
    if status is not None:
        base = base.filter(AgentExecution.status == status)
    if target_id is not None:
        # 精确匹配被执行对象 id（按字符串比较，兼容 agent_config.id 等）
        base = base.filter(AgentExecution.target_id == target_id)
    if keyword:
        like = f"%{keyword}%"
        base = base.filter(
            or_(
                AgentExecution.target_id.ilike(like),
                AgentExecution.user_input.ilike(like),
                AgentExecution.output.ilike(like),
            )
        )
    if start_time is not None:
        base = base.filter(AgentExecution.started_at >= start_time)
    if end_time is not None:
        base = base.filter(AgentExecution.started_at <= end_time)

    total = base.distinct(AgentExecution.id).count()

    rows = (
        base.order_by(AgentExecution.started_at.desc().nullslast(), AgentExecution.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_item_from_row(exec_row, title) for exec_row, title in rows]
    return items, total


def get_detail(db: Session, execution_id: str) -> Optional[AgentExecutionDetail]:
    """查询单条执行详情，JOIN AgentTrace 取链路概要。"""
    exec_row = (
        db.query(AgentExecution)
        .filter(AgentExecution.execution_id == execution_id)
        .first()
    )
    if exec_row is None:
        return None

    # 关联链路概要（按 trace_id 取最新一条）
    trace_summary: Optional[AgentTraceSummary] = None
    if exec_row.trace_id:
        trace = (
            db.query(AgentTrace)
            .filter(AgentTrace.trace_id == exec_row.trace_id)
            .order_by(AgentTrace.start_time.desc())
            .first()
        )
        if trace is not None:
            trace_summary = AgentTraceSummary(
                trace_id=trace.trace_id,
                agent_id=trace.agent_id,
                agent_type=trace.agent_type,
                status=trace.status,
                duration_ms=trace.duration_ms,
            )

    session_title = None
    if exec_row.session_id is not None:
        sess = (
            db.query(AiChatSession.session_title)
            .filter(AiChatSession.session_id == exec_row.session_id)
            .first()
        )
        session_title = sess.session_title if sess else None

    return AgentExecutionDetail(
        execution_id=exec_row.execution_id,
        session_id=exec_row.session_id,
        session_title=session_title,
        user_id=exec_row.user_id,
        execution_mode=exec_row.execution_mode,
        target_id=exec_row.target_id,
        status=exec_row.status,
        user_input=exec_row.user_input,
        output=exec_row.output,
        error=exec_row.error,
        latency_ms=exec_row.latency_ms,
        started_at=exec_row.started_at,
        completed_at=exec_row.completed_at,
        metadata_json=exec_row.metadata_json,
        trace=trace_summary,
        events=_events_to_items(db, execution_id),
        hitl_pauses=_hitl_to_items(db, execution_id),
    )


def _events_to_items(db: Session, execution_id: str) -> List[AgentExecutionEventItem]:
    """加载调用链节点事件（按 sequence/id 升序，保持执行时序）。"""
    rows = (
        db.query(AgentExecutionEvent)
        .filter(AgentExecutionEvent.execution_id == execution_id)
        .order_by(AgentExecutionEvent.sequence.asc(), AgentExecutionEvent.id.asc())
        .all()
    )
    return [AgentExecutionEventItem.from_orm_event(r) for r in rows]


def _hitl_to_items(db: Session, execution_id: str) -> List[AgentHitlPauseItem]:
    """加载人工介入暂停记录（按 id 升序）。"""
    rows = (
        db.query(AgentHitlPause)
        .filter(AgentHitlPause.execution_id == execution_id)
        .order_by(AgentHitlPause.id.asc())
        .all()
    )
    return [AgentHitlPauseItem.model_validate(r, from_attributes=True) for r in rows]


def get_events(db: Session, execution_id: str) -> AgentExecutionEventListResp:
    """调用链事件列表响应（供前端单独拉取分层 DAG 拓扑数据）。"""
    rows = (
        db.query(AgentExecutionEvent)
        .filter(AgentExecutionEvent.execution_id == execution_id)
        .order_by(AgentExecutionEvent.sequence.asc(), AgentExecutionEvent.id.asc())
        .all()
    )
    items = [AgentExecutionEventItem.from_orm_event(r) for r in rows]
    return AgentExecutionEventListResp(items=items, total=len(items))


def get_hitl_pauses(db: Session, execution_id: str) -> List[AgentHitlPauseItem]:
    """人工介入暂停列表。"""
    return _hitl_to_items(db, execution_id)


def list_by_session(db: Session, session_id: int) -> List[AgentExecutionItem]:
    """按 session 列出该会话下的所有执行记录（含 session_title）。"""
    rows = (
        db.query(AgentExecution)
        .filter(AgentExecution.session_id == session_id)
        .order_by(AgentExecution.started_at.desc().nullslast(), AgentExecution.id.desc())
        .all()
    )
    # 单次取 title（同一 session 共享）
    title = None
    if rows:
        sess = (
            db.query(AiChatSession.session_title)
            .filter(AiChatSession.session_id == session_id)
            .first()
        )
        title = sess.session_title if sess else None

    return [_item_from_row(r, title) for r in rows]


def get_stats(db: Session) -> AgentExecutionStats:
    """统计聚合：按 execution_mode / status 分组 count，总耗时 / 平均耗时。"""
    total = db.query(func.count(AgentExecution.id)).scalar() or 0

    mode_rows = (
        db.query(AgentExecution.execution_mode, func.count(AgentExecution.id))
        .group_by(AgentExecution.execution_mode)
        .all()
    )
    by_execution_mode = {m or 'unknown': c for m, c in mode_rows}

    status_rows = (
        db.query(AgentExecution.status, func.count(AgentExecution.id))
        .group_by(AgentExecution.status)
        .all()
    )
    by_status = {s or 'unknown': c for s, c in status_rows}

    total_latency = (
        db.query(func.coalesce(func.sum(AgentExecution.latency_ms), 0)).scalar() or 0
    )
    latencies = db.query(AgentExecution.latency_ms).filter(
        AgentExecution.latency_ms.isnot(None)
    ).all()
    counted = len(latencies)
    avg_latency = round(total_latency / counted, 2) if counted else 0.0

    return AgentExecutionStats(
        total=total,
        by_execution_mode=by_execution_mode,
        by_status=by_status,
        total_latency_ms=int(total_latency),
        avg_latency_ms=avg_latency,
    )
