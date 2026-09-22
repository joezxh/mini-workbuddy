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


### Task 8: execute() 接线（bus / 主记录 / 超时熔断）

> **后续任务将修改本任务产物**：Task 9 会把 `if timed_out:` 收尾段替换为通用中断收尾（支持 user_cancel），并把 consumer 注册进 AgentRunRegistry；Task 10 会在主循环 `yield evt` 处插入 hitl_pause/hitl_resume 控制面；Task 11 会在 `AGENT_START` 之后插入模式路由。按任务顺序执行即可。

**Files:**
- Modify: `backend/app/ai/skills/execution.py`（`execute` 方法主体，原第 248-366 行）
- Test: `backend/tests/unit/test_skill_execution_timeout.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_skill_execution_timeout.py`：

```python
"""SkillExecutionService.execute() 超时熔断与主记录生命周期单测（Fake 全家桶，无 DB）。"""
import asyncio
import types

import pytest

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService, SkillEvent


class FakeBus:
    def __init__(self):
        self.published = []
        self.execution_id = "exec-test"
        self.trace_id = "trace-test"

    def publish(self, env):
        self.published.append(env)


class FakeAgent:
    """慢 Agent：reply_stream 每个事件 sleep，制造超时。"""
    def __init__(self, events, delay=0.0):
        self._events = events
        self._delay = delay

    async def reply_stream(self, inputs):
        for e in self._events:
            await asyncio.sleep(self._delay)
            yield e


class FakeRecords:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _call(db, *a, **kw):
            self.calls.append((name, kw))
        return _call


def _patch_all(monkeypatch, svc, *, events, delay, timeout):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: FakeAgent(events, delay))
    monkeypatch.setattr(svc, "timeout", timeout)
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: None)
    monkeypatch.setattr(exec_mod, "EventBus", lambda event_service=None: FakeBus())


def test_timeout_emits_interrupt_events_and_marks_cancelled(monkeypatch):
    svc = SkillExecutionService(timeout=0.1)
    _patch_all(monkeypatch, svc,
               events=[types.SimpleNamespace()], delay=0.3, timeout=0.1)

    records = FakeRecords()
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: records.calls.append(("failed", kw)))

    async def run():
        return [e async for e in svc.execute("demo", "hi")]

    evts = asyncio.run(run())
    # SSE 输出含超时 error
    assert any(e.type == "error" and "超时" in e.data["message"] for e in evts)
    # 主记录走 failed 路径且带 interrupt_reason=timeout
    failed = [c for c in records.calls if c[0] == "failed"]
    assert failed and failed[0][1]["interrupt_reason"] == "timeout"


def test_normal_run_calls_start_and_done(monkeypatch):
    from agentscope.event import ReplyStartEvent, ReplyEndEvent
    svc = SkillExecutionService(timeout=5)
    _patch_all(monkeypatch, svc,
               events=[ReplyStartEvent(reply_id="r1", session_id="s", name="demo", role="assistant"),
                       ReplyEndEvent(reply_id="r1", session_id="s")],
               delay=0.0, timeout=5)

    calls = []
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: calls.append(("start", kw)))
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: calls.append(("done", kw)))

    async def run():
        return [e async for e in svc.execute("demo", "hi")]

    evts = asyncio.run(run())
    kinds = [c[0] for c in calls]
    assert kinds == ["start", "done"]
    assert any(e.type == "done" for e in evts)
```

> 若 `ReplyStartEvent` 等构造参数与安装版不符，同 Task 7 Step 0 的字段检查修正。

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_skill_execution_timeout.py -v
```

Expected: FAIL（execute 仍是旧实现：无 bus 接线 / 无超时 / handler 构造签名不符）。

- [ ] **Step 3: 重写 `execute()` 方法主体**

替换 `backend/app/ai/skills/execution.py` 的 `SkillExecutionService.execute()`（保留方法签名）为：

```python
    async def execute(
        self,
        skill_name: str,
        user_message: str,
        session_id: int | None = None,
        user_id: int | None = None,
        extra_tools: list[ToolBase] | None = None,
        model_id: int | None = None,
        execution_id: str | None = None,
        trace_id: str | None = None,
    ) -> AsyncGenerator[SkillEvent, None]:
        """流式执行技能（分级事件 + 主记录 + 超时熔断）。"""
        _exec_start = time.perf_counter()
        _exec_success = False

        if execution_id is None:
            execution_id = str(uuid.uuid4())

        if self.event_service is None:
            self.event_service = ExecutionEventService(
                execution_id=execution_id, trace_id=trace_id,
                agent_config_id=self.SKILL_AGENT_CONFIG_ID,
                agent_code=f"skill_{skill_name}",
                session_id=session_id, user_id=user_id,
            )
        self.bus = EventBus(event_service=self.event_service)
        self.bus.execution_id = execution_id
        self.bus.trace_id = trace_id

        # ── 主记录：start（替换原 pass 存根调用）──────────────────────────
        _record_db = None
        try:
            _record_db = SessionLocal()
            record_execution_start(
                _record_db, execution_id=execution_id,
                session_id=session_id, user_id=user_id, execution_mode="skill",
                target_id=str(skill_name), user_input=user_message,
                metadata={"worker_skill": skill_name}, trace_id=trace_id,
            )
        except Exception:
            pass

        self.bus.publish(EventEnvelope(
            execution_id=execution_id, trace_id=trace_id,
            event_type="agent_start", category=EventCategory.AGENT,
            levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
            content={"skill_name": skill_name, "user_message": user_message},
            source="skill_execution", source_id=skill_name, ui_hint="timeline",
        ))

        # 加载 Skill
        skill = await self._load_skill(skill_name)
        if skill is None:
            self.bus.publish(EventEnvelope(
                execution_id=execution_id, trace_id=trace_id,
                event_type="error", category=EventCategory.ERROR,
                levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                content={"message": f"技能不存在：{skill_name}"},
                source="skill_execution", source_id=skill_name,
            ))
            yield SkillEvent(type="error", data={"message": f"技能不存在：{skill_name}"})
            record_execution_failed(_record_db, execution_id,
                                    error=f"技能不存在：{skill_name}")
            return

        yield SkillEvent(type="start", data={
            "skill_name": skill["name"],
            "description": skill.get("description", ""),
        })

        # 注入 sys.path
        _skill_dir = skill.get("dir")
        self._injected_sys_paths = []
        if _skill_dir:
            for candidate in [Path(_skill_dir)] + list(Path(_skill_dir).iterdir()):
                if candidate.is_dir() and str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))
                    self._injected_sys_paths.append(str(candidate))

        yield SkillEvent(type="progress", data={
            "stage": "skill_agent_running",
            "message": "正在执行技能 Agent...",
        })

        # ── 执行 Agent：总超时 + 队列桥接 SSE ────────────────────────────
        out_q: asyncio.Queue = asyncio.Queue()
        handler = SkillEventHandler(skill_name=skill_name, bus=self.bus, out_q=out_q)

        timed_out = False
        try:
            toolkit = self._build_toolkit(extra_tools, skill.get("allowed_tools"))
            system_prompt = self._build_system_prompt(skill, session_id, user_id)
            model = self._build_model(model_id)
            agent = self._create_agent(skill_name, system_prompt, model, toolkit)
            user_msg = UserMsg(name="user", content=user_message)

            async def _consume() -> None:
                async for event in agent.reply_stream(inputs=user_msg):
                    await handler.handle(event)

            consumer = asyncio.create_task(_consume())
            deadline = time.monotonic() + self.timeout
            while True:
                if consumer.done() and out_q.empty():
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    consumer.cancel()
                    break
                try:
                    evt = await asyncio.wait_for(asyncio.shield(out_q.get()),
                                                 timeout=remaining)
                    yield evt
                except asyncio.TimeoutError:
                    timed_out = True
                    consumer.cancel()
                    break

            # 传播消费者异常
            exc = consumer.exception() if consumer.done() and not consumer.cancelled() else None
            if exc is not None and not timed_out:
                raise exc

        except Exception as e:
            logger.exception("技能执行异常：%s", e)
            self.bus.publish(EventEnvelope(
                execution_id=execution_id, trace_id=trace_id,
                event_type="error", category=EventCategory.ERROR,
                levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                content={"message": str(e)},
                source="skill_execution", source_id=skill_name, ui_hint="timeline",
            ))
            yield SkillEvent(type="error", data={"message": str(e)})

        finally:
            # 清理 sys.path
            for p in getattr(self, "_injected_sys_paths", []):
                if p in sys.path:
                    sys.path.remove(p)

        # ── 超时熔断收尾 ─────────────────────────────────────────────────
        elapsed_ms = int((time.perf_counter() - _exec_start) * 1000)
        if timed_out:
            for etype in ("interrupt_requested", "interrupted"):
                self.bus.publish(EventEnvelope(
                    execution_id=execution_id, trace_id=trace_id,
                    event_type=etype, category=EventCategory.INTERRUPT,
                    levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                    content={"reason": "timeout"},
                    interrupt_reason="timeout", source="skill_execution",
                    source_id=skill_name, ui_hint="timeline",
                ))
            yield SkillEvent(type="error", data={"message": f"执行超时（>{self.timeout}s），已熔断"})
            record_execution_failed(
                _record_db, execution_id,
                error=f"执行超时（>{self.timeout}s）", latency_ms=elapsed_ms,
                interrupt_reason="timeout",
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

        # 记录指标 + 关闭数据库
        self._record_metrics(skill_name, _exec_success, elapsed_ms / 1000.0)
        if _record_db is not None:
            try:
                _record_db.close()
            except Exception:
                pass
```

并在正常完成路径上置位成功标记：在 `while True` 循环正常退出（未超时、无异常）后、`finally` 之前加 `_exec_success = True`。具体实现时：把 `_exec_success = True` 放在 `while True` 循环 `break` 之后的下一行（即消费者正常跑完）。同时在 `except` 分支中保持 `_exec_success = False`。

> 简化实现提示：与其严格按上方顺序，落地时可整理为 —— `while` 循环后：`if not timed_out and not consumer_exception: _exec_success = True`。保持测试断言（start→done 顺序、超时→interrupt_reason）满足即可。

同时需要：
- `__init__` 中初始化 `self.bus: EventBus | None = None`；
- 顶部 import 补 `EventEnvelope`：`from app.schemas.agent.event_types import EventCategory, EventEnvelope, EventLevel`（Task 7 已引入前两者则仅补 `EventEnvelope`）；
- `SessionLocal` 需在模块顶部可用：文件内已按函数内 import 使用；为 monkeypatch 方便，改为顶部 `from app.db.database import SessionLocal  # noqa`——**注意**：顶部 import SessionLocal 会建立 DB 连接依赖吗？不会（仅类导入）。但为了最小化改动，保持函数内 `from app.db.database import SessionLocal` 亦可 —— 此时测试 monkeypatch 目标是 `app.db.database.SessionLocal`。**选择：保持函数内 import，测试 monkeypatch `app.db.database.SessionLocal`**（把测试中 `monkeypatch.setattr(exec_mod, "SessionLocal", ...)` 改为 `monkeypatch.setattr("app.db.database.SessionLocal", lambda: None)`）。

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_skill_execution_timeout.py -v
cd backend && python -m pytest tests/unit -q
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/skills/execution.py backend/tests/unit/test_skill_execution_timeout.py
git commit -m "feat(agent): execute() 接线 EventBus/主记录/总超时熔断"
```

---

