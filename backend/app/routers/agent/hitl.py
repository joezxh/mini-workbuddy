"""AgentHitlPause 只读查询路由（spec 步骤三 4.4）。

HITL 审批列表的最小只读端点：读取 agent_hitl_pause 表（带租户过滤），
不做任何写操作。风格对齐同目录 agent_config.py（自带 /api/v1 前缀）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.agent.agent_hitl_pause import AgentHitlPause
from app.models.sys.sys_user import SysUser

router = APIRouter(prefix="/api/v1/agent-hitl", tags=["Agent HITL 审批"])


@router.get("/pauses")
def list_hitl_pauses(
    status: Optional[str] = Query(None, description="状态过滤 waiting/approved/rejected/interrupted"),
    execution_id: Optional[str] = Query(None, description="执行 ID 过滤"),
    tenant_id: Optional[int] = Query(None, description="租户 ID 过滤（租户隔离行级过滤）"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """分页读取 HITL 人机交互暂停记录（只读）"""
    query = db.query(AgentHitlPause)
    if status:
        query = query.filter(AgentHitlPause.status == status)
    if execution_id:
        query = query.filter(AgentHitlPause.execution_id == execution_id)
    if tenant_id is not None:
        query = query.filter(AgentHitlPause.tenant_id == tenant_id)
    total = query.count()
    items = (
        query.order_by(AgentHitlPause.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return {
        "data": [
            {
                "id": i.id,
                "execution_id": i.execution_id,
                "reply_id": i.reply_id,
                "tool_calls": i.tool_calls,
                "suggested_rules": i.suggested_rules,
                "status": i.status,
                "accept_rules": i.accept_rules,
                "timeout_at": i.timeout_at,
                "answered_at": i.answered_at,
                "created_at": i.created_at,
                "tenant_id": i.tenant_id,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }
