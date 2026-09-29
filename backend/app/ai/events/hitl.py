"""HITL 协调器 —— 暂停记录、恢复与超时（spec §5.4/§5.5）。

resume_hitl 供 confirm API 调用：向暂停中的 Agent 发送
UserConfirmResultEvent / UserInterruptEvent 并续跑事件流。
Skill 与 Agent 执行共用（统一运行时声明见 spec §5）。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

PAUSE_TIMEOUT_MINUTES = 30


def record_pause(db: Any, *, execution_id: str, reply_id: Optional[str] = None,
                 tool_calls: Optional[list] = None,
                 suggested_rules: Optional[list] = None,
                 timeout_minutes: int = PAUSE_TIMEOUT_MINUTES) -> Optional[int]:
    """写入 HITL 暂停记录（status=waiting）。吞异常：不阻断执行流。"""
    from app.models.agent.agent_hitl_pause import AgentHitlPause

    try:
        row = AgentHitlPause(
            execution_id=execution_id, reply_id=reply_id,
            tool_calls=tool_calls, suggested_rules=suggested_rules,
            status="waiting",
            timeout_at=datetime.now() + timedelta(minutes=timeout_minutes),
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_pause 失败 {}: {}", execution_id, e)
        return None


def resolve_pause(db: Any, *, execution_id: str, action: str,
                  accept_rules: bool = False) -> Optional[int]:
    """action ∈ approve/reject/interrupt；更新最近一条 waiting 记录。"""
    from app.models.agent.agent_hitl_pause import AgentHitlPause

    status_map = {"approve": "approved", "reject": "rejected",
                  "interrupt": "interrupted"}
    try:
        row = (db.query(AgentHitlPause)
               .filter(AgentHitlPause.execution_id == execution_id,
                       AgentHitlPause.status == "waiting")
               .order_by(AgentHitlPause.id.desc())
               .first())
        if row is None:
            return None
        row.status = status_map[action]
        row.accept_rules = 1 if accept_rules else 0
        row.answered_at = datetime.now()
        db.commit()
        return row.id
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("resolve_pause 失败 {}: {}", execution_id, e)
        return None


def build_resume_event(action: str, reply_id: Optional[str],
                       tool_calls: list[dict]) -> Any:
    """构造恢复事件：approve→确认；reject→拒绝；interrupt→UserInterruptEvent。"""
    from agentscope.event import ConfirmResult, UserConfirmResultEvent, UserInterruptEvent
    from agentscope.message import ToolCallBlock

    if action == "interrupt":
        return UserInterruptEvent(reply_id=reply_id)
    tcs = [ToolCallBlock(id=tc["id"], name=tc["name"],
                         input=tc.get("input", "{}")) for tc in tool_calls]
    confirmed = action == "approve"
    return UserConfirmResultEvent(
        reply_id=reply_id,
        confirm_results=[ConfirmResult(confirmed=confirmed, tool_call=tc,
                                       rules=None) for tc in tcs],
    )


def resume_hitl(handle: Any, action: str,
                tool_calls: Optional[list[dict]] = None,
                resume_payload: Optional[dict] = None) -> bool:
    """恢复暂停中的执行：新起 consumer 续跑 agent.reply_stream(恢复事件)。

    handle.status 置回 running，并向 out_q 投递 hitl_resume 控制事件
    （execute 主循环 yield 它时发布信封并更新主记录状态）。
    新 consumer 结束（含异常）时投递哨兵唤醒主循环——与 execute() 的
    done_callback 哨兵机制一致，否则恢复完成后主循环会误判超时。

    ``resume_payload`` 用于 SOP 人工验收路径（spec §4.9）：SOP 引擎以
    ``{"confirmed", "message"}`` 载荷结算验收，既不接受 agentscope 确认事件，
    也需要携带驳回原因，故与工具授权路径分开驱动。其余行为完全一致。
    """
    from app.ai.skills.execution import SkillEvent

    if resume_payload is None:
        tcs = tool_calls or getattr(handle.handler, "hitl_tool_calls", []) or []
        if action == "interrupt" and handle.handler is not None:
            # interrupt 恢复路径：ReplyEnd 的 finished_reason 应记为 interrupted
            handle.handler.interrupted_flag = True
        event = build_resume_event(action, handle.reply_id, tcs)

        async def _resume() -> None:
            async for ev in handle.agent.reply_stream(inputs=event):
                await handle.handler.handle(ev)
    else:
        async def _resume() -> None:
            async for ev in handle.agent.reply_stream(
                inputs=None, resume=resume_payload
            ):
                await handle.handler.handle(ev)

    def _on_resumed_done(_task: asyncio.Task) -> None:
        try:
            handle.out_q.put_nowait(None)
        except Exception:
            pass

    handle.task = asyncio.create_task(_resume())
    handle.task.add_done_callback(_on_resumed_done)
    handle.status = "running"
    if handle.out_q is not None:
        handle.out_q.put_nowait(
            SkillEvent(type="hitl_resume", data={"action": action}))
    return True


async def monitor_pause_timeout(db: Any, execution_id: str, 
                                reply_id: Optional[str], pause_time: datetime,
                                timeout_minutes: int = PAUSE_TIMEOUT_MINUTES):
    """后台监控 HITL 暂停超时：达到阈值后发送告警 + 可选熔断。

    流程：
    1. 休眠 timeout_minutes*60 秒
    2. 检查记录是否仍为 waiting 态 → 若已 resolve，直接返回
    3. 发送超长等待告警（DB+STREAM）
    4. 标记为超时中断（status=interrupted），record_paused 自动触发 SSE
    
    注意：此函数由执行侧在 yield hitl_pause 后立即 spawn 守护协程启动
    """
    import time as time_mod

    await asyncio.sleep(timeout_minutes * 60)

    try:
        # Import here to avoid circular dependency
        from app.models.agent.agent_hitl_pause import AgentHitlPause
        
        row = (db.query(AgentHitlPause)
               .filter(AgentHitlPause.execution_id == execution_id,
                       AgentHitlPause.status == "waiting")
               .order_by(AgentHitlPause.id.desc())
               .first())
        if row is None:
            # 已被 resolve（用户提前 approve/reject），不触发告警
            return

        # 超长等待告警
        wait_seconds = (datetime.now() - pause_time).total_seconds()
        logger.warning("HITL 暂停已等待 %.0f 分钟（超过 %d 分钟阈值）",
                       wait_seconds / 60, timeout_minutes)

        # DB 落库 + SSE 推送
        db.add(AgentHitlPause(
            execution_id=execution_id,
            reply_id=reply_id,
            status="timeout_alert",
            timeout_at=datetime.now(),
        ))
        db.commit()

        # 发送告警事件（仅 STREAM+UI，不落库避免重复）
        from app.ai.events.bus import EventBus
        from app.schemas.agent.event_types import EventEnvelope, EventCategory, EventLevel
        bus = EventBus()
        bus.publish(EventEnvelope(
            execution_id=execution_id,
            event_type="hitl_timeout_alert",
            category=EventCategory.HITL,
            levels=[EventLevel.STREAM, EventLevel.UI],
            content={
                "message": f"HITL 暂停超时警告（已等待 {wait_seconds // 60} 分钟）",
                "timeout_minutes": timeout_minutes,
                "pause_time": pause_time.isoformat(),
            },
            source="hitl_monitor",
            ui_hint="alert",
        ))

    except Exception as e:
        logger.error("HITL 超时监控失败：%s: %s", execution_id, e)
