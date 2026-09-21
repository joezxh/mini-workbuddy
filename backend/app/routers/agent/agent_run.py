"""Agent/Skill 执行运行控制 API —— cancel + HITL confirm（spec §5.3/§5.4）。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.ai.events.registry import get_run_registry

router = APIRouter(prefix="/agents/executions", tags=["Agent 运行控制"])


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """强制终止运行中的 Agent/Skill 执行。

    async def 端点：task.cancel() 只能在事件循环线程内调用，
    同步 def 会落入 FastAPI 线程池，跨线程取消不安全。
    """
    reg = get_run_registry()
    handle = reg.get(execution_id)
    if handle is None or handle.status == "done":
        raise HTTPException(status_code=404, detail="执行不存在或已结束")
    ok = reg.cancel(execution_id, reason="user_cancel")
    return {"ok": ok, "execution_id": execution_id, "interrupt_reason": "user_cancel"}


class ConfirmRequest(BaseModel):
    """HITL 确认请求（spec §5.4）。"""
    action: str = Field(..., pattern="^(approve|reject|interrupt)$")
    tool_calls: list[dict] = Field(default_factory=list)
    accept_rules: bool = False


@router.post("/{execution_id}/confirm")
async def confirm_execution(
    execution_id: str,
    req: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """人机交互确认：approve / reject / interrupt。

    权限控制：仅执行所有者可确认（execution.user_id 校验）。
    """
    reg = get_run_registry()
    handle = reg.get(execution_id)
    if handle is None or handle.status != "waiting_hitl":
        raise HTTPException(status_code=409, detail="执行不在 HITL 暂停状态")

    # 权限控制：仅执行所有者可操作
    from app.models.agent.agent_execution import AgentExecution
    row = db.query(AgentExecution).filter(
        AgentExecution.execution_id == execution_id).first()
    uid = getattr(current_user, "user_id", None)
    if (row is not None and row.user_id is not None and uid is not None
            and int(row.user_id) != int(uid)):
        raise HTTPException(status_code=403, detail="无权操作该执行")

    from app.ai.events.hitl import resolve_pause, resume_hitl
    resolve_pause(db, execution_id=execution_id, action=req.action,
                  accept_rules=req.accept_rules)
    resume_hitl(handle, req.action, req.tool_calls)
    return {"ok": True, "action": req.action, "execution_id": execution_id}
