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

