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


### Task 6: record_execution_* 真实实现（修复存根）

**Files:**
- Modify: `backend/app/ai/skills/execution.py:30-33`（存根区）
- Test: `backend/tests/unit/test_execution_records.py`

**注意**：本任务只替换存根函数并单测；`execute()` 内的调用接线在 Task 8。当前文件因语法错误无法 import —— 单测 import 目标改为把存根实现抽到独立模块 `app/ai/skills/execution_records.py`，`execution.py` 顶部改为从该模块 import（Task 7 重写时沿用）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_execution_records.py`：

```python
"""执行主记录（agent_execution 表）写入单测：start/done/failed/timeout 生命周期。"""
from datetime import datetime

from app.ai.skills.execution_records import (
    record_execution_start, record_execution_done, record_execution_failed,
)


class FakeExecutionRow:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **kw):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """add/commit/rollback/查询记账。rows 通过 query() 暴露给被测函数。"""
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
        self.committed = 0
        self.rolled_back = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def query(self, model):
        return FakeQuery(self.rows)


def test_start_creates_running_row():
    db = FakeDB()
    record_execution_start(
        db, execution_id="e1", session_id=7, user_id=3, execution_mode="skill",
        target_id="my-skill", user_input="hi", metadata={"worker_skill": "my-skill"},
        trace_id="t1",
    )
    row = db.added[0]
    assert row.execution_id == "e1"
    assert row.status == "running"
    assert row.execution_mode == "skill"
    assert row.target_id == "my-skill"
    assert row.started_at is not None
    assert db.committed == 1


def test_done_updates_existing_row():
    row = FakeExecutionRow(execution_id="e1", status="running")
    db = FakeDB(rows=[row])
    record_execution_done(db, "e1", output="final text", latency_ms=123,
                          input_tokens=10, output_tokens=20, iterations=3)
    assert row.status == "completed"
    assert row.output == "final text"
    assert row.latency_ms == 123
    assert row.finished_reason == "completed"
    assert row.input_tokens == 10 and row.output_tokens == 20 and row.iterations == 3
    assert row.completed_at is not None


def test_failed_marks_error():
    row = FakeExecutionRow(execution_id="e2", status="running")
    db = FakeDB(rows=[row])
    record_execution_failed(db, "e2", error="boom", latency_ms=50)
    assert row.status == "failed"
    assert row.error == "boom"
    assert row.finished_reason == "error"


def test_timeout_marks_cancelled_interrupted():
    row = FakeExecutionRow(execution_id="e3", status="running")
    db = FakeDB(rows=[row])
    record_execution_failed(db, "e3", error="执行超时（timeout）", latency_ms=500,
                            interrupt_reason="timeout")
    assert row.status == "cancelled"
    assert row.finished_reason == "interrupted"
    assert row.interrupt_reason == "timeout"


def test_missing_row_is_noop_no_crash():
    db = FakeDB(rows=[])
    record_execution_done(db, "ghost", output="x")   # 不存在 → 静默跳过
    assert db.committed == 0
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_execution_records.py -v
```

Expected: FAIL，`ModuleNotFoundError: app.ai.skills.execution_records`。

- [ ] **Step 3: 实现独立模块**

创建 `backend/app/ai/skills/execution_records.py`：

```python
"""执行主记录（agent_execution 表）写入 —— 替换原 pass 存根。

所有函数吞异常（记录 warning）：主记录失败不应中断 SSE 执行流。
超时路径：status=cancelled + finished_reason=interrupted + interrupt_reason=timeout。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def record_execution_start(
    db: Any,
    *,
    execution_id: str,
    session_id: Optional[int] = None,
    user_id: Optional[int] = None,
    execution_mode: str = "skill",
    target_id: Optional[str] = None,
    user_input: Optional[str] = None,
    metadata: Optional[dict] = None,
    trace_id: Optional[str] = None,
) -> None:
    """写入执行主记录（status=running）。"""
    from app.models.agent.agent_execution import AgentExecution

    try:
        db.add(AgentExecution(
            execution_id=execution_id,
            session_id=session_id,
            user_id=user_id,
            execution_mode=execution_mode,
            target_id=str(target_id) if target_id is not None else None,
            status="running",
            user_input=user_input,
            trace_id=trace_id,
            started_at=datetime.now(),
            metadata_json=metadata,
        ))
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_start 失败 %s: %s", execution_id, e)


def _get_row(db: Any, execution_id: str):
    from app.models.agent.agent_execution import AgentExecution
    return (
        db.query(AgentExecution)
        .filter(AgentExecution.execution_id == execution_id)
        .first()
    )


def record_execution_done(
    db: Any,
    execution_id: str,
    output: Optional[str] = None,
    latency_ms: Optional[int] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    iterations: Optional[int] = None,
) -> None:
    """标记完成并回填输出/用量。"""
    try:
        row = _get_row(db, execution_id)
        if row is None:
            logger.warning("record_execution_done：执行记录不存在 %s", execution_id)
            return
        row.status = "completed"
        row.finished_reason = "completed"
        row.output = output
        row.completed_at = datetime.now()
        if latency_ms is not None:
            row.latency_ms = latency_ms
        if input_tokens is not None:
            row.input_tokens = input_tokens
        if output_tokens is not None:
            row.output_tokens = output_tokens
        if iterations is not None:
            row.iterations = iterations
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_done 失败 %s: %s", execution_id, e)


def record_execution_failed(
    db: Any,
    execution_id: str,
    error: Optional[str] = None,
    latency_ms: Optional[int] = None,
    interrupt_reason: Optional[str] = None,
) -> None:
    """标记失败；带 interrupt_reason（如 timeout）时记为 cancelled/interrupted。"""
    try:
        row = _get_row(db, execution_id)
        if row is None:
            logger.warning("record_execution_failed：执行记录不存在 %s", execution_id)
            return
        if interrupt_reason:
            row.status = "cancelled"
            row.finished_reason = "interrupted"
            row.interrupt_reason = interrupt_reason
        else:
            row.status = "failed"
            row.finished_reason = "error"
        row.error = error
        row.completed_at = datetime.now()
        if latency_ms is not None:
            row.latency_ms = latency_ms
        db.commit()
    except Exception as e:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_execution_failed 失败 %s: %s", execution_id, e)
```

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_execution_records.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/skills/execution_records.py backend/tests/unit/test_execution_records.py
git commit -m "feat(agent): 执行主记录真实写入（start/done/failed，含超时路径）"
```

---

