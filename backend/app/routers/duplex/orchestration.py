"""双工语音编排 REST：Agent 设计管理、输出渠道管理、voice 会话列表。

路由自带 prefix=/duplex，由 router_registry 叠加 /api/v1 → /api/v1/duplex/*。
所有端点需登录（JWT），与既有 ai_assistant 一致。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.duplex.voice import orchestration_store as store
from app.db.database import get_db
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser

router = APIRouter(prefix="/duplex", tags=["双工编排管理"])


# ── Request 模型 ──
class AgentConfigIn(BaseModel):
    key: str
    name: Optional[str] = None
    icon: Optional[str] = None
    desc: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    prompt: Optional[str] = None
    rules: Optional[list[str]] = None
    tools: Optional[list[str]] = None


class ChannelConfigIn(BaseModel):
    key: str
    name: Optional[str] = None
    icon: Optional[str] = None
    desc: Optional[str] = None
    active: Optional[bool] = None
    output: Optional[str] = Field(None, pattern="^(text|voice|both|off)$")
    capability: Optional[str] = None


# ── Agent 编排设计管理 ──
@router.get("/agents")
def list_agents(_user: SysUser = Depends(get_current_user)):
    """列出全部 Agent 设计配置（含启用态/优先级/规则/Prompt/工具）。"""
    return {"items": store.list_agents()}


@router.post("/agents")
def upsert_agent(body: AgentConfigIn, _user: SysUser = Depends(get_current_user)):
    """新增或更新 Agent 设计配置（按 key 幂等）。"""
    try:
        agent = store.upsert_agent(body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return agent


@router.delete("/agents/{key}")
def delete_agent(key: str, _user: SysUser = Depends(get_current_user)):
    """删除 Agent 设计配置。内置 Agent 删除后回落到插件默认。"""
    if not store.delete_agent(key):
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return {"deleted": True, "key": key}


# ── 输出渠道管理 ──
@router.get("/channels")
def list_channels(_user: SysUser = Depends(get_current_user)):
    """列出全部输出渠道配置（含能力状态）。"""
    return {"items": store.list_channels()}


@router.post("/channels")
def upsert_channel(body: ChannelConfigIn, _user: SysUser = Depends(get_current_user)):
    """新增或更新输出渠道配置（按 key 幂等）。output=off 映射为 active=False。"""
    payload = body.model_dump(exclude_none=True)
    if payload.get("output") == "off":
        payload["active"] = False
        payload.pop("output", None)
    try:
        channel = store.upsert_channel(payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return channel


@router.delete("/channels/{key}")
def delete_channel(key: str, _user: SysUser = Depends(get_current_user)):
    """删除输出渠道配置。"""
    if not store.delete_channel(key):
        raise HTTPException(status_code=404, detail="渠道不存在")
    return {"deleted": True, "key": key}


# ── voice 会话列表（支持 session_type 过滤）──
@router.get("/sessions")
def list_voice_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session_type: Optional[str] = Query("voice"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """当前用户的会话列表，默认仅 voice 类型（供右侧会话列表面板）。"""
    from app.models.ai.ai_chat import AiChatSession
    from sqlalchemy import desc

    query = db.query(AiChatSession).filter(AiChatSession.user_id == current_user.user_id)
    if session_type:
        query = query.filter(AiChatSession.session_type == session_type)
    total = query.count()
    items = (
        query.order_by(desc(AiChatSession.is_pinned), desc(AiChatSession.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_session_to_dict(s) for s in items],
    }


def _session_to_dict(s) -> dict:
    return {
        "session_id": s.session_id,
        "user_id": s.user_id,
        "session_title": s.session_title,
        "session_type": s.session_type,
        "status": s.status,
        "message_count": s.message_count,
        "is_pinned": bool(s.is_pinned),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
