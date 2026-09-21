"""Agent/Skill 执行运行控制 API —— cancel（spec §5.3；confirm 在 Task 10 追加）。"""
from fastapi import APIRouter, Depends, HTTPException
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
