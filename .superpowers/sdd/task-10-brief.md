# Agent 事件体系 P0（止血）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec `docs/superpowers/specs/2026-09-21-agent-event-architecture-design.md` 的 P0：统一事件枚举单一来源、EventEnvelope + EventBus 分级（delta 停止落库）、修复执行主记录存根、超时熔断生效、DDL 47；并使 **Skill 执行与 Agent 一致**——AgentRunRegistry 中断（强制终止/用户取消/超时）、HITL 全链路（暂停/确认/拒绝/中断/超时/权限）、七模式动态切换（`ENGINE_DECISION` 引擎路由）。

**Architecture:** 新建 `app/schemas/agent/event_types.py` 作为事件枚举/类别/级别/路由/别名的唯一权威来源，schemas 与 models 双处删除本地枚举改为 re-export；`ExecutionEventService` 增加 envelope 入口并按级别过滤 DB 写入；新建 `EventBus`（Log + DB 双 handler 委托）；重写 `SkillEventHandler`（修复 `lambda: yield` 语法错误，delta 仅走 SSE、块级汇总落库、补 reply_id/tool_call_id/token 统计）；`execute()` 接入真实执行主记录、总超时熔断，并注册进 `AgentRunRegistry`（cancel API 触达）；HITL 经 `agent_hitl_pause` 表 + confirm API（approve/reject/interrupt）+ `UserConfirmResultEvent`/`UserInterruptEvent` 恢复；`resolve_execution_mode()` 实现七模式动态分派（llm/plan/team/knowledge 路由，workflow 明确报错）。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / agentscope 2.0.8 / pytest。

**范围外（P1/P2 另立计划）**：SSE Last-Event-ID 重连与 `after_seq` 补拉 / 前端改造（EventRouter/HITL 面板/Debug Panel）/ `AgentScopeEventAdapter` 双通道合并 / ConfigValidator / Custom 扩展通道 / `AgentState` 跨进程恢复 / workflow(Dify) 模式引擎接入。

**关键约束（执行前必读）：**

1. 当前 `app/ai/skills/execution.py` **无法 import**（`yield_fn=lambda evt: yield evt` 是语法错误，出现两处）。Task 7 会重写该段。
2. 统一枚举用**普通 `str` 子类**（非 `Enum`），保持 `ExecutionEventType.TEXT == "text"` 为 True —— 与现存 schemas 版行为一致，避免 `str,Enum` 相等性陷阱。
3. P0 **不改 SSE 载荷**：`SkillEvent.type` 仍输出 `text/thinking/tool_call/tool_result/done/error` 等旧值，前端零改动。DB 中 `event_type` 值经归一化变为 `text_chunk` 等 —— 前端时间线本就期望 `text_chunk`，兼容性反而提升。
4. 测试不依赖真实数据库：DB 触点用 Fake 对象；async 测试用 `asyncio.run()` 包装（仓库未确认装有 pytest-asyncio）。
5. 数据库为 **PostgreSQL**（alembic env.py / 45/46 号脚本 / database.py 均为证）：DDL 47 用 PG 方言，`ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` 保证幂等可重复执行。
6. 每个任务结束跑 `cd backend && python -m pytest tests/unit -q` 确认无回归，再 commit。

---


### Task 10: HITL 全链路（暂停/确认/拒绝/中断/超时/权限）

**Files:**
- Create: `backend/app/ai/events/hitl.py`
- Modify: `backend/app/routers/agent/agent_run.py`（追加 confirm 端点）
- Modify: `backend/app/ai/skills/execution.py`（handler HITL 分支 + 主循环控制面）
- Modify: `backend/app/ai/skills/execution_records.py`（新增 `record_execution_status`）
- Modify: `backend/app/services/agent/agent_execution_service.py`（恢复 AgentHitlPause import）
- Test: `backend/tests/unit/test_hitl_coordinator.py`

**先决验证**（事件/块构造参数以安装版为准）：

```bash
cd backend && python -c "
from agentscope.event import RequireUserConfirmEvent, UserConfirmResultEvent, UserInterruptEvent, ConfirmResult
from agentscope.message import ToolCallBlock, ToolCallState
for cls in (RequireUserConfirmEvent, UserConfirmResultEvent, UserInterruptEvent, ConfirmResult, ToolCallBlock):
    print(cls.__name__, getattr(cls, 'model_fields', None) or cls.__annotations__)
"
```

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_hitl_coordinator.py`：

```python
"""HITL 全链路单测：暂停→确认恢复 / build_resume_event / 暂停记录落库。"""
import asyncio
from datetime import datetime

from agentscope.event import (
    RequireUserConfirmEvent, ReplyEndEvent,
    UserConfirmResultEvent, UserInterruptEvent,
)

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService
from app.ai.events.hitl import build_resume_event, record_pause, resolve_pause, PAUSE_TIMEOUT_MINUTES
from app.ai.events.registry import get_run_registry


# ── 纯函数层 ─────────────────────────────────────────────────────────────

def test_build_resume_event_approve_reject_interrupt():
    tcs = [{"id": "tc1", "name": "Bash", "input": '{"cmd":"ls"}'}]
    ev = build_resume_event("approve", "r1", tcs)
    assert isinstance(ev, UserConfirmResultEvent)
    assert ev.confirm_results[0].confirmed is True

    ev2 = build_resume_event("reject", "r1", tcs)
    assert ev2.confirm_results[0].confirmed is False

    ev3 = build_resume_event("interrupt", "r1", [])
    assert isinstance(ev3, UserInterruptEvent)


# ── 暂停记录（FakeDB）────────────────────────────────────────────────────

class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
    def filter(self, *a, **kw):
        return self
    def order_by(self, *a, **kw):
        return self
    def first(self):
        return self._rows[0] if self._rows else None


class FakeHitlRow:
    def __init__(self):
        self.execution_id = "e1"
        self.status = "waiting"
        self.accept_rules = 0
        self.answered_at = None
        self.tool_calls = [{"id": "tc1", "name": "Bash"}]


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
    def add(self, o):
        self.added.append(o)
    def commit(self):
        pass
    def query(self, model):
        return FakeQuery(self.rows)


def test_record_and_resolve_pause():
    db = FakeDB()
    record_pause(db, execution_id="e1", reply_id="r1",
                 tool_calls=[{"id": "tc1", "name": "Bash"}])
    row = db.added[0]
    assert row.status == "waiting"
    assert row.timeout_at is not None
    assert (row.timeout_at - datetime.now()).total_seconds() > 0

    db.rows = [row]
    assert resolve_pause(db, execution_id="e1", action="approve",
                         accept_rules=True) is not None
    assert row.status == "approved" and row.accept_rules == 1

    row2 = FakeHitlRow()
    db.rows = [row2]
    resolve_pause(db, execution_id="e1", action="interrupt")
    assert row2.status == "interrupted"


# ── 端到端：execute 暂停 → resume_hitl 恢复 ─────────────────────────────

class FakeHitlAgent:
    """两段式：首轮 yield RequireUserConfirmEvent 后流结束（暂停）；
    第二次调用（恢复事件）yield ReplyEndEvent。"""
    def __init__(self):
        self.inputs = []

    async def reply_stream(self, inputs):
        self.inputs.append(inputs)
        if isinstance(inputs, (UserConfirmResultEvent, UserInterruptEvent)):
            yield ReplyEndEvent(reply_id="r1", session_id="s")
        else:
            yield RequireUserConfirmEvent(reply_id="r1", tool_calls=[
                # 构造参数以先决验证输出为准；至少含 id/name/input
            ])


def _patch(monkeypatch, svc, agent):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: agent)
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_status", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr("app.db.database.SessionLocal", lambda: FakeDB())


def test_execute_hitl_pause_then_resume(monkeypatch):
    agent = FakeHitlAgent()
    svc = SkillExecutionService(timeout=30)
    _patch(monkeypatch, svc, agent)

    async def run():
        from app.ai.events.hitl import resume_hitl

        async def confirmer():
            for _ in range(200):
                h = get_run_registry().get("exec-hitl")
                if h is not None and h.status == "waiting_hitl":
                    resume_hitl(h, "approve")
                    return
                await asyncio.sleep(0.02)
        asyncio.create_task(confirmer())
        return [e async for e in svc.execute("demo", "hi", execution_id="exec-hitl")]

    evts = asyncio.run(run())
    types = [e.type for e in evts]
    assert "hitl_pause" in types
    assert "hitl_resume" in types
    assert types[-1] == "done"
    # Agent 被调用两次：初始输入 + 恢复事件
    assert len(agent.inputs) == 2
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_hitl_coordinator.py -v
```

Expected: FAIL，`ModuleNotFoundError: app.ai.events.hitl`（部分用例因 `RequireUserConfirmEvent` 构造参数不匹配也可能 FAIL，按先决验证输出修正）。

- [ ] **Step 3: 实现 HITL Coordinator**

创建 `backend/app/ai/events/hitl.py`：

```python
"""HITL 协调器 —— 暂停记录、恢复与超时（spec §5.4/§5.5）。

resume_hitl 供 confirm API 调用：向暂停中的 Agent 发送
UserConfirmResultEvent / UserInterruptEvent 并续跑事件流。
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
                tool_calls: Optional[list[dict]] = None) -> bool:
    """恢复暂停中的执行：新起 consumer 续跑 agent.reply_stream(恢复事件)。

    handle.status 置回 running，并向 out_q 投递 hitl_resume 控制事件
    （execute 主循环 yield 它时发布信封并更新主记录状态）。
    """
    from app.ai.skills.execution import SkillEvent

    tcs = tool_calls or getattr(handle.handler, "hitl_tool_calls", []) or []
    event = build_resume_event(action, handle.reply_id, tcs)

    async def _resume() -> None:
        async for ev in handle.agent.reply_stream(inputs=event):
            await handle.handler.handle(ev)

    handle.task = asyncio.create_task(_resume())
    handle.status = "running"
    if handle.out_q is not None:
        handle.out_q.put_nowait(
            SkillEvent(type="hitl_resume", data={"action": action}))
    return True
```

- [ ] **Step 4: confirm 端点 + 悬空 import 修复**

(a) `backend/app/routers/agent/agent_run.py` 追加（顶部补 `from pydantic import BaseModel, Field`）：

```python
class ConfirmRequest(BaseModel):
    """HITL 确认请求。"""
    action: str = Field(..., pattern="^(approve|reject|interrupt)$")
    tool_calls: list[dict] = Field(default_factory=list)
    accept_rules: bool = False


@router.post("/{execution_id}/confirm")
def confirm_execution(
    execution_id: str,
    req: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """人机交互确认：approve / reject / interrupt。"""
    reg = get_run_registry()
    handle = reg.get(execution_id)
    if handle is None or handle.status != "waiting_hitl":
        raise HTTPException(status_code=409, detail="执行不在 HITL 暂停状态")

    # 权限控制：仅执行所有者可确认（spec §5.4）
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
```

(b) `backend/app/services/agent/agent_execution_service.py` 中把注释行：

```python
# TODO: 域特定模型已移除
# from app.models.agent_hitl_pause import AgentHitlPause
```

替换为：

```python
from app.models.agent.agent_hitl_pause import AgentHitlPause
```

（修复 `_hitl_to_items` 的悬空 `NameError`。）

(c) `backend/app/ai/skills/execution_records.py` 追加：

```python
def record_execution_status(db: Any, execution_id: str, status: str) -> None:
    """仅更新执行状态（HITL 暂停/恢复等中间态）。"""
    try:
        row = _get_row(db, execution_id)
        if row is None:
            return
        row.status = status
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_status 失败 %s: %s", execution_id, e)
```

- [ ] **Step 5: handler 与主循环接入 HITL**

修改 `backend/app/ai/skills/execution.py`：

(a) `SkillEventHandler.__init__` 追加状态：

```python
        self.hitl_tool_calls: list[dict] = []
        self.interrupted_flag: bool = False
```

(b) `handle()` 的 import 区补 `RequireUserConfirmEvent, RequireExternalExecutionEvent`；在 `ExceedMaxItersEvent` 分支之前插入：

```python
        elif isinstance(event, (RequireUserConfirmEvent, RequireExternalExecutionEvent)):
            tool_calls = [
                {"id": getattr(tc, "id", ""), "name": getattr(tc, "name", ""),
                 "input": getattr(tc, "input", "{}"),
                 "suggested_rules": [str(r) for r in
                                     (getattr(tc, "suggested_rules", None) or [])]}
                for tc in (getattr(event, "tool_calls", None) or [])
            ]
            self.hitl_tool_calls = tool_calls
            self.reply_id = getattr(event, "reply_id", None) or self.reply_id
            from app.ai.events.hitl import PAUSE_TIMEOUT_MINUTES
            self._emit_sse("hitl_pause", {
                "reply_id": self.reply_id, "tool_calls": tool_calls,
                "timeout_minutes": PAUSE_TIMEOUT_MINUTES,
            })
```

(c) `ReplyEndEvent` 分支中 `finished_reason` 由硬编码 `"completed"` 改为：

```python
                {"finished_reason": "interrupted" if self.interrupted_flag else "completed"},
```

(d) 主循环（Task 9 patch 后的 `while True` 内 `yield evt` 处）插入控制面处理——在 `evt = await asyncio.wait_for(...)` 与 `yield evt` 之间加：

```python
                    if evt.type == "hitl_pause":
                        from app.ai.events.hitl import record_pause, PAUSE_TIMEOUT_MINUTES
                        try:
                            record_pause(_record_db, execution_id=execution_id,
                                         reply_id=handler.reply_id,
                                         tool_calls=evt.data.get("tool_calls"))
                        except Exception:
                            pass
                        if handle is not None:
                            handle.status = "waiting_hitl"
                            handle.reply_id = handler.reply_id
                        record_execution_status(_record_db, execution_id, "waiting_hitl")
                        # HITL 超时接管总超时：默认 30 分钟
                        deadline = time.monotonic() + PAUSE_TIMEOUT_MINUTES * 60
                        self.bus.publish(EventEnvelope(
                            execution_id=execution_id, trace_id=trace_id,
                            event_type="hitl_pause", category=EventCategory.HITL,
                            levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                            content={"tool_calls": evt.data.get("tool_calls"),
                                     "timeout_minutes": PAUSE_TIMEOUT_MINUTES},
                            reply_id=handler.reply_id, ui_hint="confirm",
                            source="skill_execution", source_id=skill_name,
                        ))
                    elif evt.type == "hitl_resume":
                        record_execution_status(_record_db, execution_id, "running")
                        self.bus.publish(EventEnvelope(
                            execution_id=execution_id, trace_id=trace_id,
                            event_type="hitl_resume", category=EventCategory.HITL,
                            levels=[EventLevel.DB, EventLevel.STREAM],
                            content={"action": evt.data.get("action")},
                            source="skill_execution", source_id=skill_name,
                        ))
                    yield evt
```

（即把原 `yield evt` 行替换为上述 `if/elif + yield evt`。）

> **已知限制（记入 PR）**：HITL 暂停期间若 SSE 连接已断开（execute 已退出），confirm 恢复后流式输出无人消费——主记录仍能更新，完整解法（执行任务与 HTTP 请求解耦）在 P1 处理。

- [ ] **Step 6: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_hitl_coordinator.py -v
cd backend && python -m pytest tests/unit -q
```

Expected: 全部 PASS（事件构造参数不符时按先决验证输出修正）。

- [ ] **Step 7: Commit**

```bash
git add backend/app/ai/events/hitl.py backend/app/routers/agent/agent_run.py backend/app/ai/skills/execution.py backend/app/ai/skills/execution_records.py backend/app/services/agent/agent_execution_service.py backend/tests/unit/test_hitl_coordinator.py
git commit -m "feat(agent): HITL 全链路——暂停/确认/拒绝/中断/超时提示/权限校验"
```

---

