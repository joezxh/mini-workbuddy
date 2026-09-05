"""定时任务管理工具 - 封装现有 TaskSchedulerService。

基于 AgentScope 2.0.4 ToolBase 协议实现。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from agentscope.tool import ToolBase, ToolChunk
from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)

logger = logging.getLogger(__name__)


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class ScheduledTaskTool(ToolBase):
    """定时任务管理 - CRUD + 手动触发。"""

    name: str = "scheduled_task_tool"
    description: str = "管理定时任务：创建/查看/更新/删除/手动触发，支持 cron 和间隔调度"
    input_schema: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "update", "delete", "run_now", "status"],
                "description": "操作类型：list-列表 / create-创建 / update-更新 / delete-删除 / run_now-立即执行 / status-查看状态",
            },
            "task_id": {
                "type": "integer",
                "description": "任务 ID（update/delete/run_now/status 时必填）",
            },
            "task_name": {
                "type": "string",
                "description": "任务名称（create 时必填）",
            },
            "task_type": {
                "type": "string",
                "description": "任务类型（如 report/event/custom）",
            },
            "schedule_type": {
                "type": "string",
                "enum": ["cron", "interval", "once"],
                "description": "调度类型",
            },
            "cron_expression": {
                "type": "string",
                "description": "Cron 表达式（如 '0 9 * * *' 表示每天9点）",
            },
            "interval_seconds": {
                "type": "integer",
                "description": "间隔秒数（interval 类型时使用）",
            },
            "task_params": {
                "type": "object",
                "description": "任务参数 JSON 对象",
            },
            "description_text": {
                "type": "string",
                "description": "任务描述",
            },
        },
        "required": ["action"],
    }
    is_concurrency_safe: bool = False
    is_read_only: bool = False

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        action = tool_input.get("action", "list")
        if action in ("list", "status"):
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="Read-only task query.",
            )
        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            message=f"Task action '{action}' will modify task state.",
        )

    async def call(
        self,
        action: str,
        task_id: Optional[int] = None,
        task_name: Optional[str] = None,
        task_type: Optional[str] = None,
        schedule_type: Optional[str] = None,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        task_params: Optional[dict] = None,
        description_text: Optional[str] = None,
    ) -> ToolChunk:
        from app.db.database import SessionLocal
        from app.models.scheduled_task import ScheduledTask, TaskExecutionLog

        db = SessionLocal()
        try:
            if action == "list":
                tasks = db.query(ScheduledTask).filter(
                    ScheduledTask.is_deleted == False
                ).order_by(ScheduledTask.sort_order).all()
                result = []
                for t in tasks:
                    result.append({
                        "task_id": t.task_id,
                        "task_code": t.task_code,
                        "task_name": t.task_name,
                        "task_type": t.task_type,
                        "schedule_type": t.schedule_type,
                        "cron_expression": t.cron_expression,
                        "interval_seconds": t.interval_seconds,
                        "status": t.status,
                        "is_active": t.is_active,
                        "last_run_time": str(t.last_run_time) if t.last_run_time else None,
                        "last_run_status": t.last_run_status,
                        "next_run_time": str(t.next_run_time) if t.next_run_time else None,
                    })
                return _text_chunk({"action": "list", "tasks": result, "count": len(result)})

            elif action == "status":
                if task_id is None:
                    return _text_chunk({"error": "status 操作需要提供 task_id"})
                task = db.query(ScheduledTask).filter(
                    ScheduledTask.task_id == task_id,
                    ScheduledTask.is_deleted == False,
                ).first()
                if not task:
                    return _text_chunk({"error": f"任务不存在: {task_id}"})
                # 查询最近执行日志
                logs = db.query(TaskExecutionLog).filter(
                    TaskExecutionLog.task_id == task_id
                ).order_by(TaskExecutionLog.id.desc()).limit(10).all()
                log_list = []
                for log in logs:
                    log_list.append({
                        "id": log.id,
                        "status": log.status,
                        "message": log.message if hasattr(log, "message") else None,
                        "started_at": str(log.started_at) if hasattr(log, "started_at") and log.started_at else None,
                        "finished_at": str(log.finished_at) if hasattr(log, "finished_at") and log.finished_at else None,
                    })
                return _text_chunk({
                    "action": "status",
                    "task": {
                        "task_id": task.task_id,
                        "task_name": task.task_name,
                        "status": task.status,
                        "total_runs": task.total_runs,
                        "success_runs": task.success_runs,
                        "failed_runs": task.failed_runs,
                        "last_run_time": str(task.last_run_time) if task.last_run_time else None,
                    },
                    "recent_logs": log_list,
                })

            elif action == "create":
                if not task_name:
                    return _text_chunk({"error": "create 操作需要提供 task_name"})
                if not schedule_type:
                    return _text_chunk({"error": "create 操作需要提供 schedule_type"})
                import uuid
                task_code = f"agent_{uuid.uuid4().hex[:8]}"
                new_task = ScheduledTask(
                    task_code=task_code,
                    task_name=task_name,
                    task_type=task_type or "custom",
                    schedule_type=schedule_type,
                    cron_expression=cron_expression,
                    interval_seconds=interval_seconds,
                    task_params=task_params or {},
                    description=description_text or "",
                    status="enabled",
                    is_active=True,
                )
                db.add(new_task)
                db.commit()
                db.refresh(new_task)
                return _text_chunk({
                    "action": "create",
                    "task_id": new_task.task_id,
                    "task_code": new_task.task_code,
                    "task_name": new_task.task_name,
                    "status": "created",
                })

            elif action == "update":
                if task_id is None:
                    return _text_chunk({"error": "update 操作需要提供 task_id"})
                task = db.query(ScheduledTask).filter(
                    ScheduledTask.task_id == task_id,
                    ScheduledTask.is_deleted == False,
                ).first()
                if not task:
                    return _text_chunk({"error": f"任务不存在: {task_id}"})
                updated = []
                if task_name is not None:
                    task.task_name = task_name
                    updated.append("task_name")
                if task_type is not None:
                    task.task_type = task_type
                    updated.append("task_type")
                if schedule_type is not None:
                    task.schedule_type = schedule_type
                    updated.append("schedule_type")
                if cron_expression is not None:
                    task.cron_expression = cron_expression
                    updated.append("cron_expression")
                if interval_seconds is not None:
                    task.interval_seconds = interval_seconds
                    updated.append("interval_seconds")
                if task_params is not None:
                    task.task_params = task_params
                    updated.append("task_params")
                if description_text is not None:
                    task.description = description_text
                    updated.append("description")
                db.commit()
                return _text_chunk({
                    "action": "update",
                    "task_id": task_id,
                    "updated_fields": updated,
                    "status": "updated",
                })

            elif action == "delete":
                if task_id is None:
                    return _text_chunk({"error": "delete 操作需要提供 task_id"})
                task = db.query(ScheduledTask).filter(
                    ScheduledTask.task_id == task_id,
                    ScheduledTask.is_deleted == False,
                ).first()
                if not task:
                    return _text_chunk({"error": f"任务不存在: {task_id}"})
                task.is_deleted = True
                task.is_active = False
                task.status = "disabled"
                db.commit()
                return _text_chunk({
                    "action": "delete",
                    "task_id": task_id,
                    "status": "deleted",
                })

            elif action == "run_now":
                if task_id is None:
                    return _text_chunk({"error": "run_now 操作需要提供 task_id"})
                task = db.query(ScheduledTask).filter(
                    ScheduledTask.task_id == task_id,
                    ScheduledTask.is_deleted == False,
                ).first()
                if not task:
                    return _text_chunk({"error": f"任务不存在: {task_id}"})
                # 标记为需要立即执行，由 scheduler 在下次心跳时处理
                task.status = "running"
                task.last_run_status = "pending"
                task.last_run_message = "Agent triggered manual run"
                db.commit()
                return _text_chunk({
                    "action": "run_now",
                    "task_id": task_id,
                    "task_name": task.task_name,
                    "status": "triggered",
                    "message": "任务已标记为立即执行，将由调度器处理",
                })

            else:
                return _text_chunk({"error": f"未知 action: {action}"})

        except Exception as exc:
            db.rollback()
            logger.warning("scheduled_task_tool failed: %s", exc)
            return _text_chunk({"error": str(exc)})
        finally:
            db.close()
