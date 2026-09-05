"""AI会话管理路由（管理端）"""
from app.middleware.audit_logger import AuditLogRoute
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.ai.ai_chat_service import AiChatService

router = APIRouter(route_class=AuditLogRoute)


# ── Schema ───────────────────────────────────────────────────────────────────

class BatchDeleteRequest(BaseModel):
    ids: List[int]


class AddMessageRequest(BaseModel):
    role: str
    content: str
    message_type: str = "text"
    extra_data: Optional[dict] = None


def _session_to_dict(s) -> dict:
    return {
        "session_id": s.session_id,
        "user_id": s.user_id,
        "session_title": s.session_title,
        "session_type": s.session_type,
        "status": s.status,
        "message_count": s.message_count,
        "is_pinned": s.is_pinned,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_to_dict(m) -> dict:
    return {
        "message_id": m.message_id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "message_type": m.message_type,
        "extra_data": m.extra_data,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ── 会话管理接口 ─────────────────────────────────────────────────────────────

@router.get("/ai-sessions")
def list_all_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="按用户ID过滤"),
    status: Optional[str] = Query(None, description="会话状态过滤"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """管理端：获取所有会话列表"""
    svc = AiChatService(db)
    total, items = svc.get_all_sessions(
        page=page, page_size=page_size,
        user_id=user_id, status=status,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_session_to_dict(s) for s in items],
    }


@router.get("/ai-sessions/{session_id}")
def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取单个会话详情"""
    svc = AiChatService(db)
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return _session_to_dict(session)


@router.delete("/ai-sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除会话（含消息）"""
    svc = AiChatService(db)
    ok = svc.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "删除成功"}


@router.post("/ai-sessions/batch-delete")
def batch_delete_sessions(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """批量删除会话"""
    svc = AiChatService(db)
    count = svc.batch_delete_sessions(body.ids)
    return {"deleted": count, "message": f"已删除 {count} 个会话"}


# ── 消息管理接口 ─────────────────────────────────────────────────────────────

@router.get("/ai-sessions/{session_id}/messages")
def list_session_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取会话的消息列表"""
    svc = AiChatService(db)
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    total, items = svc.get_session_messages(
        session_id=session_id, page=page, page_size=page_size
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_message_to_dict(m) for m in items],
    }


@router.post("/ai-sessions/{session_id}/messages")
def add_session_message(
    session_id: int,
    body: AddMessageRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """保存一条消息（深度研究后台异步任务卡片等场景：提交后即刻落库，支持事后回放）"""
    svc = AiChatService(db)
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    msg = svc.add_message(
        session_id=session_id,
        role=body.role,
        content=body.content,
        message_type=body.message_type,
        extra_data=body.extra_data,
    )
    return _message_to_dict(msg)


@router.delete("/ai-sessions/{session_id}/messages")
def clear_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """清空会话消息"""
    svc = AiChatService(db)
    count = svc.delete_session_messages(session_id)
    return {"deleted": count, "message": f"已清空 {count} 条消息"}


@router.post("/ai-messages/batch-delete")
def batch_delete_messages(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """批量删除消息"""
    svc = AiChatService(db)
    count = svc.batch_delete_messages(body.ids)
    return {"deleted": count, "message": f"已删除 {count} 条消息"}

