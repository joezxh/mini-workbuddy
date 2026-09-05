"""Agent API 路由

TODO: AgentScope 原生 Agent API 适配（旧 agent_core 模块已移除）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
# TODO: 旧 agent_core 已移除，待 AgentScope 原生 API 重建
# from app.ai.agent_core.registry import get_agent_registry
# from app.ai.agent_core.session import AgentSessionManager
# from app.ai.agent_core.router import AgentRouter
from app.ai.schemas import (
    CreateSessionRequest,
    AiSendMessageRequest,
    ExecuteRequest,
    SessionResponse,
    MessageResponse,
    ExecuteResponse,
    AgentInfo,
    SessionListItem,
)


router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


def get_current_user_id() -> int:
    """获取当前用户 ID（实际应从 token 解析）"""
    return 1


@router.get("/registry", response_model=list[AgentInfo])
async def list_agents():
    """列出所有可用 Agent"""
    registry = get_agent_registry()
    return registry.list_agents()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """创建 Agent 会话"""
    try:
        router_instance = AgentRouter(db)
        result = await router_instance.create_session(
            user_id=user_id,
            agent_id=request.agent_id,
            event_id=request.event_id,
            sim_id=request.simulation_id,
            session_title=request.session_title,
        )
        return SessionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    """获取会话详情"""
    manager = AgentSessionManager(db)
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        session_id=session.session_id,
        agent_id=session.agent_id or "",
        agent_name=session.agent_id or "",
        agent_type="",
        context_data=session.context_data or {},
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}/history", response_model=list[dict])
async def get_session_history(
    session_id: int,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """获取会话历史"""
    manager = AgentSessionManager(db)
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    total, messages = manager.get_messages(session_id, page, page_size)
    
    return [
        {
            "message_id": m.message_id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "extra_data": m.extra_data,
        }
        for m in messages
    ]


@router.post("/sessions/{session_id}/message", response_model=MessageResponse)
async def send_message(
    session_id: int,
    request: AiSendMessageRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """发送消息"""
    try:
        router_instance = AgentRouter(db)
        result = await router_instance.send_message(
            session_id=session_id,
            user_message=request.content,
            user_id=user_id,
        )
        return MessageResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    """删除会话"""
    manager = AgentSessionManager(db)
    if not manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


@router.post("/execute", response_model=ExecuteResponse)
async def execute_direct(
    request: ExecuteRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """直接执行（无会话）"""
    try:
        router_instance = AgentRouter(db)
        result = await router_instance.execute_direct(
            agent_id=request.agent_id,
            prompt=request.prompt,
            user_id=user_id,
            event_id=request.event_id,
            tools=request.tools,
            skills=request.skills,
        )
        return ExecuteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sessions/user/{user_id}", response_model=list[SessionListItem])
async def list_user_sessions(
    user_id: int,
    agent_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """获取用户的会话列表"""
    manager = AgentSessionManager(db)
    total, sessions = manager.get_user_sessions(user_id, agent_id, page, page_size)
    
    return [
        SessionListItem(
            session_id=s.session_id,
            agent_id=s.agent_id or "",
            session_title=s.session_title or "",
            status=s.status or "active",
            message_count=s.message_count or 0,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]
