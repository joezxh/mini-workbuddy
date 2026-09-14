# 调解语音通信系统差距分析与集成策略

> 基于 qwen-audio-agent 参考架构与 risk_control 现有实现的深度对比分析

## 1. 执行摘要

本文档对 qwen-audio-agent 参考架构与 risk_control 调解语音通信系统进行全面差距分析，识别已有能力、缺失功能与优化机会，并制定具体的集成策略与分阶段迁移路线图。

**核心发现**：
- risk_control 已具备基础语音通信骨架（Provider 抽象 + WebSocket 网关 + DashScope 实现）
- 缺失关键能力：Turn 状态机、能力声明、协议适配、Agent 桥接、MCP Client 会话注入、工具策略
- MCP 服务管理已完整实现（API Key/Client/Square 三层模型 + 前端 CRUD + 广场安装/卸载/连接测试 + 已注册工具列表），仅需补全 Agent 会话级 MCP 注入
- 现有调解引擎（IntentClassifier + RouteDispatcher + MediationEngine）可直接复用，但需与语音层解耦

---

## 2. 对比差距分析

### 2.1 已实现能力（risk_control 对齐 qwen-audio-agent 模式）

| 能力域 | risk_control 实现 | qwen-audio-agent 对应 | 对齐度 |
|--------|------------------|----------------------|--------|
| **Provider 抽象** | `RealtimeProvider` ABC + `DashScopeProvider` | `RealtimeProvider` + `DashScope` + `S2S` | ✅ 基础对齐 |
| **Provider 注册表** | `ProviderRegistry`（类注册 + resolve） | `registry.mjs`（实例注册 + validate + list） | ⚠️ 部分对齐 |
| **WebSocket 网关** | `websocket_gateway.py`（双向音频转发） | `realtime-gateway.mjs`（完整事件路由） | ⚠️ 基础骨架 |
| **语音降级** | `VoiceFallback`（Provider 切换 + 文字降级） | `reconnect-backoff.mjs` + `classifyError` | ⚠️ 策略简单 |
| **调解引擎** | `MediationEngine`（Text/Voice/Auto 三 Pipeline） | 无对应（qwen 无业务调解引擎） | ✅ 独有优势 |
| **意图分类** | `IntentClassifier`（8 种意图 + LLM） | 无对应 | ✅ 独有优势 |
| **路由分发** | `RouteDispatcher`（自适应路由 + Redis 跟踪） | 无对应 | ✅ 独有优势 |
| **Agent 注册表** | `AgentRegistry`（5 个默认 Agent） | `BackendRegistry`（多后端驱动 + 能力声明） | ⚠️ 结构相似，能力声明缺失 |
| **引擎注册表** | `EngineRegistry`（6 种引擎类型） | 无对应（qwen 仅 ACP 协议） | ✅ 独有优势 |
| **MCP 服务管理** | 完整三层管理：`McpApiKey`/`MCPClient`/`McpSquareTemplate` DB 模型 + 670 行路由（CRUD/安装/卸载/连接测试）+ `McpServiceManagement.vue`（656 行，3 Tab）+ `MCPAdapter` 工具适配器 + `FastMCP` Server（risk-control-knowledge） | `AcpSessionToolServer`（会话工具 MCP） | ✅ 管理能力完整对齐 |
| **知识库工具** | 15 个知识工具 + 6 个推理工具 + 3 个写回工具（已通过 MCP Server 发布 + MCPAdapter 注册） | 前端工具（spawn_thinking/memory/notes） | ⚠️ 工具类型不同 |
| **数据模型** | AiChatMessage（extra_data 灵活扩展） | 无持久化（内存会话） | ✅ 独有优势 |

**关键对齐点**：
1. ✅ Provider 抽象接口设计一致（connect/send_audio/events/close）
2. ✅ 注册表模式相似（key → 实例映射）
3. ✅ 调解领域能力完整（意图分类 + 路由 + 阶段机 + 情绪追踪）
4. ✅ MCP 服务管理完整实现（API Key/Client/Square 三层 + 前端 CRUD + 广场安装/卸载/连接测试 + 已注册工具列表）

### 2.2 缺失能力（risk_control 需要补全）

#### 2.2.1 语音层缺失能力

| 缺失能力 | qwen-audio-agent 实现 | risk_control 现状 | 优先级 | 影响 |
|---------|----------------------|------------------|--------|------|
| **能力声明模型** | `capabilities`（acknowledgesSessionUpdate/singleResponseSlot/responseMetadataCorrelation 等） | 无 | 🔴 P0 | 无法差异化处理 Provider 行为 |
| **协议适配器** | `openai-compatible-protocol.mjs` / `ga-protocol.mjs`（消息格式归一化） | 无（DashScope 硬编码事件解析） | 🔴 P0 | 无法支持多 Provider |
| **Turn 状态机** | `TurnState`（turnGeneration 代际仲裁） | 无 | 🔴 P0 | 无法处理打断/并发 |
| **发言权仲裁** | `voice.ownership`（多方模式 holder/state） | 无 | 🟡 P1 | 无法支持多方语音 |
| **Connect 帧处理** | 解析 systemPrompt/greeting/voiceIdentity/language | 仅 case_number/party_id | 🔴 P0 | 无法初始化角色配置 |
| **开场白播报** | `speak(greeting)` after `voice.ready` | 无 | 🟡 P1 | 用户体验缺失 |
| **响应超时保护** | `responseStartTimeoutMs` / `responseInactivityTimeoutMs` | 无 | 🟡 P1 | 长响应可能挂起 |
| **错误分类** | `classifyError`（inactivity/input_busy/fatal/other） | 无 | 🟡 P1 | 无法智能重试 |
| **重连退避** | `ReconnectBackoff`（指数退避 + 超时） | 无 | 🟡 P1 | 弱网易断 |
| **事件协议丰富化** | 13+ 事件类型（voice.ready/state/ownership/turn.* 等） | 仅 3 种（audio_delta/asr_completed/tool_call） | 🔴 P0 | 前端无法感知状态 |

#### 2.2.2 Agent 层缺失能力

| 缺失能力 | qwen-audio-agent 实现 | risk_control 现状 | 优先级 | 影响 |
|---------|----------------------|------------------|--------|------|
| **AgentAdapter 抽象** | `BackendDriver`（createProfile + capabilities） | `AgentConfig`（system_prompt + tools） | 🔴 P0 | 无法接入 AgentScope/Dify |
| **能力声明** | `delegation/permissions/externalMcp/sessionMcp` | 无 | 🟡 P1 | 无法判断 Agent 能力 |
| **协调器** | `coordinator.mjs`（构建提示 + 解析决策 + 委派查询） | 无（MediationEngine 直接调用 LLM） | 🔴 P0 | 无法委派复杂任务 |
| **工具调用处理器** | `tool-call-handler.mjs`（参数校验/去重/权限/委派） | 无（DashScope 直接透传 tool_call） | 🔴 P0 | 无法管理工具生命周期 |
| **任务管理器** | `task-manager.mjs`（创建/调度/取消/进度/恢复） | `MediationWorkQueue`（仅队列） | 🟡 P1 | 缺乏进度跟踪 |
| **转写缓冲** | `turn-transcripts.mjs`（每轮最终转写） | 无 | 🟡 P1 | 委派时丢失原始意图 |

#### 2.2.3 MCP 层缺失能力

> **重要说明**：risk_control 已实现完整的 MCP 服务管理体系（见 §2.1），包括：
> - 3 个 DB 模型（`McpApiKey`/`MCPClient`/`McpSquareTemplate`）+ 完整 Pydantic Schema
> - 670 行后端路由（API Key/Client/Square 三组 CRUD + 安装/卸载/连接测试 + 已注册工具列表）
> - 656 行前端界面（`McpServiceManagement.vue`，3 个 Tab：我的 MCP / MCP 广场 / 已注册工具）
> - `MCPAdapter` 工具适配器（注册/调用/Schema 导出）+ `FastMCP` Server（risk-control-knowledge）
> - Agent 配置中已支持 MCP 服务绑定（`AgentFormModal.vue` 多选 MCP 服务）
>
> 以下为仍需补全的差距：

| 缺失能力 | qwen-audio-agent 实现 | risk_control 现状 | 优先级 | 影响 |
|---------|----------------------|------------------|--------|------|
| **多传输支持** | stdio / streamable-http / SSE | 已支持 HTTP/SSE/Nacos2/Nacos3（通过 service_type 配置） | 🟡 P1 | 不可接入 stdio 本地工具（如本地文件系统 MCP） |
| **工具策略** | `enabled/timeoutMs/maxCallsPerTurn/maxResultBytes` | 无（工具调用无超时/频次限制） | 🔴 P0 | 无法限制工具调用行为 |
| **Agent 会话级 MCP 注入** | `builtin-mcp.mjs`（为每个 Session 动态注入 MCP 工具） | MCP Server 独立运行 + Agent 可绑定 MCP 服务 ID，但会话时未动态解析绑定 | 🔴 P0 | Agent 推理时无法自动使用已绑定的 MCP 工具 |

> **注**：原列出的「前端 MCP 配置」「配置存储」已完整实现，不再列为缺失项。

#### 2.2.4 会话层缺失能力

| 缺失能力 | qwen-audio-agent 实现 | risk_control 现状 | 优先级 | 影响 |
|---------|----------------------|------------------|--------|------|
| **会话初始化配置** | greeting/systemPrompt/voiceIdentity/language | 无 | 🔴 P0 | 无法自定义角色 |
| **提示词优先级链** | connect 帧 > roleId > 服务端默认 | 无 | 🟡 P1 | 配置冲突无法解决 |
| **双模独立切换** | inputMode + outputMode 独立控制 | 仅 input_mode（text/voice） | 🟡 P1 | AI 回复模式无法独立 |
| **语音会话持久化** | 无（内存） | 无 | 🟡 P1 | 断线后无法恢复 |
| **轮次明细记录** | 无 | 无 | 🟡 P1 | 无法审计语音历史 |

### 2.3 优化机会（risk_control 现有组件可改进）

| 优化项 | 当前实现 | 优化方向 | 收益 |
|--------|---------|---------|------|
| **Provider 注册表** | 类注册（`ProviderRegistry.register(DashScopeProvider)`） | 改为实例注册 + 能力校验（参考 qwen `validateRealtimeProvider`） | 提升可扩展性 |
| **WebSocket 网关** | 简单双向转发（`_forward_client_to_provider`） | 改为事件路由 + Turn 状态机 + 发言权仲裁 | 支持复杂场景 |
| **DashScope Provider** | 硬编码事件解析（`_parse_event`） | 引入协议适配器（`openai-compatible-protocol`） | 支持多 Provider |
| **AgentRegistry** | 内存硬编码 5 个 Agent | 改为数据库驱动 + 能力声明 | 动态管理 Agent |
| **MediationEngine** | 直接调用 LLM（`_stream_llm_with_tools`） | 改为通过 AgentAdapter 调用 | 解耦语音层与推理层 |
| **MCP 服务管理** | 已完整实现（三层 DB 模型 + 前端 CRUD + 广场安装/卸载 + 连接测试 + 工具列表） | 补全 Agent 会话级 MCP 动态注入（解析已绑定 MCP 服务 ID → 拉取工具 → 注册到 Toolkit） | Agent 推理时可自动使用已绑定的 MCP 工具 |
| **VoiceFallback** | 简单降级（Provider 切换 + 文字） | 改为错误分类 + 指数退避重连 | 提升稳定性 |
| **AiChatMessage** | extra_data 存储调解字段 | 保持现状（已足够灵活） | 无需改动 |

---

## 3. 集成策略

### 3.1 AgentScope 专家团 → Provider Registry 映射

**现状**：
- risk_control 已有 `AgentRegistry`（5 个默认 Agent：risk_analyst/dispute_mediator/simulation_engineer/case_retriever/report_writer）
- 已有 `EngineRegistry`（6 种引擎：agent_loop/dify_chatflow/dify_workflow/direct_llm/skill_direct/pipeline）
- 已有 `MediationEngine`（直接调用 LLM，未通过 AgentRegistry）

**集成策略**：

```
┌─────────────────────────────────────────────────────────────┐
│                    Voice WebSocket 网关                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Provider     │  │ AgentAdapter │  │ TurnState    │      │
│  │ (语音层)     │  │ (推理层)     │  │ (状态机)     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │
│         │                 │                                  │
│         └────────┬────────┘                                  │
│                  ↓                                           │
│         ┌────────────────┐                                   │
│         │ AgentRegistry  │                                   │
│         │ (业务角色)     │                                   │
│         └────────┬───────┘                                   │
│                  ↓                                           │
│         ┌────────────────┐                                   │
│         │ EngineRegistry │                                   │
│         │ (后端实现)     │                                   │
│         └────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

**映射规则**：
1. **Provider 层**（语音层）：保持现有 `RealtimeProvider` 抽象，增加能力声明
2. **AgentAdapter 层**（推理层）：新增抽象接口，桥接到现有 `EngineRegistry`
3. **AgentRegistry**（业务角色）：保持不变，作为 Agent 配置来源
4. **EngineRegistry**（后端实现）：作为 AgentAdapter 的具体实现

**具体实现**：

> **设计原则**：充分利用 AgentScope 2.0 原生能力（Agent / Toolkit / Msg / AgentState / Plan 工具），
> 在此基础上做最小抽象，而非另起炉灶。

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AgentAdapter 抽象 — 基于 AgentScope 原生能力的最小封装
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from __future__ import annotations
from typing import Any, AsyncGenerator, Protocol
from dataclasses import dataclass


@dataclass
class AgentResponse:
    """Agent 统一响应"""
    text: str
    metadata: dict[str, Any] = {}
    tools_used: list[str] = []
    tasks_created: list[str] = []  # AgentScope Plan 创建的任务


class AgentAdapter(Protocol):
    """Agent 适配器协议 — 桥接语音层与推理层

    核心设计：
    - 基于 AgentScope Agent.reply() / reply_stream() 原生接口
    - 通过 Toolkit 注册工具（知识工具 + Plan 工具 + MCP 工具）
    - 利用 AgentState 实现跨轮次上下文持久化
    """
    key: str
    label: str

    async def initialize(self, session_config: dict) -> None: ...
    async def process(self, user_text: str, context: dict) -> AgentResponse: ...
    async def process_stream(self, user_text: str, context: dict) -> AsyncGenerator[str, None]: ...
    async def interrupt(self) -> None: ...
    async def get_plan_status(self) -> list[dict]: ...
    async def close(self) -> None: ...
```

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AgentScopeAdapter — 充分利用 AgentScope 原生能力
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from agentscope.agent import Agent, ReActConfig
from agentscope.tool import Toolkit, TaskCreate, TaskGet, TaskList, TaskUpdate
from agentscope.message import UserMsg


class AgentScopeAdapter:
    """AgentScope 适配器

    复用 AgentScope 原生能力：
    1. Agent.reply() / reply_stream() — 核心推理循环
    2. Toolkit — 工具注册与管理（知识工具 + Plan 工具 + MCP 工具）
    3. TaskCreate/Get/List/Update — Agent 自主计划与任务拆解
    4. AgentState.tasks_context — 跨轮次任务状态持久化
    5. ReActConfig — 推理-行动链配置
    6. Msg 协议 — 统一消息传递
    """
    key = "agentscope"
    label = "AgentScope 专家团"

    async def initialize(self, session_config: dict) -> None:
        """初始化 AgentScope Agent

        利用 AgentScope 原生能力构建 Agent：
        - 从 AgentRegistry 获取角色配置（system_prompt / tools / skills）
        - 构建 Toolkit 并注册：知识工具 + Plan 工具 + MCP 工具
        - 创建 Agent 实例（复用 PipelineEngine 已验证的模式）
        """
        from app.ai.agent_core.registry import get_agent_registry

        # 1. 获取 Agent 配置
        agent_id = session_config.get("agentId", "dispute_mediator")
        agent_config = get_agent_registry().get(agent_id)

        # 2. 构建 Toolkit（注册所有工具）
        self._toolkit = self._build_toolkit(session_config)

        # 3. 获取 Model（复用现有 DifyModelWrapper 或直连 LLM）
        model = self._resolve_model(session_config, agent_config)

        # 4. 创建 AgentScope Agent（原生能力）
        self._agent = Agent(
            name=agent_id,
            system_prompt=self._build_system_prompt(agent_config, session_config),
            model=model,
            toolkit=self._toolkit,
            react_config=ReActConfig(max_iters=5),  # 调解场景需要更多迭代
        )

        # 5. 恢复 AgentState（如果有历史会话）
        if session_config.get("resume_session_id"):
            self._restore_agent_state(session_config["resume_session_id"])

        # 6. 初始化 MediationEngine（复用调解领域独有能力）
        self._mediation_engine = self._create_mediation_engine(session_config)

    def _build_toolkit(self, session_config: dict) -> Toolkit:
        """构建 Toolkit — 复用现有 ToolManager + 追加 Plan 工具 + MCP 工具

        设计原则：
        - 复用 ToolManager 单例（已包含所有已注册的业务工具 + DB 元数据）
        - 保持原有工具管理功能（前端 CRUD / 分组 / 测试 / SQLBot 配置化）
        - 仅追加 Plan 工具和 MCP 工具到 ToolManager 的 Toolkit

        现有 ToolManager 已具备：
        - AgentScope 原生 Toolkit / ToolBase / ToolGroup 管理
        - DB 持久化（ToolDefinitionModel）+ 前端管理界面（ToolManagement.vue）
        - 工具分组（ToolGroup）+ 工具测试（ToolExecutor）
        - SQLBot 配置化工具 + 联网搜索工具
        - call_tool() 统一调用接口
        """
        from app.ai.tool_manager import get_tool_manager

        # 1. 复用现有 ToolManager 单例（已包含所有业务工具）
        tool_manager = get_tool_manager()

        # 2. 追加 Plan 工具（AgentScope 内置，Agent 可自主拆解复杂任务）
        plan_tools = [TaskCreate(), TaskGet(), TaskList(), TaskUpdate()]
        for pt in plan_tools:
            tool_manager.register(pt, type_hint="agentscope_plan")

        # 3. 追加 MCP 工具（通过 McpBridge 转换后注册）
        mcp_servers = session_config.get("mcpServers", [])
        if mcp_servers:
            from app.mediation.voice.mcp_bridge import McpBridge
            bridge = McpBridge(mcp_servers)
            await bridge.initialize()
            for mcp_tool in bridge.to_agentscope_tools():
                tool_manager.register(mcp_tool, type_hint="mcp")

        # 4. 返回 ToolManager 的 Toolkit（已包含所有工具）
        #    注意：不创建新 Toolkit，而是复用 ToolManager 维护的实例
        return tool_manager.toolkit

    async def process(self, user_text: str, context: dict) -> AgentResponse:
        """处理用户输入 — 利用 AgentScope Agent.reply() 原生推理循环

        流程：
        1. 先通过 MediationEngine 做意图分类 + 路由（调解独有能力）
        2. 如果是简单意图 → 直接返回（不走 Agent 推理）
        3. 如果是复杂意图 → 构造 UserMsg → Agent.reply() → 返回结果
           Agent 在推理过程中可自主调用 Toolkit 中的工具（包括 Plan 工具）
        """
        # 1. 意图分类（复用 MediationEngine 独有能力）
        classification = await self._mediation_engine.classify_intent(user_text)

        # 2. 简单意图直接处理（不走 Agent 推理，降低延迟）
        if classification.is_simple:
            result = await self._mediation_engine.handle_simple_intent(user_text, classification)
            return AgentResponse(text=result, metadata={"classification": classification})

        # 3. 复杂意图 → AgentScope Agent 推理
        #    构造 AgentScope 原生 UserMsg
        input_msg = UserMsg(name=context.get("party_id", "user"), content=user_text)

        #    Agent.reply() 内部会自动：
        #    - 思考（Reasoning）
        #    - 决定调用哪些工具（Acting）
        #    - 观察工具结果（Observation）
        #    - 循环直到得出结论（ReAct 循环）
        reply_msg = await self._agent.reply(input_msg)

        # 4. 提取结果
        text = self._extract_text(reply_msg)
        tools_used = self._extract_tools_used(reply_msg)
        tasks_created = self._get_plan_task_ids()

        return AgentResponse(
            text=text,
            metadata={"classification": classification},
            tools_used=tools_used,
            tasks_created=tasks_created,
        )

    async def process_stream(self, user_text: str, context: dict) -> AsyncGenerator[str, None]:
        """流式处理 — 利用 AgentScope Agent.reply_stream() 原生流式输出"""
        input_msg = UserMsg(name=context.get("party_id", "user"), content=user_text)

        async for chunk in self._agent.reply_stream(input_msg):
            token = getattr(chunk, "delta", None) or getattr(chunk, "text", None)
            if token:
                yield token

    async def get_plan_status(self) -> list[dict]:
        """获取 Agent 当前的任务计划状态

        通过 AgentScope 原生 AgentState.tasks_context 读取。
        前端可轮询此接口展示任务进度。
        """
        tasks = self._agent.state.tasks_context.tasks
        return [
            {
                "id": t.id,
                "subject": t.subject,
                "description": t.description,
                "state": t.state,
                "owner": t.owner,
                "blocks": t.blocks,
                "blocked_by": t.blocked_by,
                "metadata": t.metadata,
            }
            for t in tasks
        ]

    async def interrupt(self) -> None:
        """中断当前推理（用户打断时调用）"""
        # AgentScope Agent 的中断通过取消 asyncio.Task 实现
        if self._current_task:
            self._current_task.cancel()

    async def close(self) -> None:
        """关闭 Agent，持久化 AgentState"""
        # AgentState 可通过 agent.state 序列化保存
        # 下次恢复时通过 _restore_agent_state() 重建
        pass
```

**AgentScope 原生能力利用清单**：

| AgentScope 能力 | 用途 | risk_control 已有使用 |
|----------------|------|--------------------|
| `Agent.reply()` | 核心推理循环（ReAct） | ✅ PipelineEngine 已使用 |
| `Agent.reply_stream()` | 流式推理输出 | ✅ PipelineEngine 已使用 |
| `Toolkit` / `ToolBase` / `ToolGroup` | 工具注册与管理 | ✅ **ToolManager 已使用**（`app/ai/tool_manager/manager.py`） |
| `TaskCreate/Get/List/Update` | Agent 自主计划与任务拆解 | ❌ 未使用（新增） |
| `AgentState.tasks_context` | 跨轮次任务状态持久化 | ❌ 未使用（新增） |
| `UserMsg` / `Msg` | 统一消息协议 | ✅ PipelineEngine 已使用 |
| `ReActConfig` | 推理-行动链配置 | ✅ PipelineEngine 已使用 |

> **重要**：risk_control 的 `ToolManager` 已完整使用 AgentScope 原生 `Toolkit`/`ToolBase`/`ToolGroup`，
> 并具备 DB 持久化（`ToolDefinitionModel`）、前端管理界面（`ToolManagement.vue`）、
> 工具分组、工具测试、SQLBot 配置化工具等完整管理能力。
> AgentScopeAdapter 应**复用 ToolManager 单例**，而非从零构建 Toolkit。

**Connect 事件扩展**：

```json
{
  "type": "connect",
  "sessionId": "mediation-case-001",
  "participantId": "party_a",
  "mode": "single",
  "agentId": "dispute_mediator",
  "engineCode": "agentscope",
  "systemPrompt": "你是一名专业的纠纷调解员...",
  "greeting": "您好，我是 AI 调解助手...",
  "voiceIdentity": "longanqian",
  "language": "用普通话回答",
  "mcpServers": ["risk-control-knowledge"],
  "tools": ["dispute_strategy_search", "knowledge_base_search"],
  "enablePlan": true,
  "maxReActIters": 5
}
```

### 3.2 Skill 定义 → Tool Calling 框架集成

**现状**：
- risk_control 已有 `SkillCategory`（7 类技能）+ `SkillExecution`（技能执行引擎）
- 已有 15 个知识工具 + 6 个推理工具（遵循 AgentScope ToolBase 协议）
- 已有 `ToolDefinition` 模型 + `ToolGroup` 工具分组管理（数据库驱动）
- 已有 `ToolExecutor` 工具执行器（支持 custom/skill/mcp/agentscope_builtin 多种类型）
- **已有 `ToolManager`（`app/ai/tool_manager/manager.py`）已使用 AgentScope 原生 `Toolkit`/`ToolBase`/`ToolGroup`**
- **已有前端管理界面 `ToolManagement.vue`（工具 CRUD + 分组 + 测试 + SQLBot 配置化）**

**集成策略**：

工具集成统一通过现有 `ToolManager` 管理，所有工具类型（知识工具/技能/MCP/自定义）归一化为 AgentScope ToolBase 接口。
AgentScopeAdapter 复用 ToolManager 单例，仅追加 Plan 工具和 MCP 工具，**保持原有管理功能不变**。

```
┌─────────────────────────────────────────────────────────────┐
│        AgentScopeAdapter._build_toolkit()                  │
│                                                              │
│  ┌─ 复用现有 ToolManager 单例 ────────────────────────┐  │
│  │  （已包含所有业务工具，保持原有管理功能）         │  │
│  │                                                      │  │
│  │  • DB 持久化（ToolDefinitionModel）              │  │
│  │  • 前端管理界面（ToolManagement.vue）           │  │
│  │  • 工具分组（ToolGroup）                           │  │
│  │  • 工具测试（ToolExecutor）                       │  │
│  │  • SQLBot 配置化工具                              │  │
│  │  • 调解知识工具（15 个 ToolBase 实例）          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ 追加 Plan 工具（AgentScope 内置）─────────────┐  │
│  │  TaskCreate / TaskGet / TaskList / TaskUpdate   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ 追加 MCP 工具（通过 McpBridge 转换）─────────┐  │
│  │  risk-control-knowledge (streamable-http)        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                              │
│  全部注册到 → ToolManager.toolkit（复用，非新建）   │
│  Agent 自主决定调用哪些工具（ReAct 循环）               │
└─────────────────────────────────────────────────────────────┘
```

**工具策略配置**（可通过前端配置界面管理）：

```json
{
  "mcpServers": [
    {
      "key": "risk-control-knowledge",
      "enabled": true,
      "transport": {
        "type": "streamable-http",
        "url": "http://localhost:8000/mcp/risk-control-knowledge"
      },
      "tools": {
        "dispute_strategy_search": {
          "enabled": true,
          "timeoutMs": 8000,
          "maxCallsPerTurn": 2,
          "maxResultBytes": 32768
        },
        "dispute_case_search": {
          "enabled": true,
          "timeoutMs": 8000
        }
      }
    }
  ]
}
```

### 3.3 调解知识库 → 语义查询系统连接

**现状**：
- risk_control 已有 `risk-control-knowledge` MCP Server（15 个知识工具 + 6 个推理工具）
- 已有 `DisputeStrategySearch`、`DisputeCaseSearch`、`KnowledgeBaseSearch` 等调解相关工具
- 已有向量存储（`pg_vector_store.py`）支持语义检索

**集成策略**：

**无需改动** — 现有 MCP Server 可直接被 AgentAdapter 调用。

**工具清单**（已实现，可直接使用）：

| 工具名 | 功能 | 调解场景 |
|--------|------|---------|
| `dispute_strategy_search` | 搜索调解策略 | Leader Agent 选择策略 |
| `dispute_case_search` | 搜索相似案例 | 提供参考案例 |
| `dispute_gold_saying_search` | 搜索金句 | 生成安抚话术 |
| `knowledge_base_search` | 语义检索知识库 | 回答法律/政策问题 |
| `semantic_query` | 通用语义查询 | 模糊匹配 |
| `reasoning_rule_lookup` | 查找推理规则 | 逻辑推理支持 |

**连接方式**：

```python
# AgentAdapter 初始化时注入 MCP 工具
class AgentScopeAdapter:
    async def initialize(self, session_config: dict) -> None:
        # ... 现有初始化逻辑 ...
        
        # 注入调解知识库工具
        from app.ai.mcp.knowledge_tools import (
            DisputeStrategySearch,
            DisputeCaseSearch,
            DisputeGoldSayingSearch,
            KnowledgeBaseSearch,
        )
        
        db_session_factory = session_config["db_session_factory"]
        self._knowledge_tools = [
            DisputeStrategySearch(db_session_factory),
            DisputeCaseSearch(db_session_factory),
            DisputeGoldSayingSearch(db_session_factory),
            KnowledgeBaseSearch(db_session_factory),
        ]
    
    async def process(self, user_text: str, context: dict) -> AgentResponse:
        # 将知识工具传递给 MediatorLeader
        leader = MediatorLeader(tools=self._knowledge_tools)
        result = await leader.run(user_text, context)
        return AgentResponse(text=result)
```

### 3.4 MediationSession/MediationWorkRecord → 语音会话状态管理对齐

**现状**：
- `MediationSession`：调解会话（一轮对话），包含 `total_turns`、`phase`、`mode`
- `AiChatMessage`：统一消息表，`extra_data` 存储 `input_mode`、`emotion_score` 等
- 设计文档已规划新增 `MediationVoiceSession` + `MediationVoiceTurn`

**对齐策略**：

```
MediationCase (案件)
  ├── MediationSession (调解会话 — 一轮对话)
  │     ├── total_turns ← 语音轮次结束时 +1
  │     ├── AiChatMessage (统一消息表)
  │     │     ├── input_mode="voice"  ← 语音转写
  │     │     └── input_mode="manual" ← 文字输入
  │     ├── MediationVoiceSession (新增 — 语音连接会话)
  │     │     └── MediationVoiceTurn (新增 — 语音轮次明细)
  │     ├── MediationEmotionLog ← 语音情绪分析
  │     └── MediationWorkRecord ← 语音触发复杂意图
  └── MediationParticipant ← 语音会话参与者关联
```

**数据写入映射**：

| 语音事件 | 写入目标表 | 写入内容 |
|---------|-----------|---------|
| 用户语音 → STT 最终转写 | `ai_chat_message` | `role="user"`, `content=转写文本`, `extra_data.input_mode="voice"` |
| AI 回复文本 | `ai_chat_message` | `role="assistant"`, `content=回复文本` |
| 语音情绪分析 | `mediation_emotion_log` | `party_id`, `turn`, `emotion_score`, `emotion_type`, `source_text` |
| 语音触发复杂意图 | `mediation_work_records` | `user_request=转写文本`, `result_speech=AI 回复`, `owner=party_id` |
| 每轮对话结束 | `mediation_session.total_turns` | +1 递增 |
| 语音会话开始 | `mediation_voice_session` | 新建记录 |
| 语音轮次完成 | `mediation_voice_turn` | 新建记录 |

**ORM 模型扩展现有字段**：

```python
# AiChatMessage 已支持调解字段（通过 extra_data 属性）
# 无需改动表结构，仅需在语音层写入时使用正确字段

# 语音层写入示例
async def _save_voice_transcript(self, turn_id: str, role: str, text: str, party_id: str):
    """保存语音转写到 AiChatMessage。"""
    message = AiChatMessage(
        session_id=self.chat_session_id,
        role=role,
        content=text,
        message_type="text",
    )
    # 使用 AiChatMessage 的属性设置器
    message.party_id = party_id
    message.input_mode = "voice"
    message.turn = self.turn_state.turn_generation
    
    self.db.add(message)
    await self.db.commit()
```

#### 3.4.1 新增表结构（来自设计方案）

**`mediation_voice_session`** — 语音连接会话：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `mediation_session_id` | FK → mediation_session | 关联调解会话 |
| `participant_id` | VARCHAR(64) | 参与者标识 |
| `provider` | VARCHAR(32) | `dashscope` / `local` |
| `mode` | VARCHAR(16) | `single` / `multi` |
| `status` | VARCHAR(16) | `connecting` / `active` / `reconnecting` / `closed` |
| `input_sample_rate` | INT | 上行采样率（默认 16000） |
| `output_sample_rate` | INT | 下行采样率（默认 24000） |
| `connected_at` | TIMESTAMP | 连接建立时间 |
| `disconnected_at` | TIMESTAMP | 断开时间 |
| `disconnect_reason` | VARCHAR(64) | 断开原因 |
| `reconnect_count` | INT | 重连次数 |
| `metadata` | JSONB | 扩展信息 |

**`mediation_voice_turn`** — 语音轮次明细：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `voice_session_id` | FK → mediation_voice_session | 关联语音会话 |
| `turn_id` | VARCHAR(64) | 轮次 ID |
| `turn_generation` | INT | 代际序号 |
| `role` | VARCHAR(16) | `user` / `assistant` / `system` |
| `input_type` | VARCHAR(16) | `voice` / `text` |
| `transcript` | TEXT | 最终转写文本 |
| `response_text` | TEXT | AI 回复文本 |
| `audio_duration_ms` | INT | 用户语音时长 |
| `response_duration_ms` | INT | AI 回复时长 |
| `started_at` | TIMESTAMP | 轮次开始时间 |
| `completed_at` | TIMESTAMP | 轮次完成时间 |
| `cancelled` | BOOLEAN | 是否被取消 |

#### 3.4.2 WebSocket 事件协议（来自设计方案）

**客户端 → 服务端**：

| 事件 | 说明 | 载荷 |
|------|------|------|
| `connect` | 建立连接（含角色配置） | `{ sessionId, participantId, mode, systemPrompt, greeting, voiceIdentity, language, agentId, mcpServers, textOnly, voiceEnabled, outputEnabled }` |
| `audio.append` | 上行音频帧 | `{ audio: "base64_pcm16", sampleRate: 16000 }` |
| `input.message` | 文字消息 | `{ parts: [{type:"text", text:"..."}] }` |
| `mute` / `unmute` | 麦克风开关 | — |
| `output.mode` | 切换 AI 回复模式 | `{ mode: "voice"\|"text" }` |
| `interrupt` | 打断 AI 播放 | — |
| `playback.started` / `playback.ended` | 播放状态确认 | `{ responseId }` |

**服务端 → 客户端**：

| 事件 | 说明 | 载荷 |
|------|------|------|
| `voice.ready` | 连接就绪 | `{ inputSampleRate, outputSampleRate, provider, providerLabel }` |
| `voice.state` | 状态变更 | `{ state: "idle"\|"listening"\|"processing"\|"speaking" }` |
| `voice.ownership` | 发言权变更（多方） | `{ state: "active"\|"available", holder }` |
| `turn.started` | 新轮次开始 | `{ turnId, role }` |
| `audio.delta` | TTS 音频帧 | `{ audio, sampleRate: 24000, responseId }` |
| `audio.done` | 音频结束 | `{ responseId }` |
| `transcript.delta` / `transcript.final` | STT 转写 | `{ content, turnId, role }` |
| `playback.clear` | 清除播放 | — |
| `error` | 错误 | `{ message, code }` |

#### 3.4.3 音频格式约定

| 方向 | 采样率 | 格式 | 编码 |
|------|--------|------|------|
| 上行（麦克风→服务端） | 16kHz | PCM16 | Base64 |
| 下行（服务端→播放器） | 24kHz | PCM16 | Base64 |
| 前端重采样 | 浏览器原生(48kHz) → 16kHz | 线性插值 | — |

#### 3.4.4 语音/文字双模矩阵

| 用户输入 | AI 回复 | 场景示例 |
|---------|---------|----------|
| 语音 | 语音 | 默认全语音模式 |
| 语音 | 文字 | 用户说话，AI 文字回复（安静环境） |
| 文字 | 语音 | 用户打字，AI 语音播报（驾车场景） |
| 文字 | 文字 | 纯文字对话模式 |

### 3.5 任务管理器：AgentScope Plan 模式与现有异步调度能力调研

#### 3.5.1 现有异步调度能力

risk_control 已具备完整的异步任务调度基础设施：

| 组件 | 位置 | 能力 | 适用场景 |
|------|------|------|----------|
| **Celery** | `app/tasks/celery_config.py` + 4 Worker | 分布式任务队列，5 优先级队列，重试/监控 | 批量 AI 任务、数据迁移、报表生成 |
| **APScheduler** | `app/tasks/scheduler.py` | 进程内定时调度（CronTrigger/IntervalTrigger） | 风险评级、事件聚类、缓存预热 |
| **MediationWorkQueue** | `app/mediation/work_queue.py` | Redis+PG 案件级 Work 队列（FIFO + 状态跟踪） | 调解意图处理 |

#### 3.5.2 AgentScope Plan 模式

AgentScope 2.0.8dev 内置了 4 个计划工具（`TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate`），特点：

- **以 Agent 为作用域**：任务清单存储在 `agent.state.tasks_context`，随 AgentState 序列化/恢复
- **支持依赖关系**：`blocks` / `blocked_by` 双向维护，自动清理
- **状态流转**：`pending → in_progress → completed`（任意状态可 `deleted`）
- **可编程操作**：除 LLM 工具调用外，也可从代码直接操作 `tasks_context`
- **可预置任务**：在 Agent 推理前通过代码注入任务清单（Seeding）

#### 3.5.3 复用决策

| 层级 | 复用方案 | 理由 |
|------|----------|------|
| **Agent 内部任务拆解** | ✅ 复用 AgentScope Plan | Agent 自主拆解复杂调解任务，无需额外开发 |
| **案件级 Work 队列** | ✅ 复用 MediationWorkQueue | 已具备完整的 Redis+PG 双写、状态跟踪、优先级调度 |
| **批量异步任务** | ✅ 复用 Celery/APScheduler | 已具备 Worker 集群、监控脚本、死信队列 |

**结论**：三层任务管理能力互补，无需新建组件。

```
┌─────────────────────────────────────────────────────────────┐
│                    任务管理三层架构                       │
│                                                              │
│  Layer 1: AgentScope Plan（Agent 内部）                │
│  ├─ Agent 自主拆解复杂调解任务                       │
│  ├─ 任务状态存储在 AgentState.tasks_context            │
│  └─ 前端可通过 get_plan_status() 查询进度            │
│                                                              │
│  Layer 2: MediationWorkQueue（案件级）                   │
│  ├─ 调解意图入队 → 路由分发 → 执行 → 完成           │
│  ├─ Redis FIFO + PG 持久化（双写保障）                │
│  └─ 支持优先级、状态跟踪、超时处理                    │
│                                                              │
│  Layer 3: Celery/APScheduler（批量异步）                  │
│  ├─ 批量案件处理、数据迁移、报表生成                 │
│  ├─ 4 Worker + 5 队列 + 监控脚本                        │
│  └─ 定时任务（风险评级/事件聚类/缓存预热）           │
└─────────────────────────────────────────────────────────────┘
```

**AgentScope Plan 复用示例**：

```python
# AgentScopeAdapter 初始化时预置调解任务计划
async def _seed_mediation_plan(self, case_context: dict) -> None:
    """预置调解任务计划 — Agent 推理前注入"""
    from agentscope.state import Task

    self._agent.state.tasks_context.tasks.extend([
        Task(
            id="1",
            subject="分析纠纷事实",
            description=f"案件编号: {case_context['case_number']}，分析各方诉求和争议焦点",
            metadata={"source": "mediation_seed"},
        ),
        Task(
            id="2",
            subject="检索相关法条和案例",
            description="根据纠纷事实检索相关法律依据和相似案例",
            blocked_by=["1"],
            metadata={"source": "mediation_seed"},
        ),
        Task(
            id="3",
            subject="生成调解方案",
            description="基于事实分析和法律依据，提出调解方案建议",
            blocked_by=["2"],
            metadata={"source": "mediation_seed"},
        ),
    ])
    # 保持反向边一致
    self._agent.state.tasks_context.tasks[0].blocks.append("2")
    self._agent.state.tasks_context.tasks[1].blocks.append("3")
```

### 3.6 可配置化集成策略与前端配置界面

> **设计原则**：Agent / Skill / 知识库 / MCP Server 的集成配置尽量通过前端界面完成，
> 减少硬编码，支持动态调整。

#### 3.6.1 可配置化范围

| 配置项 | 存储位置 | 当前状态 | 目标状态 |
|---------|----------|----------|----------|
| **Agent 配置**（角色/system_prompt/模型/工具） | DB `ai_agent_config` | ❌ 内存硬编码（`AgentRegistry`） | ✅ 数据库 + 前端 CRUD |
| **工具/Skill 配置** | DB `tool_definition` | ✅ 已数据库化 + 前端界面（`ToolManagement.vue`） | ✅ 保持现状，追加 Plan/MCP 工具支持 |
| **工具分组** | DB `tool_group` | ✅ 已数据库化 + 前端界面 | ✅ 保持现状 |
| **MCP Server 配置** | DB `mcp_api_key` + `mcp_client` + `mcp_square_template` | ✅ 已数据库化 + 前端界面（`McpServiceManagement.vue`） | ✅ 保持现状，补全 Agent 会话级动态注入 |
| **语音会话配置**（greeting/voice/language） | DB `mediation_voice_config` | ❌ 无 | ✅ 数据库 + 前端 CRUD |
| **工具策略**（timeout/maxCalls/enabled） | DB `tool_policy` | ❌ 无 | ✅ 数据库 + 前端 CRUD |

#### 3.6.2 前端配置界面设计

```
┌─────────────────────────────────────────────────────────────┐
│  AI 配置中心（前端菜单）                                  │
│                                                              │
│  ┌─ Agent 管理 ──────────────────────────────────────┐  │
│  │  • Agent 列表（卡片视图）                           │  │
│  │  • Agent 编辑表单：                                  │  │
│  │    - 基本信息：agent_id / name / type               │  │
│  │    - 模型配置：model / temperature / max_tokens   │  │
│  │    - System Prompt（富文本编辑器）               │  │
│  │    - 工具绑定：多选工具列表（从 ToolDefinition 加载）│  │
│  │    - 技能绑定：多选技能列表                       │  │
│  │    - MCP Server 绑定：多选 MCP 服务               │  │
│  │    - 高级配置：maxReActIters / enablePlan          │  │
│  └───────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ MCP Server 管理（已实现） ──────────────────────┐  │
│  │  • 已实现：McpServiceManagement.vue（3 Tab）      │  │
│  │    - Tab 1「我的 MCP」：API Key CRUD + 连接测试  │  │
│  │    - Tab 2「MCP 广场」：模板浏览/安装/卸载       │  │
│  │    - Tab 3「已注册工具」：查看已注册 MCP 工具    │  │
│  │  • 待补全：                                          │  │
│  │    - 工具策略配置（timeout/maxCalls/enabled）      │  │
│  │    - Agent 会话级 MCP 动态注入配置展示            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ 语音会话配置 ────────────────────────────────────┐  │
│  │  • 角色配置列表（按案件类型）                     │  │
│  │  • 配置编辑表单：                                  │  │
│  │    - 角色标识：role_id / role_name                │  │
│  │    - 开场白：greeting（文本输入 + 试听）         │  │
│  │    - 语音身份：voiceIdentity（下拉选择）            │  │
│  │    - 语言偏好：language                             │  │
│  │    - 关联 Agent：agentId（下拉选择）              │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### 3.6.3 前端组件规划

| Vue 组件 | 路径 | 功能 |
|---------|------|------|
| `AgentConfigPanel.vue` | `views/admin/ai-config/agents/` | Agent CRUD + 工具/技能/MCP 绑定 |
| `McpServiceManagement.vue`（已有） | `views/admin/ai/` | MCP 服务管理（3 Tab：我的 MCP/广场/已注册工具），追加工具策略配置 |
| `VoiceSessionConfig.vue` | `views/admin/mediation/config/` | 语音会话角色配置 |
| `ToolManagement.vue`（已有） | `views/admin/ai/` | 保持现有功能，追加 Plan/MCP 工具类型支持 |
| `ToolPolicyEditor.vue` | `views/admin/ai/components/` | 工具策略编辑（timeout/maxCalls，嵌入现有 ToolManagement） |

#### 3.6.4 后端 API 规划

| API 端点 | 方法 | 功能 |
|---------|------|------|
| `/api/v1/admin/ai-config/agents` | GET/POST | Agent 列表 / 创建 |
| `/api/v1/admin/ai-config/agents/{id}` | GET/PUT/DELETE | Agent 详情 / 更新 / 删除 |
| `/api/v1/admin/ai/mcp-api-key/*` | GET/POST/DELETE | ✅ 已实现：MCP API Key CRUD（分页/详情/创建/更新/删除/简易列表/下拉选择） |
| `/api/v1/admin/ai/mcp-client/*` | GET/POST/DELETE | ✅ 已实现：MCP Client CRUD |
| `/api/v1/admin/ai/mcp-square/*` | GET/POST/DELETE | ✅ 已实现：MCP 广场模板 CRUD + 安装/卸载/连接测试 |
| `/api/v1/admin/ai/mcp-tools/list` | GET | ✅ 已实现：已注册 MCP 工具列表（分页/搜索/分类筛选） |
| `/api/v1/admin/ai-config/mcp-servers/{id}/test` | POST | ✅ 已实现（`/api/v1/admin/ai/mcp-square/test/{id}`） |
| `/api/v1/admin/ai-config/mcp-servers/{id}/tools` | GET | ✅ 已实现（`/api/v1/admin/ai/mcp-tools/list`） |
| `/api/v1/admin/mediation/config/voice-roles` | GET/POST/PUT/DELETE | 语音角色配置 CRUD |

---

## 4. 优先级建议与成功指标

### 4.1 高影响快速胜利（低复杂度 + 高业务价值）

| 序号 | 改进项 | 复杂度 | 业务价值 | 成功指标 |
|------|--------|--------|---------|---------|
| **QW-1** | Connect 帧处理（会话初始化配置） | 低 | 高 | 支持 greeting/systemPrompt/voiceIdentity 配置 |
| **QW-2** | 事件协议丰富化（voice.ready/state/turn.*） | 低 | 高 | 前端可感知 5+ 种状态 |
| **QW-3** | AgentAdapter 抽象（桥接 MediationEngine） | 低 | 高 | 语音层可调用 AgentScope/Dify |
| **QW-4** | MCP Bridge（注入知识库工具） | 低 | 高 | Agent 可调用 3+ 个调解知识工具 |
| **QW-5** | 语音会话持久化（MediationVoiceSession） | 低 | 中 | 断线后可恢复会话 |

**实施周期**：3-5 天

### 4.2 战略增强（高复杂度 + 高业务价值）

| 序号 | 改进项 | 复杂度 | 业务价值 | 成功指标 |
|------|--------|--------|---------|---------|
| **SE-1** | Turn 状态机（代际仲裁） | 高 | 高 | 支持打断/并发场景 |
| **SE-2** | 能力声明模型（Provider 差异化） | 高 | 高 | 支持 2+ Provider |
| **SE-3** | 协议适配器（消息格式归一化） | 高 | 高 | 支持 OpenAI/GA 协议 |
| **SE-4** | 工具调用处理器（参数校验/去重/权限） | 高 | 高 | 工具调用成功率 > 95% |
| **SE-5** | 多方发言权仲裁（voice.ownership） | 高 | 高 | 支持 3+ 方语音 |

**实施周期**：7-10 天

### 4.3 技术债解决（中复杂度 + 高可维护性收益）

| 序号 | 改进项 | 复杂度 | 可维护性收益 | 成功指标 |
|------|--------|--------|-------------|---------|
| **TD-1** | Provider 注册表改造（实例注册 + 校验） | 中 | 高 | 注册表通过单元测试 |
| **TD-2** | 错误分类 + 指数退避重连 | 中 | 高 | 弱网断线重连成功率 > 80% |
| **TD-3** | 响应超时保护（responseStartTimeoutMs） | 中 | 中 | 长响应不挂起 |
| **TD-4** | AgentRegistry 数据库驱动 | 中 | 高 | 支持动态管理 Agent |
| **TD-5** | MCP 工具策略配置（timeout/maxCalls） | 中 | 中 | 工具调用行为可控 |

**实施周期**：5-7 天

---

## 5. 分阶段迁移路线图（统一执行规划）

> **整合说明**：本节合并了差距分析的优先级分类（QW/SE/TD）与设计方案（communication_design）的
> Task 1-6 细化任务，形成统一执行规划。每个 Phase 的天数分配已考虑任务依赖关系与并行度。

> **实施状态（截至 2026-09-12，M5）**：端到端最小可用闭环已提前达成，对应 Phase 1 中 QW-1~QW-5 的「基础可用性」目标——连接建立后**可播放返回语音**、**用户/调解员文字分角色显示**、**支持文字输入对聊**、**页面宽度充满窗体**（详见附录 A.7）。剩余战略增强（Turn 状态机 SE-1、协议适配器 SE-3、能力声明 SE-2、多方发言权仲裁 SE-5、工具调用处理器 SE-4、AgentAdapter/MCP 注入、Local Provider、前端组件体系化等）仍按 Phase 2/3 路线图推进，未受 M5 影响。

### Phase 1：基础能力补全（Week 1，5 天）

**目标**：完成高影响快速胜利（QW-1 ~ QW-5），使语音层具备基本可用性。

**任务**：

1. **Day 1-2**：基础设施层 + Connect 帧处理 + 事件协议丰富化 `[QW-1, QW-2, 设计Task1+Task3]`
   - 新增 `ai/voice/audio_codec.py`：重采样 / PCM16 / Base64 工具
   - 新增 `ai/voice/provider_protocol.py`：`VoiceProvider` Protocol 定义（connect/send_audio/interrupt/close + 回调注册）
   - 新增 `schemas/mediation/voice.py`：`VoiceConnectConfig` 请求模型（greeting/systemPrompt/voiceIdentity/language/agentId/mcpServers 等）
   - 修改 `websocket_gateway.py`：解析 connect 事件 → 提取角色配置 → 合并 systemPrompt + language → 构建 instructions
   - 新增事件类型：`voice.ready`、`voice.state`、`turn.started`
   - 实现开场白播报（`speak(greeting)`，outputEnabled 时触发）

2. **Day 3**：AgentAdapter 抽象（基于 AgentScope 原生能力）`[QW-3, 设计Task4]`
   - 新增 `ai/voice/agent_adapter.py`：定义 AgentAdapter Protocol（initialize/process/process_stream/interrupt/get_plan_status/close）
   - 实现 `AgentScopeAdapter`：基于 AgentScope Agent/Toolkit/Msg/ReActConfig 原生能力
   - 复用 ToolManager 单例 + 追加 Plan 工具（TaskCreate/Get/List/Update）
   - 修改 WebSocket 网关：语音层通过 AgentAdapter 调用推理

3. **Day 4**：MCP 会话注入 `[QW-4, 设计Task4]`
   - 新增 `ai/voice/mcp_session_resolver.py`：解析 Agent 绑定的 MCP 服务 ID → 查询 `McpApiKey` 配置 → 通过 `MCPAdapter` 拉取工具 → 注册到当前会话 Toolkit
   - 复用现有 `MCPAdapter`（`app/ai/mcp/tool_adapter.py`）和 `McpApiKey`/`MCPClient` DB 模型
   - 注入调解知识库工具（dispute_strategy_search / dispute_case_search / semantic_query 等）
   - 测试 Agent 推理时可自动调用已绑定的 MCP 工具

4. **Day 5**：语音会话持久化 + 轮次管理 `[QW-5, 设计Task1+Task3]`
   - 新增 ORM 模型：`MediationVoiceSession` + `MediationVoiceTurn`（表结构见 §3.4）
   - `app/db/init_models.py` 登记新模型 + Alembic 迁移脚本
   - 新增 `services/mediation/voice_session_service.py`：会话生命周期管理（create/close/query）
   - 新增 `services/mediation/voice_turn_service.py`：轮次管理 + 业务数据同步
     - 转写 → `AiChatMessage`（`input_mode="voice"`）
     - 情绪 → `MediationEmotionLog`
     - 轮次 → `MediationSession.total_turns`
     - 复杂意图 → `MediationWorkRecord`
   - 集成测试

**交付物**：
- 可运行的单方语音对话（支持角色配置 + 开场白 + Agent 推理 + MCP 工具）
- 语音/文字双模基础支持（input_mode 区分 voice/manual）
- 语音会话 + 轮次记录可查询

**验收标准**：
- ✅ 前端发送 connect 事件可配置 greeting/systemPrompt/voiceIdentity/language
- ✅ 前端可感知 voice.ready / voice.state / turn.started 事件
- ✅ 语音输入 → Agent 推理（AgentScope ReAct） → MCP 工具调用 → 语音输出
- ✅ 语音会话记录写入 mediation_voice_session 表，轮次写入 mediation_voice_turn 表
- ✅ 转写文本同步写入 AiChatMessage（input_mode="voice"）

### Phase 2：核心能力增强 + 前端组件（Week 2，8 天）

**目标**：完成战略增强（SE-1 ~ SE-5），支持复杂场景（打断/并发/多方），并完成前端组件开发。

**任务**：

1. **Day 1-2**：Turn 状态机 + Provider 实现 `[SE-1, 设计Task2]`
   - 新增 `ai/voice/turn_state.py`：实现 TurnState（turnGeneration 代际仲裁 + committed_generation + is_stale）
   - 修改 WebSocket 网关：每个连接维护 TurnState，begin_voice/end_speech 生命周期
   - 实现打断逻辑（用户说话时停止 AI 播放，cancel stale generation）
   - 完善 `dashscope_provider.py`：对接 DashScope Realtime API（Qwen-Audio 端到端）
   - 新增 `local_provider.py`：FunASR `paraformer-zh-streaming` + CosyVoice（可先 mock STT/TTS）
   - 单元测试：Provider 接口契约测试

2. **Day 3-4**：能力声明 + 协议适配器 `[SE-2, SE-3]`
   - 修改 `RealtimeProvider` ABC：增加 `capabilities` 属性（acknowledgesSessionUpdate / singleResponseSlot 等）
   - 实现 `openai_compatible_protocol.py`：消息格式归一化（参考 qwen `openai-compatible-protocol.mjs`）
   - 修改 DashScopeProvider：使用协议适配器替代硬编码事件解析
   - 实现 `validate_realtime_provider`：校验接口/能力/采样率

3. **Day 5-6**：工具调用处理器 + 语音/文字双模前端 `[SE-4, 设计Task5]`
   - 新增 `ai/voice/tool_call_handler.py`：参数校验 / 去重 / 权限检查 / 委派
   - 实现工具策略（timeoutMs / maxCallsPerTurn / maxResultBytes）
   - 修改 AgentAdapter：通过 ToolCallHandler 调用工具
   - 新增 `useMediationVoice.js`：核心组合式 API（connect 角色配置 + switchInputMode + switchOutputMode）
   - 新增 `useMicrophoneCapture.js`：麦克风采集（getUserMedia + echoCancellation + 重采样 48k→16k）
   - 新增 `useAudioPlayback.js`：音频播放队列（decodePcm + AudioBufferSourceNode 24kHz）
   - 新增 `MediationVoiceRoom.vue`：顶层容器 + 子组件
   - 新增 `VoiceControlBar.vue`：语音/文字切换按钮（输入模式 + AI 回复模式独立切换）
   - 新增 `VoiceStatusBar.vue` + `TranscriptPanel.vue`：状态指示 + 实时转写面板

4. **Day 7-8**：多方发言权仲裁 + 断线重连 `[SE-5, 设计Task6]`
   - 新增 `ai/voice/voice_ownership.py`：实现发言权仲裁逻辑（holder/state 模式）
   - 修改 WebSocket 网关：多方模式下仲裁发言权 + 音频路由
   - 实现 `voice.ownership` 事件广播（state: active/available + holder）
   - 实现 `reconnect_backoff.py`：错误分类（inactivity/input_busy/fatal/other）+ 指数退避重连
   - 修改 WebSocket 网关：断线后自动重连 + 状态恢复

**交付物**：
- 支持打断/并发的单方语音对话（Turn 状态机 + 协议适配器）
- 支持 2+ Provider（DashScope + Local）
- 完整前端组件（语音房间 + 状态栏 + 转写面板 + 控制栏 + 音频管线）
- 支持 3+ 方语音对话（发言权仲裁）
- 弱网断线自动重连

**验收标准**：
- ✅ 用户打断 AI 播放时，AI 立即停止（TurnState.is_stale 仲裁）
- ✅ 支持 2+ Provider（DashScope + Local，ProviderRegistry 自动降级）
- ✅ 工具调用成功率 > 95%（ToolCallHandler 参数校验 + 超时保护）
- ✅ 多方模式下发言权不冲突（voice.ownership 仲裁）
- ✅ 前端组件可运行：MediationVoiceRoom → 语音采集 → WebSocket → 音频播放
- ✅ 弱网断线重连成功率 > 80%（指数退避）

### Phase 3：稳定性与可维护性（Week 3，5 天）

**目标**：解决技术债（TD-1 ~ TD-5），提升系统稳定性与可管理性。

**任务**：

1. **Day 1**：Provider 注册表改造 `[TD-1]`
   - 修改 `ProviderRegistry`：类注册 → 实例注册 + `validate_realtime_provider` 能力校验
   - 实现 `is_configured()` 检查：API Key 存在性 + 网络可达性
   - 单元测试：注册表通过测试

2. **Day 2**：响应超时保护 + Dify Agent 适配器 `[TD-3, 设计Task4]`
   - 修改 Provider：增加 `responseStartTimeoutMs` / `responseInactivityTimeoutMs`
   - 实现超时检测逻辑（asyncio.wait_for + 超时回调）
   - 新增 `dify_adapter.py`：Dify 工作流接入（复用现有 DifyModelWrapper）

3. **Day 3**：Local Provider 完善 + 集成测试 `[设计Task2+Task6]`
   - 完善 `local_provider.py`：FunASR + CosyVoice 真实对接（替换 mock）
   - 本地 WebRTC VAD 集成
   - 端到端集成测试（DashScope → Local 降级场景）

4. **Day 4**：AgentRegistry 数据库驱动 + Agent 配置前端化 `[TD-4]`
   - 修改 `AgentRegistry`：从数据库加载 Agent 配置（替代内存硬编码）
   - 实现 Agent CRUD API（`/api/v1/admin/ai-config/agents`）
   - 新增 `AgentConfigPanel.vue`：Agent 管理前端界面（卡片视图 + 编辑表单）

5. **Day 5**：MCP 工具策略配置 + 收尾 `[TD-5]`
   - 在现有 `McpServiceManagement.vue` 中追加工具策略配置 Tab
   - 新增 `tool_policy` DB 模型（timeout / maxCallsPerTurn / enabled / maxResultBytes）
   - 修改 AgentAdapter：调用工具前检查策略
   - 全流程回归测试

**交付物**：
- 稳定的语音通信系统（弱网可重连、长响应不挂起、多 Provider 降级）
- 可管理的 Agent 配置（DB 驱动 + 前端 CRUD）
- MCP 工具策略可配置（前端界面 + DB 持久化）

**验收标准**：
- ✅ Provider 注册表通过单元测试（实例注册 + 能力校验 + 自动降级）
- ✅ 弱网断线重连成功率 > 80%
- ✅ 长响应（> 10s）不挂起（超时保护生效）
- ✅ 支持动态管理 Agent（CRUD + 前端界面）
- ✅ MCP 工具策略可配置（timeout/maxCalls/enabled）
- ✅ Local Provider 可用（FunASR + CosyVoice 端到端）

### 工期总览

| Phase | 天数 | 周次 | 核心交付 |
|-------|------|------|----------|
| Phase 1 | 5 天 | Week 1 | 单方语音对话 + Agent 推理 + MCP 工具 + 会话持久化 |
| Phase 2 | 8 天 | Week 2 | 打断/并发 + 多 Provider + 前端组件 + 多方仲裁 |
| Phase 3 | 5 天 | Week 3 | 稳定性 + Agent 管理 + MCP 工具策略 |
| **总计** | **18 天** | **3 周** | **完整调解语音通信系统** |

---

## 6. 关键文件路径对照表

| 能力域 | qwen-audio-agent 文件 | risk_control 对应文件 | 状态 |
|--------|----------------------|----------------------|------|
| **Provider 抽象** | `server/src/voice/providers/registry.mjs` | `app/mediation/voice/providers/registry.py` | ✅ 已实现 |
| **DashScope Provider** | `server/src/voice/providers/dashscope.mjs` | `app/mediation/voice/providers/dashscope.py` | ✅ 已实现 |
| **协议适配器** | `server/src/voice/providers/openai-compatible-protocol.mjs` | 无 | ❌ 缺失 |
| **WebSocket 网关** | `server/src/voice/realtime-gateway.mjs` | `app/mediation/voice/websocket_gateway.py` | ⚠️ 基础实现 |
| **Turn 状态机** | `server/src/voice/realtime-gateway.mjs`（内嵌） | 无 | ❌ 缺失 |
| **Agent 注册表** | `server/src/agent/backends/registry.mjs` | `app/ai/agent_core/registry.py` | ✅ 已实现 |
| **引擎注册表** | 无对应 | `app/ai/engines/registry.py` | ✅ 独有 |
| **AgentAdapter** | `server/src/agent/backends/local-acp.mjs` | 无 | ❌ 缺失 |
| **协调器** | `server/src/agent/coordinator.mjs` | 无 | ❌ 缺失 |
| **工具调用处理器** | `server/src/voice/tools/tool-call-handler.mjs` | 无 | ❌ 缺失 |
| **任务管理器** | `server/src/task/task-manager.mjs` | `app/mediation/work_queue.py` | ⚠️ 基础实现 |
| **MCP 服务管理** | `server/src/agent/acp-session-tools.mjs` | `app/ai/mcp/server.py` + `app/ai/mcp/tool_adapter.py` + `app/routers/ai/mcp.py`（670 行） + `McpServiceManagement.vue`（656 行） | ✅ 完整实现 |
| **知识库工具** | 无对应 | `app/ai/mcp/knowledge_tools.py` | ✅ 独有 |
| **调解引擎** | 无对应 | `app/mediation/engine.py` | ✅ 独有 |
| **意图分类** | 无对应 | `app/mediation/intent_classifier.py` | ✅ 独有 |
| **路由分发** | 无对应 | `app/mediation/route_dispatcher.py` | ✅ 独有 |

**新增文件（待开发）**：

| 能力域 | 文件路径 | 对应 Phase | 说明 |
|--------|---------|-----------|------|
| **音频编解码** | `ai/voice/audio_codec.py` | Phase 1 | 重采样 / PCM16 / Base64 |
| **Provider Protocol** | `ai/voice/provider_protocol.py` | Phase 1 | VoiceProvider Protocol 定义 |
| **Connect Schema** | `schemas/mediation/voice.py` | Phase 1 | VoiceConnectConfig 请求模型 |
| **AgentAdapter** | `ai/voice/agent_adapter.py` | Phase 1 | AgentAdapter Protocol + AgentScopeAdapter |
| **MCP 会话解析** | `ai/voice/mcp_session_resolver.py` | Phase 1 | MCP 服务 ID → 工具注入 |
| **语音会话服务** | `services/mediation/voice_session_service.py` | Phase 1 | 会话生命周期 |
| **轮次管理服务** | `services/mediation/voice_turn_service.py` | Phase 1 | 轮次管理 + 数据同步 |
| **Turn 状态机** | `ai/voice/turn_state.py` | Phase 2 | 代际仲裁 |
| **协议适配器** | `ai/voice/openai_compatible_protocol.py` | Phase 2 | 消息格式归一化 |
| **工具调用处理器** | `ai/voice/tool_call_handler.py` | Phase 2 | 参数校验/去重/权限 |
| **发言权仲裁** | `ai/voice/voice_ownership.py` | Phase 2 | 多方模式 holder/state |
| **重连退避** | `ai/voice/reconnect_backoff.py` | Phase 2 | 错误分类 + 指数退避 |
| **Local Provider** | `ai/voice/local_provider.py` | Phase 2/3 | FunASR + CosyVoice |
| **Dify 适配器** | `ai/voice/dify_adapter.py` | Phase 3 | Dify 工作流接入 |
| **前端核心 API** | `frontend/src/composables/useMediationVoice.js` | Phase 2 | WebSocket + 双模切换 |
| **麦克风采集** | `frontend/src/composables/useMicrophoneCapture.js` | Phase 2 | getUserMedia + 重采样 |
| **音频播放** | `frontend/src/composables/useAudioPlayback.js` | Phase 2 | 播放队列 + AudioBuffer |
| **语音房间** | `frontend/src/views/mediation/MediationVoiceRoom.vue` | Phase 2 | 顶层容器 |
| **控制栏** | `frontend/src/views/mediation/components/VoiceControlBar.vue` | Phase 2 | 语音/文字切换 |
| **Agent 配置** | `frontend/src/views/admin/ai-config/AgentConfigPanel.vue` | Phase 3 | Agent CRUD |
| **VoiceSession ORM** | `app/models/mediation_voice_session.py` | Phase 1 | 语音会话表 |
| **VoiceTurn ORM** | `app/models/mediation_voice_turn.py` | Phase 1 | 轮次明细表 |

---

## 7. 结论与建议

### 7.1 核心结论

1. **risk_control 已具备基础语音通信骨架**，但缺失关键能力（Turn 状态机、能力声明、协议适配）
2. **调解领域能力是独有优势**（意图分类 + 路由 + 阶段机 + 情绪追踪），应保留并增强
3. **AgentAdapter 应基于 AgentScope 原生能力构建**（Agent/Toolkit/Plan/Msg/AgentState），而非另起炉灶
4. **任务管理三层架构互补**（AgentScope Plan + MediationWorkQueue + Celery/APScheduler），无需新建组件
5. **MCP 服务管理已完整实现**（三层 DB 模型 + 前端 CRUD + 广场安装/卸载 + 连接测试 + 工具列表），仅需补全 Agent 会话级动态注入和工具策略
6. **数据模型设计灵活**（AiChatMessage.extra_data），无需改动表结构；新增 2 张表（voice_session + voice_turn）即可支撑语音层
7. **配置化是核心方向**：Agent/Skill/MCP/语音角色等配置应通过前端界面管理，减少硬编码
8. **前端组件是缺失环节**：设计方案补充了完整的前端组件规划（composables + Vue 组件），填补了差距分析中的前端空白
9. **统一执行规划 18 天 3 周**：Phase 1（5d 基础）→ Phase 2（8d 核心+前端）→ Phase 3（5d 稳定性），每个 Phase 均有明确交付物与验收标准

### 7.2 实施建议

1. **优先完成 Phase 1**（5 天），使语音层具备基本可用性
2. **Phase 2 扩展到 8 天**，包含前端组件开发（设计Task5 的 composables + Vue 组件）
3. **Phase 3 保持 5 天**，优先保证核心功能稳定 + Local Provider 真实对接
4. **保持调解领域能力独立**，不要强行对齐 qwen-audio-agent（它没有调解引擎）
5. **数据模型保持现状**，AiChatMessage.extra_data 已足够灵活，新增 2 张表即可
6. **前后端并行开发**：Phase 2 前端组件可与后端 Turn 状态机/协议适配器并行推进

### 7.3 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **DashScope API 不稳定** | 语音通信中断 | 实现错误分类 + 指数退避重连 |
| **Agent 推理延迟** | 用户体验差 | 实现响应超时保护 + 进度播报 |
| **多方发言冲突** | 音频混乱 | 实现发言权仲裁（voice.ownership） |
| **MCP 工具调用失败** | 功能不可用 | 实现工具策略（超时/重试/降级） |
| **数据库性能瓶颈** | 语音延迟 | 语音会话异步写入 + 批量提交 |

---

## 附录 A：实现期补充与修复（M2–M4 验收回归）

> 本节逆向同步 M2–M4 落地后、UAT/验收阶段发现并修复的问题，供后续维护与回归参考。
> 这些问题不改变 §2 的差距结论，但修正了落地形态与配置约定。

### A.1 语音模型配置改为数据库驱动（替换硬编码 / 环境变量 api_key）

- **问题**：`DashScopeProvider` 直接依赖环境变量 `DASHSCOPE_API_KEY`，未配置时连接即报 `需要 api_key`，且无法在界面切换模型。
- **方案**：新增 `app/mediation/voice/voice_config.py`，网关连接前调用 `resolve_voice_config(provider, model_id)` 从 `ai_api_key` / `ai_chat_model`（`type=7` 标记「语音实时」，`VOICE_MODEL_TYPE=7`）读取 `api_key` + `model`，避免硬编码。
- **界面**：新增「语音模型配置」页（`frontend/src/views/admin/mediation/config/VoiceModelConfig.vue`），支持模型 CRUD + 设默认；`VoiceDemo.vue` 提供模型下拉，默认取 DB 默认模型。
- **初始化数据**：参考 `qwen-audio-agent`（`config/settings.json` 的 `voice.dashscope`）生成种子，见 `docs/sql/45_voice_realtime_init.sql`：
  - `ai_api_key`：平台 `DashScope`，`url=wss://dashscope.aliyuncs.com/api-ws/v1/realtime`；`api_key` 留空占位，需后台填真实 Key。
  - `ai_chat_model`：`model=qwen-audio-3.0-realtime-plus`、`type=7`、`is_default=true`、`status=1`。
  - SQL 幂等（重复执行不重复插入、不产生多个默认），并内置 `UPDATE ai_chat_model SET type=7 WHERE type=6` 归正早期误写值。

#### A.1.1 类别值对齐数据字典（type 6 → 7）

- 前端「模型类别」数据字典 `model_type` 中「语音模型」的取值为 **7**（对话=1、向量=5、语音实时=7）。
- 原代码/SQL 误用 `type=6`，与字典不一致：前端「类别」列无法映射、且网关只认 6 会漏掉字典值 7 的模型。
- 改动：`VOICE_MODEL_TYPE` 由 `6` 改为 `7`（`voice_config.py`）；`45_voice_realtime_init.sql` 全部 `type=6` → `type=7`；新增 `type=6→7` 幂等迁移。

#### A.1.2 默认模型全局唯一

- **问题**：`create_voice_model` / `update_voice_model` / `set_default_voice_model` 仅在「同 key_id + 同 type」内清除其它默认，跨 key 会并存多个 `is_default=true`；`resolve_voice_config` 取默认时 `filter(is_default).first()` 顺序不确定，可能选错模型（曾导致 `test_voice_model_crud_and_default` 取到种子默认而非测试新建默认）。
- **方案**：清除范围改为「同 type 全局」（不限定 key_id），保证语音默认唯一。初始化 SQL 的默认清除同步改为同类型全局。

#### A.1.3 空密钥 / 无模型 精准提示

- `resolve_voice_config` 改为恒返回 dict，含 `configured` 标志与 `reason`（`no_model` / `empty_key`）：
  - `reason=empty_key`：模型已启用但关联 `ai_api_key.api_key` 为空 → 网关报：`语音模型「{model}」(id={id}) 已启用，但关联密钥「{key_name}」的 api_key 为空：请在「API Key 管理」中填写真实的 DashScope API Key`（此前笼统报「未配置语音模型」并误导去「语音模型配置」页，而该页改不了密钥）。
  - `reason=no_model`：无任何启用语音模型 → 网关报：`未配置语音模型：请在「语音模型配置」中新增并启用一个语音模型（type=7）`。
- 路由 `/config/voice-models/default` 透出 `configured` / `reason`，前端可据此显示更精确的配置状态与告警。

#### A.1.4 测试修正（默认唯一化联动）

- `tests/mediation/test_voice_model_crud_and_default.py` 的 `test_voice_model_crud_and_default`：测试库已存在种子默认模型（不同 key_id）时，因多默认并存，断言 `d["model"] == "qwen-realtime"` 失败（实际取到种子模型）。A.1.2 的默认全局唯一化从根因修复该用例，无需改动测试断言本身。

### A.2 前端页面与路由整理

- **问题**：早期误将语音 RTC 演示页注册为**顶层路由**，导致点击菜单无反应（admin 菜单走 `componentMap`，按 `menuKey=path 末段` 静态映射，而非 vue-router 动态匹配）。
- **方案**：
  - 演示页（`VoiceDemo` 等）改为挂在根布局 `AppLayout` 的 `children` 下（保留侧边栏），撤销顶层路由。
  - `views/admin/index.vue` 用 `componentMap` 注册组件（`'voice-demo'` / `'voice-models'` 等），并补 `AudioOutlined`/`SoundOutlined` 图标。

### A.3 菜单录入 SQL

- 语音 RTC 设置菜单（演示 + 配置）通过菜单录入 SQL 注入，使前端菜单在「设置」下可见（4 条菜单：语音 RTC 演示、语音角色配置、Agent 配置、工具策略、语音模型配置）。

### A.4 prometheus_client 依赖与降级

- **问题**：`metrics.py` 直接 `import prometheus_client`，生产/部分开发环境未安装时 `ModuleNotFoundError` 导致应用启动崩溃。
- **方案**：`metrics.py` 改为 `try/except ImportError` 降级为空 stub（缺失时指标端点不可用但不影响主应用）；`requirements.txt` 增加 `prometheus_client>=0.20.0`。

### A.5 语音 WebSocket 连接健壮性

- **问题**：前端连接 `/api/v1/mediation/voice/ws` 未带 `case_number`，触发 422 握手失败（`failed: 语音连接异常`）。
- **方案**：前端连接 URL 补齐 `case_number` / `participant_id` / `provider` 参数；网关将 `case_number` / `participant_id` 改为可选并给默认值兜底，避免因缺参整体拒绝。

### A.6 DashScope Realtime 连接鉴权与音频编码修复（对齐 qwen-audio-agent）

> 现象：日志报 `Provider 连接失败: server rejected WebSocket connection: HTTP 401`。
> 根因与修复（已落地 `app/mediation/voice/providers/dashscope.py`，对照 `qwen-audio-agent` 可用实现）：

- **A.6.1 鉴权方式（`Authorization` 头，弃用 `?api-key=` 查询参数）**
  - DashScope Realtime API 的 WebSocket 握手阶段**只认 `Authorization: Bearer <api_key>` 头**（`qwen-audio-agent/server/src/voice/providers/dashscope.mjs:74`）。
  - 旧的 `?api-key=<key>` 查询参数已被官方实时 API 弃用，单独使用会触发 **HTTP 401**（被服务端视为密钥缺失）。
  - 连接 URL 改为仅带 `?model=<model>`（参考 `qwen-audio-agent/server/src/core/config.mjs:578` 的 `realtimeUrl`：`${baseUrl}?model=...`），不再拼接 `api-key`。
  - 实现：`websockets.connect(url, extra_headers=[("Authorization", f"Bearer {api_key}")])`。

- **A.6.2 音频编码（base64，非 hex）**
  - DashScope `input_audio_buffer.append` 的 `audio` 字段接受 **base64 编码的 PCM**（`qwen-audio-agent/web/src/audio.js` 的 `pcmBase64`）。
  - 浏览器经 WebSocket 上行原始 PCM 字节（`websocket_gateway.py` 的 `client_reader` 直接 `send_audio(data)`），网关侧 `send_audio` 改为 `base64.b64encode(pcm_data).decode("ascii")`，不再使用 `pcm_data.hex()`。
  - 下行 `response.audio.delta.delta` 是 base64 编码的 PCM。早期实现「原样转发 base64 字符串给前端、由前端解码」因前后端帧类型对不上（网关发 `audio.delta`、前端只认 `audio`）导致**完全无声**。M5 已修正：网关侧 `base64.b64decode(delta)` 还原为原始 PCM 字节，以**二进制 WebSocket 帧**下发（`provider_reader` 检测 `frame["data"]` 为 `bytes` → `send_bytes`），浏览器 `AudioContext` 直接播放（24kHz 单声道 16bit）。前端同时保留 base64 字符串回退分支以兼容。

- **A.6.3 鉴权头必须用 `additional_headers`（非 `extra_headers`）**
  - `websockets.connect` 的 `extra_headers` 参数会转发到 `loop.create_connection(extra_headers=...)`，而该参数 **Python 3.12+ 才有**；在 Python 3.11（本项目运行环境）上会抛 `TypeError: ... create_connection() got an unexpected keyword argument 'extra_headers'`。
  - 此前代码用 `extra_headers` 且带 `except TypeError` 静默回退到「无头连接」——`Authorization` 头因此从未发出，DashScope 收不到密钥 → 恒为 401（与 `websockets` 安装版本无关，17.x 仍复现）。
  - 正确做法：`websockets.connect(url, additional_headers=[("Authorization", f"Bearer {api_key}")])`。`additional_headers` 直接写入握手请求头（`self.request.headers`），**Python 3.11 即可**，且 DashScope 实时 API 只认此头。已落地验证 `DashScopeProvider.connect` 返回 OK。
  - `requirements.txt` 维持 `websockets>=12` 无碍（现行 17.x），但根因是参数名而非版本。

- **A.6.4 端点可配置（支持百炼业务空间）**
  - `DashScopeProvider` 默认端点 `wss://dashscope.aliyuncs.com/api-ws/v1/realtime`；连接时若 `session_config` 提供 `base_url` 则覆盖。
  - 网关经 `resolve_voice_config` 从 `ai_api_key.url` 读取端点，可在「API Key 管理」中为对应密钥配置百炼业务空间专属域名（如 `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime`）。

**排查清单（401）**：① Key 无效/过期/无实时权限；② `model_id` 对应模型名不存在；③ `websockets` 版本过旧导致头未发出；④ 百炼工作空间密钥未配置专属 `url`。

### A.7 语音通道端到端联调修复（M5 验收回归）

> 现象：连接已建立、麦克风已开，但**无返回语音、无文字显示、无法文字对聊**。
> 根因：前后端协议帧类型不一致 + 后端缺文本发送 / 音频未解码。

#### A.7.1 后端：DashScopeProvider 文本输入 `send_text`（新增）

- 此前 `RealtimeProvider.send_text` 为同步 no-op，网关 `_handle_control_frame` 对 `input.message` 执行 `await realtime_provider.send_text(text)` 会因「非 awaitable」崩溃，文字对聊不可用。
- 现 `DashScopeProvider.send_text(text)` 为 `async`，对齐 qwen-audio-agent：
  - 发送 `conversation.item.create`，`item = { type:"message", role:"user", content:[{type:"input_text", text}] }`；
  - 紧接发送 `response.create` 触发模型回复（文本模式 / 打断时）。
- `base.py` 的 `send_text` 同时改为 `async def`（无覆盖子类不再崩溃）。

#### A.7.2 后端：下行音频 base64 解码为二进制帧（修正无声）

- `DashScopeProvider._parse_event` 对 `response.audio.delta` 的 `delta` 执行 `base64.b64decode`（带 try/except 兜底）得到原始 PCM 字节，包装为 `ProviderEvent("audio_delta", {"audio": bytes})`。
- 网关 `_normalize_outbound` 将其映射为 `{type:"audio.delta", data: <bytes>}`；`provider_reader` 检测到 `data` 为 `bytes` → `websocket.send_bytes(bytes)`，前端收到裸 `ArrayBuffer` 直接喂 `AudioContext`（24kHz/16bit/单声道）。
- 不动 client→server 上行：浏览器上行仍是原始 PCM 字节，网关 `send_audio` 侧 base64 编码（见 A.6.2）。

#### A.7.3 后端：转写事件归一化为带 role 的 `transcript.delta`

- `response.audio_transcript.delta`（模型口播文字）→ `ProviderEvent("tts_transcript", {"text"})` → 网关映射为 `{type:"transcript.delta", data:{text, role:"assistant"}}`。
- `conversation.item.input_audio_transcription.completed`（用户 ASR）→ 由旧的 `asr_completed` 改为 `ProviderEvent("transcript", {"text"})` → 网关映射为 `{type:"transcript.delta", data:{text, role:"user"}}`。
- 前端 `useVoiceChannel` 据此**分角色累积显示**：用户语音转写为独立气泡；调解员口播文字按 delta 累加到同一气泡，新一轮回复（`response_started`）开始前定稿上一条。

#### A.7.4 前端：帧类型对齐 + 播放/显示/回显

- `useVoiceChannel.ts`：`handleFrame` 由旧的 `audio`/`transcript` 分支改为匹配网关实际下发的 `audio.delta`/`transcript.delta`；`playAudio` 兼容二进制帧与 base64 字符串；`sendText` 发送后本地回显用户输入（`appendTranscript('user', text, finalize=true)`）。
- `types/voice.ts`：`VoiceEventType` 补充 `audio.delta`/`transcript.delta`/`transcript.final`；`VoiceTurn` 增加 `finalized?: boolean`（支撑流式累积）。
- `VoiceChannel.vue`：卡片 `width:100%`（去除原 `max-width:720px` 限制，**充满窗体**）；新增文本输入框（`a-input-search`，连接态可输入/回车发送），实现文字对聊。

#### A.7.5 实际生效的 WebSocket 协议（与 §3.4.2 设计稿的差异）

| 方向 | 设计稿约定 | M5 实际落地 |
|------|-----------|------------|
| 上行文字 | `input.message` `{ parts:[{type:"text",text}] }` | `input.message` `{ text }`（网关按 `event.get("text")` 解析） |
| 下行音频 | `audio.delta` `{audio,sampleRate,responseId}`（JSON+base64） | **二进制帧**承载原始 PCM（`ArrayBuffer`），无 JSON 信封 |
| 下行转写 | `transcript.delta` `{content,turnId}` | `transcript.delta` `{ text, role:"user"\|"assistant" }`（JSON） |
| 文字对聊 | `send_text` 缺失（no-op） | `DashScopeProvider.send_text` 已实现（`conversation.item.create`+`response.create`） |

> 说明：§3.4.2 的协议是「目标设计」，M5 落地做了务实收敛（音频走二进制帧降低延迟、转写用 `role` 区分说话人）。后续若需严格对齐设计稿（如 `audio.done`/`transcript.final` 终态帧、`turnId`），可在网关 `_normalize_outbound` 增补。

### A.8 语音质量修复：根因修复 + 轻量 DSP 播放链（2026-09-14）

> 现象：AI 调解员返回的音频包含大量背景噪音（回声/咔哒声/底噪嘶声）。
> 设计文档：`2026-09-14-voice-audio-quality-design.md`（方案 A，对标 qwen-audio-agent 实测实现）。

**根因与修复**：

| # | 根因 | 修复 | 落地文件 |
|---|------|------|---------|
| 1 | 上行 PCM 未重采样：AudioContext 48k 采样直发，模型按 16k 解析（音频拉慢 3 倍、频谱畸变，ASR/VAD 大量误触发） | `createStreamingResampler`（跨 chunk 保留插值相位，逐字节移植 qwen `audio.js`）：`ctx.sampleRate → input_sample_rate(16k)` | `frontend/src/utils/audioDsp.ts` + `useVoiceChannel.ts` |
| 2 | getUserMedia 未显式声明 AEC/NS/AGC：外放时扬声器 TTS 被麦克回采，模型"听到自己"产生回声噪声 | 显式 `{ echoCancellation: true, noiseSuppression: true, autoGainControl: true }` | `useVoiceChannel.ts` |
| 3 | 下行播放无连续时间轴：逐 delta 立即 `src.start()`，重叠/缝隙产生周期性咔哒声 | `useVoicePlayback`：连续 cursor 调度（`max(ctx.currentTime+0.02, cursor)`）+ ~100ms 抖动合并 | `frontend/src/composables/useVoicePlayback.ts` |
| 4 | session.update 缺 turn_detection：默认 VAD 阈值不可控，回声易误触发 | 默认下发 `{type: "smart_turn"}`（session_config 可覆盖，`"off"` 关闭回退默认 VAD）；`error` 事件落 warning 日志 | `backend/app/mediation/voice/providers/dashscope.py` |
| 5 | 播放链无任何后处理：底噪嘶声与削波不受控 | `createPlaybackChain`：HPF(80Hz)→LPF(8kHz)（4 阶 Butterworth，每侧两级 biquad）→ 压缩器(-12dB, 3:1, attack 3ms, release 250ms) → +2dB 补偿增益；采样域去直流 + 噪声门（播放侧 -60dBFS / 上行侧 -50dBFS） | `audioDsp.ts` + `useVoicePlayback.ts` |

**其它落地约束**：
- AudioContext 显式 `{ sampleRate: 48000 }`（旧浏览器 try/catch 回退设备默认，以其为重采样源率）。
- 全部 DSP 参数集中在 `AUDIO_DSP_CONFIG`（`audioDsp.ts`），一行可切 300–3400Hz 电话带宽（默认 80Hz–8kHz 保留 TTS 自然度）。
- 播放职责从 `useVoiceChannel.ts`（307 行）拆出 `useVoicePlayback.ts`，满足单文件 < 400 行约束。
- 不引入 RNNoise WASM（qwen-audio-agent 未使用；TTS 源底噪低，重降噪反损人声自然度），验证不达标再评估。

**验证（Node 内置 `node:test`，零新增依赖，`npm test` = `node --test`，`frontend/src/utils/__tests__/audioDsp.spec.ts`）**：
1. 重采样 48k→16k 长度 1/3 精确 + 1kHz 频率保持（跨 10 chunk 相位连续）；
2. 噪声门：-80dBFS 底噪过门后 ≤ -60dBFS；-6dBFS 语音能量保留 ≥ 90%；门状态跨 buffer 保持不截字头；
3. SNR：50Hz 哼声 + 16kHz 嘶声过 4 阶滤波级联衰减 ≥ 15dB、带内 1kHz 增益 |·| < 1dB（RBJ 双二阶仿真，与 BiquadFilterNode 等价）；
4. PCM16 roundtrip 误差 ≤ 1/32767 + clamp；
5. 去直流稳态均值 < 1e-4。

### A.9 语音模型可用性清理 + 本地 Docker S2S 支持（2026-09-14）

> 现象：RTC 演示页模型下拉出现无效模型名（历史测试数据 `qwen-realtime`/`qwen-realtime-v2`，
> 连接必 401）；且无法使用本地 Docker 部署的 qwen-audio-s2s。

**A.9.1 有效模型目录与可用性过滤**
- `voice_config.py` 新增 `VALID_DASHSCOPE_REALTIME_MODELS`（对齐 qwen-audio-agent 模型目录）：
  `qwen-audio-3.0-realtime-plus` / `qwen-audio-3.0-realtime-flash` / `qwen3.5-omni-flash-realtime` / `qwen3.5-omni-plus-realtime`。
- `list_voice_models()` 只返回**可用**行：DashScope 要求模型名在目录内且 api_key 非空；
  其它平台要求 api_key 非空；s2s 平台无需 Key。
- `resolve_voice_config(provider, model_id)`：默认解析只在可用候选中选取；
  model_id 显式指定不可用行时报 `invalid_model`（模型名无效）/ `empty_key`（密钥为空）。
- 网关对 `invalid_model` 给出精确报错；`provider=local`（本地管线不依赖云端配置）跳过解析，
  修复其被误报 no_model 而无法连接的问题。

**A.9.2 本地 Docker S2S Provider（`providers/s2s.py`，key=`s2s`）**
- 对齐 qwen-audio-agent 的 speech-to-speech Provider + GA Realtime 协议（`ga-protocol.mjs`）：
  `session.update` 带 `session.type='realtime'` 判别字段与 `output_modalities`；
  `response.create` 用 `output_modalities`（非 beta 的 `modalities`）；
  文本增量事件 `response.output_text.delta` 归一化为口播转写；
  server_vad + `interrupt_response`，输出 PCM 24kHz。
- 端点：`ai_api_key.url`（缺省 `ws://127.0.0.1:8765/v1/realtime`），api_key 可选作 Bearer Token。
- 采样率 16k/24k；`ProviderRegistry` 惰性注册 `s2s`；前端 provider 下拉新增「本地 S2S（Docker）」，
  模型下拉按平台过滤，默认模型按其平台自适应切换 provider。
- 引导数据：`docs/sql/46_voice_model_cleanup_and_local_s2s_init.sql`（幂等）——停用无效 DashScope
  模型行（含 platform 为空的历史行并清除其默认标记）、补插有效默认模型、插入 s2s 密钥（仅承载端点 url）与模型行。

**验证**：后端 mediation 全量测试通过（含新增 `test_s2s_provider.py` 11 例：
GA session 结构 / base64 音频 / output_modalities / 事件归一化 / registry 注册；
`test_voice_config_router.py` 更新为有效模型名并新增可用性过滤断言，测试自清理防污染共享库）。

---

**文档版本**：v1.9  
**创建日期**：2026-09-03  
**最后更新**：2026-09-14  
**更新记录**：
- v1.9（2026-09-14）：附录 A 新增 A.9——语音模型可用性清理（VALID_DASHSCOPE_REALTIME_MODELS 目录 + list/resolve 过滤无效模型与空密钥）+ 本地 Docker qwen-audio-s2s 支持（S2SProvider，GA Realtime 协议，端点 ws://127.0.0.1:8765/v1/realtime）+ 46 号幂等 SQL（停用无效模型/补插有效默认/插入 s2s 引导数据）+ provider=local 跳过云端配置解析修复
- v1.8（2026-09-14）：附录 A 新增 A.8——语音质量修复（方案 A：根因修复 + 轻量 DSP 播放链）：① 上行流式重采样 48k→16k（根治采样率错配）；② getUserMedia 显式 AEC/NS/AGC（根治外放回声）；③ useVoicePlayback 连续时间轴调度 + 抖动合并（根治咔哒声）；④ session.update 补配 turn_detection=smart_turn；⑤ createPlaybackChain 播放链（HPF/LPF/压缩器/噪声门/去直流）；AudioContext 显式 48kHz；node:test 合成信号验证（SNR ≥15dB、静音段 ≤-60dBFS）
- v1.7（2026-09-12）：附录 A 新增 A.7——语音通道端到端联调修复（M5）：① DashScopeProvider.send_text 文本输入实现（conversation.item.create+response.create）；② 下行音频 base64 解码为二进制帧（修正无声）；③ 转写事件归一化为带 role 的 transcript.delta（用户/调解员分角色显示）；④ 前端帧类型对齐 + 播放/显示/本地回显 + 页面充满窗体 + 文本输入框；⑤ 登记实际生效协议与 §3.4.2 设计稿的差异
- v1.6（2026-09-09）：附录 A 新增 A.6——DashScope Realtime 连接鉴权（`Authorization` 头、弃用 `?api-key=` 查询参数）/ 上行音频 base64 编码 / `websockets>=12.0` 依赖约束（Windows 发头必需）/ 端点可配置（百炼工作空间专属域名）四项实现修正，对齐 `qwen-audio-agent` 可用实现
- v1.5（2026-09-09）：附录 A 同步 M4 收尾修复——A.1 类别值 `type 6→7`（对齐数据字典 `model_type`）、默认模型全局唯一（跨 key 清除）、`resolve_voice_config` 返回 `{configured, reason}` 精准提示（empty_key/no_model）、`test_voice_model_crud_and_default` 多默认导致的断言失败根因修复
- v1.4（2026-09-09）：新增附录 A「实现期补充与修复（M2–M4 验收回归）」——语音模型 DB 配置（voice_config.py + docs/sql/45_voice_realtime_init.sql）、前端路由/菜单整理、prometheus_client 依赖降级、WS 连接健壮性
- v1.3（2026-09-03）：整合设计方案（communication_design）任务列表到迁移路线图——§5 重写为统一执行规划（18 天 3 周）；§3.4 补充 DB 表结构/事件协议/音频格式/双模矩阵；§6 新增 22 个待开发文件路径；§7 结论扩展到 9 条
- v1.2（2026-09-03）：修正 MCP 服务管理描述——risk_control 已实现完整 MCP 管理体系（3 DB 模型 + 670 行路由 + 656 行前端 + MCPAdapter + FastMCP Server），仅 Agent 会话级注入和工具策略待补全
- v1.1（2026-09-03）：AgentAdapter 基于 AgentScope 原生能力重构；新增任务管理器调研（§3.5）；新增可配置化集成策略与前端 UI 设计（§3.6）
- v1.0（2026-09-03）：初始版本
