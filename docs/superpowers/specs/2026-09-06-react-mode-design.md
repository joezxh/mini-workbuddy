# ReAct（Reasoning + Acting）模式设计规格

> 日期：2026-09-06
> 状态：设计中
> 范围：后端 AI 模块 + 前端配置/展示 UI + Skill 适配

---

## 1. 概述

在现有 AI 模块中新增 ReAct（Reasoning + Acting）配置模式，使 Agent 能够根据用户下达的任务与目标，自动制定持续性执行计划，按计划逐步分解、执行、反思、调整，最终完成用户指定的功能目标。

### 1.1 核心设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 架构方案 | ReActOrchestrator 独立编排器 | 与 ResearchOrchestrator 模式一致，完全控制循环和事件流 |
| 核心场景 | 混合通用 | 不限定领域，支持数据分析、工具调用、自动化流程等 |
| 交互模式 | 可配置（全自动/先审批/关键步骤确认） | 通过 react_config 配置 |
| 反思机制 | 可配置（轻量自评估/深度独立调用） | 通过 react_config 配置 |
| 会话集成 | AgentConfig execution_mode + session_type 双入口 | 灵活触发 |
| 前端展示 | 步骤时间线（CI/CD 流水线风格） | 直观展示执行进度 |
| HITL 确认 | 推荐选项 + 自定义输入 | 兼顾效率与灵活性 |
| Skill 适配 | Skill 内部也支持 ReAct 模式（嵌套） | Skill 可自主规划执行 |

### 1.2 现有架构概览

- **3 种 Agent 实现类型**：`CHAT`（通用对话）、`WORKFLOW`（深度研究）、`SKILL`（技能执行）
- **会话类型路由**：`AgentFactory.create_agent(session_type)` → general/thinking/deep_research/skill/agent/team
- **统一流式接口**：所有 Agent 通过 `reply_stream()` → `SSEBridge` → 前端 SSE
- **已有预留字段**：`AgentConfig.react_config`（JSONB）、`ExecutionMode.PLAN = "plan"` 已存在但未实现

---

## 2. 后端设计

### 2.1 新增文件结构

```
backend/app/ai/react/
├── __init__.py
├── orchestrator.py       # ReActOrchestrator 核心编排器
├── plan_generator.py     # 计划生成 + 反思 + 调整
└── skill_adapter.py      # Skill → FunctionTool 包装
```

### 2.2 数据模型

```python
@dataclass
class PlanStep:
    id: str               # "step_1", "step_2"...
    title: str            # 步骤标题
    description: str      # 详细描述
    status: str           # pending / running / done / failed / skipped
    result: str = ""      # 执行结果摘要
    tool_calls: list = [] # 工具调用记录 [{name, input, output}]
    depth: int = 0        # 嵌套深度（0=外层, 1=Skill 内部...）

@dataclass
class ExecutionPlan:
    goal: str             # 用户目标
    steps: List[PlanStep]
    current_step: int = 0
    status: str = "planning"  # planning / executing / reflecting / done / cancelled
    iteration: int = 0    # 当前迭代轮次
```

### 2.3 ReActOrchestrator 核心

**文件**：`backend/app/ai/react/orchestrator.py`

**构造参数**（从 `react_config` JSONB 读取）：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_iters` | int | 10 | 最大迭代步数 |
| `timeout_seconds` | int | 300 | 超时时间（秒） |
| `interaction_mode` | str | "auto" | auto / approve / confirm_steps |
| `reflection_mode` | str | "lightweight" | lightweight（自评估）/ deep（独立 LLM 调用） |
| `skills` | list[str] | [] | ReAct 模式下可用的 Skill 列表 |

**核心循环**：

```
async def run(user_text: str) -> AsyncGenerator[dict, None]:
    1. yield react_start {goal}
    2. plan = await PlanGenerator.generate(user_text, tools, skills)
    3. yield react_plan {steps}
    4. if interaction_mode == "approve":
         yield react_confirm {question, options}
         await self._gate.wait()  # 等待用户确认
    5. for step in plan.steps:
         yield react_step_start {step_id, title}
         result = await StepExecutor.execute(step, agent, toolkit)
         yield react_step_done {step_id, result, status}
         if reflection_mode == "deep":
             reflection = await Reflector.reflect(step, result)
         else:
             reflection = await agent 自评估（通过 system prompt 引导）
         yield react_reflect {step_id, assessment}
         if reflection.needs_adjust:
             plan = await PlanAdjuster.adjust(plan, reflection)
             yield react_plan_update {steps}
    6. summary = await summarize(plan)
    7. yield react_report {summary, steps_completed}
    8. yield react_done {final_result}
```

**暂停/恢复/取消机制**：

```python
self._gate = asyncio.Event()       # 暂停门控
self._cancelled = False            # 取消标记
self._run_id = str(uuid.uuid4())   # 运行 ID

# 注册到全局注册表
REACT_REGISTRY[self._run_id] = self

# 暂停：在关键节点 await self._gate.wait()
# 恢复：外部调用 self.resume() → self._gate.set()
# 取消：外部调用 self.cancel() → self._cancelled = True
```

### 2.4 PlanGenerator

**文件**：`backend/app/ai/react/plan_generator.py`

**职责**：
1. **计划生成**：接收用户目标 + 可用工具列表，调用 LLM 生成结构化执行计划
2. **反思评估**：评估步骤执行结果，判断是否需要调整
3. **计划调整**：基于反思结果，更新/新增/跳过后续步骤

**计划生成 Prompt 模板**：

```
你是一个任务规划专家。用户的目标如下：
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
{{"steps": [{{"title": "...", "description": "...", "tool": "tool_name or null", "skill": "skill_name or null"}}]}}
```

**反思 Prompt 模板（深度模式）**：

```
你是任务执行的质量评估官。

当前步骤：{step.title}
步骤描述：{step.description}
执行结果：{result}
用户原始目标：{goal}

请评估：
1. 该步骤是否达到预期？(satisfied: true/false)
2. 是否需要调整后续计划？(needs_adjust: true/false)
3. 如需调整，具体建议是什么？

输出 JSON：
{{"satisfied": true, "needs_adjust": false, "reason": "...", "suggestions": []}}
```

### 2.5 HITL 人机交互

**全局注册表**：

```python
REACT_REGISTRY: Dict[str, ReActOrchestrator] = {}
```

**REST API**（`backend/app/routers/ai/react.py`）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/react/{run_id}/status` | GET | 获取当前执行状态和计划 |
| `/api/v1/react/{run_id}/approve` | POST | 批准计划（approve 模式） |
| `/api/v1/react/{run_id}/respond` | POST | 响应确认请求（confirm_steps 模式） |
| `/api/v1/react/{run_id}/pause` | POST | 暂停执行 |
| `/api/v1/react/{run_id}/resume` | POST | 恢复执行 |
| `/api/v1/react/{run_id}/cancel` | POST | 取消执行 |

**响应格式**（`/respond`）：

```python
# 请求
{
    "step_id": "step_2",
    "answer": "func_price",       # 选中的 value 或自定义文本
    "action": "confirm"           # confirm / skip / cancel
}

# confirm 事件携带的选项格式
{
    "type": "react_confirm",
    "step_id": "step_2",
    "question": "分析范围应该包含哪些维度？",
    "options": [
        {"label": "功能对比 + 定价分析", "description": "推荐", "value": "func_price"},
        {"label": "技术架构 + 性能指标", "value": "tech_perf"},
        {"label": "全面分析", "value": "full"},
    ],
    "allow_custom": True
}
```

### 2.6 ReactAgent 封装 + AgentFactory 集成

**ReactAgent**（`backend/app/ai/agent_factory.py` 中新增）：

```python
class ReactAgent:
    """ReAct 计划执行 Agent 封装"""

    def __init__(self, db, model_id, tools, react_config, sys_prompt, name="ReAct 助手"):
        self._db = db
        self._model_id = model_id
        self._tools = tools
        self._react_config = react_config or {}
        self._sys_prompt = sys_prompt
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
        )
        async for event in orchestrator.run(topic):
            yield {"type": event.get("type", "message"), "data": event}
```

**AgentFactory 扩展**：

```python
# create_agent() 新增 case
case "react":
    return self._create_react_agent(config)

def _create_react_agent(self, config: dict):
    return ReactAgent(
        db=self._db,
        model_id=config.get("model_id_db"),
        tools=config.get("tools"),
        react_config=config.get("react_config", {}),
        sys_prompt=config.get("sys_prompt"),
        name=config.get("name", "ReAct 助手"),
    )
```

**双入口触发机制**：

**入口 1：session_type 直接路由**
- 前端新建会话时选择 `session_type="react"` → 存储到 `AiChatSession.session_type`
- 路由层读取 `session_type="react"` → `AgentFactory.create_agent("react", config)` → 创建 ReactAgent

**入口 2：execution_mode 自动映射**
- 前端新建会话时选择 `session_type="agent"` + `req.agent_id`（指向某个 AgentConfig）
- 路由层调用 `_build_agent_config()` 时，从 `AgentConfig` 读取 `execution_mode`
- 若 `execution_mode="plan"`，路由层自动将 `session_type` 覆盖为 `"react"`，并将 `react_config` 注入 config
- 最终调用 `AgentFactory.create_agent("react", config)` → 创建 ReactAgent

**路由层实现**（`backend/app/routers/ai/ai_agent.py`）：

```python
# 在 _build_agent_config() 之后、create_agent() 之前
agent_config = _build_agent_config(req, session_type, db)

# 双入口：execution_mode="plan" 自动映射为 react session_type
if req.agent_id and agent_config.get("execution_mode") == "plan":
    session_type = "react"
    agent_config["react_config"] = agent_config.get("react_config", {})

factory = AgentFactory(db)
agent = factory.create_agent(session_type, agent_config)
```

**_build_agent_config() 扩展**：

```python
# 读取 AgentConfig 时，同时提取 execution_mode 和 react_config
if req.agent_id:
    from app.models.agent.agent_config import AgentConfig
    agent_cfg = db.query(AgentConfig).filter(AgentConfig.id == req.agent_id).first()
    if agent_cfg:
        config["name"] = agent_cfg.name or "助手"
        config["sys_prompt"] = agent_cfg.system_prompt or ""
        config["tools"] = agent_cfg.tools or []
        config["execution_mode"] = agent_cfg.execution_mode or "llm"
        config["react_config"] = agent_cfg.react_config or {}
```

### 2.7 SSE 事件协议

| 事件类型 | 数据 | 说明 |
|---------|------|------|
| `react_start` | `{goal, plan_summary}` | 开始执行 |
| `react_plan` | `{steps: [{id, title, description, status}]}` | 生成计划 |
| `react_confirm` | `{step_id, question, options, allow_custom}` | HITL 确认请求 |
| `react_step_start` | `{step_id, title, depth}` | 步骤开始 |
| `react_thinking` | `{step_id, content}` | Agent 思考过程 |
| `react_tool_call` | `{step_id, tool_name, input}` | 工具调用 |
| `react_tool_result` | `{step_id, tool_name, result}` | 工具结果 |
| `react_step_done` | `{step_id, title, result, status}` | 步骤完成 |
| `react_reflect` | `{step_id, assessment, adjusted}` | 反思结果 |
| `react_plan_update` | `{steps: [...]}` | 计划调整 |
| `react_progress` | `{progress, message, current_step, total_steps}` | 进度更新 |
| `react_skill_start` | `{skill_name, depth}` | Skill 内部执行开始 |
| `react_skill_done` | `{skill_name, result, depth}` | Skill 内部执行完成 |
| `react_report` | `{summary, steps_completed, result}` | 执行报告 |
| `react_error` | `{message, step_id?}` | 错误 |
| `react_done` | `{final_result}` | 全部完成 |

---

## 3. 前端设计

### 3.1 步骤时间线组件

**文件**：`frontend/src/views/assistant/components/ReactTimeline.vue`

**展示风格**：CI/CD 流水线时间线，每个步骤为一个节点。

**状态图标映射**：
- `pending` → ⏳ 灰色
- `running` → 🔄 蓝色（旋转动画）
- `done` → ✅ 绿色
- `failed` → ❌ 红色
- `skipped` → ⏭ 灰色

**步骤展开详情**：
- 💭 思考内容（折叠显示）
- 🔧 工具调用列表（工具名 + 输入 + 输出）
- 📝 步骤结果摘要

**嵌套 Skill 面板**：
- 当 `depth > 0` 时，步骤内部嵌套显示 Skill 执行子面板
- 子面板样式与外层一致，但带缩进和「Skill: xxx」标题
- Skill 内部的 HITL 确认也在子面板中展示

**操作按钮**：
- `[⏸ 暂停]` `[✏ 修改计划]` `[✖ 取消]`（执行中显示）
- `[▶ 继续]` `[⏭ 跳过此步]`（暂停时显示）
- `[✅ 确认执行]` `[✏ 修改计划]`（approve 模式等待确认时显示）

**HITL 确认面板**：

当收到 `react_confirm` 事件时，在时间线下方展示确认面板：
- 显示 Agent 的问题
- 推荐选项列表（radio button）
- 自定义输入框（textarea）
- 确认 / 跳过按钮

### 3.2 SSE 事件消费

在 AI 助手聊天组件中扩展 SSE 事件处理：

```typescript
// 新增事件处理
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
  // 更新 ReactTimeline 组件的响应式数据
```

### 3.3 Agent 配置 UI

**文件**：在现有 Agent 管理表单中扩展

在 Agent 编辑表单中新增「ReAct 模式配置」区域：

- **执行模式**下拉：`llm` / `workflow` / `skill` / `plan`(ReAct)
- 选择 `plan` 时展开：
  - **交互模式**：全自动 / 先审批 / 关键步骤确认
  - **反思模式**：轻量（自评估）/ 深度（独立调用）
  - **最大步数**：数字输入（默认 10）
  - **超时时间**：数字输入（默认 300s）
  - **可用 Skill**：多选下拉（从已安装 Skill 中选择）

### 3.4 AI 助手新建会话

新建会话对话框中新增「ReAct 模式」选项：
- 与通用对话、深度研究、技能模式并列
- 图标：`NodeIndexOutlined` 或 `BranchesOutlined`
- 选择后 `session_type="react"`

### 3.5 API 文件

**文件**：`frontend/src/api/react.ts`

```typescript
export function getReactStatus(runId: string) { ... }
export function approveReact(runId: string, data: any) { ... }
export function respondReact(runId: string, data: any) { ... }
export function pauseReact(runId: string) { ... }
export function resumeReact(runId: string) { ... }
export function cancelReact(runId: string) { ... }
```

---

## 4. Skill 适配

### 4.1 Skill ReAct 执行模式

Skill 执行器（`SkillExecutionService`）新增 `execution_mode` 参数：
- `mode="direct"`（默认）：现有行为，直接执行
- `mode="react"`：Skill 内部启动 ReAct 循环

**SKILL.md frontmatter 新增字段**：

```yaml
---
execution-mode: react    # direct | react（默认 direct）
max-iters: 8             # ReAct 模式最大步数
reflection-mode: lightweight  # lightweight | deep
---
```

### 4.2 Skill → FunctionTool 包装

**文件**：`backend/app/ai/react/skill_adapter.py`

将可用 Skill 包装为 `FunctionTool`，注册到 ReAct 的 Toolkit 中：

```python
def create_skill_tool(skill_name: str, skill_config: dict, db) -> FunctionTool:
    """将 Skill 包装为 FunctionTool"""
    async def execute_skill(input: str) -> str:
        service = SkillExecutionService()
        result_parts = []
        async for event in service.execute(
            skill_name=skill_name,
            user_message=input,
            execution_mode=skill_config.get("execution_mode", "direct"),
        ):
            if event.type == "done":
                result_parts.append(event.data.get("result", ""))
        return "\n".join(result_parts)

    return FunctionTool(
        execute_skill,
        name=f"skill_{skill_name}",
        description=skill_config.get("description", f"执行技能 {skill_name}"),
    )
```

### 4.3 嵌套事件流

Skill 以 ReAct 模式执行时，事件通过 `depth` 字段区分层级：

```
react_step_start {depth: 0}     # 外层
  react_skill_start {depth: 1}  # Skill 内部
    react_plan {depth: 1}       # Skill 内部计划
    react_step_start {depth: 1} # Skill 内部步骤
    react_step_done {depth: 1}
  react_skill_done {depth: 1}
react_step_done {depth: 0}      # 外层完成
```

前端通过 `depth` 值缩进展示嵌套层级。

---

## 5. 文件变更清单

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/app/ai/react/__init__.py` | 新建 | 模块初始化 |
| `backend/app/ai/react/orchestrator.py` | 新建 | ReActOrchestrator 核心编排器 |
| `backend/app/ai/react/plan_generator.py` | 新建 | 计划生成 + 反思 + 调整 |
| `backend/app/ai/react/skill_adapter.py` | 新建 | Skill → FunctionTool 包装 |
| `backend/app/ai/agent_factory.py` | 修改 | 新增 ReactAgent + react session_type |
| `backend/app/routers/ai/react.py` | 新建 | HITL REST API 路由 |
| `backend/app/schemas/agent/react.py` | 新建 | Pydantic 请求/响应模型 |
| `frontend/src/views/assistant/components/ReactTimeline.vue` | 新建 | 步骤时间线组件 |
| `frontend/src/views/assistant/components/ReactSkillPanel.vue` | 新建 | 嵌套 Skill 执行面板 |
| `frontend/src/views/assistant/components/ReactConfirmPanel.vue` | 新建 | HITL 确认面板 |
| `frontend/src/views/admin/ai/agent/AgentForm.vue` | 修改 | 新增 ReAct 配置区域 |
| `frontend/src/api/react.ts` | 新建 | HITL API 调用 |
| `frontend/src/api/aiSession.ts` | 修改 | 新增 react 会话类型 |
| `frontend/src/i18n/locales/zh-CN.ts` | 修改 | 新增 react 命名空间翻译键 |
| `frontend/src/i18n/locales/en-US.ts` | 修改 | 同上 |
| `frontend/src/i18n/locales/zh-TW.ts` | 修改 | 同上 |
| `frontend/src/i18n/locales/ja-JP.ts` | 修改 | 同上 |

---

## 6. 兼容性保证

1. **现有 Agent 类型零侵入**：ReAct 作为独立的 session_type 和 execution_mode，不修改现有 CHAT/WORKFLOW/SKILL 的任何代码路径
2. **AgentFactory 扩展点**：仅在 `create_agent()` 的 match 分支中新增 `case "react"`
3. **SkillExecutionService 向后兼容**：`execution_mode` 参数默认 `"direct"`，现有调用方不受影响
4. **数据库无迁移**：`react_config` JSONB 字段已存在于 `agent_config` 表中，无需新增列
5. **SSE 事件命名空间**：所有新事件以 `react_` 前缀开头，不与现有事件冲突
