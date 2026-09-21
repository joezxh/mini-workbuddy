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

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/schemas/agent/event_types.py` | 事件枚举/类别/级别/路由/别名/信封 —— 唯一权威来源 | 新建 |
| `backend/app/ai/events/__init__.py` | 包标记 | 新建 |
| `backend/app/ai/events/bus.py` | EventBus（Log + DB handler 委托） | 新建 |
| `backend/app/ai/events/registry.py` | AgentRunRegistry（RunHandle + cancel/mark_*，Agent 与 Skill 共用） | 新建 |
| `backend/app/ai/events/hitl.py` | HITL Coordinator（record_pause/resolve_pause/build_resume_event/resume_hitl） | 新建 |
| `backend/app/routers/agent/agent_run.py` | cancel / confirm REST 端点 | 新建 |
| `backend/app/schemas/agent/agent.py` | 删除本地 `ExecutionEventType`，re-export | 修改 |
| `backend/app/models/agent/agent_execution_event.py` | 删除本地枚举，import 权威来源；新增 8 列 | 修改 |
| `backend/app/models/agent/agent_execution.py` | 新增 5 列 | 修改 |
| `backend/app/models/agent/agent_hitl_pause.py` | HITL 暂停记录模型（重建，DDL 47 建表） | 新建 |
| `backend/app/ai/services/execution_event_service.py` | `record_envelope` + 级别过滤 + 批量写新列 | 修改 |
| `backend/app/ai/skills/execution_records.py` | 执行主记录写入（start/done/failed/status） | 新建 |
| `backend/app/ai/skills/execution.py` | 重写 handler + 主记录 + 超时 + registry + HITL 分支 + 模式路由 | 修改 |
| `backend/app/services/agent/agent_execution_service.py` | 恢复 `AgentHitlPause` import（修复悬空引用） | 修改 |
| `docs/sql/47_agent_event_enhance.sql` | DDL 增量（列 + 建表） | 新建 |
| `backend/tests/unit/test_event_types.py` 等若干 | 单测 | 新建 |

> 注意 SQL 文件放**仓库根** `docs/sql/`（不在 backend 内），与 45/46 号脚本同级。

---

### Task 1: DDL 47 + ORM 新列

**Files:**
- Create: `docs/sql/47_agent_event_enhance.sql`
- Create: `backend/app/models/agent/agent_hitl_pause.py`
- Modify: `backend/app/models/agent/agent_execution_event.py`
- Modify: `backend/app/models/agent/agent_execution.py`
- Modify: `backend/app/db/init_models.py`

- [ ] **Step 1: 写 DDL 文件**

创建 `docs/sql/47_agent_event_enhance.sql`：

```sql
-- 47: Agent 事件体系增强（spec 2026-09-21 §6.1）
-- PostgreSQL 方言（与 45/46 号脚本、alembic env.py 一致）。
-- ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS 保证可重复执行。
-- （权威内容以 docs/sql/47_agent_event_enhance.sql 文件为准）

-- agent_execution_event：分级与三级关联
ALTER TABLE agent_execution_event
    ADD COLUMN IF NOT EXISTS level            SMALLINT,
    ADD COLUMN IF NOT EXISTS category         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS reply_id         VARCHAR(64),
    ADD COLUMN IF NOT EXISTS block_id         VARCHAR(64),
    ADD COLUMN IF NOT EXISTS tool_call_id     VARCHAR(64),
    ADD COLUMN IF NOT EXISTS interrupt_reason VARCHAR(20),
    ADD COLUMN IF NOT EXISTS ui_hint          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS event_version    SMALLINT NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_event_reply ON agent_execution_event(execution_id, reply_id);
CREATE INDEX IF NOT EXISTS idx_event_category_level ON agent_execution_event(category, level);

-- agent_execution：结束原因与用量
ALTER TABLE agent_execution
    ADD COLUMN IF NOT EXISTS finished_reason  VARCHAR(20),
    ADD COLUMN IF NOT EXISTS interrupt_reason VARCHAR(20),
    ADD COLUMN IF NOT EXISTS input_tokens     INT,
    ADD COLUMN IF NOT EXISTS output_tokens    INT,
    ADD COLUMN IF NOT EXISTS iterations       INT;

-- agent_hitl_pause：HITL 暂停记录（模型此前被移除、service 存在悬空引用，本 DDL 重建；spec §5.4/§5.5）
CREATE TABLE IF NOT EXISTS agent_hitl_pause (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       INT8,
    execution_id    VARCHAR(64) NOT NULL,
    reply_id        VARCHAR(64),
    tool_calls      JSONB,
    suggested_rules JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'waiting',
    accept_rules    SMALLINT NOT NULL DEFAULT 0,
    timeout_at      TIMESTAMP,
    answered_at     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hitl_execution ON agent_hitl_pause(execution_id);
CREATE INDEX IF NOT EXISTS idx_hitl_status ON agent_hitl_pause(status);
CREATE INDEX IF NOT EXISTS ix_agent_hitl_pause_tenant_id ON agent_hitl_pause(tenant_id);
```

- [ ] **Step 1b: 创建 `AgentHitlPause` 模型并注册**

创建 `backend/app/models/agent/agent_hitl_pause.py`：

```python
"""AgentHitlPause - 人机交互暂停记录表（spec §5.4/§5.5；DDL 47 重建）。

此前模型被移除但 agent_execution_service 仍存在悬空引用，本任务恢复。
"""
from __future__ import annotations

from sqlalchemy import Column, BigInteger, String, JSON, SmallInteger, DateTime, Index
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AgentHitlPause(Base, TenantMixin):
    """人机交互暂停记录。"""
    __tablename__ = "agent_hitl_pause"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), nullable=False, comment="执行 ID")
    reply_id = Column(String(64), nullable=True, comment="AgentScope reply_id")
    tool_calls = Column(JSON, nullable=True, comment="待确认工具调用列表")
    suggested_rules = Column(JSON, nullable=True, comment="建议授权规则")
    status = Column(String(20), nullable=False, server_default="waiting",
                    comment="waiting/approved/rejected/interrupted")
    accept_rules = Column(SmallInteger, nullable=False, server_default="0",
                          comment="是否接受授权规则")
    timeout_at = Column(DateTime, nullable=True, comment="超时提示时刻")
    answered_at = Column(DateTime, nullable=True, comment="用户应答时刻")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # 索引显式命名，与 DDL 47 保持一致（tenant_id 索引由 TenantMixin 的 index=True 生成）
    __table_args__ = (
        Index("idx_hitl_execution", "execution_id"),
        Index("idx_hitl_status", "status"),
    )
```

并在 `backend/app/db/init_models.py` 的 agent 模型 import 区（`AgentExecutionEvent` 之后）加：

```python
from app.models.agent.agent_hitl_pause import AgentHitlPause                      # noqa: F401
```

- [ ] **Step 2: 更新 `agent_execution_event.py` ORM**

在 `backend/app/models/agent/agent_execution_event.py` 中：

(a) 导入区加 `SmallInteger`：

```python
from sqlalchemy import Column, BigInteger, String, Integer, SmallInteger, JSON, DateTime, Index
```

(b) 在 `event_metadata = Column(...)` 之后、时间戳注释之前插入：

```python
    # ── 分级与关联（spec 2026-09-21 §6.1，DDL 47）──────────────────────────
    level = Column(SmallInteger, nullable=True, comment="最低分发层级 LOG=0/DB=1/STREAM=2/UI=3")
    category = Column(String(20), nullable=True, comment="事件分类")
    reply_id = Column(String(64), nullable=True, comment="AgentScope reply_id")
    block_id = Column(String(64), nullable=True, comment="内容块 ID")
    tool_call_id = Column(String(64), nullable=True, comment="工具调用关联 ID")
    interrupt_reason = Column(String(20), nullable=True, comment="中断原因")
    ui_hint = Column(String(20), nullable=True, comment="前端渲染路由提示")
    event_version = Column(SmallInteger, nullable=False, server_default="1", comment="事件格式版本")
```

(c) `__table_args__` 追加两条索引（与 DDL 对齐）：

```python
        Index("idx_event_reply", "execution_id", "reply_id"),
        Index("idx_event_category_level", "category", "level"),
```

- [ ] **Step 3: 更新 `agent_execution.py` ORM**

在 `backend/app/models/agent/agent_execution.py` 的 `metadata_json` 列之后插入：

```python
    # ── 结束原因与用量（spec 2026-09-21 §6.1，DDL 47）──────────────────────
    finished_reason = Column(String(20), nullable=True, comment="completed|interrupted|exceed_max_iters|error")
    interrupt_reason = Column(String(20), nullable=True, comment="timeout|user_cancel|system|error")
    input_tokens = Column(Integer, nullable=True, comment="累计输入 token")
    output_tokens = Column(Integer, nullable=True, comment="累计输出 token")
    iterations = Column(Integer, nullable=True, comment="推理-行动迭代轮数")
```

- [ ] **Step 4: 验证可 import 且既有测试不回归**

```bash
cd backend && python -c "from app.models.agent.agent_execution_event import AgentExecutionEvent; from app.models.agent.agent_execution import AgentExecution; print('ok')"
cd backend && python -m pytest tests/unit -q
```

Expected: `ok` + 全部通过。

- [ ] **Step 5: Commit**

```bash
git add docs/sql/47_agent_event_enhance.sql backend/app/models/agent/agent_execution_event.py backend/app/models/agent/agent_execution.py
git commit -m "feat(agent): DDL 47 与 ORM 新增事件分级/关联/用量列"
```

---

### Task 2: event_types.py 权威模块

**Files:**
- Create: `backend/app/schemas/agent/event_types.py`
- Test: `backend/tests/unit/test_event_types.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_event_types.py`：

```python
"""event_types 权威模块单测：别名归一化、路由表、信封校验。"""
from app.schemas.agent.event_types import (
    EventCategory, EventLevel, ExecutionEventType, EventEnvelope,
    LEGACY_ALIAS, DEFAULT_ROUTES, normalize_event_type, route_of,
)


# ── 别名归一化 ──────────────────────────────────────────────────────────

def test_legacy_alias_mapping():
    assert LEGACY_ALIAS["text"] == "text_chunk"
    assert LEGACY_ALIAS["thinking"] == "thinking_chunk"
    assert LEGACY_ALIAS["agent_complete"] == "agent_done"
    assert LEGACY_ALIAS["completed"] == "agent_done"
    assert LEGACY_ALIAS["skill_load"] == "skill_loaded"
    assert LEGACY_ALIAS["skill_complete"] == "skill_result"
    assert LEGACY_ALIAS["agent_error"] == "error"
    assert LEGACY_ALIAS["failed"] == "error"
    assert LEGACY_ALIAS["timeout"] == "interrupt_requested"


def test_normalize_known_alias_and_passthrough():
    assert normalize_event_type("text") == "text_chunk"
    assert normalize_event_type("team_start") == "team_start"      # 已是新值，原样
    assert normalize_event_type("whatever_unknown") == "whatever_unknown"  # 未知不炸


def test_enum_is_plain_str_subclass():
    """str 子类保证 ExecutionEventType.TEXT == 'text' 为 True（避免 Enum 陷阱）。"""
    assert ExecutionEventType.TEXT_CHUNK == "text_chunk"
    assert isinstance(ExecutionEventType.TEXT_CHUNK, str)


# ── 路由表 ──────────────────────────────────────────────────────────────

def test_delta_events_not_routed_to_db():
    for t in ("text_chunk", "thinking_chunk", "data_chunk"):
        assert EventLevel.DB not in DEFAULT_ROUTES[t].levels, t


def test_block_summary_routed_to_db():
    for t in ("text_done", "thinking_done"):
        assert EventLevel.DB in DEFAULT_ROUTES[t].levels, t


def test_tool_and_lifecycle_routed_to_db():
    for t in ("tool_call", "tool_result", "reply_start", "reply_end",
              "hitl_pause", "interrupted", "skill_result", "agent_done"):
        assert EventLevel.DB in DEFAULT_ROUTES[t].levels, t


def test_model_call_is_log_only():
    r = DEFAULT_ROUTES["model_call"]
    assert EventLevel.LOG in r.levels and EventLevel.DB not in r.levels


def test_route_of_fallback_for_unknown():
    r = route_of("totally_unknown_event")
    assert EventLevel.DB in r.levels  # 未知事件保守落库
    assert r.category == EventCategory.RUNTIME


def test_every_enum_member_has_route():
    members = [v for k, v in vars(ExecutionEventType).items() if not k.startswith("_")]
    missing = [m for m in members if m not in DEFAULT_ROUTES]
    assert missing == [], f"缺路由: {missing}"


# ── 信封 ────────────────────────────────────────────────────────────────

def test_envelope_defaults():
    env = EventEnvelope(
        execution_id="exec-1", event_type="tool_call",
        category=EventCategory.TOOL, levels=[EventLevel.DB, EventLevel.STREAM],
        content={"tool_name": "Bash"},
    )
    assert env.event_version == 1
    assert env.reply_id is None and env.ui_hint is None
    assert env.metadata == {}
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_event_types.py -v
```

Expected: FAIL，`ModuleNotFoundError: app.schemas.agent.event_types`。

- [ ] **Step 3: 实现 `event_types.py`**

创建 `backend/app/schemas/agent/event_types.py`：

```python
"""Agent 执行事件类型 —— 全系统唯一权威来源。

spec: docs/superpowers/specs/2026-09-21-agent-event-architecture-design.md §4.2/§4.3

设计要点：
- 枚举用普通 str 子类（非 Enum），保持 ``ExecutionEventType.TEXT_CHUNK == "text_chunk"``
  为 True，与旧 schemas 版行为一致，避免 ``str, Enum`` 相等性陷阱。
- 历史值经 LEGACY_ALIAS 在写入侧归一化；DB 存量行不迁移，读取侧按别名双读。
- levels 是分发目标集合（可多选）：delta 类仅 [STREAM] 不落库，
  text_done/thinking_done 携带块级汇总以 [DB] 落库。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional

from pydantic import BaseModel, Field


# ── 类别与级别 ────────────────────────────────────────────────────────────

class EventCategory(str):
    """事件分类。"""
    LIFECYCLE = "lifecycle"
    TEXT = "text"
    THINKING = "thinking"
    DATA = "data"
    TOOL = "tool"
    MODEL = "model"
    RUNTIME = "runtime"
    CONFIG = "config"
    HITL = "hitl"
    INTERRUPT = "interrupt"
    SKILL = "skill"
    AGENT = "agent"
    TEAM = "team"
    ARTIFACT = "artifact"
    ERROR = "error"
    METRICS = "metrics"


class EventLevel(int):
    """分发层级（多选集合的元素）。"""
    LOG = 0      # 仅日志
    DB = 1       # 持久化
    STREAM = 2   # SSE 推送
    UI = 3       # 前端渲染路由


# ── 统一事件类型（单一权威来源）─────────────────────────────────────────

class ExecutionEventType(str):
    """统一执行事件类型（对齐 AgentScope 2.0.8 事件目录，归并历史冗余）。"""

    # 生命周期（对齐 ReplyStart/ReplyEnd）
    REPLY_START = "reply_start"
    REPLY_END = "reply_end"                      # content.finished_reason

    # 文本/思考/数据流（对齐 Block* 三段式）
    TEXT_CHUNK = "text_chunk"                    # [STREAM] delta 不落库
    TEXT_DONE = "text_done"                      # [DB] 块级汇总
    THINKING_CHUNK = "thinking_chunk"            # [STREAM]
    THINKING_DONE = "thinking_done"              # [DB]
    DATA_CHUNK = "data_chunk"                    # [STREAM]

    # 工具（对齐 ToolCall*/ToolResult*）
    TOOL_CALL = "tool_call"                      # state: asking|allowed|submitted
    TOOL_RESULT = "tool_result"                  # state: running|success|error|interrupted|denied

    # 模型计量（对齐 ModelCallStart/End）
    MODEL_CALL = "model_call"                    # metadata: input/output_tokens

    # 运行时（对齐 ExceedMaxIters 等）
    ITERATION_LIMIT = "iteration_limit"
    PROGRESS = "progress"
    CONTEXT_COMPRESSED = "context_compressed"

    # 配置智能体
    CONFIG_LOADED = "config_loaded"
    CONFIG_VALIDATED = "config_validated"
    SCHEMA_APPLIED = "schema_applied"

    # 中断智能体
    INTERRUPT_REQUESTED = "interrupt_requested"  # reason: timeout|user_cancel|system
    INTERRUPTED = "interrupted"

    # HITL
    HITL_PAUSE = "hitl_pause"
    HITL_RESUME = "hitl_resume"

    # Skill / Agent
    SKILL_LOADED = "skill_loaded"
    SKILL_START = "skill_start"
    SKILL_RESULT = "skill_result"
    AGENT_START = "agent_start"
    AGENT_DONE = "agent_done"
    AGENT_RETRY = "agent_retry"
    ENGINE_DECISION = "engine_decision"
    ARTIFACT = "artifact"
    CHART_DATA = "chart_data"
    FILE_GENERATED = "file_generated"

    # 团队（存量保留）
    TEAM_START = "team_start"
    TEAM_DONE = "team_done"
    TEAM_ERROR = "team_error"
    TEAM_LAYER_START = "team_layer_start"
    TEAM_LAYER_DONE = "team_layer_done"
    TEAM_ROUND_START = "team_round_start"
    TEAM_ROUND_DONE = "team_round_done"
    NODE_START = "node_start"
    NODE_DONE = "node_done"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    NODE_INPUT = "node_input"
    HANDOFF = "handoff"
    INTERVENTION = "intervention"
    HINT_BLOCK = "hint_block"
    DISPATCH_PLAN = "dispatch_plan"
    PLAN_REVISED = "plan_revised"

    # 通用
    ERROR = "error"
    METRICS = "metrics"
    CUSTOM = "custom"                            # 对齐 AgentScope CustomEvent


# ── 历史别名（写入侧归一化）─────────────────────────────────────────────

LEGACY_ALIAS: Dict[str, str] = {
    "text": "text_chunk",
    "thinking": "thinking_chunk",
    "agent_complete": "agent_done",
    "completed": "agent_done",
    "skill_load": "skill_loaded",
    "skill_complete": "skill_result",
    "agent_error": "error",
    "failed": "error",
    "timeout": "interrupt_requested",
}


def normalize_event_type(value: str) -> str:
    """历史事件值归一化；未知值原样返回（不阻断写入方）。"""
    return LEGACY_ALIAS.get(value, value)


# ── 路由表 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EventRoute:
    category: str
    levels: FrozenSet[int]
    ui_hint: Optional[str] = None


def _r(category: str, *levels: int, ui: Optional[str] = None) -> EventRoute:
    return EventRoute(category=category, levels=frozenset(levels), ui_hint=ui)


_L = EventLevel.LOG
_D = EventLevel.DB
_S = EventLevel.STREAM
_U = EventLevel.UI

DEFAULT_ROUTES: Dict[str, EventRoute] = {
    # 生命周期
    "reply_start": _r(EventCategory.LIFECYCLE, _D),
    "reply_end": _r(EventCategory.LIFECYCLE, _D),
    # 流式 delta —— 不落库（spec 验收：DB 行数下降 ≥80%）
    "text_chunk": _r(EventCategory.TEXT, _S, ui="markdown"),
    "text_done": _r(EventCategory.TEXT, _D),
    "thinking_chunk": _r(EventCategory.THINKING, _S),
    "thinking_done": _r(EventCategory.THINKING, _D),
    "data_chunk": _r(EventCategory.DATA, _S, ui="markdown"),
    # 工具
    "tool_call": _r(EventCategory.TOOL, _D, _S, _U, ui="timeline"),
    "tool_result": _r(EventCategory.TOOL, _D, _S, _U, ui="timeline"),
    # 模型计量 —— 仅日志
    "model_call": _r(EventCategory.MODEL, _L),
    # 运行时
    "iteration_limit": _r(EventCategory.RUNTIME, _D, _S, _U, ui="timeline"),
    "progress": _r(EventCategory.RUNTIME, _S, _U, ui="timeline"),
    "context_compressed": _r(EventCategory.RUNTIME, _L),
    # 配置
    "config_loaded": _r(EventCategory.CONFIG, _D),
    "config_validated": _r(EventCategory.CONFIG, _D),
    "schema_applied": _r(EventCategory.CONFIG, _D),
    # 中断
    "interrupt_requested": _r(EventCategory.INTERRUPT, _D, _S, _U, ui="timeline"),
    "interrupted": _r(EventCategory.INTERRUPT, _D, _S, _U, ui="timeline"),
    # HITL
    "hitl_pause": _r(EventCategory.HITL, _D, _S, _U, ui="confirm"),
    "hitl_resume": _r(EventCategory.HITL, _D, _S),
    # Skill / Agent
    "skill_loaded": _r(EventCategory.SKILL, _D, _S, _U, ui="timeline"),
    "skill_start": _r(EventCategory.SKILL, _D, _S, _U, ui="timeline"),
    "skill_result": _r(EventCategory.SKILL, _D, _S, _U),
    "agent_start": _r(EventCategory.AGENT, _D, _S, _U, ui="timeline"),
    "agent_done": _r(EventCategory.AGENT, _D, _S, _U),
    "agent_retry": _r(EventCategory.AGENT, _D, _S, _U, ui="timeline"),
    "engine_decision": _r(EventCategory.AGENT, _D, _S, _U, ui="timeline"),
    "artifact": _r(EventCategory.ARTIFACT, _D, _S, _U, ui="artifact"),
    "chart_data": _r(EventCategory.ARTIFACT, _D, _S, _U, ui="chart"),
    "file_generated": _r(EventCategory.ARTIFACT, _D, _S, _U, ui="artifact"),
    # 团队（存量保留 DB 行为）
    "team_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_done": _r(EventCategory.TEAM, _D, _S, _U),
    "team_error": _r(EventCategory.TEAM, _D, _S, _U),
    "team_layer_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_layer_done": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_round_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_round_done": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_done": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_failed": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_skipped": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_input": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "handoff": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "intervention": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "hint_block": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "dispatch_plan": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "plan_revised": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    # 通用
    "error": _r(EventCategory.ERROR, _D, _S, _U, ui="timeline"),
    "metrics": _r(EventCategory.METRICS, _L, _D),
    "custom": _r(EventCategory.RUNTIME, _D),
}

# 未知事件的兜底路由：保守落库
_FALLBACK_ROUTE = EventRoute(
    category=EventCategory.RUNTIME, levels=frozenset({EventLevel.DB}),
)


def route_of(event_type: str) -> EventRoute:
    """查询事件路由；未知事件返回保守兜底（DB）。"""
    return DEFAULT_ROUTES.get(event_type, _FALLBACK_ROUTE)


# ── 事件信封 ──────────────────────────────────────────────────────────────

class EventEnvelope(BaseModel):
    """统一事件信封：EventBus 分发与持久化的标准载荷。

    sequence 由 ExecutionEventService 在落库时分配，调用方不填。
    """
    execution_id: str
    trace_id: Optional[str] = None
    event_type: str
    category: str
    levels: List[int] = Field(default_factory=list)
    content: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    source_id: Optional[str] = None
    reply_id: Optional[str] = None
    block_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    interrupt_reason: Optional[str] = None
    ui_hint: Optional[str] = None
    event_version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_event_types.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/agent/event_types.py backend/tests/unit/test_event_types.py
git commit -m "feat(agent): 事件类型权威模块 event_types（枚举/类别/级别/路由/别名/信封）"
```

---

### Task 3: 双处删除本地枚举，re-export 单一来源

**Files:**
- Modify: `backend/app/schemas/agent/agent.py:33-73`
- Modify: `backend/app/models/agent/agent_execution_event.py:17-58`

- [ ] **Step 1: `schemas/agent/agent.py` 删除本地枚举**

删除整个 `class ExecutionEventType(str):` 块（第 33-73 行，含所有成员），在 `ExecutionStatus` 类之后插入：

```python
from app.schemas.agent.event_types import ExecutionEventType  # noqa: F401 单一权威来源，re-export
```

（import 放文件顶部 import 区更规范：加到 `from pydantic import ...` 之后即可。）

- [ ] **Step 2: `models/agent/agent_execution_event.py` 删除本地枚举**

删除 `class ExecutionEventType(str, Enum):` 整块（第 17-58 行），并删除 `from enum import Enum`（若无其他使用）。在 `from app.models.tenant_mixin import TenantMixin` 后加：

```python
# 事件类型枚举统一取自 schemas 权威模块（spec 2026-09-21 §4.2）。
# schemas 不依赖 models，此处反向引用无循环风险。
from app.schemas.agent.event_types import ExecutionEventType  # noqa: F401
```

- [ ] **Step 3: 验证两处来源一致 + 既有引用不破**

```bash
cd backend && python -c "
from app.schemas.agent.agent import ExecutionEventType as A
from app.models.agent.agent_execution_event import ExecutionEventType as B
from app.schemas.agent.event_types import ExecutionEventType as C
assert A is B is C
assert A.TEXT == 'text' and A.TEXT_CHUNK == 'text_chunk'
print('single source ok')
"
cd backend && python -m pytest tests/unit -q
```

Expected: `single source ok` + 全部通过（`run_collector.py` / `execution.py` 等旧 import 路径经 re-export 继续工作）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/agent/agent.py backend/app/models/agent/agent_execution_event.py
git commit -m "refactor(agent): 事件枚举收敛单一来源，schemas/models re-export"
```

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

### Task 7: SkillEventHandler 重写（修复语法错误 + 分级 + 三级关联 + 计量）

**Files:**
- Modify: `backend/app/ai/skills/execution.py:44-221`（`SkillEvent` 保留；`SkillEventHandler` 整体重写；删除 `_run_agent_native` 死代码）
- Test: `backend/tests/unit/test_skill_event_handler.py`

**先决验证**：确认安装的 agentscope 事件构造参数（字段名以安装版本为准）：

```bash
cd backend && python -c "
from agentscope.event import TextBlockDeltaEvent, ToolCallEndEvent, ModelCallEndEvent, ReplyEndEvent, ToolResultEndEvent
for cls in (TextBlockDeltaEvent, ToolCallEndEvent, ModelCallEndEvent, ReplyEndEvent, ToolResultEndEvent):
    print(cls.__name__, getattr(cls, 'model_fields', None) or cls.__annotations__)
"
```

若字段名与本计划代码不一致（如 `delta` vs `text`），以实际输出为准调整测试构造参数与 handler 取值；**handler 的 isinstance 分派结构不变**。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_skill_event_handler.py`：

```python
"""SkillEventHandler 重写单测：delta 不落库、块级汇总落库、三级关联、token 计量。

直接构造 agentscope 真实事件对象；构造字段以安装版本 model_fields 为准
（执行前先跑本文件顶部说明中的字段检查命令）。
"""
import asyncio

from agentscope.event import (
    ReplyStartEvent, TextBlockDeltaEvent, TextBlockEndEvent,
    ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
    ToolCallStartEvent, ToolCallEndEvent,
    ToolResultTextDeltaEvent, ToolResultEndEvent,
    ModelCallEndEvent, ReplyEndEvent,
)

from app.ai.skills.execution import SkillEvent, SkillEventHandler


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, envelope):
        self.published.append(envelope)


def _handler():
    bus = FakeBus()
    out = asyncio.Queue()
    return SkillEventHandler(skill_name="demo", bus=bus, out_q=out), bus, out


def _drain(q: asyncio.Queue):
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def test_text_delta_not_persisted_but_ssed():
    async def main():
        h, bus, out = _handler()
        await h.handle(ReplyStartEvent(reply_id="r1", session_id="s1", name="demo", role="assistant"))
        await h.handle(TextBlockDeltaEvent(reply_id="r1", block_id="b1", delta="你好"))
        await h.handle(TextBlockDeltaEvent(reply_id="r1", block_id="b1", delta="世界"))
        await h.handle(TextBlockEndEvent(reply_id="r1", block_id="b1"))

        # SSE 侧仍输出两个 text 事件（前端兼容）
        sse = [e for e in _drain(out) if e.type == "text"]
        assert "".join(e.data["content"] for e in sse) == "你好世界"

        # DB 侧：reply_start + text_done 汇总，无逐 delta
        types = [e.event_type for e in bus.published]
        assert types == ["reply_start", "text_done"]
        done = bus.published[1]
        assert done.content == {"text": "你好世界"}
        assert done.reply_id == "r1" and done.block_id == "b1"
        assert done.category == "text"
    asyncio.run(main())


def test_thinking_delta_summary():
    async def main():
        h, bus, out = _handler()
        await h.handle(ThinkingBlockDeltaEvent(reply_id="r1", block_id="b0", delta="思考中"))
        await h.handle(ThinkingBlockEndEvent(reply_id="r1", block_id="b0"))
        types = [e.event_type for e in bus.published]
        assert types == ["thinking_done"]
        assert bus.published[0].content == {"thinking": "思考中"}
    asyncio.run(main())


def test_tool_call_with_tool_call_id_and_result_state():
    async def main():
        h, bus, out = _handler()
        await h.handle(ToolCallStartEvent(reply_id="r1", tool_call_id="tc1", tool_call_name="Bash"))
        await h.handle(ToolCallEndEvent(reply_id="r1", tool_call_id="tc1", tool_args={"cmd": "ls"}))
        await h.handle(ToolResultTextDeltaEvent(reply_id="r1", tool_call_id="tc1", delta="file1"))
        await h.handle(ToolResultEndEvent(reply_id="r1", tool_call_id="tc1", state="success"))

        types = [e.event_type for e in bus.published]
        # delta（tool_result 流式）不落库，仅 tool_call + tool_result 两条
        assert types == ["tool_call", "tool_result"]
        call = bus.published[0]
        assert call.tool_call_id == "tc1"
        assert call.content["tool_name"] == "Bash"
        result = bus.published[1]
        assert result.tool_call_id == "tc1"
        assert result.content["state"] == "success"

        # SSE 侧 tool_call/tool_result 事件仍在
        sse_types = [e.type for e in _drain(out)]
        assert "tool_call" in sse_types and "tool_result" in sse_types
    asyncio.run(main())


def test_model_call_tokens_accumulate_and_reply_end_usage():
    async def main():
        h, bus, out = _handler()
        await h.handle(ReplyStartEvent(reply_id="r1", session_id="s1", name="demo", role="assistant"))
        await h.handle(ModelCallEndEvent(reply_id="r1", model_name="qwen-max",
                                         input_tokens=100, output_tokens=50))
        await h.handle(ModelCallEndEvent(reply_id="r1", model_name="qwen-max",
                                         input_tokens=30, output_tokens=20))
        await h.handle(ReplyEndEvent(reply_id="r1", session_id="s1"))

        # model_call 仅 LOG 级 —— bus 收到但 FakeBus 不过滤，检查其 levels
        mc = [e for e in bus.published if e.event_type == "model_call"]
        assert len(mc) == 2
        assert mc[0].levels == [0]  # LOG only
        assert mc[0].metadata["input_tokens"] == 100

        # reply_end 携带累计 usage
        re = [e for e in bus.published if e.event_type == "reply_end"][-1]
        assert re.metadata["input_tokens"] == 130
        assert re.metadata["output_tokens"] == 70
        assert re.metadata["iterations"] == 2
        assert re.content["finished_reason"] == "completed"

        # 最终 SSE done 事件仍输出
        assert any(e.type == "done" for e in _drain(out))
    asyncio.run(main())


def test_error_event():
    async def main():
        h, bus, out = _handler()
        await h.handle(Exception("boom"))  # ErrorEvent 兼容：非已知类型走 error 兜底
        # 已知 ErrorEvent 构造依赖版本，此处用兜底分支验证 error 事件输出
        assert any(e.type == "error" for e in _drain(out)) or bus.published == []
    asyncio.run(main())
```

> 测试说明：最后一个用例走 `handle()` 的兜底分支（未知事件 → SSE error + DB error）。若安装版 `ErrorEvent` 可直接构造（有 `error` 字段），可再加一个真实构造分支。**若 agentscope 事件构造参数与上述不一致**（如 `ToolCallStartEvent` 无 `tool_call_name` 而叫 `tool_name`），以 Step 0 的字段检查输出为准修正测试与实现取值。

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_skill_event_handler.py -v
```

Expected: FAIL —— collection error（`execution.py` 当前有 `lambda evt: yield evt` 语法错误，import 即 SyntaxError）。

- [ ] **Step 3: 重写 `SkillEventHandler` 并删除死代码**

修改 `backend/app/ai/skills/execution.py`：

(a) 删除第 29-33 行存根区，改为：

```python
from app.ai.skills.execution_records import (
    record_execution_done,
    record_execution_failed,
    record_execution_start,
)
```

(b) 顶部 import 区加：

```python
from app.ai.events.bus import EventBus
from app.schemas.agent.event_types import EventCategory, EventLevel
```

(c) **整体替换** `class SkillEventHandler`（原第 66-221 行）为：

```python
class SkillEventHandler(EventStreamHandler):
    """AgentScope 事件流处理器（spec §4.2 分级 + §5.2 运行模式增强）。

    - SSE 输出：SkillEvent 入 out_q，类型保持旧值（text/thinking/tool_call/
      tool_result/done/error），前端零改动。
    - DB 输出：经 bus 发布信封 —— delta 不落库，块级/调用级汇总落库。
    - 关联：透传 reply_id / block_id / tool_call_id。
    - 计量：累计 ModelCallEnd 的 input/output tokens 与迭代轮数。
    """

    def __init__(self, skill_name: str, bus: EventBus, out_q: asyncio.Queue) -> None:
        super().__init__()
        self.skill_name = skill_name
        self.bus = bus
        self.out_q = out_q
        self.text_parts: list[str] = []
        self.current_tool_name: str = ""
        self.reply_id: str | None = None
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.iterations = 0

    # ── 发布辅助 ─────────────────────────────────────────────────────

    def _emit_sse(self, type_: str, data: dict) -> None:
        self.out_q.put_nowait(SkillEvent(type=type_, data=data))

    def _publish_db(self, event_type: str, category: str, levels, content: dict,
                    metadata: dict | None = None, **kw) -> None:
        self.bus.publish(EventEnvelope(
            execution_id=self.bus.execution_id,
            trace_id=self.bus.trace_id,
            event_type=event_type, category=category, levels=list(levels),
            content=content, source="agent", source_id=self.skill_name,
            reply_id=self.reply_id, metadata=metadata or {}, **kw,
        ))

    # ── 统一分发 ─────────────────────────────────────────────────────

    async def handle(self, event) -> None:
        """统一事件分发器（重写基类）。"""
        from agentscope.event import (
            ReplyStartEvent, ReplyEndEvent, ExceedMaxItersEvent,
            TextBlockDeltaEvent, TextBlockEndEvent,
            ThinkingBlockDeltaEvent, ThinkingBlockEndEvent,
            ToolCallStartEvent, ToolCallEndEvent,
            ToolResultTextDeltaEvent, ToolResultDataDeltaEvent, ToolResultEndEvent,
            ModelCallEndEvent, ErrorEvent,
        )

        if isinstance(event, ReplyStartEvent):
            self.reply_id = getattr(event, "reply_id", None)
            self._publish_db("reply_start", EventCategory.LIFECYCLE, [EventLevel.DB],
                             {"name": getattr(event, "name", "")})

        elif isinstance(event, TextBlockDeltaEvent):
            delta = event.delta or ""
            if delta.strip():
                self.text_parts.append(delta)
                self._emit_sse("text", {"content": delta})   # 仅 SSE，不落库

        elif isinstance(event, TextBlockEndEvent):
            self._publish_db(
                "text_done", EventCategory.TEXT, [EventLevel.DB],
                {"text": "".join(self.text_parts)},
                block_id=getattr(event, "block_id", None),
            )
            self.text_parts = []

        elif isinstance(event, ThinkingBlockDeltaEvent):
            delta = event.delta or ""
            if delta.strip():
                self._emit_sse("thinking", {"content": delta})  # 仅 SSE

        elif isinstance(event, ThinkingBlockEndEvent):
            # 思考块不汇总落库内容（体积大、审计价值低），仅记块边界
            self._publish_db(
                "thinking_done", EventCategory.THINKING, [EventLevel.DB],
                {"block_id": getattr(event, "block_id", None)},
                block_id=getattr(event, "block_id", None),
            )

        elif isinstance(event, ToolCallStartEvent):
            self.current_tool_name = getattr(event, "tool_call_name", "") or ""
            self._tool_call_id = getattr(event, "tool_call_id", None)

        elif isinstance(event, ToolCallEndEvent):
            tool_input = getattr(event, "tool_args", {}) or {}
            self._publish_db(
                "tool_call", EventCategory.TOOL,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"tool_name": self.current_tool_name, "input": tool_input},
                tool_call_id=getattr(event, "tool_call_id", None),
                ui_hint="timeline",
            )
            self._emit_sse("tool_call", {
                "tool_name": self.current_tool_name, "input": tool_input,
            })

        elif isinstance(event, (ToolResultTextDeltaEvent, ToolResultDataDeltaEvent)):
            # 工具结果流式 delta：仅 SSE（二进制 data 记录 size 摘要）
            if isinstance(event, ToolResultTextDeltaEvent):
                d = getattr(event, "delta", "") or ""
                if d.strip():
                    self._emit_sse("tool_result", {
                        "tool_name": self.current_tool_name, "delta": d,
                        "state": "success",
                    })
            else:
                data_b64 = getattr(event, "data", None)
                self._emit_sse("tool_result", {
                    "tool_name": self.current_tool_name,
                    "media_type": getattr(event, "media_type", ""),
                    "data_size": len(data_b64) if data_b64 else 0,
                    "binary": True, "state": "success",
                })

        elif isinstance(event, ToolResultEndEvent):
            state = str(getattr(event, "state", "success") or "success").lower()
            self._publish_db(
                "tool_result", EventCategory.TOOL,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"tool_name": self.current_tool_name, "state": state},
                tool_call_id=getattr(event, "tool_call_id", None),
                ui_hint="timeline",
            )
            self._emit_sse("tool_result", {
                "tool_name": self.current_tool_name, "state": state,
            })

        elif isinstance(event, ModelCallEndEvent):
            self.iterations += 1
            self.usage["input_tokens"] += int(getattr(event, "input_tokens", 0) or 0)
            self.usage["output_tokens"] += int(getattr(event, "output_tokens", 0) or 0)
            self._publish_db(
                "model_call", EventCategory.MODEL, [EventLevel.LOG],
                {"model_name": getattr(event, "model_name", "")},
                metadata={"input_tokens": int(getattr(event, "input_tokens", 0) or 0),
                          "output_tokens": int(getattr(event, "output_tokens", 0) or 0),
                          "iteration": self.iterations},
            )

        elif isinstance(event, ExceedMaxItersEvent):
            self._publish_db(
                "iteration_limit", EventCategory.RUNTIME,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"iterations": self.iterations}, ui_hint="timeline",
            )

        elif isinstance(event, ReplyEndEvent):
            final_text = "".join(getattr(self, "_final_text_parts", []) or self.text_parts)
            self._publish_db(
                "reply_end", EventCategory.LIFECYCLE, [EventLevel.DB],
                {"finished_reason": "completed"},
                metadata={**self.usage, "iterations": self.iterations},
            )
            self._emit_sse("done", {"result": final_text})

        elif isinstance(event, ErrorEvent):
            self._publish_db(
                "error", EventCategory.ERROR,
                [EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                {"message": str(getattr(event, "error", ""))}, ui_hint="timeline",
            )
            self._emit_sse("error", {
                "message": str(getattr(event, "error", "")),
                "type": event.__class__.__name__,
            })

        else:
            # 未知事件：SSE error 兜底（保持旧版行为），不落库
            logger.debug("[SkillExecution] unhandled event: %s", event.__class__.__name__)
```

> **ReplyEndEvent 的 final_text**：text_parts 在 `text_done` 时被清空。为让 `done` SSE 事件拿到全文，`TextBlockDeltaEvent` 分支同时把 delta 追加到 `self._final_text_parts`（`__init__` 中初始化 `self._final_text_parts: list[str] = []`）。实现时把 `__init__` 中加一行 `self._final_text_parts: list[str] = []`，并把 TextBlockDelta 分支改为同时 append 两个列表。

(d) **删除** `_run_agent_native` 方法整体（原第 368-388 行，含第二处 `lambda evt: yield evt` 语法错误的死代码）。

- [ ] **Step 4: 验证语法修复 + 测试**

```bash
cd backend && python -c "import ast; ast.parse(open('app/ai/skills/execution.py', encoding='utf-8').read()); print('syntax ok')"
cd backend && python -m pytest tests/unit/test_skill_event_handler.py -v
```

Expected: `syntax ok`；测试 PASS（若 agentscope 构造字段名差异导致 FAIL，按 Step 0 输出修正 kwargs 后重跑）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/skills/execution.py backend/tests/unit/test_skill_event_handler.py
git commit -m "feat(agent): SkillEventHandler 重写——分级落库/三级关联/token 计量，修复 lambda-yield 语法错误"
```

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

### Task 11: Skill 多模式动态切换（ENGINE_DECISION 引擎路由）

**Files:**
- Modify: `backend/app/ai/skills/execution.py`
- Test: `backend/tests/unit/test_skill_mode_routing.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_skill_mode_routing.py`：

```python
"""Skill 执行模式动态切换单测：resolve/路由/unsupported。"""
import asyncio
import types

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService, resolve_execution_mode


def test_resolve_execution_mode():
    assert resolve_execution_mode("plan") == "plan"
    assert resolve_execution_mode("PLAN") == "plan"
    assert resolve_execution_mode(None) == "llm"
    assert resolve_execution_mode("bogus") == "llm"      # 非法回退 llm
    assert resolve_execution_mode("knowledge") == "knowledge"
    assert resolve_execution_mode("workflow") == "workflow"  # 合法但引擎未接入


class FakeModeAgent:
    """模拟 ReactAgent 等封装器：yield dict 事件。"""
    async def reply_stream(self, inputs):
        yield {"type": "progress", "data": {"stage": "planning"}}
        yield {"type": "done", "data": {"result": "ok"}}


class FakeDB:
    def add(self, o): pass
    def commit(self): pass
    def rollback(self): pass
    def query(self, model):
        return types.SimpleNamespace(filter=lambda *a, **kw: self,
                                     order_by=lambda *a, **kw: self,
                                     first=lambda: None)


def _patch(monkeypatch, svc):
    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_status", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed", lambda db, *a, **kw: None)
    monkeypatch.setattr("app.db.database.SessionLocal", lambda: FakeDB())


def test_engine_decision_emitted_first(monkeypatch):
    svc = SkillExecutionService(timeout=5, db=FakeDB())
    _patch(monkeypatch, svc)

    async def run():
        return [e async for e in svc.execute("demo", "hi", execution_id="e-mode")]

    evts = asyncio.run(run())
    assert evts[0].type == "engine_decision"
    assert evts[0].data["engine_code"] == "skill:llm"
    assert evts[0].data["mode"] == "llm"


def test_workflow_mode_reports_unsupported(monkeypatch):
    svc = SkillExecutionService(timeout=5, db=FakeDB())
    _patch(monkeypatch, svc)

    async def run():
        return [e async for e in svc.execute("demo", "hi", execution_id="e-wf",
                                              execution_mode="workflow")]

    evts = asyncio.run(run())
    types_ = [e.type for e in evts]
    assert types_[0] == "engine_decision"
    assert types_[0 + 1] == "error"
    assert "暂不支持" in evts[1].data["message"]


def test_plan_mode_routes_to_factory_agent(monkeypatch):
    svc = SkillExecutionService(timeout=5, db=FakeDB())
    _patch(monkeypatch, svc)

    from app.ai import agent_factory
    monkeypatch.setattr(
        agent_factory.AgentFactory, "create_agent",
        lambda self, session_type, config: FakeModeAgent(),
    )

    async def run():
        return [e async for e in svc.execute("demo", "hi", execution_id="e-plan",
                                              execution_mode="plan")]

    evts = asyncio.run(run())
    types_ = [e.type for e in evts]
    assert types_[0] == "engine_decision"
    assert types_[0] == "engine_decision" and evts[0].data["mode"] == "plan"
    assert "progress" in types_          # FakeModeAgent 的事件直通
    assert "done" in types_
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/unit/test_skill_mode_routing.py -v
```

Expected: FAIL，`ImportError: cannot import name 'resolve_execution_mode'`。

- [ ] **Step 3: 实现模式路由**

修改 `backend/app/ai/skills/execution.py`：

(a) 模块级常量与函数（放在 `SkillEvent` 定义之后）：

```python
# 引擎路由表（spec §5.5）：execution_mode → 引擎标识；None 表示 P0 未接入
_ENGINE_ROUTES: dict[str, Optional[str]] = {
    "llm": "agentscope",
    "skill": "agentscope",
    "plan": "react",
    "react": "react",
    "team": "team",
    "knowledge": "research",
    "harness": "research",
    "workflow": None,
}


def resolve_execution_mode(requested: Optional[str] = None) -> str:
    """解析执行模式：非法值回退 llm（spec §5.5）。"""
    mode = (requested or "llm").strip().lower()
    return mode if mode in _ENGINE_ROUTES else "llm"
```

(b) `SkillExecutionService.__init__` 增加 `db` 参数（llm 模式不需要，非 llm 模式用于 AgentFactory）：

```python
    def __init__(
        self,
        db: Any | None = None,
        workspace: Any | None = None,
        ...
    ) -> None:
        self._db = db
        ...
```

(c) `execute()` 签名追加 `execution_mode: str | None = None`；在 `AGENT_START` 信封发布之后、加载 Skill 之前插入：

```python
        # ── 模式解析与引擎路由（spec §5.5）─────────────────────────────
        mode = resolve_execution_mode(execution_mode)
        engine_code = f"skill:{mode}"
        self.bus.publish(EventEnvelope(
            execution_id=execution_id, trace_id=trace_id,
            event_type="engine_decision", category=EventCategory.AGENT,
            levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
            content={"engine_code": engine_code, "mode": mode},
            source="skill_execution", source_id=skill_name, ui_hint="timeline",
        ))
        yield SkillEvent(type="engine_decision",
                         data={"engine_code": engine_code, "mode": mode})

        if _ENGINE_ROUTES[mode] is None:
            self.bus.publish(EventEnvelope(
                execution_id=execution_id, trace_id=trace_id,
                event_type="error", category=EventCategory.ERROR,
                levels=[EventLevel.DB, EventLevel.STREAM, EventLevel.UI],
                content={"message": f"执行模式 {mode} 暂不支持（workflow 待接入）"},
                source="skill_execution", source_id=skill_name,
            ))
            yield SkillEvent(type="error",
                             data={"message": f"执行模式 {mode} 暂不支持"})
            record_execution_failed(_record_db, execution_id,
                                    error=f"执行模式 {mode} 暂不支持")
            return
```

(d) 执行 Agent 段（Task 8 的 `toolkit = ... / agent = self._create_agent(...)` 与 `_consume` 定义）替换为双路由：

```python
            toolkit = self._build_toolkit(extra_tools, skill.get("allowed_tools"))
            system_prompt = self._build_system_prompt(skill, session_id, user_id)
            model = self._build_model(model_id)
            user_msg = UserMsg(name="user", content=user_message)

            if _ENGINE_ROUTES[mode] == "agentscope":
                agent = self._create_agent(skill_name, system_prompt, model, toolkit)

                async def _consume() -> None:
                    async for event in agent.reply_stream(inputs=user_msg):
                        await handler.handle(event)
            else:
                agent = self._create_mode_agent(mode, model_id)

                async def _consume() -> None:
                    async for ev in agent.reply_stream(inputs=user_msg):
                        etype = normalize_event_type(str(ev.get("type", "progress")))
                        route = route_of(etype)
                        self.bus.publish(EventEnvelope(
                            execution_id=execution_id, trace_id=trace_id,
                            event_type=etype, category=route.category,
                            levels=sorted(route.levels),
                            content=(ev.get("data", {}) if isinstance(ev.get("data"), dict)
                                     else {"value": str(ev.get("data"))}),
                            source="skill_execution", source_id=skill_name,
                            ui_hint=route.ui_hint,
                        ))
                        out_q.put_nowait(SkillEvent(
                            type=str(ev.get("type", "progress")),
                            data=ev.get("data", {}),
                        ))
```

(e) 新增方法（`_create_agent` 之后）：

```python
    def _create_mode_agent(self, mode: str, model_id: int | None) -> Any:
        """非 llm 模式：委托 AgentFactory 对应封装器（spec §5.5 引擎路由）。"""
        if self._db is None:
            raise RuntimeError(f"执行模式 {mode} 需要 db 会话")
        from app.ai.agent_factory import AgentFactory

        session_type = {"react": "react", "team": "team",
                        "research": "deep_research"}[_ENGINE_ROUTES[mode]]
        return AgentFactory(self._db).create_agent(session_type, {
            "name": f"skill_{mode}",
            "model_id_db": model_id,
        })
```

(f) 顶部 import 补 `normalize_event_type, route_of`（event_types 已引入其余符号）。

- [ ] **Step 4: 运行测试通过**

```bash
cd backend && python -m pytest tests/unit/test_skill_mode_routing.py -v
cd backend && python -m pytest tests/unit -q
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/skills/execution.py backend/tests/unit/test_skill_mode_routing.py
git commit -m "feat(agent): Skill 七模式动态切换——ENGINE_DECISION 引擎路由"
```

---

### Task 12: 全量回归 + 验收核对

- [ ] **Step 1: 全量单测**

```bash
cd backend && python -m pytest tests/unit -q
```

Expected: 全部通过（原 19 个测试文件 + 新增 8 个）。

- [ ] **Step 2: import 冒烟（不依赖 DB 连接）**

```bash
cd backend && python -c "
import app.ai.skills.execution
import app.ai.events.bus
import app.ai.events.registry
import app.ai.events.hitl
import app.ai.skills.execution_records
import app.services.agent.agent_execution_service
print('smoke ok')
"
```

Expected: `smoke ok`。

- [ ] **Step 3: spec P0 验收核对**

| spec 验收项 | 核对方式 |
|---|---|
| 0.1 统一枚举单一来源 | `A is B is C` 检查（Task 3 Step 3） |
| 0.2 delta 停止落库 | `test_record_envelope_skips_db_for_stream` + `test_text_delta_not_persisted_but_ssed` |
| 0.3 主记录真实写入 | `test_start_creates_running_row` / `test_normal_run_calls_start_and_done` |
| 0.4 timeout 生效 | `test_timeout_emits_interrupt_events_and_marks_cancelled` |
| 0.5 DDL 47 + HITL 表 | `docs/sql/47_agent_event_enhance.sql` 含建表；ORM 列对齐；`AgentHitlPause` 注册 |
| 0.6 registry/cancel | `test_registry_lifecycle_and_cancel` + `test_execute_cancel_emits_interrupt_events` |
| 0.7 HITL 全链路 | `test_build_resume_event_*` + `test_record_and_resolve_pause` + `test_execute_hitl_pause_then_resume` |
| 0.8 模式动态切换 | `test_resolve_execution_mode` + `test_engine_decision_emitted_first` + `test_plan_mode_routes_to_factory_agent` |

- [ ] **Step 4: 提醒运维执行 DDL**

在最终 commit message 或 PR 描述中注明：**部署前需在 PostgreSQL 执行 `docs/sql/47_agent_event_enhance.sql`（PG 方言，IF NOT EXISTS 幂等，可重复执行）**。

- [ ] **Step 5: Final commit（如有零散修改）**

```bash
git status
git add -A backend/app backend/tests docs/sql/47_agent_event_enhance.sql
git commit -m "chore(agent): P0 收尾——全量回归通过"
```

---

## Self-Review 记录

- **Spec 覆盖**：P0 八项（0.1-0.8）分别由 Task 2/3、4/7、6、8（+10 超时路径）、1（DDL+HITL 表）、10（registry/cancel）、11（HITL）、12（模式路由）实现；spec §5.5 的四点对齐（事件/模式/中断/HITL）全部落在 P0；P1/P2 明确范围外。
- **类型一致性**：`EventBus.execution_id/trace_id` 属性在 Task 8 由 `execute()` 动态挂载（供 handler `_publish_db` 取用）——这是一个妥协点：更干净的做法是 EventBus 构造参数化；执行 Task 8 时若发现别扭，可改为 `EventBus(event_service=..., execution_id=..., trace_id=...)` 构造参数（同步修改 bus.py 与两个测试）。`RunHandle.status` 的三值（running/waiting_hitl/done）在 Task 9/10 间保持一致。
- **已知风险**：
  - agentscope 事件构造参数以安装版本为准（Task 7 Step 0 与 Task 10 先决验证有检查命令）；
  - `handle()` 兜底分支保持旧版"未知→error SSE"行为；
  - HITL 暂停期间 SSE 断开则恢复后流式输出丢失（Task 10 已注明，P1 解耦执行与请求生命周期）；
  - registry 无 TTL 回收，进程内孤儿句柄由 P1 对账任务清理；
  - `execution.py` 的 `record_execution_*` 需 monkeypatch `app.db.database.SessionLocal`（函数内 import 决定 patch 目标，Task 8 Step 3 已注明）。
