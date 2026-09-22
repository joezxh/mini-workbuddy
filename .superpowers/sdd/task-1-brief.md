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
5. MySQL 8 的 `ALTER TABLE ... ADD COLUMN` 不支持 `IF NOT EXISTS`，DDL 47 只能执行一次。
6. 每个任务结束跑 `cd backend && python -m pytest tests/unit -q` 确认无回归，再 commit。

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
-- ⚠️ MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，本脚本只能执行一次。
-- 执行前请确认 47 号未应用过。

-- agent_execution_event：分级与三级关联
ALTER TABLE agent_execution_event
    ADD COLUMN level           SMALLINT     NULL COMMENT '最低分发层级 LOG=0/DB=1/STREAM=2/UI=3',
    ADD COLUMN category        VARCHAR(20)  NULL COMMENT '事件分类（EventCategory）',
    ADD COLUMN reply_id        VARCHAR(64)  NULL COMMENT 'AgentScope reply_id',
    ADD COLUMN block_id        VARCHAR(64)  NULL COMMENT '内容块 ID',
    ADD COLUMN tool_call_id    VARCHAR(64)  NULL COMMENT '工具调用关联 ID',
    ADD COLUMN interrupt_reason VARCHAR(20) NULL COMMENT 'timeout|user_cancel|system|error',
    ADD COLUMN ui_hint         VARCHAR(20)  NULL COMMENT '前端渲染路由提示',
    ADD COLUMN event_version   SMALLINT     NOT NULL DEFAULT 1 COMMENT '事件格式版本';

CREATE INDEX idx_event_reply ON agent_execution_event(execution_id, reply_id);
CREATE INDEX idx_event_category_level ON agent_execution_event(category, level);

-- agent_execution：结束原因与用量
ALTER TABLE agent_execution
    ADD COLUMN finished_reason  VARCHAR(20) NULL COMMENT 'completed|interrupted|exceed_max_iters|error',
    ADD COLUMN interrupt_reason VARCHAR(20) NULL COMMENT 'timeout|user_cancel|system|error',
    ADD COLUMN input_tokens     INT NULL COMMENT '累计输入 token',
    ADD COLUMN output_tokens    INT NULL COMMENT '累计输出 token',
    ADD COLUMN iterations       INT NULL COMMENT '推理-行动迭代轮数';

-- agent_hitl_pause：HITL 暂停记录（模型此前被移除、service 存在悬空引用，本 DDL 重建；spec §5.4/§5.5）
CREATE TABLE IF NOT EXISTS agent_hitl_pause (
    id              BIGINT      PRIMARY KEY AUTO_INCREMENT,
    execution_id    VARCHAR(64) NOT NULL COMMENT '执行 ID',
    reply_id        VARCHAR(64) NULL COMMENT 'AgentScope reply_id',
    tool_calls      JSON        NULL COMMENT '待确认工具调用列表（id/name/input）',
    suggested_rules JSON        NULL COMMENT '建议授权规则',
    status          VARCHAR(20) NOT NULL DEFAULT 'waiting' COMMENT 'waiting/approved/rejected/interrupted',
    accept_rules    TINYINT(1)  NOT NULL DEFAULT 0 COMMENT '是否接受授权规则',
    timeout_at      DATETIME    NULL COMMENT '超时提示时刻',
    answered_at     DATETIME    NULL COMMENT '用户应答时刻',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hitl_execution (execution_id),
    INDEX idx_hitl_status (status)
) COMMENT 'Agent/Skill 人机交互暂停记录';
```

- [ ] **Step 1b: 创建 `AgentHitlPause` 模型并注册**

创建 `backend/app/models/agent/agent_hitl_pause.py`：

```python
"""AgentHitlPause - 人机交互暂停记录表（spec §5.4/§5.5；DDL 47 重建）。

此前模型被移除但 agent_execution_service 仍存在悬空引用，本任务恢复。
"""
from __future__ import annotations

from sqlalchemy import Column, BigInteger, String, JSON, SmallInteger, DateTime
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AgentHitlPause(Base, TenantMixin):
    """人机交互暂停记录。"""
    __tablename__ = "agent_hitl_pause"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), nullable=False, index=True, comment="执行 ID")
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

