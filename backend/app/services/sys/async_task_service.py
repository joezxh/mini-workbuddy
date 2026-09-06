"""云端调度异步任务服务（SCHEDULED 模式后端）

复用现有调度框架：
- 调度执行复用 app.state.scheduler_service（TaskSchedulerService 封装的进程内 APScheduler）
- 执行逻辑复用 UnifiedAgentGateway（与同步/流式通道一致）

任务生命周期：
  queued -> running -> completed / failed / cancelled

设计要点：
- 用户提交即异步执行（一次性），通过 DateTrigger(run_date=now+1s) 投递到调度器；
  若调度器不可用则降级为当前事件循环 asyncio.create_task 兜底。
- 全局并发上限由 _GLOBAL_SEM 控制（上限来自 settings.ASYNC_TASK_MAX_CONCURRENCY）。
- 超时 / 指数退避重试来自 settings（ASYNC_TASK_BACKOFF_BASE / CAP）。
- 失败分类：仅「非业务性失败」（超时 / 连接 / 系统异常）重试；
  「业务性失败」（参数错误等 BusinessError）直接 failed 不重试。
- 取消：cancel_task 置 cancel_requested=1；running 任务在每步轮询该标记主动中断（APScheduler 的
  remove_job 只能取消未开始的 job，无法中断已在跑的协程）。
- 监控：内存计数器累计 queued/running/done/failed/重试；失败率超阈值 + 失败外发告警
  （ASYNC_TASK_FAILURE_ALERT_ENABLED + webhook，复用钉钉/飞书/Slack webhook 语义）。
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Optional

import requests
from sqlalchemy import update
from app.db.database import SessionLocal
from app.models.agent.agent_async_task import AgentAsyncTask
from app.config import settings

logger = logging.getLogger(__name__)

# 全局并发信号量（容量来自配置）
_GLOBAL_SEM = asyncio.Semaphore(max(1, settings.ASYNC_TASK_MAX_CONCURRENCY))

# 内存统计（进程级，仅用于监控/告警；非持久）
_STATS_LOCK = threading.Lock()
_STATS = {
    "submitted": 0,
    "running": 0,
    "done": 0,
    "failed": 0,
    "cancelled": 0,
    "retries": 0,
}


class BusinessError(Exception):
    """业务性失败：参数错误等，不重试。"""


def _inc_stat(key: str, n: int = 1) -> None:
    with _STATS_LOCK:
        _STATS[key] = _STATS.get(key, 0) + n


def get_stats() -> dict:
    """返回当前进程内统计快照（供 /metrics 或运维看板）。"""
    with _STATS_LOCK:
        snap = dict(_STATS)
    snap["config_concurrency"] = settings.ASYNC_TASK_MAX_CONCURRENCY
    return snap


def _is_business_error(exc: BaseException) -> bool:
    return isinstance(exc, (BusinessError, ValueError, TypeError, KeyError, AttributeError))


def _backoff_seconds(retry_count: int) -> float:
    base = settings.ASYNC_TASK_BACKOFF_BASE
    cap = settings.ASYNC_TASK_BACKOFF_CAP
    return min(base * (2 ** max(0, retry_count - 1)), cap)


def _should_register_job() -> bool:
    """多 worker 部署时，若开启 PRIMARY_ONLY，仅主进程（app.state.is_primary）注册 job，
    避免 APScheduler 非分布式导致的重复调度。"""
    if not settings.ASYNC_TASK_SCHEDULER_PRIMARY_ONLY:
        return True
    try:
        from app.main import app as _app  # 延迟导入避免循环
    except Exception:
        return True
    return bool(getattr(_app.state, "is_primary", True))


def submit_task(
    *,
    user_id: int,
    task_name: str,
    target_mode: str,
    payload: Optional[dict] = None,
    session_id: Optional[str] = None,
    priority: int = 5,
    timeout_seconds: int = 1800,
    max_retries: int = 2,
) -> AgentAsyncTask:
    """提交一个异步任务。复用调度器立即投递，或降级到 asyncio。"""
    import json
    import uuid

    db = SessionLocal()
    try:
        task = AgentAsyncTask(
            task_no=f"AT{uuid.uuid4().hex[:12].upper()}",
            session_id=session_id,
            user_id=user_id,
            task_name=task_name,
            target_mode=target_mode,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
            status="queued",
            priority=priority,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_count=0,
            cancel_requested=False,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
        task_no = task.task_no
    finally:
        db.close()

    _inc_stat("submitted")
    _dispatch_now(task_id)

    return AgentAsyncTask(id=task_id, task_no=task_no, status="queued", priority=priority)


def _get_scheduler():
    try:
        from app.main import app
        return getattr(app.state, "scheduler_service", None)
    except Exception as e:
        logger.warning(f"[async_task] 获取调度器失败: {e}")
        return None


def _dispatch_now(task_id: int) -> None:
    """立即投递任务到调度器执行（submit / retry 共用）。

    调度器不可用或非主进程时降级为当前事件循环 asyncio.create_task。
    """
    scheduler = _get_scheduler()
    run_at = datetime.now() + timedelta(seconds=1)
    try:
        if scheduler is not None and _should_register_job():
            scheduler.scheduler.add_job(
                func=_run_task,
                trigger="date",
                run_date=run_at,
                id=f"async_{task_id}",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info(f"[async_task] 已投递调度器 task_id={task_id} run_at={run_at.isoformat()}")
        else:
            if scheduler is None:
                logger.warning("[async_task] 调度器不可用，降级为 asyncio.create_task 即时执行")
            else:
                logger.info("[async_task] PRIMARY_ONLY 模式非主进程，跳过调度器注册（由主进程托管）")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                asyncio.create_task(_run_task(task_id))
            else:
                logger.error(f"[async_task] 无事件循环且调度器不可用，任务 {task_id} 无法执行")
    except Exception as e:
        logger.error(f"[async_task] 调度投递失败，降级 asyncio: {e}")
        try:
            asyncio.create_task(_run_task(task_id))
        except RuntimeError:
            logger.error(f"[async_task] 降级也失败，任务 {task_id} 滞留 queued")


def _update_execution_id(task_id: int, execution_id: str) -> None:
    """任务启动即落库 execution_id（独立短事务）。

    使前端在任务运行中即可通过 /agent-execution/{id}/unified-events
    实时回放思考过程 / 执行事件 / 时间线，无需等待任务完成。
    """
    try:
        db = SessionLocal()
        try:
            db.execute(
                update(AgentAsyncTask)
                .where(AgentAsyncTask.id == task_id)
                .values(execution_id=execution_id)
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[async_task] 更新 execution_id 失败 task={task_id}: {e}")


async def _run_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.get(AgentAsyncTask, task_id)
        if task is None:
            logger.warning(f"[async_task] task {task_id} 不存在，跳过")
            return
        if task.status in ("completed", "failed", "cancelled"):
            logger.info(f"[async_task] task {task_id} 已终态({task.status})，跳过")
            return
        if task.cancel_requested:
            await _finalize(db, task, "cancelled", error_message="用户取消（未开始）")
            return

        task.status = "running"
        task.started_at = datetime.now()
        db.commit()

        async with _GLOBAL_SEM:
            _inc_stat("running")
            try:
                await _execute_and_collect(db, task)
                await _finalize(db, task, "completed")
                _inc_stat("done")
                logger.info(f"[async_task] task {task_id} 完成")
            except asyncio.CancelledError:
                await _finalize(db, task, "cancelled", error_message="用户取消（执行中中断）")
                _inc_stat("cancelled")
                logger.info(f"[async_task] task {task_id} 已被取消")
            except Exception as e:  # noqa: BLE001
                await _handle_failure(db, task, e)
            finally:
                _inc_stat("running", -1)
    finally:
        db.close()


async def _execute_and_collect(db, task: AgentAsyncTask) -> None:
    """执行 Agent/Team/Skill，并通过 cancel_requested 轮询实现主动中断。

    TODO: 替换为 AgentScope 原生 Agent API（旧 Gateway 已移除）。
    """
    import json

    payload = json.loads(task.payload) if task.payload else {}
    message = payload.get("message", "")
    agent_id = payload.get("agent_id")
    team_id = payload.get("team_id")
    target_mode = (task.target_mode or "agent").lower()

    pre_execution_id = str(uuid.uuid4())

    async def _run_once():
        if task.cancel_requested:
            raise asyncio.CancelledError()
        if not message and not agent_id and not team_id:
            raise BusinessError("payload 缺少 message 或 agent_id/team_id")
        await asyncio.to_thread(_update_execution_id, task.id, pre_execution_id)
        # TODO: 使用 AgentFactory + SSEBridge 替代旧 Gateway dispatch_stream
        raise NotImplementedError(
            f"异步任务执行模式 '{target_mode}' 待 AgentScope 原生 API 适配"
        )

    try:
        result = await asyncio.wait_for(_run_once(), timeout=task.timeout_seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"执行超时（>{task.timeout_seconds}s）")

    task.result_data = result
    task.progress = 100.0
    task.finished_at = datetime.now()
    db.commit()


async def _handle_failure(db, task: AgentAsyncTask, exc: BaseException) -> None:
    is_business = _is_business_error(exc)
    err_msg = f"{type(exc).__name__}: {exc}"

    if task.retry_count < task.max_retries and not is_business:
        task.retry_count += 1
        _inc_stat("retries")
        backoff = _backoff_seconds(task.retry_count)
        logger.warning(
            f"[async_task] task {task.id} 第{task.retry_count}次重试（{err_msg}），{backoff:.0f}s 后"
        )
        task.status = "queued"
        task.error_message = err_msg
        task.started_at = None
        db.commit()
        scheduler = _get_scheduler()
        if scheduler is not None and _should_register_job():
            scheduler.scheduler.add_job(
                func=_run_task,
                trigger="date",
                run_date=datetime.now() + timedelta(seconds=backoff),
                id=f"async_{task.id}",
                replace_existing=True,
                misfire_grace_time=3600,
            )
        else:
            asyncio.create_task(_delayed_retry(task.id, backoff))
        return

    await _finalize(db, task, "failed", error_message=err_msg)
    _inc_stat("failed")
    logger.error(f"[async_task] task {task.id} 最终失败: {err_msg}")
    _maybe_alert(task, err_msg)


async def _delayed_retry(task_id: int, backoff: float) -> None:
    await asyncio.sleep(backoff)
    await _run_task(task_id)


async def _finalize(
    db, task: AgentAsyncTask, status: str, *, error_message: Optional[str] = None
) -> None:
    task.status = status
    if error_message is not None:
        task.error_message = error_message
    if status in ("completed", "failed", "cancelled") and task.finished_at is None:
        task.finished_at = datetime.now()
    db.commit()
    # 站内通知
    try:
        from app.services.sys.sys_notification_service import notify_user
        _notify_title = {
            "completed": f"异步任务完成：{task.task_name}",
            "failed": f"异步任务失败：{task.task_name}",
            "cancelled": f"异步任务已取消：{task.task_name}",
        }.get(status, f"异步任务更新：{task.task_name}")
        notify_user(
            user_id=task.user_id,
            ntype="async_task",
            title=_notify_title,
            content=error_message or (task.result_data or "")[:500],
            ref_id=task.id,
            ref_type="agent_async_task",
        )
    except Exception as e:
        logger.warning(f"[async_task] 站内通知失败(忽略): {e}")


def _maybe_alert(task: AgentAsyncTask, err_msg: str) -> None:
    """失败率阈值告警 + 可选外发 webhook。"""
    with _STATS_LOCK:
        done_total = _STATS["done"] + _STATS["failed"]
        fail_rate = (_STATS["failed"] / done_total) if done_total else 0.0
    if fail_rate >= settings.ASYNC_TASK_ALERT_FAILURE_RATE:
        logger.warning(
            f"[async_task] 失败率告警: {fail_rate:.1%} (阈值 {settings.ASYNC_TASK_ALERT_FAILURE_RATE:.1%})"
        )
    if settings.ASYNC_TASK_FAILURE_ALERT_ENABLED and settings.ASYNC_TASK_FAILURE_ALERT_WEBHOOK:
        try:
            text_msg = (
                f"【异步任务失败告警】\n任务: {task.task_name} (id={task.id})\n"
                f"用户: {task.user_id}\n错误: {err_msg}"
            )
            requests.post(
                settings.ASYNC_TASK_FAILURE_ALERT_WEBHOOK,
                json={"msgtype": "text", "text": {"content": text_msg}},
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"[async_task] 外发告警失败(忽略): {e}")


def get_task(task_id: int) -> Optional[AgentAsyncTask]:
    db = SessionLocal()
    try:
        return db.get(AgentAsyncTask, task_id)
    finally:
        db.close()


def list_tasks(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    target_mode: Optional[str] = None,
    page: int = 1,
    size: int = 20,
):
    """查询任务列表。status 支持逗号分隔多状态（如 "queued,running"）。"""
    db = SessionLocal()
    try:
        q = db.query(AgentAsyncTask)
        if user_id is not None:
            q = q.filter(AgentAsyncTask.user_id == user_id)
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                q = q.filter(AgentAsyncTask.status.in_(statuses))
        if target_mode:
            q = q.filter(AgentAsyncTask.target_mode == target_mode)
        total = q.count()
        items = (
            q.order_by(AgentAsyncTask.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return total, items
    finally:
        db.close()


def cancel_task(task_id: int, user_id: Optional[int] = None) -> bool:
    """取消任务：置 cancel_requested=1（running 任务主动中断）；未开始的从调度器移除 job。

    user_id 提供时校验任务归属，非本人任务返回 False。
    """
    db = SessionLocal()
    try:
        task = db.get(AgentAsyncTask, task_id)
        if task is None:
            return False
        if user_id is not None and task.user_id != user_id:
            return False
        if task.status in ("completed", "failed", "cancelled"):
            return False
        task.cancel_requested = True
        db.commit()

        scheduler = _get_scheduler()
        if scheduler is not None:
            try:
                scheduler.scheduler.remove_job(f"async_{task_id}")
                logger.info(f"[async_task] 已从调度器移除 job async_{task_id}")
            except Exception:
                pass  # 可能已在运行或不存在
        # 若尚未 running，直接置为 cancelled
        if task.status == "queued":
            task.status = "cancelled"
            task.finished_at = datetime.now()
            task.error_message = "用户取消"
            db.commit()
            _inc_stat("cancelled")
            try:
                from app.services.sys.sys_notification_service import notify_user
                notify_user(
                    user_id=task.user_id,
                    ntype="async_task",
                    title=f"异步任务已取消：{task.task_name}",
                    ref_id=task.id,
                    ref_type="agent_async_task",
                )
            except Exception:
                pass
        return True
    finally:
        db.close()


def retry_task(task_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    """手动重试终态任务（failed/cancelled）：重置状态并重新投递。

    - 仅任务归属人可重试；任务不存在或非本人返回 None
    - 非终态任务抛 BusinessError（router 转 400）
    - retry_count 保持累计值（与自动退避重试共用字段，仅展示用途）
    - 返回重置后的任务 dict
    """
    db = SessionLocal()
    try:
        task = db.get(AgentAsyncTask, task_id)
        if task is None or (user_id is not None and task.user_id != user_id):
            return None
        if task.status not in ("failed", "cancelled"):
            raise BusinessError("仅失败或已取消的任务可重试")
        task.status = "queued"
        task.progress = 0.0
        task.cancel_requested = False
        task.error_message = None
        task.result_data = None
        task.execution_id = None
        task.started_at = None
        task.finished_at = None
        db.commit()
        data = task.to_dict()
    finally:
        db.close()

    _inc_stat("submitted")
    _dispatch_now(task_id)
    logger.info(f"[async_task] task {task_id} 已由用户手动重试")
    return data
