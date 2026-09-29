"""Agent/Skill 执行运行控制 API —— cancel + HITL confirm + SSE 订阅/回放（spec §5.3/§5.4/§6.3）。"""
import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.agent.agent_execution_event import AgentExecutionEvent
from app.schemas.agent.event_types import EventEnvelope, route_of
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

    # 权限控制：仅执行所有者可取消（与 confirm 端点一致——终审 BLK-03）
    from app.models.agent.agent_execution import AgentExecution
    row = db.query(AgentExecution).filter(
        AgentExecution.execution_id == execution_id).first()
    uid = getattr(current_user, "user_id", None)
    if (row is not None and row.user_id is not None and uid is not None
            and int(row.user_id) != int(uid)):
        raise HTTPException(status_code=403, detail="无权操作该执行")

    ok = reg.cancel(execution_id, reason="user_cancel")
    return {"ok": ok, "execution_id": execution_id, "interrupt_reason": "user_cancel"}


class ConfirmRequest(BaseModel):
    """HITL 确认请求（spec §5.4）。"""
    action: str = Field(..., pattern="^(approve|reject|interrupt)$")
    tool_calls: list[dict] = Field(default_factory=list)
    accept_rules: bool = False
    message: str = ""
    """人工意见：SOP 步骤验收驳回时填写原因（spec §4.9）。"""


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

    # SOP 步骤验收：改走引擎 resume 载荷（携带驳回原因），
    # 其余模式仍用 agentscope 确认事件，行为不变。
    resume_payload = None
    try:
        from app.ai.sop.agent import SOPAgent
        if isinstance(getattr(handle, "agent", None), SOPAgent):
            resume_payload = {
                "confirmed": req.action == "approve",
                "message": req.message or "",
            }
    except Exception:  # noqa: BLE001 - SOP 包不可用时不影响既有模式
        resume_payload = None

    resume_hitl(handle, req.action, req.tool_calls,
                resume_payload=resume_payload)
    return {"ok": True, "action": req.action, "execution_id": execution_id}


# ── SSE 实时订阅（P1.2：Last-Event-ID 断线重放）────────────────────────────

@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    request: Request,
    after_seq: Optional[int] = Query(None, alias="after_seq"),
    replay_only: bool = Query(False, alias="replay_only"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """实时订阅执行事件流（统一信封格式，spec §4.4 / §6.3）。

    - 支持 ``Last-Event-ID`` 请求头（SSE 规范自动重连）或 ``?after_seq=`` 补拉：
      服务端先从环形缓冲回放 seq > after_seq 的历史事件，再推送实时事件；
    - ``?replay_only=1`` 仅回放历史后即刻关闭连接（供只需补拉、不需要长连接的客户端）；
    - 每 15s 发送 ``: keep-alive`` 心跳保活；
    - 事件格式为 ``id: <seq>\\nevent: <event_type>\\ndata: <envelope json>\\n\\n``。
    """
    last_seq = after_seq
    lei = request.headers.get("Last-Event-ID")
    if lei is not None:
        try:
            last_seq = int(lei)
        except (TypeError, ValueError):
            pass

    from app.ai.events.sse_handler import get_sse_handler
    from app.ai.events.adapter import envelope_to_sse
    handler = get_sse_handler()

    async def event_source():
        replay, q = handler.subscribe(execution_id, last_seq)
        for env in replay:
            yield envelope_to_sse(env)
        if replay_only:
            return
        # 每秒轮询一次客户端断开，避免连接关闭后生成器悬挂（生产侧防泄漏）；
        # 每 15s 发送一次 keep-alive 心跳保活。
        last_keepalive = time.monotonic()
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    env = await asyncio.wait_for(q.get(), timeout=1)
                except asyncio.TimeoutError:
                    if time.monotonic() - last_keepalive >= 15:
                        yield ": keep-alive\n\n"
                        last_keepalive = time.monotonic()
                    continue
                yield envelope_to_sse(env)
        finally:
            handler.unsubscribe(execution_id, q)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 事件回放 API（P1.4：DB 落库回放，与流式输出一致）──────────────────────

@router.get("/{execution_id}/events")
async def get_execution_events(
    execution_id: str,
    after_seq: int = Query(0, alias="after_seq"),
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """回放执行事件（DB 落库，按 sequence 升序；spec §6.3）。

    返回与 /stream 一致的统一信封；levels 由 event_type 经 route_of 还原，
    保证回放与流式格式统一。
    """
    rows = (
        db.query(AgentExecutionEvent)
        .filter(
            AgentExecutionEvent.execution_id == execution_id,
            AgentExecutionEvent.sequence > after_seq,
        )
        .order_by(AgentExecutionEvent.sequence.asc())
        .limit(limit)
        .all()
    )

    events = []
    for r in rows:
        route = route_of(r.event_type)
        envelope = EventEnvelope(
            sequence=r.sequence,
            execution_id=r.execution_id,
            trace_id=r.trace_id,
            event_type=r.event_type,
            category=r.category or route.category,
            levels=sorted(route.levels),
            content=r.content or {},
            source=r.source,
            source_id=r.source_id,
            reply_id=r.reply_id,
            block_id=r.block_id,
            tool_call_id=r.tool_call_id,
            interrupt_reason=r.interrupt_reason,
            ui_hint=r.ui_hint or route.ui_hint,
            event_version=r.event_version or 1,
            metadata=r.event_metadata or {},
        )
        events.append(envelope.model_dump(mode="json", exclude_none=True))

    return {"execution_id": execution_id, "after_seq": after_seq, "events": events}
