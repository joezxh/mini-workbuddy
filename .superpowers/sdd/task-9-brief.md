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


### Task 9: AgentRunRegistry + cancel API（强制终止/用户取消）

**Files:**
- Create: `backend/app/ai/events/registry.py`
- Create: `backend/app/routers/agent/agent_run.py`
- Modify: `backend/app/core/router_registry.py`
- Modify: `backend/app/ai/skills/execution.py`（consumer 注册 + 通用中断收尾）
- Test: `backend/tests/unit/test_agent_run_registry.py`

**设计说明**：InterruptManager 的 cancel 职责 P0 并入 `registry.py`（`cancel`/`mark_*` 方法），P1 若需独立超时调度器再拆 `interrupt.py`。registry 是 Agent 与 Skill 共用的唯一运行实例表（spec §5.3/§5.5）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_agent_run_registry.py`：

```python
"""AgentRunRegistry 与执行取消路径单测。"""
import asyncio
import types

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService, SkillEvent
from app.ai.events.registry import AgentRunRegistry, get_run_registry


def test_registry_lifecycle_and_cancel():
    async def main():
        reg = AgentRunRegistry()
        async def forever():
            await asyncio.sleep(30)
        t = asyncio.create_task(forever())
        reg.register("e1", t)
        assert reg.get("e1").task is t
        assert reg.cancel("e1", reason="user_cancel") is True
        await asyncio.sleep(0)
        assert t.cancelled()
        reg.unregister("e1")
        assert reg.get("e1") is None
        assert reg.cancel("e1") is False      # 已反注册 → False
    asyncio.run(main())


def test_waiting_hitl_status_transition():
    async def main():
        reg = AgentRunRegistry()
        async def noop():
            await asyncio.sleep(30)
        t = asyncio.create_task(noop())
        h = reg.register("e2", t)
        reg.mark_waiting_hitl("e2", reply_id="r1")
        assert h.status == "waiting_hitl" and h.reply_id == "r1"
        reg.mark_running("e2")
        assert h.status == "running"
        t.cancel()
    asyncio.run(main())


class SlowAgent:
    def __init__(self, delay=0.2):
        self._delay = delay

    async def reply_stream(self, inputs):
        for _ in range(5):
            await asyncio.sleep(self._delay)
            yield types.SimpleNamespace()


def _patch(monkeypatch, svc, records):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: SlowAgent())
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_status", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed",
                        lambda db, eid, *a, **kw: records.append(kw))
    monkeypatch.setattr("app.db.database.SessionLocal", lambda: None)


def test_execute_cancel_emits_interrupt_events(monkeypatch):
    """运行中取消：SSE 输出中断提示，主记录 interrupt_reason=user_cancel。"""
    svc = SkillExecutionService(timeout=30)
    records = []
    _patch(monkeypatch, svc, records)

    async def run():
        async def canceller():
            for _ in range(100):
                h = get_run_registry().get("exec-cancel")
                if h is not None:
                    get_run_registry().cancel("exec-cancel", reason="user_cancel")
                    return
                await asyncio.sleep(0.02)
        asyncio.create_task(canceller())
        return [e async for e in svc.execute("demo", "hi", execution_id="exec-cancel")]

    evts = asyncio.run(run())
    assert any(e.type == "error" and "中断" in e.data["message"] for e in evts)
    failed = [r for r in records if r.get("interrupt_reason") == "user_cancel"]
    assert failed, "取消路径应落 interrupt_reason=user_cancel"
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_agent_run_registry.py -v
```

Expected: FAIL，`ModuleNotFoundError: app.ai.events.registry`。

- [ ] **Step 3: 实现 registry 与 cancel API**

创建 `backend/app/ai/events/registry.py`：

```python
"""AgentRunRegistry —— 运行中执行注册表（Agent 与 Skill 共用，spec §5.3/§5.5）。

InterruptManager 的 cancel 职责 P0 并入本模块；P1 若需独立
超时调度器再拆 app/ai/events/interrupt.py。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class RunHandle:
    """一次执行的可触达句柄（cancel / HITL 恢复的入口）。"""
    execution_id: str
    task: asyncio.Task
    out_q: Optional[asyncio.Queue] = None
    agent: Any = None
    handler: Any = None
    reply_id: Optional[str] = None
    status: str = "running"          # running | waiting_hitl | done
    interrupt_reason: Optional[str] = None
    user_id: Optional[int] = None
    started_at: float = field(default_factory=time.monotonic)


class AgentRunRegistry:
    """execution_id → RunHandle。进程内单例，TTL 兜底由 P1 对账任务补充。"""

    def __init__(self) -> None:
        self._handles: dict[str, RunHandle] = {}

    def register(self, execution_id: str, task: asyncio.Task, *,
                 out_q: Optional[asyncio.Queue] = None, agent: Any = None,
                 handler: Any = None, user_id: Optional[int] = None) -> RunHandle:
        handle = RunHandle(execution_id=execution_id, task=task, out_q=out_q,
                           agent=agent, handler=handler, user_id=user_id)
        self._handles[execution_id] = handle
        return handle

    def get(self, execution_id: str) -> Optional[RunHandle]:
        return self._handles.get(execution_id)

    def unregister(self, execution_id: str) -> None:
        self._handles.pop(execution_id, None)

    # ── InterruptManager（P0 合并实现）─────────────────────────────────

    def cancel(self, execution_id: str, reason: str = "user_cancel") -> bool:
        """强制终止运行中的执行（task.cancel → asyncio.CancelledError）。"""
        handle = self._handles.get(execution_id)
        if handle is None or handle.status == "done":
            return False
        handle.interrupt_reason = reason
        handle.task.cancel()
        logger.info("execution {} cancelled: {}", execution_id[:8], reason)
        return True

    def mark_waiting_hitl(self, execution_id: str,
                          reply_id: Optional[str] = None) -> None:
        handle = self._handles.get(execution_id)
        if handle is None:
            return
        handle.status = "waiting_hitl"
        if reply_id:
            handle.reply_id = reply_id

    def mark_running(self, execution_id: str) -> None:
        handle = self._handles.get(execution_id)
        if handle is not None:
            handle.status = "running"


_REGISTRY = AgentRunRegistry()


def get_run_registry() -> AgentRunRegistry:
    return _REGISTRY
```

创建 `backend/app/routers/agent/agent_run.py`：

```python
"""Agent/Skill 执行运行控制 API —— cancel（spec §5.3；confirm 在 Task 10 追加）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.ai.events.registry import get_run_registry

router = APIRouter(prefix="/agents/executions", tags=["Agent 运行控制"])


@router.post("/{execution_id}/cancel")
def cancel_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """强制终止运行中的 Agent/Skill 执行。"""
    reg = get_run_registry()
    handle = reg.get(execution_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="执行不存在或已结束")
    ok = reg.cancel(execution_id, reason="user_cancel")
    return {"ok": ok, "execution_id": execution_id, "interrupt_reason": "user_cancel"}
```

在 `backend/app/core/router_registry.py` 中仿照现有 `app.routers.agent.*` 的 `RouterSpec` 行追加：

```python
    RouterSpec("app.routers.agent.agent_run", prefix=API_V1_PREFIX, tags=["Agent 运行控制"]),
```

- [ ] **Step 4: `execute()` 接入 registry（对 Task 8 代码的三处 patch）**

修改 `backend/app/ai/skills/execution.py`：

(a) consumer 创建与主循环（Task 8 的 `consumer = asyncio.create_task(_consume())` 与 `while True:` 块）替换为：

```python
            consumer = asyncio.create_task(_consume())
            from app.ai.events.registry import get_run_registry
            handle = get_run_registry().register(
                execution_id, consumer, out_q=out_q, agent=agent,
                handler=handler, user_id=user_id,
            )
            self._run_handle = handle
            deadline = time.monotonic() + self.timeout
            while True:
                if (consumer.done() and out_q.empty()
                        and handle.status != "waiting_hitl"):
                    break
```

（`waiting_hitl` 分支在 Task 10 使用，此处先加条件无副作用。）

(b) 收尾段（Task 8 的 `if timed_out:` 块）替换为通用中断收尾：

```python
        elapsed_ms = int((time.perf_counter() - _exec_start) * 1000)
        handle = getattr(self, "_run_handle", None)
        cancel_reason = None
        if timed_out:
            cancel_reason = "timeout"
        elif handle is not None and handle.task.cancelled():
            cancel_reason = handle.interrupt_reason or "user_cancel"
        if cancel_reason:
            for etype in ("interrupt_requested", "interrupted"):
                self.bus.publish(EventEnvelope(
                    execution_id=execution_id, trace_id=trace_id,
                    event_type=etype, category=EventCategory.INTERRUPT,
                    levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                    content={"reason": cancel_reason},
                    interrupt_reason=cancel_reason, source="skill_execution",
                    source_id=skill_name, ui_hint="timeline",
                ))
            yield SkillEvent(type="error", data={
                "message": f"执行被中断（{cancel_reason}）"})
            record_execution_failed(
                _record_db, execution_id,
                error=f"执行被中断（{cancel_reason}）", latency_ms=elapsed_ms,
                interrupt_reason=cancel_reason,
            )
        elif not _exec_success:
            record_execution_failed(_record_db, execution_id, error=None,
                                    latency_ms=elapsed_ms)
        else:
            record_execution_done(
                _record_db, execution_id,
                output=None, latency_ms=elapsed_ms,
                input_tokens=handler.usage.get("input_tokens"),
                output_tokens=handler.usage.get("output_tokens"),
                iterations=handler.iterations,
            )
```

（原 `elif not _exec_success` / `else` 分支保持 Task 8 内容不变。）

(c) `finally` 块末尾（关闭 `_record_db` 之前）加反注册：

```python
            from app.ai.events.registry import get_run_registry
            get_run_registry().unregister(execution_id)
```

- [ ] **Step 5: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_agent_run_registry.py -v
cd backend && python -m pytest tests/unit -q
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/ai/events/registry.py backend/app/routers/agent/agent_run.py backend/app/core/router_registry.py backend/app/ai/skills/execution.py backend/tests/unit/test_agent_run_registry.py
git commit -m "feat(agent): AgentRunRegistry + cancel API——Skill/Agent 共用强制终止与用户取消"
```

---

