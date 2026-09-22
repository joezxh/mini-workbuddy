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


### Task 5: EventBus（Log + DB 双 handler）

**Files:**
- Create: `backend/app/ai/events/__init__.py`（空文件，内容仅一行注释 `"""Agent 事件总线包。"""`）
- Create: `backend/app/ai/events/bus.py`
- Test: `backend/tests/unit/test_event_bus.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_event_bus.py`：

```python
"""EventBus 分发单测：LOG 级走日志、DB 级委托事件服务。"""
from app.schemas.agent.event_types import EventCategory, EventEnvelope, EventLevel
from app.ai.events.bus import EventBus


class FakeEventService:
    def __init__(self):
        self.envelopes = []

    def record_envelope(self, env):
        self.envelopes.append(env)
        return len(self.envelopes)


def _env(event_type, levels, category=EventCategory.MODEL):
    return EventEnvelope(
        execution_id="e1", event_type=event_type, category=category,
        levels=list(levels), content={},
    )


def test_db_level_delegates_to_service():
    svc = FakeEventService()
    bus = EventBus(event_service=svc)
    bus.publish(_env("tool_call", [EventLevel.DB, EventLevel.STREAM], EventCategory.TOOL))
    assert [e.event_type for e in svc.envelopes] == ["tool_call"]


def test_log_only_does_not_hit_db():
    svc = FakeEventService()
    bus = EventBus(event_service=svc)
    bus.publish(_env("model_call", [EventLevel.LOG]))
    assert svc.envelopes == []


def test_publish_always_debug_logs(capsys):
    import logging
    logging.basicConfig(level=logging.DEBUG)
    svc = FakeEventService()
    bus = EventBus(event_service=svc)
    bus.publish(_env("model_call", [EventLevel.LOG]))
    # 不抛异常即视为通过（日志绑定由 loguru 处理，此处验证无副作用）
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_event_bus.py -v
```

Expected: FAIL，`ModuleNotFoundError: app.ai.events.bus`。

- [ ] **Step 3: 实现 EventBus**

创建 `backend/app/ai/events/bus.py`：

```python
"""EventBus —— 基于 Observer 模式的事件分发（spec §4.1）。

P0 范围：LOG（结构化日志）+ DB（委托 ExecutionEventService）两级 handler。
STREAM/UI 级由调用方（SSE 生成器）自行消费，不经 bus。
handler 异常相互隔离：一个 handler 失败不影响其他 handler。
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from app.schemas.agent.event_types import EventEnvelope, EventLevel


class EventBus:
    """事件总线：publish 一次，按 levels 分发到各 handler。"""

    def __init__(self, event_service: Optional[Any] = None) -> None:
        # event_service: ExecutionEventService（DB handler 目标）
        self._event_service = event_service

    def publish(self, envelope: EventEnvelope) -> None:
        """分发单个事件信封。同步、不抛出（handler 异常吞掉并记日志）。"""
        # L0：所有事件统一 debug 日志（含被降级不落库的）
        logger.bind(
            execution_id=envelope.execution_id,
            trace_id=envelope.trace_id,
            category=envelope.category,
        ).debug("event[{}] {} levels={}", envelope.execution_id[:8],
                envelope.event_type, envelope.levels)

        # L1：DB 持久化（service 内部会再次校验 DB 级并过滤）
        if self._event_service is not None:
            try:
                self._event_service.record_envelope(envelope)
            except Exception as e:  # noqa: BLE001 —— handler 隔离
                logger.opt(exception=True).warning(
                    "DBHandler 处理事件失败 {}: {}", envelope.event_type, e,
                )


from typing import Any  # noqa: E402 —— 放尾部避免与 Optional 循环可读性问题
```

> 注意：`from typing import Any` 应合并到文件顶部的 import 行（`from typing import Any, Optional`），上面分两行仅为排版说明；实现时合并为顶部一行，删除尾部那行。

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_event_bus.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/events/__init__.py backend/app/ai/events/bus.py backend/tests/unit/test_event_bus.py
git commit -m "feat(agent): EventBus 观察者分发（LOG+DB handler，异常隔离）"
```

---

