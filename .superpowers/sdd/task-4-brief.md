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


### Task 4: ExecutionEventService 支持 envelope 与级别过滤

**Files:**
- Modify: `backend/app/ai/services/execution_event_service.py`
- Test: `backend/tests/unit/test_execution_event_service.py`

**行为变化（有意）**：旧 `record()` 调用方（run_collector 等）自动获得分级 —— delta 类事件不再落库，仅日志。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_execution_event_service.py`：

```python
"""ExecutionEventService 分级写入单测：delta 不入库、envelope 新列、别名归一。"""
import asyncio

from app.schemas.agent.event_types import EventCategory, EventEnvelope, EventLevel
from app.ai.services.execution_event_service import ExecutionEventService


def _env(event_type: str, category: str, levels, content=None, **kw) -> EventEnvelope:
    return EventEnvelope(
        execution_id="exec-1", trace_id="t-1", event_type=event_type,
        category=category, levels=list(levels), content=content or {},
        source="test", **kw,
    )


def test_record_envelope_skips_db_for_stream_only():
    """delta 类（仅 STREAM）不入队列。"""
    async def main():
        svc = ExecutionEventService(execution_id="exec-1", trace_id="t-1")
        svc.record_envelope(_env("text_chunk", EventCategory.TEXT, [EventLevel.STREAM],
                                 {"delta": "hi"}))
        assert svc._queue.empty()
    asyncio.run(main())


def test_record_envelope_enqueues_db_level_with_new_columns():
    async def main():
        svc = ExecutionEventService(execution_id="exec-1", trace_id="t-1")
        svc.record_envelope(_env(
            "tool_call", EventCategory.TOOL, [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
            {"tool_name": "Bash"}, reply_id="r1", tool_call_id="tc1", ui_hint="timeline",
        ))
        assert svc._queue.qsize() == 1
        row = svc._queue.get_nowait()
        assert row["event_type"] == "tool_call"
        assert row["level"] == EventLevel.DB
        assert row["category"] == "tool"
        assert row["reply_id"] == "r1"
        assert row["tool_call_id"] == "tc1"
        assert row["ui_hint"] == "timeline"
        assert row["event_version"] == 1
        assert row["sequence"] == 0
    asyncio.run(main())


def test_legacy_record_normalizes_and_filters():
    """旧 record('text') 归一化为 text_chunk → 仅 STREAM → 不落库。"""
    async def main():
        svc = ExecutionEventService(execution_id="exec-1", trace_id="t-1")
        svc.record(event_type="text", content={"delta": "x"})
        assert svc._queue.empty()
        # team_start 仍落库（存量行为保留）
        svc.record(event_type="team_start", content={"team_code": "t"})
        assert svc._queue.qsize() == 1
        row = svc._queue.get_nowait()
        assert row["event_type"] == "team_start"
        assert row["category"] == "team"
        assert EventLevel.DB in row["levels"]
    asyncio.run(main())


def test_batch_write_sync_maps_new_columns(monkeypatch):
    """批量写 ORM 时新列映射正确（Fake ORM + Fake Session）。"""
    import app.ai.services.execution_event_service as svc_mod

    created = []

    class FakeEventORM:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            created.append(self)

    class FakeDB:
        def add(self, obj): pass
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

    monkeypatch.setattr(svc_mod, "AgentExecutionEvent", FakeEventORM)
    monkeypatch.setattr(svc_mod, "SessionLocal", lambda: FakeDB())

    svc = ExecutionEventService(execution_id="exec-2")
    svc._batch_write_sync([{
        "execution_id": "exec-2", "trace_id": "t", "event_type": "interrupted",
        "sequence": 3, "content": {}, "source": "agent", "source_id": None,
        "metadata": {}, "level": 1, "category": "interrupt",
        "reply_id": "r9", "block_id": None, "tool_call_id": None,
        "interrupt_reason": "timeout", "ui_hint": "timeline", "event_version": 1,
    }])
    assert created[0].event_type == "interrupted"
    assert created[0].reply_id == "r9"
    assert created[0].interrupt_reason == "timeout"
    assert created[0].level == 1
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_execution_event_service.py -v
```

Expected: FAIL，`AttributeError: record_envelope`。

- [ ] **Step 3: 实现改造**

修改 `backend/app/ai/services/execution_event_service.py`：

(a) 顶部 import 区加：

```python
from app.schemas.agent.event_types import (
    EventEnvelope, EventLevel, normalize_event_type, route_of,
)
```

(b) 将 `record()` 方法整体替换为（签名不变，内部走路由）：

```python
    def record(
        self,
        event_type: str,
        content: Optional[dict[str, Any]] = None,
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        async_write: bool = True,
    ) -> Optional[int]:
        """记录事件（兼容入口）。

        事件值先经 LEGACY_ALIAS 归一化，再按 DEFAULT_ROUTES 分级：
        仅 STREAM 的 delta 类不再落库（spec §4.2）。
        """
        etype = normalize_event_type(event_type)
        route = route_of(etype)
        envelope = EventEnvelope(
            execution_id=self.execution_id,
            trace_id=self.trace_id,
            event_type=etype,
            category=route.category,
            levels=sorted(route.levels),
            content=content or {},
            source=source or "skill_execution",
            source_id=source_id,
            ui_hint=route.ui_hint,
            metadata=metadata or {},
        )
        if async_write is False:
            # 同步路径：仅当需要落库时写
            if EventLevel.DB in route.levels:
                self._write_event_sync(self._envelope_to_row(envelope))
            return None
        return self.record_envelope(envelope)
```

(c) 在 `record()` 之后新增两个方法：

```python
    def record_envelope(self, envelope: EventEnvelope) -> Optional[int]:
        """按信封级别分发：含 DB 级才入队，否则仅结构化日志。"""
        if EventLevel.DB not in (envelope.levels or []):
            logger.debug(
                "event[{}] {} -> no-DB (levels={})",
                envelope.execution_id[:8], envelope.event_type, envelope.levels,
            )
            return None
        seq = self.sequence
        row = self._envelope_to_row(envelope, seq)
        self._events.append(row)
        self.start()
        if self._owning_loop is not None and self._owning_loop.is_running():
            try:
                self._owning_loop.call_soon_threadsafe(self._safe_put, row)
            except RuntimeError:
                logger.warning("事件队列 loop 不可用，丢弃事件 seq={}", seq)
        else:
            try:
                self._queue.put_nowait(row)
            except asyncio.QueueFull:
                logger.warning("事件队列已满（{}），丢弃事件 seq={}", _QUEUE_MAX_SIZE, seq)
        return seq

    def _envelope_to_row(self, envelope: EventEnvelope, seq: Optional[int] = None) -> dict[str, Any]:
        """信封 → DB 行 dict（含 DDL 47 新列）。"""
        levels = envelope.levels or []
        return {
            "execution_id": envelope.execution_id,
            "trace_id": envelope.trace_id,
            "event_type": envelope.event_type,
            "sequence": seq if seq is not None else self.sequence,
            "content": envelope.content,
            "source": envelope.source,
            "source_id": envelope.source_id,
            "metadata": envelope.metadata or {},
            "level": min(levels) if levels else None,
            "category": envelope.category,
            "reply_id": envelope.reply_id,
            "block_id": envelope.block_id,
            "tool_call_id": envelope.tool_call_id,
            "interrupt_reason": envelope.interrupt_reason,
            "ui_hint": envelope.ui_hint,
            "event_version": envelope.event_version,
        }
```

(d) `_batch_write_sync` 中 ORM 构造替换为：

```python
            for event in events:
                db_event = AgentExecutionEvent(
                    execution_id=event["execution_id"],
                    trace_id=event.get("trace_id"),
                    event_type=event["event_type"],
                    sequence=event["sequence"],
                    content=event.get("content"),
                    source=event.get("source"),
                    source_id=event.get("source_id"),
                    event_metadata=event.get("metadata"),
                    level=event.get("level"),
                    category=event.get("category"),
                    reply_id=event.get("reply_id"),
                    block_id=event.get("block_id"),
                    tool_call_id=event.get("tool_call_id"),
                    interrupt_reason=event.get("interrupt_reason"),
                    ui_hint=event.get("ui_hint"),
                    event_version=event.get("event_version") or 1,
                )
                db.add(db_event)
```

注意：旧 `record(async_write=False)` 同步路径原先无条件写库；新逻辑改为「仅 DB 级才写」。若有调用方依赖同步写 delta（grep 确认目前无 `async_write=False` 调用方），行为差异可接受。

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_execution_event_service.py -v
cd backend && python -m pytest tests/unit -q
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/services/execution_event_service.py backend/tests/unit/test_execution_event_service.py
git commit -m "feat(agent): 事件服务支持信封分级写入，delta 停止落库"
```

---

