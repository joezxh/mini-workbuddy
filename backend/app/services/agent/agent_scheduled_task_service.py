"""AI 任务定时调度服务（深度研究 / Agent / AgentTeam 周期自动执行）

- 持久化 agent_scheduled_task 表，APScheduler 动态注册/移除 job
- 触发时调用 async_task_service.submit_task 生成一次性异步任务，
  执行结果回到「我的异步任务」列表
- 多进程保护：复用 async_task_service._should_register_job，仅主进程注册
- 单次触发失败仅计数（fail_count），不停止后续调度
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.db.database import SessionLocal
from app.models.agent.agent_scheduled_task import AgentScheduledTask
from app.services.async_task_service import (
    _get_scheduler as _get_base_scheduler,
    _should_register_job,
    submit_task,
)

logger = logging.getLogger(__name__)

_JOB_PREFIX = "agent_sched_"

VALID_TARGET_MODES = ("deep_research", "agent", "team", "skill")

# update_task 允许修改的字段白名单
_ALLOWED_UPDATE_FIELDS = (
    "task_name", "description", "prompt", "agent_id", "team_id",
    "model_id", "schedule_type", "cron_expression", "interval_seconds",
    "run_at", "timezone", "skill_info",
)


class ScheduledTaskError(Exception):
    """调度任务业务错误（参数非法 / 状态不允许等），router 转 400。"""


# ── 校验 ─────────────────────────────────────────────────────────────

def _validate_schedule_config(
    schedule_type: str,
    cron_expression: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    run_at: Optional[datetime] = None,
) -> None:
    if schedule_type == "cron":
        if not cron_expression:
            raise ScheduledTaskError("cron 类型必须提供 cron_expression")
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(cron_expression)
        except ValueError as e:
            raise ScheduledTaskError(f"cron 表达式非法（需 5 段：分 时 日 月 周）: {e}")
    elif schedule_type == "interval":
        if not interval_seconds or interval_seconds < 60:
            raise ScheduledTaskError("interval 类型间隔不能小于 60 秒")
    elif schedule_type == "once":
        if not run_at:
            raise ScheduledTaskError("once 类型必须提供执行时间")
        if run_at <= datetime.now():
            raise ScheduledTaskError("once 类型的执行时间必须在未来")
    else:
        raise ScheduledTaskError(f"不支持的调度类型: {schedule_type}")


def _coerce_skill_info(value: Any) -> Optional[dict]:
    """skill_info 兼容 dict / JSON 字符串 / None，统一为 dict 或 None。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            v = json.loads(value)
            return v if isinstance(v, dict) else None
        except (ValueError, TypeError):
            return None
    return None


def _validate_target(
    target_mode: str,
    agent_id: Optional[int] = None,
    team_id: Optional[int] = None,
    prompt: Optional[str] = None,
    skill_info: Any = None,
) -> None:
    if target_mode not in VALID_TARGET_MODES:
        raise ScheduledTaskError(f"不支持的执行模式: {target_mode}")
    if not prompt or not str(prompt).strip():
        raise ScheduledTaskError("执行输入不能为空")
    if target_mode == "agent" and not agent_id:
        raise ScheduledTaskError("agent 模式必须选择智能体")
    if target_mode == "skill":
        info = _coerce_skill_info(skill_info)
        if not info or not info.get("package_id"):
            raise ScheduledTaskError("skill 模式必须选择技能包")
    # team 模式允许 team_id 为空：网关侧使用默认专家团队


# ── 内部工具 ─────────────────────────────────────────────────────────

def _build_trigger(sched: AgentScheduledTask):
    if sched.schedule_type == "cron":
        from apscheduler.triggers.cron import CronTrigger
        return CronTrigger.from_crontab(sched.cron_expression, timezone=sched.timezone)
    if sched.schedule_type == "interval":
        from apscheduler.triggers.interval import IntervalTrigger
        return IntervalTrigger(seconds=sched.interval_seconds, timezone=sched.timezone)
    from apscheduler.triggers.date import DateTrigger
    return DateTrigger(run_date=sched.run_at, timezone=sched.timezone)


def _naive(dt: Optional[datetime]) -> Optional[datetime]:
    """时区感知时间 → 朴素时间（与 DateTime 无时区列匹配）。"""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _should_register() -> bool:
    return _should_register_job()


def _persist_run_meta(
    sched_id: int,
    *,
    next_run_at: Optional[datetime] = None,
    last_run_at: Optional[datetime] = None,
    last_task_id: Optional[int] = None,
    run_delta: int = 0,
    fail_delta: int = 0,
) -> None:
    """回填调度任务的运行元信息（独立短事务）。"""
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None:
            return
        if next_run_at is not None:
            sched.next_run_at = _naive(next_run_at)
        if last_run_at is not None:
            sched.last_run_at = _naive(last_run_at)
        if last_task_id is not None:
            sched.last_task_id = last_task_id
        if run_delta:
            sched.run_count = (sched.run_count or 0) + run_delta
        if fail_delta:
            sched.fail_count = (sched.fail_count or 0) + fail_delta
        db.commit()
    finally:
        db.close()


def _resolve_default_model_id() -> Optional[int]:
    """深度研究未指定模型时兜底取默认文本模型（避免空兜底无 API key 失败）。"""
    try:
        from app.models.ai.ai_api_key import AiChatModel
        db = SessionLocal()
        try:
            row = (
                db.query(AiChatModel)
                .filter(AiChatModel.is_default == True, AiChatModel.type == 1)  # noqa: E712
                .order_by(AiChatModel.id.asc())
                .first()
            )
            return row.id if row is not None else None
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[agent_sched] 解析默认模型失败(忽略): {e}")
        return None


def _build_payload(sched: AgentScheduledTask) -> dict:
    """按执行模式构造 async_task payload（字段与手动提交链路一致）。

    skill 模式 payload 约定（与 chat 流式路径一致）：
      skill      = package_id（网关 skill_code）
      skill_info = {package_id, package_name, script_id, script_name, params}
    """
    if sched.target_mode == "deep_research":
        return {
            "message": sched.prompt,
            "research_topic": sched.prompt,
            "model_id": sched.model_id or _resolve_default_model_id(),
            "context": {},
            "config": {},
        }
    payload: dict = {"message": sched.prompt, "model_id": sched.model_id}
    if sched.target_mode == "agent":
        payload["agent_id"] = sched.agent_id
    elif sched.target_mode == "team":
        payload["team_id"] = sched.team_id
    elif sched.target_mode == "skill":
        info = _coerce_skill_info(sched.skill_info) or {}
        pkg_id = info.get("package_id") or ""
        payload["skill"] = pkg_id
        payload["skill_info"] = info
    return payload


def _load_spec(
    sched_id: int,
    *,
    user_id: Optional[int] = None,
    require_enabled: bool = True,
) -> Optional[dict]:
    """加载调度任务的执行规格（submit_task 入参）。"""
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None or sched.status == "deleted":
            return None
        if require_enabled and sched.status != "enabled":
            return None
        if user_id is not None and sched.user_id != user_id:
            return None
        return {
            "user_id": sched.user_id,
            "task_name": f"[定时] {sched.task_name}",
            "target_mode": sched.target_mode,
            "payload": _build_payload(sched),
            "session_id": sched.session_id,
            "timeout_seconds": 1800,
            "max_retries": 1,
        }
    finally:
        db.close()


# ── APScheduler job 管理 ─────────────────────────────────────────────

async def _trigger_job(sched_id: int) -> None:
    """APScheduler 触发回调：生成一次性异步任务并回填统计。

    单次失败仅计数，不影响后续调度。协程函数由 AsyncIOScheduler 在事件循环执行。
    """
    try:
        spec = _load_spec(sched_id)
        if spec is None:
            logger.warning(f"[agent_sched] 调度 {sched_id} 不存在或已停用，跳过触发")
            return
        task = submit_task(
            user_id=spec["user_id"],
            task_name=spec["task_name"],
            target_mode=spec["target_mode"],
            payload=spec["payload"],
            session_id=spec["session_id"],
            timeout_seconds=spec["timeout_seconds"],
            max_retries=spec["max_retries"],
        )
        _persist_run_meta(sched_id, last_run_at=datetime.now(), last_task_id=task.id, run_delta=1)
        logger.info(f"[agent_sched] 调度 {sched_id} 已触发 → async_task {task.id}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[agent_sched] 调度 {sched_id} 触发失败: {e}")
        try:
            _persist_run_meta(sched_id, fail_delta=1)
        except Exception:
            pass


def _register_row(sched_id: int) -> None:
    """向 APScheduler 注册（或替换）单个调度任务并回填 next_run_at。"""
    svc = _get_base_scheduler()
    if svc is None:
        raise ScheduledTaskError("调度器不可用")
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None or sched.status != "enabled":
            return
        job_id = f"{_JOB_PREFIX}{sched_id}"
        svc.scheduler.add_job(
            func=_trigger_job,
            trigger=_build_trigger(sched),
            args=[sched_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )
        next_run = None
        try:
            job = svc.scheduler.get_job(job_id)
            next_run = getattr(job, "next_run_time", None)
        except Exception:
            pass
        _persist_run_meta(sched_id, next_run_at=next_run)
        logger.info(f"[agent_sched] 已注册调度 {sched_id} job={job_id}")
    finally:
        db.close()


def _remove_row(sched_id: int) -> None:
    svc = _get_base_scheduler()
    if svc is None:
        return
    try:
        svc.scheduler.remove_job(f"{_JOB_PREFIX}{sched_id}")
    except Exception:
        pass


def _sync_job(sched_id: int, *, enabled: bool) -> None:
    """根据当前状态同步 APScheduler job（注册 / 移除）。"""
    if not _should_register():
        return
    if not enabled:
        _remove_row(sched_id)
        return
    try:
        _register_row(sched_id)
    except Exception as e:
        logger.error(f"[agent_sched] 注册调度 {sched_id} 失败: {e}")


# ── 对外 API（router 调用） ──────────────────────────────────────────

def create_task(
    *,
    user_id: int,
    task_name: str,
    target_mode: str,
    prompt: str,
    schedule_type: str,
    agent_id: Optional[int] = None,
    team_id: Optional[int] = None,
    description: Optional[str] = None,
    session_id: Optional[str] = None,
    model_id: Optional[int] = None,
    cron_expression: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    run_at: Optional[datetime] = None,
    timezone: Optional[str] = None,
    skill_info: Optional[dict] = None,
) -> dict:
    _validate_target(target_mode, agent_id, team_id, prompt, skill_info)
    _validate_schedule_config(schedule_type, cron_expression, interval_seconds, run_at)

    db = SessionLocal()
    try:
        sched = AgentScheduledTask(
            task_name=task_name,
            user_id=user_id,
            description=description,
            target_mode=target_mode,
            agent_id=agent_id,
            team_id=team_id,
            skill_info=json.dumps(skill_info, ensure_ascii=False) if skill_info else None,
            prompt=prompt,
            session_id=str(session_id) if session_id else None,
            model_id=model_id,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            run_at=run_at,
            timezone=timezone or "Asia/Shanghai",
            status="enabled",
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
        data = sched.to_dict()
        sched_id = sched.id
    finally:
        db.close()

    _sync_job(sched_id, enabled=True)
    return data


def update_task(sched_id: int, user_id: Optional[int] = None, update: Optional[dict] = None) -> Optional[dict]:
    """更新调度任务（合并校验后重注册）。任务不存在/非本人/已删除返回 None。"""
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None or sched.status == "deleted":
            return None
        if user_id is not None and sched.user_id != user_id:
            return None
        upd = {k: v for k, v in (update or {}).items() if k in _ALLOWED_UPDATE_FIELDS}
        _validate_schedule_config(
            upd.get("schedule_type", sched.schedule_type),
            upd.get("cron_expression", sched.cron_expression),
            upd.get("interval_seconds", sched.interval_seconds),
            upd.get("run_at", sched.run_at),
        )
        # skill_info 入参为 dict，落库统一序列化为 JSON 字符串
        if "skill_info" in upd:
            upd["skill_info"] = (
                json.dumps(upd["skill_info"], ensure_ascii=False)
                if isinstance(upd["skill_info"], dict) and upd["skill_info"]
                else None
            )
        _validate_target(
            sched.target_mode,
            upd.get("agent_id", sched.agent_id),
            upd.get("team_id", sched.team_id),
            upd.get("prompt", sched.prompt),
            upd.get("skill_info", sched.skill_info),
        )
        for key, value in upd.items():
            setattr(sched, key, value)
        db.commit()
        data = sched.to_dict()
        status_val = sched.status
    finally:
        db.close()

    _sync_job(sched_id, enabled=(status_val == "enabled"))
    return data


def _set_status(sched_id: int, user_id: Optional[int], status: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None or sched.status == "deleted":
            return None
        if user_id is not None and sched.user_id != user_id:
            return None
        sched.status = status
        db.commit()
        data = sched.to_dict()
    finally:
        db.close()
    _sync_job(sched_id, enabled=(status == "enabled"))
    return data


def pause_task(sched_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    return _set_status(sched_id, user_id, "paused")


def resume_task(sched_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    return _set_status(sched_id, user_id, "enabled")


def delete_task(sched_id: int, user_id: Optional[int] = None) -> bool:
    """软删：status='deleted' 并移除调度 job。"""
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None or (user_id is not None and sched.user_id != user_id):
            return False
        if sched.status == "deleted":
            return True
        sched.status = "deleted"
        db.commit()
    finally:
        db.close()
    _sync_job(sched_id, enabled=False)
    return True


async def run_now(sched_id: int, user_id: Optional[int] = None) -> int:
    """立即执行一次调度任务（不改变调度计划），返回生成的异步任务 ID。"""
    spec = _load_spec(sched_id, user_id=user_id, require_enabled=False)
    if spec is None:
        raise ScheduledTaskError("调度任务不存在或无权操作")
    task = submit_task(
        user_id=spec["user_id"],
        task_name=spec["task_name"],
        target_mode=spec["target_mode"],
        payload=spec["payload"],
        session_id=spec["session_id"],
        timeout_seconds=spec["timeout_seconds"],
        max_retries=spec["max_retries"],
    )
    _persist_run_meta(sched_id, last_task_id=task.id)
    return task.id


def get_task(sched_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    db = SessionLocal()
    try:
        sched = db.get(AgentScheduledTask, sched_id)
        if sched is None or sched.status == "deleted":
            return None
        if user_id is not None and sched.user_id != user_id:
            return None
        return sched.to_dict()
    finally:
        db.close()


def list_tasks(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
):
    """查询调度任务列表（按归属用户过滤，支持状态筛选）。"""
    db = SessionLocal()
    try:
        q = db.query(AgentScheduledTask).filter(AgentScheduledTask.status != "deleted")
        if user_id is not None:
            q = q.filter(AgentScheduledTask.user_id == user_id)
        if status:
            q = q.filter(AgentScheduledTask.status == status)
        total = q.count()
        items = (
            q.order_by(AgentScheduledTask.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return total, [t.to_dict() for t in items]
    finally:
        db.close()


def register_all_enabled() -> int:
    """服务启动时恢复注册所有 enabled 调度任务（仅主进程执行）。"""
    if not _should_register():
        return 0
    if _get_base_scheduler() is None:
        logger.warning("[agent_sched] 调度器不可用，跳过启动注册")
        return 0
    db = SessionLocal()
    try:
        rows = (
            db.query(AgentScheduledTask.id)
            .filter(AgentScheduledTask.status == "enabled")
            .all()
        )
        ids = [r[0] for r in rows]
    finally:
        db.close()
    count = 0
    for sid in ids:
        try:
            _register_row(sid)
            count += 1
        except Exception as e:
            logger.error(f"[agent_sched] 启动注册调度 {sid} 失败: {e}")
    logger.info(f"[agent_sched] 启动注册 AI 调度任务 {count}/{len(ids)} 个")
    return count
