# ReAct（Reasoning + Acting）模式实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 AI 模块中新增 ReAct 计划执行模式，使 Agent 能自动制定计划、逐步执行、反思调整，支持 HITL 人机交互和 Skill 嵌套 ReAct。

**Architecture:** 采用 ReActOrchestrator 独立编排器（仿 ResearchOrchestrator 模式），通过 PlanGenerator 生成结构化计划，逐步执行并反思调整。双入口触发（session_type="react" 直接路由 + execution_mode="plan" 自动映射）。HITL 通过 asyncio.Event 门控 + 全局注册表 + REST API 实现暂停/恢复/确认。

**Tech Stack:** Python 3.11+ / FastAPI / AgentScope 2.0.7 / SQLAlchemy / Vue 3 + Ant Design Vue / SSE

## Global Constraints

- 现有 Agent 类型零侵入：不修改 CHAT/WORKFLOW/SKILL 任何代码路径
- SkillExecutionService 向后兼容：`execution_mode` 参数默认 `"direct"`
- 数据库无迁移：`react_config` JSONB 字段已存在于 `agent_config` 表
- SSE 事件命名空间：所有新事件以 `react_` 前缀
- 遵循现有代码风格：ResearchOrchestrator 的 emit 闭包模式、AgentFactory 的 match/case 扩展

---

## File Structure

```
新建文件：
  backend/app/ai/react/__init__.py              — 模块初始化，导出 ReActOrchestrator
  backend/app/ai/react/orchestrator.py          — 核心编排器：循环、暂停/恢复、事件 yield
  backend/app/ai/react/plan_generator.py        — LLM 计划生成 + 反思评估 + 计划调整
  backend/app/ai/react/skill_adapter.py         — Skill → FunctionTool 包装
  backend/app/routers/ai/react.py               — HITL REST API（状态/批准/响应/暂停/恢复/取消）
  backend/app/schemas/agent/react_schemas.py    — Pydantic 请求/响应模型
  frontend/src/views/assistant/components/ReactTimeline.vue    — 步骤时间线组件
  frontend/src/views/assistant/components/ReactSkillPanel.vue  — 嵌套 Skill 执行面板
  frontend/src/views/assistant/components/ReactConfirmPanel.vue — HITL 确认面板
  frontend/src/api/react.ts                     — HITL API 调用

修改文件：
  backend/app/ai/agent_factory.py               — 新增 ReactAgent + case "react"
  backend/app/routers/ai/ai_agent.py            — 双入口路由 + _build_agent_config 扩展
  frontend/src/api/aiSession.ts                 — 新增 react 会话类型
  frontend/src/views/assistant/components/ChatContainer.vue — SSE 事件消费 + ReactTimeline 集成
  frontend/src/views/admin/agent/components/AgentFormModal.vue — ReAct 配置区域
  frontend/src/i18n/locales/zh-CN.ts            — react 命名空间翻译
  frontend/src/i18n/locales/en-US.ts            — 同上
  frontend/src/i18n/locales/zh-TW.ts            — 同上
  frontend/src/i18n/locales/ja-JP.ts            — 同上
```

---

### Task 1: 数据模型 + 模块初始化

**Files:**
- Create: `backend/app/ai/react/__init__.py`
- Create: `backend/app/ai/react/orchestrator.py`（仅数据模型部分）

**Interfaces:**
- Produces: `PlanStep` dataclass, `ExecutionPlan` dataclass — 后续 Task 2/3 依赖

- [ ] **Step 1: 创建模块初始化文件**

```python
# backend/app/ai/react/__init__.py
"""ReAct 计划执行模式 — 基于 Plan-Execute-Reflect 循环的 Agent 编排。"""
```

- [ ] **Step 2: 在 orchestrator.py 中定义数据模型**

```python
# backend/app/ai/react/orchestrator.py 顶部
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# 全局注册表：供 HITL REST API 触达运行中的编排器实例
REACT_REGISTRY: Dict[str, "ReActOrchestrator"] = {}


@dataclass
class PlanStep:
    """执行计划中的单个步骤。"""
    id: str               # "step_1", "step_2"...
    title: str            # 步骤标题
    description: str      # 详细描述
    status: str = "pending"  # pending / running / done / failed / skipped
    result: str = ""      # 执行结果摘要
    tool_calls: list = field(default_factory=list)  # [{name, input, output}]
    depth: int = 0        # 嵌套深度（0=外层, 1=Skill 内部...）

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "status": self.status, "result": self.result,
            "tool_calls": self.tool_calls, "depth": self.depth,
        }


@dataclass
class ExecutionPlan:
    """ReAct 执行计划。"""
    goal: str             # 用户目标
    steps: List[PlanStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "planning"  # planning / executing / reflecting / done / cancelled
    iteration: int = 0

    def to_dict(self) -> dict:
        return {
            "goal": self.goal, "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step, "status": self.status,
            "iteration": self.iteration,
        }
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/react/__init__.py backend/app/ai/react/orchestrator.py
git commit -m "feat(react): add data models and module init"
```

---

### Task 2: PlanGenerator — LLM 计划生成 + 反思

**Files:**
- Create: `backend/app/ai/react/plan_generator.py`

**Interfaces:**
- Consumes: `PlanStep`, `ExecutionPlan` from Task 1
- Consumes: `app.ai.research.llm.llm_json` 和 `app.ai.research.llm.llm_complete`（复用 LLM 调用）
- Produces: `PlanGenerator` 类 — Task 3 orchestrator 依赖

- [ ] **Step 1: 实现计划生成 Prompt 和 generate() 方法**

```python
# backend/app/ai/react/plan_generator.py
"""ReAct 计划生成器 — LLM 驱动的计划生成、反思评估、计划调整。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.ai.research.llm import llm_json, llm_complete
from app.ai.react.orchestrator import PlanStep, ExecutionPlan

logger = logging.getLogger(__name__)

_PROMPT_GENERATE_PLAN = """你是一个任务规划专家。用户的目标如下：
<goal>{goal}</goal>

可用的工具：
<tools>{tool_descriptions}</tools>

可用的技能：
<skills>{skill_descriptions}</skills>

请将目标分解为不超过 {max_steps} 个具体、可执行的步骤。
每个步骤应明确：
1. 步骤标题
2. 具体描述（需要做什么）
3. 使用的工具或技能（如有）

输出 JSON：
{{"steps": [{{"title": "...", "description": "...", "tool": "tool_name or null", "skill": "skill_name or null"}}]}}"""

_PROMPT_REFLECT = """你是任务执行的质量评估官。

当前步骤：{step_title}
步骤描述：{step_description}
执行结果：{result}
用户原始目标：{goal}

请评估：
1. 该步骤是否达到预期？(satisfied: true/false)
2. 是否需要调整后续计划？(needs_adjust: true/false)
3. 如需调整，具体建议是什么？

输出 JSON：
{{"satisfied": true, "needs_adjust": false, "reason": "...", "suggestions": []}}"""

_PROMPT_ADJUST = """你是任务规划专家。原计划执行过程中发现需要调整。

用户原始目标：{goal}

当前计划：
{current_plan}

已完成的步骤及结果：
{completed_results}

反思评估：
{reflection}

请调整后续计划（保留未变更的步骤，修改/新增/跳过需要的步骤）。
输出 JSON：
{{"steps": [{{"title": "...", "description": "...", "tool": "tool_name or null", "skill": "skill_name or null"}}]}}"""


class PlanGenerator:
    """LLM 驱动的计划生成与调整。"""

    def __init__(self, model_id: Optional[int] = None):
        self.model_id = model_id

    async def generate(
        self,
        goal: str,
        tools: Optional[List[dict]] = None,
        skills: Optional[List[dict]] = None,
        max_steps: int = 10,
    ) -> ExecutionPlan:
        """根据用户目标和可用工具/技能，生成执行计划。"""
        tool_descs = "\n".join(
            f"- {t.get('name', '')}: {t.get('description', '')}" for t in (tools or [])
        ) or "（无可用工具）"
        skill_descs = "\n".join(
            f"- {s.get('name', '')}: {s.get('description', '')}" for s in (skills or [])
        ) or "（无可用技能）"

        prompt = _PROMPT_GENERATE_PLAN.format(
            goal=goal, tool_descriptions=tool_descs,
            skill_descriptions=skill_descs, max_steps=max_steps,
        )
        try:
            result = await llm_json(prompt, self.model_id)
        except Exception as e:
            logger.error(f"计划生成失败: {e}")
            raise

        steps = []
        for i, s in enumerate(result.get("steps", [])[:max_steps]):
            steps.append(PlanStep(
                id=f"step_{i + 1}",
                title=s.get("title", f"步骤 {i + 1}"),
                description=s.get("description", ""),
            ))
        return ExecutionPlan(goal=goal, steps=steps)

    async def reflect(
        self,
        step: PlanStep,
        result: str,
        goal: str,
    ) -> Dict[str, Any]:
        """评估步骤执行结果（深度反思模式）。"""
        prompt = _PROMPT_REFLECT.format(
            step_title=step.title,
            step_description=step.description,
            result=result[:2000],
            goal=goal,
        )
        try:
            return await llm_json(prompt, self.model_id)
        except Exception as e:
            logger.error(f"反思评估失败: {e}")
            return {"satisfied": True, "needs_adjust": False, "reason": f"反思失败: {e}"}

    async def adjust(
        self,
        plan: ExecutionPlan,
        reflection: Dict[str, Any],
        goal: str,
    ) -> List[PlanStep]:
        """基于反思结果调整后续计划。"""
        current_plan_text = "\n".join(
            f"{s.id}: {s.title} [{s.status}] {s.description}" for s in plan.steps
        )
        completed_text = "\n".join(
            f"{s.id}: {s.title} → {s.result[:200]}" for s in plan.steps if s.status == "done"
        ) or "（无已完成步骤）"
        suggestions = reflection.get("suggestions", [])
        reflection_text = f"原因: {reflection.get('reason', '')}\n建议: {'; '.join(suggestions)}"

        prompt = _PROMPT_ADJUST.format(
            goal=goal, current_plan=current_plan_text,
            completed_results=completed_text, reflection=reflection_text,
        )
        try:
            result = await llm_json(prompt, self.model_id)
        except Exception as e:
            logger.error(f"计划调整失败: {e}")
            return plan.steps  # 失败时保持原计划

        new_steps = []
        for i, s in enumerate(result.get("steps", [])):
            new_steps.append(PlanStep(
                id=f"step_adj_{i + 1}",
                title=s.get("title", f"调整步骤 {i + 1}"),
                description=s.get("description", ""),
            ))
        return new_steps
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ai/react/plan_generator.py
git commit -m "feat(react): add PlanGenerator with LLM-based plan/reflect/adjust"
```

---

### Task 3: ReActOrchestrator 核心编排器

**Files:**
- Modify: `backend/app/ai/react/orchestrator.py`（补充完整 ReActOrchestrator 类）

**Interfaces:**
- Consumes: `PlanStep`, `ExecutionPlan`, `REACT_REGISTRY` from Task 1
- Consumes: `PlanGenerator` from Task 2
- Produces: `ReActOrchestrator.run()` → `AsyncGenerator[dict, None]` — Task 4 ReactAgent 消费

- [ ] **Step 1: 实现 ReActOrchestrator 类**

在 `backend/app/ai/react/orchestrator.py` 中数据模型之后添加：

```python
class ReActOrchestrator:
    """ReAct 计划执行编排器 — Plan → Execute → Reflect → Adjust 循环。"""

    def __init__(
        self,
        db: Any,
        model_id: Optional[int] = None,
        tools: Optional[list] = None,
        react_config: Optional[dict] = None,
        sys_prompt: str = "",
        skills: Optional[list] = None,
    ):
        self.db = db
        self.model_id = model_id
        self.tools = tools or []
        self.skills = skills or []
        self.sys_prompt = sys_prompt

        cfg = react_config or {}
        self.max_iters = cfg.get("max_iters", 10)
        self.timeout_seconds = cfg.get("timeout_seconds", 300)
        self.interaction_mode = cfg.get("interaction_mode", "auto")
        self.reflection_mode = cfg.get("reflection_mode", "lightweight")

        self._gate = asyncio.Event()
        self._gate.set()  # 默认不暂停
        self._cancelled = False
        self._run_id = str(uuid.uuid4())
        self._plan: Optional[ExecutionPlan] = None

    async def run(self, user_text: str) -> AsyncGenerator[dict, None]:
        """执行 ReAct 循环，yield SSE 兼容的 dict 事件。"""
        REACT_REGISTRY[self._run_id] = self
        _start = time.perf_counter()

        try:
            yield {"type": "react_start", "goal": user_text,
                   "plan_summary": f"目标: {user_text[:100]}"}

            # 1. 生成计划
            from app.ai.react.plan_generator import PlanGenerator
            generator = PlanGenerator(model_id=self.model_id)

            yield {"type": "react_progress", "message": "正在生成执行计划...",
                   "current_step": 0, "total_steps": 0}

            plan = await generator.generate(
                goal=user_text,
                tools=[{"name": t.get("name", ""), "description": t.get("description", "")}
                       for t in self.tools] if self.tools else None,
                skills=[{"name": s, "description": s} for s in self.skills],
                max_steps=self.max_iters,
            )
            self._plan = plan
            yield {"type": "react_plan", "steps": [s.to_dict() for s in plan.steps]}

            # 2. approve 模式：等待用户确认计划
            if self.interaction_mode == "approve":
                yield {"type": "react_confirm", "step_id": "__plan__",
                       "question": "是否批准执行此计划？",
                       "options": [
                           {"label": "批准执行", "value": "approve", "description": "按计划执行"},
                           {"label": "取消", "value": "cancel", "description": "取消执行"},
                       ],
                       "allow_custom": False}
                await self._gate.wait()
                if self._cancelled:
                    yield {"type": "react_done", "final_result": "用户已取消执行"}
                    return

            # 3. 逐步执行
            plan.status = "executing"
            for idx, step in enumerate(plan.steps):
                if self._cancelled:
                    break

                # 超时检查
                if time.perf_counter() - _start > self.timeout_seconds:
                    yield {"type": "react_error", "message": "执行超时", "step_id": step.id}
                    break

                step.status = "running"
                plan.current_step = idx + 1
                plan.iteration = idx + 1

                yield {"type": "react_step_start", "step_id": step.id,
                       "title": step.title, "depth": step.depth}

                # 执行步骤
                result = await self._execute_step(step, user_text)
                step.result = result
                step.status = "done" if result else "failed"

                yield {"type": "react_step_done", "step_id": step.id,
                       "title": step.title, "result": result[:500],
                       "status": step.status}

                # 反思
                if self.reflection_mode == "deep" and step.status == "done":
                    yield {"type": "react_progress", "message": f"反思步骤: {step.title}...",
                           "current_step": idx + 1, "total_steps": len(plan.steps)}
                    reflection = await generator.reflect(step, result, user_text)
                    yield {"type": "react_reflect", "step_id": step.id,
                           "assessment": reflection.get("reason", ""),
                           "adjusted": reflection.get("needs_adjust", False)}

                    if reflection.get("needs_adjust"):
                        new_steps = await generator.adjust(plan, reflection, user_text)
                        # 替换未执行的步骤
                        plan.steps = plan.steps[:idx + 1] + new_steps
                        yield {"type": "react_plan_update",
                               "steps": [s.to_dict() for s in plan.steps]}

                # confirm_steps 模式：关键步骤暂停
                if (self.interaction_mode == "confirm_steps"
                        and idx < len(plan.steps) - 1):
                    yield {"type": "react_confirm", "step_id": step.id,
                           "question": f"步骤 {step.title} 已完成，是否继续？",
                           "options": [
                               {"label": "继续执行", "value": "continue"},
                               {"label": "跳过下一步", "value": "skip"},
                               {"label": "取消", "value": "cancel"},
                           ],
                           "allow_custom": True}
                    await self._gate.wait()
                    if self._cancelled:
                        break

            # 4. 汇总报告
            plan.status = "done"
            completed = [s for s in plan.steps if s.status == "done"]
            summary_parts = [f"- {s.title}: {s.result[:200]}" for s in completed]
            summary = f"## 执行报告\n\n目标: {user_text}\n\n完成 {len(completed)}/{len(plan.steps)} 步:\n" + "\n".join(summary_parts)

            yield {"type": "react_report", "summary": summary,
                   "steps_completed": len(completed), "result": summary}
            yield {"type": "react_done", "final_result": summary}

        except Exception as e:
            logger.exception("ReAct 执行异常: %s", e)
            yield {"type": "react_error", "message": str(e)}
        finally:
            REACT_REGISTRY.pop(self._run_id, None)

    async def _execute_step(self, step: PlanStep, goal: str) -> str:
        """执行单个步骤（通过 LLM + 工具调用）。"""
        # 构建执行 prompt：让 LLM 根据步骤描述和目标执行
        from app.ai.research.llm import llm_complete

        tool_context = ""
        if step.tool_calls:
            tool_context = "\n已有工具调用记录: " + json.dumps(step.tool_calls, ensure_ascii=False)

        prompt = f"""你是一个任务执行助手。请完成以下步骤。

用户目标：{goal}

当前步骤：{step.title}
步骤描述：{step.description}
{tool_context}

请直接执行并给出结果。"""

        try:
            result = await llm_complete(prompt, self.model_id)
            return result
        except Exception as e:
            logger.error(f"步骤执行失败 [{step.id}]: {e}")
            return f"执行失败: {e}"

    # ── HITL 控制 ──────────────────────────────────────────
    def request_pause(self) -> None:
        self._gate.clear()

    def resume(self, answer: Optional[str] = None) -> None:
        self._gate.set()

    def cancel(self) -> None:
        self._cancelled = True
        self._gate.set()

    def get_status(self) -> dict:
        return {
            "run_id": self._run_id,
            "plan": self._plan.to_dict() if self._plan else None,
            "cancelled": self._cancelled,
            "interaction_mode": self.interaction_mode,
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ai/react/orchestrator.py
git commit -m "feat(react): add ReActOrchestrator with plan-execute-reflect loop"
```

---

### Task 4: ReactAgent 封装 + AgentFactory 集成

**Files:**
- Modify: `backend/app/ai/agent_factory.py`

**Interfaces:**
- Consumes: `ReActOrchestrator` from Task 3
- Produces: `ReactAgent` 类 + `AgentFactory.create_agent("react", ...)` 支持

- [ ] **Step 1: 在 agent_factory.py 中添加 ReactAgent 类**

在 `TeamAgent` 类之后添加：

```python
class ReactAgent:
    """ReAct 计划执行 Agent 封装。"""

    def __init__(self, db, model_id, tools, react_config, sys_prompt,
                 name="ReAct 助手", skills=None):
        self._db = db
        self._model_id = model_id
        self._tools = tools
        self._react_config = react_config or {}
        self._sys_prompt = sys_prompt
        self._skills = skills or []
        self.name = name

    async def reply_stream(self, user_msg) -> AsyncGenerator[dict, None]:
        from app.ai.react.orchestrator import ReActOrchestrator
        topic = text_of(user_msg)
        orchestrator = ReActOrchestrator(
            db=self._db,
            model_id=self._model_id,
            tools=self._tools,
            react_config=self._react_config,
            sys_prompt=self._sys_prompt,
            skills=self._skills,
        )
        async for event in orchestrator.run(topic):
            yield {"type": event.get("type", "message"), "data": event}
```

- [ ] **Step 2: 在 AgentFactory.create_agent() 中添加 react case**

```python
# 在 match session_type 中添加 case "react"
case "react":
    return self._create_react_agent(config)
```

- [ ] **Step 3: 添加 `_create_react_agent()` 方法**

```python
def _create_react_agent(self, config: dict):
    """ReAct 计划执行 Agent"""
    return ReactAgent(
        db=self._db,
        model_id=config.get("model_id_db"),
        tools=config.get("tools", []),
        react_config=config.get("react_config", {}),
        sys_prompt=config.get("sys_prompt", ""),
        name=config.get("name", "ReAct 助手"),
        skills=config.get("skills", []),
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/ai/agent_factory.py
git commit -m "feat(react): add ReactAgent and factory integration"
```

---

### Task 5: 双入口路由 + _build_agent_config 扩展

**Files:**
- Modify: `backend/app/routers/ai/ai_agent.py`

**Interfaces:**
- Consumes: `AgentConfig.execution_mode`, `AgentConfig.react_config`
- Produces: `session_type="react"` 自动路由

- [ ] **Step 1: 扩展 _build_agent_config() 读取 execution_mode 和 react_config**

修改 `_build_agent_config()` 中 `if req.agent_id` 块，使其不限于 `session_type == "agent"`：

```python
# 原代码：if req.agent_id and session_type == "agent":
# 改为：
if req.agent_id:
    from app.models.agent.agent_config import AgentConfig
    agent_cfg = db.query(AgentConfig).filter(
        AgentConfig.id == req.agent_id
    ).first()
    if agent_cfg:
        config["name"] = agent_cfg.name or "助手"
        config["sys_prompt"] = agent_cfg.system_prompt or ""
        config["tools"] = agent_cfg.tools or []
        config["execution_mode"] = agent_cfg.execution_mode or "llm"
        config["react_config"] = agent_cfg.react_config or {}
        config["skills"] = agent_cfg.skills or []
```

- [ ] **Step 2: 在 chat_stream 中添加双入口路由逻辑**

在 `agent_config = _build_agent_config(...)` 之后、`async def event_generator()` 之前添加：

```python
# 双入口：execution_mode="plan" 自动映射为 react session_type
if req.agent_id and agent_config.get("execution_mode") == "plan":
    session_type = "react"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/ai/ai_agent.py
git commit -m "feat(react): add dual-entry routing for execution_mode=plan"
```

---

### Task 6: HITL REST API

**Files:**
- Create: `backend/app/schemas/agent/react_schemas.py`
- Create: `backend/app/routers/ai/react.py`

**Interfaces:**
- Consumes: `REACT_REGISTRY` from Task 3
- Produces: REST 端点供前端 HITL 面板调用

- [ ] **Step 1: 创建 Pydantic 模型**

```python
# backend/app/schemas/agent/react_schemas.py
"""ReAct HITL 请求/响应模型。"""
from pydantic import BaseModel
from typing import Optional


class ReactRespondRequest(BaseModel):
    """响应 HITL 确认请求。"""
    step_id: Optional[str] = None
    answer: str = ""
    action: str = "confirm"  # confirm / skip / cancel


class ReactStatusResponse(BaseModel):
    """ReAct 运行状态响应。"""
    run_id: str
    plan: Optional[dict] = None
    cancelled: bool = False
    interaction_mode: str = "auto"
```

- [ ] **Step 2: 创建路由**

```python
# backend/app/routers/ai/react.py
"""ReAct HITL REST API — 暂停/恢复/确认/取消运行中的 ReAct 编排器。"""
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.agent.react_schemas import ReactRespondRequest, ReactStatusResponse

router = APIRouter(prefix="/react", tags=["ReAct HITL"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_orchestrator(run_id: str):
    from app.ai.react.orchestrator import REACT_REGISTRY
    orch = REACT_REGISTRY.get(run_id)
    if not orch:
        raise HTTPException(status_code=404, detail=f"ReAct 运行不存在或已结束: {run_id}")
    return orch


@router.get("/{run_id}/status")
async def get_status(run_id: str):
    orch = _get_orchestrator(run_id)
    return orch.get_status()


@router.post("/{run_id}/approve")
async def approve_plan(run_id: str):
    orch = _get_orchestrator(run_id)
    orch.resume()
    return {"message": "计划已批准"}


@router.post("/{run_id}/respond")
async def respond(run_id: str, req: ReactRespondRequest):
    orch = _get_orchestrator(run_id)
    if req.action == "cancel":
        orch.cancel()
        return {"message": "已取消"}
    if req.action == "skip":
        orch.resume(answer="__skip__")
        return {"message": "已跳过"}
    orch.resume(answer=req.answer)
    return {"message": "已确认"}


@router.post("/{run_id}/pause")
async def pause(run_id: str):
    orch = _get_orchestrator(run_id)
    orch.request_pause()
    return {"message": "已暂停"}


@router.post("/{run_id}/resume")
async def resume(run_id: str):
    orch = _get_orchestrator(run_id)
    orch.resume()
    return {"message": "已恢复"}


@router.post("/{run_id}/cancel")
async def cancel(run_id: str):
    orch = _get_orchestrator(run_id)
    orch.cancel()
    return {"message": "已取消"}
```

- [ ] **Step 3: 注册路由到 main.py**

在 `backend/app/main.py` 中添加：

```python
from app.routers.ai.react import router as react_router
app.include_router(react_router, prefix="/api/v1")
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/agent/react_schemas.py backend/app/routers/ai/react.py backend/app/main.py
git commit -m "feat(react): add HITL REST API for pause/resume/confirm/cancel"
```

---

### Task 7: Skill 适配器

**Files:**
- Create: `backend/app/ai/react/skill_adapter.py`

**Interfaces:**
- Consumes: `SkillExecutionService` from `app.ai.skills.execution`
- Produces: `create_skill_tool()` → `FunctionTool` — 供 ReActOrchestrator 注入 Toolkit

- [ ] **Step 1: 实现 Skill → FunctionTool 包装**

```python
# backend/app/ai/react/skill_adapter.py
"""Skill → FunctionTool 适配器 — 将 Skill 包装为 ReAct 可调用的工具。"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def create_skill_tool(skill_name: str, skill_config: dict, db: Any) -> Any:
    """将 Skill 包装为 AgentScope FunctionTool。

    Args:
        skill_name: 技能名称
        skill_config: 技能配置 {"description": "...", "execution_mode": "direct|react"}
        db: SQLAlchemy Session

    Returns:
        FunctionTool 实例
    """
    from agentscope.tool import FunctionTool

    async def execute_skill(input: str) -> str:
        """执行技能并返回结果。

        Args:
            input: 传递给技能的输入文本。
        """
        from app.ai.skills.execution import SkillExecutionService

        service = SkillExecutionService()
        execution_mode = skill_config.get("execution_mode", "direct")
        result_parts = []

        async for event in service.execute(
            skill_name=skill_name,
            user_message=input,
        ):
            if event.type == "done":
                result_parts.append(event.data.get("result", ""))
            elif event.type == "text":
                result_parts.append(event.data.get("content", ""))

        return "\n".join(result_parts) if result_parts else f"技能 {skill_name} 无输出"

    return FunctionTool(
        execute_skill,
        name=f"skill_{skill_name}",
        description=skill_config.get("description", f"执行技能 {skill_name}"),
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ai/react/skill_adapter.py
git commit -m "feat(react): add skill adapter for FunctionTool wrapping"
```

---

### Task 8: 前端 — ReactTimeline.vue 步骤时间线

**Files:**
- Create: `frontend/src/views/assistant/components/ReactTimeline.vue`

**Interfaces:**
- Consumes: SSE 事件 `react_*` 系列
- Produces: 时间线 UI 组件，供 ChatContainer 消费

- [ ] **Step 1: 实现步骤时间线组件**

创建 `ReactTimeline.vue`，包含：
- Props: `events: Array<ReactEvent>`（从父组件传入的 SSE 事件列表）
- 响应式数据: `steps: PlanStep[]`, `planStatus: string`, `goal: string`
- 监听 `react_*` 事件更新步骤状态
- CI/CD 流水线风格：左侧竖线 + 节点图标（pending/running/done/failed/skipped）
- 每个节点可展开查看详情（思考内容、工具调用、结果摘要）
- 嵌套 Skill 子面板（depth > 0 时缩进展示）

组件核心结构：
```vue
<template>
  <div class="react-timeline">
    <!-- 目标标题 -->
    <div class="timeline-header">
      <span class="goal-icon">🎯</span>
      <span class="goal-text">{{ goal }}</span>
      <a-tag :color="statusColor">{{ statusText }}</a-tag>
    </div>

    <!-- 步骤列表 -->
    <div class="timeline-steps">
      <div v-for="step in steps" :key="step.id" class="timeline-step"
           :class="[`depth-${step.depth}`, step.status]">
        <!-- 连接线 + 图标 -->
        <div class="step-indicator">
          <div class="step-line" />
          <span class="step-icon" v-html="statusIcon(step.status)" />
        </div>
        <!-- 内容 -->
        <div class="step-content" @click="toggleExpand(step.id)">
          <div class="step-header">
            <span class="step-title">{{ step.title }}</span>
            <a-tag :color="stepStatusColor(step.status)" size="small">
              {{ stepStatusText(step.status) }}
            </a-tag>
          </div>
          <!-- 展开详情 -->
          <div v-if="expanded.has(step.id)" class="step-detail">
            <div v-if="step.result" class="step-result">
              <pre>{{ step.result }}</pre>
            </div>
            <!-- 嵌套 Skill 子面板 -->
            <ReactSkillPanel v-if="step.depth > 0" :events="skillEvents(step.id)" />
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="timeline-actions" v-if="planStatus === 'executing'">
      <a-button size="small" @click="$emit('pause')">⏸ 暂停</a-button>
      <a-button size="small" danger @click="$emit('cancel')">✖ 取消</a-button>
    </div>
  </div>
</template>
```

样式参考现有 `UnifiedTimeline.vue` 和 `DeepResearchExecutionPanel.vue` 的设计语言。

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/assistant/components/ReactTimeline.vue
git commit -m "feat(react): add ReactTimeline step component"
```

---

### Task 9: 前端 — ReactConfirmPanel + ReactSkillPanel

**Files:**
- Create: `frontend/src/views/assistant/components/ReactConfirmPanel.vue`
- Create: `frontend/src/views/assistant/components/ReactSkillPanel.vue`

- [ ] **Step 1: 实现 HITL 确认面板**

`ReactConfirmPanel.vue`：
- Props: `question: string`, `options: Array<{label, value, description}>`, `allowCustom: boolean`
- Emits: `confirm(value, action)`, `skip`, `cancel`
- UI: 问题文本 + radio 选项列表 + 自定义输入框(textarea) + 确认/跳过按钮
- 参考 Qoder AskUserQuestion 的交互模式

```vue
<template>
  <div class="react-confirm-panel">
    <div class="confirm-question">{{ question }}</div>
    <a-radio-group v-model:value="selectedValue" class="confirm-options">
      <a-radio v-for="opt in options" :key="opt.value" :value="opt.value">
        <span class="option-label">{{ opt.label }}</span>
        <span v-if="opt.description" class="option-desc">{{ opt.description }}</span>
      </a-radio>
    </a-radio-group>
    <a-textarea v-if="allowCustom" v-model:value="customInput"
                placeholder="或输入自定义回答..." :auto-size="{ minRows: 2, maxRows: 4 }" />
    <div class="confirm-actions">
      <a-button type="primary" size="small" @click="handleConfirm">✅ 确认</a-button>
      <a-button size="small" @click="$emit('skip')">⏭ 跳过</a-button>
      <a-button size="small" danger @click="$emit('cancel')">✖ 取消</a-button>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 实现嵌套 Skill 面板**

`ReactSkillPanel.vue`：
- Props: `events: Array`（该 Skill 的 react_* 事件子集）
- 展示 Skill 内部的步骤时间线（缩进 + "Skill: xxx" 标题）
- 复用 ReactTimeline 的渲染逻辑

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/assistant/components/ReactConfirmPanel.vue
git add frontend/src/views/assistant/components/ReactSkillPanel.vue
git commit -m "feat(react): add HITL confirm panel and nested skill panel"
```

---

### Task 10: 前端 — API 层 + SSE 事件消费

**Files:**
- Create: `frontend/src/api/react.ts`
- Modify: `frontend/src/api/aiSession.ts`
- Modify: `frontend/src/views/assistant/components/ChatContainer.vue`

- [ ] **Step 1: 创建 HITL API 调用文件**

```typescript
// frontend/src/api/react.ts
import request from '@/utils/request'

const BASE = '/api/v1/react'

export function getReactStatus(runId: string) {
  return request.get(`${BASE}/${runId}/status`)
}

export function approveReact(runId: string) {
  return request.post(`${BASE}/${runId}/approve`)
}

export function respondReact(runId: string, data: { step_id?: string; answer: string; action: string }) {
  return request.post(`${BASE}/${runId}/respond`, data)
}

export function pauseReact(runId: string) {
  return request.post(`${BASE}/${runId}/pause`)
}

export function resumeReact(runId: string) {
  return request.post(`${BASE}/${runId}/resume`)
}

export function cancelReact(runId: string) {
  return request.post(`${BASE}/${runId}/cancel`)
}
```

- [ ] **Step 2: 在 aiSession.ts 中添加 react 会话类型**

在会话类型常量或类型定义中添加 `"react"` 选项。

- [ ] **Step 3: 在 ChatContainer.vue 中集成 SSE 事件消费**

在 SSE 事件处理逻辑中添加 `react_*` 事件的处理：

```typescript
// 在事件处理 switch/if 中添加
case 'react_start':
case 'react_plan':
case 'react_step_start':
case 'react_step_done':
case 'react_thinking':
case 'react_tool_call':
case 'react_tool_result':
case 'react_reflect':
case 'react_plan_update':
case 'react_progress':
case 'react_confirm':
case 'react_skill_start':
case 'react_skill_done':
case 'react_report':
case 'react_done':
  // 更新 ReactTimeline 响应式数据
  reactEvents.value.push({ type: eventType, ...eventData })
  break
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/react.ts frontend/src/api/aiSession.ts
git add frontend/src/views/assistant/components/ChatContainer.vue
git commit -m "feat(react): add API layer and SSE event consumption"
```

---

### Task 11: 前端 — Agent 配置 UI

**Files:**
- Modify: `frontend/src/views/admin/agent/components/AgentFormModal.vue`

- [ ] **Step 1: 添加 ReAct 配置区域**

在执行模式下拉中新增 `plan`(ReAct) 选项。选择 `plan` 时展开配置区域：

```vue
<!-- 在 AgentFormModal.vue 中添加 -->
<a-form-item label="执行模式" name="execution_mode">
  <a-select v-model:value="formData.execution_mode">
    <a-select-option value="llm">LLM 对话</a-select-option>
    <a-select-option value="workflow">工作流</a-select-option>
    <a-select-option value="skill">技能执行</a-select-option>
    <a-select-option value="plan">ReAct 计划执行</a-select-option>
    <a-select-option value="team">团队协作</a-select-option>
  </a-select>
</a-form-item>

<!-- ReAct 配置区域（execution_mode="plan" 时显示） -->
<template v-if="formData.execution_mode === 'plan'">
  <a-divider>ReAct 模式配置</a-divider>
  <a-row :gutter="16">
    <a-col :span="12">
      <a-form-item label="交互模式">
        <a-select v-model:value="reactConfig.interaction_mode">
          <a-select-option value="auto">全自动</a-select-option>
          <a-select-option value="approve">先审批</a-select-option>
          <a-select-option value="confirm_steps">关键步骤确认</a-select-option>
        </a-select>
      </a-form-item>
    </a-col>
    <a-col :span="12">
      <a-form-item label="反思模式">
        <a-select v-model:value="reactConfig.reflection_mode">
          <a-select-option value="lightweight">轻量（自评估）</a-select-option>
          <a-select-option value="deep">深度（独立调用）</a-select-option>
        </a-select>
      </a-form-item>
    </a-col>
  </a-row>
  <a-row :gutter="16">
    <a-col :span="12">
      <a-form-item label="最大步数">
        <a-input-number v-model:value="reactConfig.max_iters" :min="1" :max="50" />
      </a-form-item>
    </a-col>
    <a-col :span="12">
      <a-form-item label="超时时间（秒）">
        <a-input-number v-model:value="reactConfig.timeout_seconds" :min="30" :max="3600" />
      </a-form-item>
    </a-col>
  </a-row>
</template>
```

- [ ] **Step 2: 在表单数据中添加 reactConfig 响应式对象**

```typescript
const reactConfig = reactive({
  interaction_mode: 'auto',
  reflection_mode: 'lightweight',
  max_iters: 10,
  timeout_seconds: 300,
})
```

- [ ] **Step 3: 在提交时将 reactConfig 写入 react_config 字段**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/admin/agent/components/AgentFormModal.vue
git commit -m "feat(react): add ReAct config section to Agent form"
```

---

### Task 12: 前端 — AI 助手新建会话 + 会话类型选择

**Files:**
- Modify: `frontend/src/views/assistant/components/SessionSidebar.vue` 或新建会话对话框

- [ ] **Step 1: 在新建会话对话框中添加 ReAct 模式选项**

在会话类型选择中添加：
- 图标: `BranchesOutlined` 或 `NodeIndexOutlined`
- 标签: "ReAct 计划执行"
- 值: `session_type="react"`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/assistant/components/SessionSidebar.vue
git commit -m "feat(react): add react session type to new session dialog"
```

---

### Task 13: 国际化

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/i18n/locales/en-US.ts`
- Modify: `frontend/src/i18n/locales/zh-TW.ts`
- Modify: `frontend/src/i18n/locales/ja-JP.ts`

- [ ] **Step 1: 添加 react 命名空间翻译键**

```typescript
// zh-CN.ts
react: {
  title: 'ReAct 计划执行',
  status_planning: '规划中',
  status_executing: '执行中',
  status_done: '已完成',
  status_cancelled: '已取消',
  status_failed: '执行失败',
  step_pending: '待执行',
  step_running: '执行中',
  step_done: '已完成',
  step_failed: '失败',
  step_skipped: '已跳过',
  confirm_title: '确认操作',
  confirm_approve: '批准执行',
  confirm_continue: '继续执行',
  confirm_skip: '跳过',
  confirm_cancel: '取消',
  interaction_auto: '全自动',
  interaction_approve: '先审批',
  interaction_confirm_steps: '关键步骤确认',
  reflection_lightweight: '轻量自评估',
  reflection_deep: '深度反思',
  max_iters: '最大步数',
  timeout: '超时时间',
  pause: '暂停',
  resume: '继续',
  cancel: '取消',
},
```

- [ ] **Step 2: 为 en-US / zh-TW / ja-JP 添加对应翻译**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/i18n/locales/
git commit -m "feat(react): add i18n translations for react mode"
```

---

### Task 14: 集成测试 + 端到端验证

- [ ] **Step 1: 后端冒烟测试**

启动后端服务，使用 curl 或 httpie 测试：
1. 创建 react 会话: `POST /api/v1/ai-agent/session {"session_type": "react"}`
2. 发送消息: `POST /api/v1/ai-agent/chat/stream` 验证 SSE 事件流包含 `react_start` → `react_plan` → `react_step_*` → `react_done`
3. HITL API: `POST /api/v1/react/{run_id}/status` 验证状态返回

- [ ] **Step 2: 前端冒烟测试**

1. 新建 ReAct 会话，发送任务消息
2. 验证时间线组件正确渲染步骤
3. 验证 HITL 确认面板在 approve 模式下弹出
4. 验证 Agent 配置表单中 ReAct 区域正确展示

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat(react): ReAct mode implementation complete"
```
