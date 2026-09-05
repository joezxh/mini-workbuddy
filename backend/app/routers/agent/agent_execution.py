"""AgentExecution 查询接口。

router 仅做参数校验 + 调用 service + 组装响应；
聚合 / JOIN 全部下沉到 AgentExecutionService。
"""
from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
import json

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.services.agent.agent_execution_service import (
    list_executions,
    get_detail,
    list_by_session,
    get_stats,
    get_events,
)
from app.schemas.agent.agent_execution import (
    AgentExecutionListResp,
    AgentExecutionDetail,
    AgentExecutionStats,
    AgentExecutionEventListResp,
)


router = APIRouter(prefix="/api/v1/agent-execution", tags=["Agent执行查询"])


@router.get("", response_model=AgentExecutionListResp)
def get_execution_list(
    session_id: Optional[int] = Query(None, description="按会话ID筛选"),
    execution_mode: Optional[str] = Query(None, description="按执行模式筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    target_id: Optional[str] = Query(None, description="按被执行对象ID精确筛选（如 agent_config.id / ai_skill_package.id）"),
    keyword: Optional[str] = Query(None, description="关键词搜索（匹配 target_id / user_input / output）"),
    start_time: Optional[datetime] = Query(None, description="开始时间（ISO8601），筛选 started_at>="),
    end_time: Optional[datetime] = Query(None, description="结束时间（ISO8601），筛选 started_at<="),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """分页 + 筛选查询 agent_execution 记录。"""
    items, total = list_executions(
        db,
        session_id=session_id,
        execution_mode=execution_mode,
        status=status,
        target_id=target_id,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )
    return AgentExecutionListResp(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/stats", response_model=AgentExecutionStats)
def get_execution_stats(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """执行记录统计聚合。"""
    return get_stats(db)


@router.get("/session/{session_id}", response_model=list)  # noqa: A003 - 路径参数列表
def get_executions_by_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """按 session 列出该会话下的全部执行记录。"""
    return list_by_session(db, session_id)


@router.get("/{execution_id}", response_model=AgentExecutionDetail)
def get_execution_detail(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """查询单条执行详情（含完整输出、关联链路概要、调用链事件与人工介入）。"""
    detail = get_detail(db, execution_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return detail


@router.get("/{execution_id}/events", response_model=AgentExecutionEventListResp)
def get_execution_events(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """查询单条执行的调用链节点事件（用于绘制分层 DAG 拓扑与时间线）。"""
    return get_events(db, execution_id)


@router.get("/{execution_id}/unified-events")
def get_unified_events(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """归一化事件回放：仅返回 step / artifact 两类统一事件。

    step 事件对应前端时间线（StepEvent），artifact 事件对应产物画廊（ArtifactItem）。
    content 已解析为结构化 dict，前端可直接渲染。
    """
    resp = get_events(db, execution_id)
    steps: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = []
    for item in resp.items:
        if item.event_type not in ("step", "artifact"):
            continue
        content = item.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
        if not isinstance(content, dict):
            continue
        content.setdefault("seq", item.sequence)
        # 注入落库时间，供前端时间列展示（StepEvent 落库时不带 timestamp）
        if item.created_at is not None:
            content.setdefault("timestamp", item.created_at.isoformat())
        if item.event_type == "step":
            steps.append(content)
        else:
            artifacts.append(content)
    return {"execution_id": execution_id, "steps": steps, "artifacts": artifacts, "total": len(steps) + len(artifacts)}

