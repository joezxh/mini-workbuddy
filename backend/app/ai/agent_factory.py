"""AgentScope Agent 工厂 — 根据 session_type 创建对应 Agent 实例。"""
from __future__ import annotations

from typing import AsyncGenerator, Optional
from loguru import logger
from sqlalchemy.orm import Session


from app.ai.msg_utils import text_of


def resolve_skill_name(skill_config: Optional[dict]) -> str:
    """解析技能标识：兼容 name（潜在旧调用方）与 package_id（当前前端载荷）。

    前端 skill 载荷为 ``{package_id, package_name, script_id, script_name}``；
    后端技能执行单位本就是整技能（package_id）。两者都缺失时回退 ``general``
    并记录 warning（保持原有兜底语义）。
    """
    cfg = skill_config or {}
    name = cfg.get("name") or cfg.get("package_id")
    if not name:
        logger.warning("SkillAgent 未收到 skill 标识（name/package_id），回退 general")
        return "general"
    return str(name)


class ResearchAgent:
    """深度研究 Agent 封装 — 将 ResearchOrchestrator 适配为 AgentScope Agent 接口。

    实现 reply_stream() 方法，将研究事件转换为 SSE 兼容的 dict 事件，
    由 SSEBridge 或 ai_agent router 直接消费。
    """

    def __init__(self, db: Session, model_id: Optional[int] = None,
                 knowledge_bases: Optional[list] = None, name: str = "深度研究"):
        self._db = db
        self._model_id = model_id
        self._knowledge_bases = knowledge_bases
        self.name = name

    async def reply_stream(self, user_msg) -> AsyncGenerator[dict, None]:
        """运行 ResearchOrchestrator 并 yield 研究事件。"""
        from app.ai.research.orchestrator import ResearchOrchestrator

        topic = text_of(user_msg)
        orchestrator = ResearchOrchestrator(
            db=self._db,
            model_id=self._model_id,
            knowledge_bases=self._knowledge_bases,
        )
        async for event in orchestrator.run(topic):
            # 将研究事件包装为 SSE 友好的 dict
            event_type = event.pop("type", "research_progress")
            yield {"type": event_type, "data": event}


class SkillAgent:
    """技能执行 Agent 封装 — 将 SkillExecutionService 适配为 AgentScope Agent 接口。"""

    def __init__(self, db: Session, model_id: Optional[int] = None,
                 skill_config: Optional[dict] = None, name: str = "技能执行"):
        self._db = db
        self._model_id = model_id
        self._skill_config = skill_config
        self.name = name

    async def reply_stream(self, user_msg) -> AsyncGenerator[dict, None]:
        """运行 SkillExecutionService 并 yield 技能执行事件。"""
        from app.ai.skills.execution import SkillExecutionService

        topic = text_of(user_msg)
        skill_name = resolve_skill_name(self._skill_config)
        service = SkillExecutionService()
        async for skill_event in service.execute(
            skill_name=skill_name,
            user_message=topic,
            model_id=self._model_id,
        ):
            yield {"type": skill_event.type, "data": skill_event.data}


class ReactAgent:
    """ReAct 计划执行 Agent 封装 — 将 ReActOrchestrator 适配为 AgentScope Agent 接口。

    实现 reply_stream() 方法，将 ReAct 事件转换为 SSE 兼容的 dict 事件，
    由 SSEBridge 或 ai_agent router 直接消费。
    """

    def __init__(self, db: Session, model_id: Optional[int] = None,
                 tools: Optional[list] = None, react_config: Optional[dict] = None,
                 sys_prompt: str = "", name: str = "ReAct 助手",
                 skills: Optional[list] = None):
        self._db = db
        self._model_id = model_id
        self._tools = tools or []
        self._react_config = react_config or {}
        self._sys_prompt = sys_prompt
        self._skills = skills or []
        self.name = name

    async def reply_stream(self, user_msg) -> AsyncGenerator[dict, None]:
        """运行 ReActOrchestrator 并 yield ReAct 事件。"""
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


class TeamAgent:
    """团队协调 Agent 封装 — 将 TeamManager 适配为 AgentScope Agent 接口。"""

    def __init__(self, db: Session, team_id: Optional[int] = None,
                 model_id: Optional[int] = None, name: str = "团队协调者"):
        self._db = db
        self._team_id = team_id
        self._model_id = model_id
        self.name = name

    async def reply_stream(self, user_msg) -> AsyncGenerator[dict, None]:
        """运行团队编排并 yield 执行事件。"""
        from app.ai.team_manager import TeamManager

        topic = text_of(user_msg)
        manager = TeamManager(self._db)
        async for event in manager.run_team(
            team_id=self._team_id,
            user_input=topic,
            model_id=self._model_id,
        ):
            yield event


class AgentFactory:
    """根据 session_type 创建对应的 AgentScope Agent"""

    def __init__(self, db: Session):
        self._db = db

    def create_agent(self, session_type: str, config: dict):
        """根据会话类型创建对应的 Agent

        Args:
            session_type: 会话类型 (general/thinking/deep_research/skill/agent/team)
            config: Agent 配置字典，包含 name/model_id/sys_prompt/tools 等

        Returns:
            AgentScope Agent 实例
        """
        # 大小写规整：DB agent_config.agent_type 登记为大写（如 SUPERAGENT），
        # 而 case 标签均为小写 —— 不规整会直接落入 case _ 抛 ValueError
        session_type = str(session_type or "").strip().lower()
        match session_type:
            case "general":
                return self._create_general_agent(config)
            case "thinking":
                return self._create_thinking_agent(config)
            case "deep_research":
                return self._create_research_agent(config)
            case "skill":
                return self._create_skill_agent(config)
            case "agent":
                return self._create_expert_agent(config)
            case "plan":
                return self._create_plan_agent(config)
            case "react":
                return self._create_react_agent(config)
            case "team":
                return self._create_team_agent(config)
            case "sop":
                return self._create_sop_agent(config)
            case "superagent":
                return self._create_superagent_agent(config)
            case "data":
                # 数据分析模式：复用通用 Agent，SQLBot 能力经 AgentConfig.tools
                # （tool_key=sqlbot_*）注入；会话收尾由 STRATEGY_TABLE["data"] 记录
                return self._create_general_agent(config)
            case _:
                raise ValueError(f"Unknown session_type: {session_type}")

    # ── 公共构建（agentscope 2.x 契约）────────────────────────
    def _build_model_and_toolkit(self, config: dict):
        """构建 AgentScope 2.x 需要的 (model, toolkit)。

        2.x 的 ``Agent`` 需要真实的 ChatModel 实例与 Toolkit，不再接受旧版的
        ``model_config_name`` / ``tools`` 列表。model_id 为 DB 模型 ID 时走
        DB 配置，否则（如 "default" 这类占位字符串）降级到 ENV 兜底模型。
        """
        from app.ai.strategy.factory_ext import (
            build_default_model_config,
            build_model,
            resolve_model_config,
        )
        from app.ai.tool_manager.manager import build_toolkit

        raw = config.get("model_id_db") or config.get("model_id")
        cfg = {}
        if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
            cfg = resolve_model_config(int(raw))
        model = build_model(cfg or build_default_model_config())
        # 工具注入：config["tools"] 为 tool_key 列表，按 DB 定义实例化
        toolkit = build_toolkit(self._db, config.get("tools"))
        return model, toolkit

    def _rag_kwargs(self, config: dict, toolkit) -> dict:
        """按配置装配原生 RAGMiddleware（对齐文档 §7 / D16）。

        未配置 ``knowledge_bases`` 时返回空 dict（不改动既有 Agent 构造语义）；
        agentic 模式下 ``RAGMiddleware.list_tools`` 不会被 Agent 自动调用，
        必须手动并入 Toolkit。
        """
        kb_ids = config.get("knowledge_bases") or []
        if not kb_ids:
            return {}

        import asyncio

        from agentscope.tool import Toolkit

        from app.services.kb.rag.knowledge_factory import knowledge_base
        from app.services.kb.rag.rag_middleware import build_rag_middleware

        tenant_id = config.get("tenant_id")
        if not tenant_id:
            logger.warning("[RAG] 缺少 tenant_id，跳过 RAG 中间件装配")
            return {}

        from app.db.database import SessionLocal
        from app.services.kb.rag.embedding_factory import build_embedding_model
        from app.services.kb.rag.pg_vector_store import PgVectorStore
        from agentscope.rag import KnowledgeBase

        async def _build():
            kbs = []
            from app.services.kb.index_mode import resolve_index_mode

            for kid in kb_ids:
                # economy 库不建向量索引（向量列 NULL），经 RAGMiddleware 检索会
                # 徒耗 query 嵌入且无命中，故直接跳过（D11 / AC7）；其检索由独立
                # 关键词服务承担，不在 Agent RAG 链路内。
                if resolve_index_mode(self._db, f"kb_{kid}") == "economy":
                    logger.info(f"[RAG] 知识库 {kid} 为 economy 模式，跳过向量 RAG 装配")
                    continue
                # Agent 运行期检索发生在请求之外，故 store 取长生命周期
                # （与 Agent 同存活），不走 async with 退出。
                store = PgVectorStore(
                    SessionLocal, tenant_id=tenant_id,
                    dimensions=self._kb_dimensions(f"kb_{kid}"),
                )
                await store.__aenter__()
                kbs.append(KnowledgeBase(
                    name=str(kid),
                    description=f"知识库 {kid}",
                    embedding_model=build_embedding_model(),
                    vector_store=store,
                    collection=f"kb_{kid}",
                    metadata_filter={"tenant_id": tenant_id},  # 深度防御
                ))
            return kbs

        try:
            kbs = asyncio.run(_build())
        except Exception as exc:  # noqa: BLE001 - RAG 装配失败不阻断 Agent 创建
            logger.warning(f"[RAG] 知识库装配失败，Agent 以无 RAG 模式创建: {exc}")
            return {}
        if not kbs:
            return {}

        mw = build_rag_middleware(kbs, config.get("rag", {}))
        try:
            rag_tools = asyncio.run(mw.list_tools()) or []
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[RAG] 检索工具收集失败: {exc}")
            rag_tools = []
        merged_toolkit = (Toolkit(tools=[*self._iter_toolkit_tools(toolkit), *rag_tools])
                          if rag_tools else toolkit)
        return {"toolkit": merged_toolkit, "middlewares": [mw]}

    def _kb_dimensions(self, collection_name: str) -> int:
        """取 collection 维度；缺失时回退嵌入模型维度（D19 由 create_collection 强校验）。"""
        from sqlalchemy import select

        from app.models.kb.kb_collection import KbCollection

        coll = self._db.execute(
            select(KbCollection).where(KbCollection.name == collection_name)
        ).scalar_one_or_none()
        if coll is not None:
            return coll.dimensions
        from app.config import settings

        return settings.GPUSTACK_EMBEDDING_DIMENSION

    def _create_general_agent(self, config: dict):
        """通用对话 Agent"""
        from agentscope.agent import Agent
        model, toolkit = self._build_model_and_toolkit(config)
        return Agent(
            name=config.get("name", "助手"),
            system_prompt=config.get("sys_prompt", "你是一个智能助手，可以回答各种问题。"),
            model=model,
            toolkit=toolkit,
            **self._rag_kwargs(config, toolkit),
        )

    def _create_thinking_agent(self, config: dict):
        """深度思考 Agent — 通过提示词引导逐步推理。

        下沉开关：``config["use_sop"]=True`` 时改为返回内置思考模板的
        ``SOPAgent``（spec §4.1 / §4.6）。默认仍走原生 Agent。

        注：旧版 ``thinking=True`` 参数在 2.x 已移除；若底层模型原生支持思考，
        可在模型配置的 ``parameters`` 中开启。
        """
        if config.get("use_sop"):
            return self._create_sop_agent({**config, "sop_source": "builtin:thinking"})

        from agentscope.agent import Agent
        model, toolkit = self._build_model_and_toolkit(config)
        return Agent(
            name=config.get("name", "深度思考"),
            system_prompt=config.get("sys_prompt", "你是一个深度思考助手，面对复杂问题时会逐步分解和推理。请先分析问题结构，然后一步步展开推理过程。"),
            model=model,
            toolkit=toolkit,
        )

    def _create_research_agent(self, config: dict):
        """深度研究 Agent — 使用 ResearchOrchestrator 多步研究流程。

        下沉开关：``config["use_sop"]=True`` 时改为返回内置研究模板的
        ``SOPAgent``（spec §4.6）。**默认保留 ResearchOrchestrator**——
        它会真实联网检索取证，而 SOP 默认执行器目前只调用 LLM，
        默认切换会丢失联网取证能力，故需显式开启。
        """
        if config.get("use_sop"):
            return self._create_sop_agent({**config, "sop_source": "builtin:research"})

        return ResearchAgent(
            db=self._db,
            model_id=config.get("model_id_db"),  # DB 模型 ID
            knowledge_bases=config.get("knowledge_bases"),
            name=config.get("name", "深度研究"),
        )

    def _create_sop_agent(self, config: dict):
        """SOP 流程 Agent — 按模板/动态定义驱动多里程碑流程（spec §4.1）。

        config 支持三种指定方式，按优先级：
        1. ``sop_definition``：SOPDefinition 字典（动态生成场景）
        2. ``sop_template_id``：代码注册表模板 id（如 ``builtin_thinking``）
        3. ``sop_source``：内置模式标识（``builtin:thinking`` / ``builtin:research``）

        三者都缺失时回退到内置思考模板，保证 session_type=sop 总有可用编排。
        """
        from app.ai.sop.agent import SOPAgent
        from app.ai.sop.schemas import SOPDefinition
        from app.ai.sop.templates import get_template, resolve_source

        raw = config.get("sop_definition")
        if raw:
            definition = SOPDefinition.model_validate(raw)
        else:
            template = None
            template_id = config.get("sop_template_id")
            if template_id:
                template = get_template(template_id)
            if template is None and config.get("sop_source"):
                template = resolve_source(config["sop_source"])
            if template is None:
                template = resolve_source("builtin:thinking")
            definition = template.definition

        return SOPAgent(
            db=self._db,
            definition=definition,
            model_id=config.get("model_id_db"),
            name=config.get("name") or definition.name,
            state_json=config.get("sop_state_json"),
        )

    def _create_skill_agent(self, config: dict):
        """技能模式 Agent — 使用 SkillExecutionService 执行技能"""
        return SkillAgent(
            db=self._db,
            model_id=config.get("model_id_db"),
            skill_config=config.get("skill"),
            name=config.get("name", "技能执行"),
        )

    # ── 配置白名单（agentscope 2.x 构造参数，spec B5）──────────────────
    _REACT_CONFIG_KEYS = (
        "max_iters", "structured_output_grace_iters", "stop_on_reject",
        "interruption_message", "interruption_raise_cancelled_error",
    )
    _CONTEXT_CONFIG_KEYS = (
        "trigger_ratio", "reserve_ratio", "context_buffer_ratio",
        "compression_prompt", "summary_template", "tool_result_limit",
        "compression_fallback_to_truncation", "compression_tool_enabled",
        "max_image_num",
    )

    def _agentscope_react_config(self, config: dict):
        """react_config → agentscope ReActConfig（白名单过滤，None 跳过）。"""
        raw = config.get("react_config") or {}
        kwargs = {k: raw[k] for k in self._REACT_CONFIG_KEYS
                  if raw.get(k) is not None}
        if not kwargs:
            return None
        from agentscope.agent import ReActConfig
        try:
            return ReActConfig(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ReActConfig 构造失败，忽略: {} ({})", kwargs, exc)
            return None

    def _agentscope_context_config(self, config: dict):
        """context_config → agentscope ContextConfig（白名单过滤）。"""
        raw = config.get("context_config") or {}
        kwargs = {k: raw[k] for k in self._CONTEXT_CONFIG_KEYS
                  if raw.get(k) is not None}
        if not kwargs:
            return None
        from agentscope.agent import ContextConfig
        try:
            return ContextConfig(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ContextConfig 构造失败，忽略: {} ({})", kwargs, exc)
            return None

    def _agentscope_model_config(self, config: dict):
        """model_config.max_retries → agentscope ModelConfig（其余键忽略）。"""
        raw = config.get("model_config") or {}
        max_retries = raw.get("max_retries")
        if max_retries is None:
            return None
        from agentscope.agent import ModelConfig
        try:
            return ModelConfig(max_retries=int(max_retries))
        except Exception as exc:  # noqa: BLE001
            logger.warning("ModelConfig 构造失败，忽略: {}", exc)
            return None

    @staticmethod
    def _iter_toolkit_tools(toolkit) -> list:
        """枚举 Toolkit 全部工具实例（tool_groups[].tools）。"""
        tools = []
        for group in getattr(toolkit, "tool_groups", None) or []:
            tools.extend(getattr(group, "tools", None) or [])
        return tools

    def _apply_ask_permissions(toolkit, tool_names) -> None:
        """对命中名单的工具强制 ASK 权限（→ RequireUserConfirmEvent）。

        引擎（permission/_engine.py Step 4）调用 tool.check_permissions；
        实例属性覆盖为恒 ASK 决策即可拦截。命中失败仅告警不阻断。
        """
        wanted = {str(n) for n in (tool_names or [])}
        if not wanted:
            return
        from agentscope.permission import PermissionBehavior, PermissionDecision

        hit = 0
        for tool in AgentFactory._iter_toolkit_tools(toolkit):
            name = getattr(tool, "name", None)
            if name not in wanted:
                continue

            async def _ask(tool_input, context, _name=name):  # noqa: ANN001
                return PermissionDecision(
                    behavior=PermissionBehavior.ASK,
                    message=f"工具 {_name} 已配置人工确认（HITL）",
                )
            tool.check_permissions = _ask
            hit += 1
        if hit < len(wanted):
            logger.warning("HITL 工具名单未全部命中 Toolkit：{}/{}", hit, len(wanted))

    @staticmethod
    def _restore_tool_permission(tool) -> None:
        """清除实例级 check_permissions 覆盖（计划审批通过后恢复 TaskUpdate）。"""
        try:
            del tool.check_permissions
        except AttributeError:
            pass

    def _create_expert_agent(self, config: dict):
        """专家 Agent — 从 agent_config 表读取专家人设与完整配置。

        装配：模型（model_id/model_config.model_code）+ Toolkit（tools/MCP）
        + RAG 知识库 + ReActConfig/ContextConfig/ModelConfig（白名单）
        + HITL（confirm_tools ASK 权限、AskUser 对话式追问）。
        """
        from agentscope.agent import Agent
        from agentscope.tool import Toolkit

        model, toolkit = self._build_model_and_toolkit(config)
        # model_config.model_code 优先（与 superagent 分支一致），失败回退上面的模型
        if config.get("model_config") and config["model_config"].get("model_code"):
            from app.ai.strategy.registry_bridge import build_model_from_db
            coded = build_model_from_db(self._db, str(config["model_config"]["model_code"]))
            if coded is not None:
                model = coded

        hitl_cfg = config.get("hitl_config") or {}
        if hitl_cfg.get("enabled") and hitl_cfg.get("confirm_tools"):
            self._apply_ask_permissions(toolkit, hitl_cfg["confirm_tools"])
        if hitl_cfg.get("enabled") and hitl_cfg.get("allow_ask_user"):
            from agentscope.tool import AskUser
            existing = self._iter_toolkit_tools(toolkit)
            toolkit = Toolkit(tools=[*existing, AskUser()])

        agent = Agent(
            name=config.get("name", "专家"),
            system_prompt=config.get("sys_prompt", "你是一位专业领域助手，在特定领域具有深入的专业知识和经验。"),
            model=model,
            toolkit=toolkit,
            **({"model_config": mc} if (mc := self._agentscope_model_config(config)) else {}),
            **({"context_config": cc} if (cc := self._agentscope_context_config(config)) else {}),
            **({"react_config": rc} if (rc := self._agentscope_react_config(config)) else {}),
            **self._rag_kwargs(config, toolkit),
        )
        agent._hitl_config = hitl_cfg  # 事件层消费（chat 主循环识别 pause_type）
        return agent

    def _create_plan_agent(self, config: dict):
        """计划模式 Agent — AgentScope 原生计划工具链（TaskCreate/Get/List/Update）。

        Plan & Execute：先 TaskCreate 建清单（TaskUpdate 建依赖）→
        plan_approval 开启时首个 TaskUpdate 触发计划审批暂停 →
        批准后恢复工具权限并按清单执行（in_progress→completed）→ 汇报。
        """
        from agentscope.agent import Agent
        from agentscope.permission import PermissionBehavior, PermissionDecision
        from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate, Toolkit

        _, business_toolkit = self._build_model_and_toolkit(config)
        plan_tools = [TaskCreate(), TaskGet(), TaskList(), TaskUpdate()]
        biz_tools = self._iter_toolkit_tools(business_toolkit)
        toolkit = Toolkit(tools=[*plan_tools, *biz_tools])

        agent = Agent(
            name=config.get("name", "计划助手"),
            system_prompt=config.get("sys_prompt") or (
                "你是计划执行专家（Plan & Execute）。工作流程：\n"
                "1. 收到任务后，先用 TaskCreate 把工作拆解为有序任务（明确的 subject 与 description），"
                "再用 TaskUpdate 设置任务间依赖（blocked_by/blocks）；\n"
                "2. 清单建好后，按依赖顺序逐个执行：开始前将任务置为 in_progress，完成后置为 completed；\n"
                "3. 若你的 TaskUpdate 调用被用户拒绝，表示计划需要调整——根据反馈修改任务清单后重新开始；\n"
                "4. 执行中发现遗漏工作时随时 TaskCreate 补充；\n"
                "5. 全部任务完成后，向用户汇总执行结果。"
            ),
            model=self._create_superagent_model(config)
            if config.get("model_config") else self._build_model_and_toolkit(config)[0],
            toolkit=toolkit,
            **({"model_config": mc} if (mc := self._agentscope_model_config(config)) else {}),
            **({"context_config": cc} if (cc := self._agentscope_context_config(config)) else {}),
            **({"react_config": rc} if (rc := self._agentscope_react_config(config)) else {}),
            **self._rag_kwargs(config, toolkit),
        )

        # 计划审批：TaskUpdate 强制 ASK，首次调用即暂停审批；批准后由主循环恢复
        hitl_cfg = config.get("hitl_config") or {}
        agent._hitl_config = hitl_cfg
        if hitl_cfg.get("plan_approval"):
            for tool in self._iter_toolkit_tools(toolkit):
                if getattr(tool, "name", "") == "TaskUpdate":
                    original = tool.check_permissions

                    async def _plan_ask(tool_input, context):  # noqa: ANN001
                        return PermissionDecision(
                            behavior=PermissionBehavior.ASK,
                            message="计划审批：请确认任务清单后再开始执行",
                        )
                    tool.check_permissions = _plan_ask
                    agent._plan_approval_restore = (tool, original)
                    break
        return agent

    def _create_react_agent(self, config: dict):
        """ReAct 计划执行 Agent — 使用 ReActOrchestrator 编排 Plan-Execute-Reflect 循环"""
        return ReactAgent(
            db=self._db,
            model_id=config.get("model_id_db"),
            tools=config.get("tools", []),
            react_config=config.get("react_config", {}),
            sys_prompt=config.get("sys_prompt", ""),
            name=config.get("name", "ReAct 助手"),
            skills=config.get("skills", []),
        )

    def _create_team_agent(self, config: dict):
        """团队协调者 Agent — 使用 TeamManager 编排多 Agent 协作"""
        return TeamAgent(
            db=self._db,
            team_id=config.get("team_id"),
            model_id=config.get("model_id_db"),
            name=config.get("name", "团队协调者"),
        )

    def _create_superagent_model(self, config: dict):
        """SUPERAGENT 模型构建 — model_config（to_agent_kwargs 形状）。

        llm_config 支持 {model_code}（ai_chat_model.code 引用）或
        {provider, model, base_url, api_key} 内联形状；前者经
        registry_bridge 按 DB 行构建，失败回退 ENV 兜底模型。
        """
        from app.ai.strategy.factory_ext import build_default_model_config, build_model

        model_cfg = dict(config.get("model_config") or {})
        model_code = model_cfg.pop("model_code", None)
        if model_code and not model_cfg.get("provider"):
            from app.ai.strategy.registry_bridge import build_model_from_db

            model = build_model_from_db(self._db, str(model_code))
            if model is not None:
                return model
            logger.warning(f"SUPERAGENT 模型编码 {model_code} 不可用，回退 ENV 兜底")
        return build_model(model_cfg or build_default_model_config())

    def _superagent_toolkit_to_agentscope(self, sa_toolkit) -> list:
        """superagent Toolkit 工具桥接为 agentscope FunctionTool 列表。

        MCP 工具经 toolkit.call('server:tool', args) 转发；本地工具（Knowledge/
        Sandbox/登记 custom/skill）经 LocalTool.call 转发。登记工具统一 ALLOW
        （登记即授权；superagent 自身 HITL 在 ticket/policy 层控制）。
        """
        from agentscope.permission import PermissionBehavior, PermissionDecision
        from agentscope.tool import FunctionTool

        allow = PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="登记工具自动授权（SUPERAGENT）",
        )

        def _bridge(func, name, description, input_schema):
            schema = input_schema or {}
            if not isinstance(schema, dict):
                schema = {}
            # agentscope Toolkit 校验要求 object schema 含 properties
            if schema.get("type") == "object" and "properties" not in schema:
                schema = {**schema, "properties": {}}
            return FunctionTool(
                func=func, name=name, description=description,
                input_schema=schema or {"type": "object", "properties": {}},
                permission=allow,
            )

        tools = []
        for ref, t in sa_toolkit.tools.items():
            def _make_mcp_func(_ref=ref, _tk=sa_toolkit):
                def _mcp_func(**kwargs):
                    return _tk.call(_ref, kwargs)
                return _mcp_func
            tools.append(_bridge(_make_mcp_func(), ref, t.description, t.input_schema))
        for lt in sa_toolkit.extra_tools.values():
            def _make_local_func(_lt=lt):
                def _local_func(**kwargs):
                    return _lt.call(kwargs)
                return _local_func
            tools.append(_bridge(_make_local_func(), lt.name, lt.description, lt.input_schema))
        return tools

    def _create_superagent_agent(self, config: dict):
        """SUPERAGENT — 按 agent_config.to_agent_kwargs() 委托 superagent 装配。

        能力唯一来源为登记列（mcp_servers/tools/skills/knowledge_bases）：
        build_agent_toolkit_sync 装配 superagent Toolkit 后桥接为 agentscope
        Toolkit，返回物与其它分支一致（agentscope Agent，reply 可真实调用
        登记的 MCP 工具）。
        """
        from agentscope.agent import Agent, ReActConfig
        from agentscope.tool import Toolkit as AgentScopeToolkit

        from app.ai.superagent.tools.toolkit import build_agent_toolkit_sync

        model = self._create_superagent_model(config)
        sa_toolkit = build_agent_toolkit_sync(
            config, db=self._db,
            workspace_id=config.get("workspace_id") or 0,
        )
        as_tools = self._superagent_toolkit_to_agentscope(sa_toolkit)

        construct_kwargs = {}
        react_cfg = config.get("react_config") or {}
        if react_cfg.get("max_iters"):
            construct_kwargs["react_config"] = ReActConfig(
                max_iters=int(react_cfg["max_iters"]))

        return Agent(
            name=config.get("name") or config.get("agent_code") or "SUPERAGENT",
            system_prompt=config.get("system_prompt")
            or "你是 SuperAgent，按登记的工具与知识能力完成领域任务。",
            model=model,
            toolkit=AgentScopeToolkit(tools=as_tools),
            **construct_kwargs,
        )
