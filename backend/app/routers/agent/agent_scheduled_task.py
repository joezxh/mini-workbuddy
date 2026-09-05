"""AI 任务定时调度接口（深度研究 / Agent / AgentTeam 周期自动执行）

归属用户隔离：所有接口按 current_user.user_id 过滤/校验。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.agent.agent_scheduled_task_service import (
    ScheduledTaskError,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    pause_task,
    resume_task,
    run_now,
    update_task,
)

router = APIRouter(prefix="/agent-scheduled-tasks", tags=["AI任务调度"])


class AgentScheduledTaskCreate(BaseModel):
    task_name: str = Field(..., max_length=200)
    description: Optional[str] = None
    target_mode: str = Field(..., description="deep_research / agent / team / skill")
    agent_id: Optional[int] = None
    team_id: Optional[int] = None
    skill_info: Optional[dict] = Field(
        None, description="skill 模式：{package_id, package_name, script_id, script_name, params}"
    )
    prompt: str = Field(..., description="执行输入：深度研究=研究主题，agent/team/skill=指令")
    session_id: Optional[str] = None
    model_id: Optional[int] = None
    schedule_type: str = Field(..., description="cron / interval / once")
    cron_expression: Optional[str] = Field(None, description="5 段 cron：分 时 日 月 周")
    interval_seconds: Optional[int] = Field(None, ge=60)
    run_at: Optional[datetime] = None
    timezone: Optional[str] = None


class AgentScheduledTaskUpdate(BaseModel):
    task_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    prompt: Optional[str] = None
    agent_id: Optional[int] = None
    team_id: Optional[int] = None
    skill_info: Optional[dict] = None
    model_id: Optional[int] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = Field(None, ge=60)
    run_at: Optional[datetime] = None
    timezone: Optional[str] = None


@router.get("")
async def list_scheduled_tasks(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
):
    """查询当前用户的调度任务列表。"""
    total, items = list_tasks(current_user.user_id, status=status, page=page, size=size)
    return {"total": total, "items": items}


@router.get("/{sched_id}")
async def get_scheduled_task(sched_id: int, current_user: SysUser = Depends(get_current_user)):
    data = get_task(sched_id, current_user.user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")
    return data


@router.post("")
async def create_scheduled_task(req: AgentScheduledTaskCreate, current_user: SysUser = Depends(get_current_user)):
    try:
        return create_task(user_id=current_user.user_id, **req.model_dump())
    except ScheduledTaskError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{sched_id}")
async def update_scheduled_task(
    sched_id: int,
    req: AgentScheduledTaskUpdate,
    current_user: SysUser = Depends(get_current_user),
):
    try:
        data = update_task(sched_id, current_user.user_id, req.model_dump(exclude_none=True))
    except ScheduledTaskError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if data is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")
    return data


@router.post("/{sched_id}/pause")
async def pause_scheduled_task(sched_id: int, current_user: SysUser = Depends(get_current_user)):
    data = pause_task(sched_id, current_user.user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")
    return data


@router.post("/{sched_id}/resume")
async def resume_scheduled_task(sched_id: int, current_user: SysUser = Depends(get_current_user)):
    data = resume_task(sched_id, current_user.user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="调度任务不存在")
    return data


@router.post("/{sched_id}/run-now")
async def run_scheduled_task_now(sched_id: int, current_user: SysUser = Depends(get_current_user)):
    """立即执行一次（不改变调度计划），返回生成的异步任务 ID。"""
    try:
        task_id = await run_now(sched_id, current_user.user_id)
    except ScheduledTaskError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"scheduledId": sched_id, "asyncTaskId": task_id, "message": "已触发执行，请在异步任务列表查看进度"}


@router.delete("/{sched_id}")
async def delete_scheduled_task(sched_id: int, current_user: SysUser = Depends(get_current_user)):
    ok = delete_task(sched_id, current_user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="调度任务不存在")
    return {"id": sched_id, "status": "deleted", "message": "已删除"}
