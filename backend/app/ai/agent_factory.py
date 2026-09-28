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
            case "react":
                return self._create_react_agent(config)
            case "team":
                return self._create_team_agent(config)
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
            for kid in kb_ids:
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
        merged_toolkit = Toolkit(tools=[*toolkit.tools, *rag_tools]) if rag_tools else toolkit
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

        注：旧版 ``thinking=True`` 参数在 2.x 已移除；若底层模型原生支持思考，
        可在模型配置的 ``parameters`` 中开启。
        """
        from agentscope.agent import Agent
        model, toolkit = self._build_model_and_toolkit(config)
        return Agent(
            name=config.get("name", "深度思考"),
            system_prompt=config.get("sys_prompt", "你是一个深度思考助手，面对复杂问题时会逐步分解和推理。请先分析问题结构，然后一步步展开推理过程。"),
            model=model,
            toolkit=toolkit,
        )

    def _create_research_agent(self, config: dict):
        """深度研究 Agent — 使用 ResearchOrchestrator 多步研究流程"""
        return ResearchAgent(
            db=self._db,
            model_id=config.get("model_id_db"),  # DB 模型 ID
            knowledge_bases=config.get("knowledge_bases"),
            name=config.get("name", "深度研究"),
        )

    def _create_skill_agent(self, config: dict):
        """技能模式 Agent — 使用 SkillExecutionService 执行技能"""
        return SkillAgent(
            db=self._db,
            model_id=config.get("model_id_db"),
            skill_config=config.get("skill"),
            name=config.get("name", "技能执行"),
        )

    def _create_expert_agent(self, config: dict):
        """专家 Agent — 从 agent_config 表读取专家人设"""
        from agentscope.agent import Agent
        model, toolkit = self._build_model_and_toolkit(config)
        return Agent(
            name=config.get("name", "专家"),
            system_prompt=config.get("sys_prompt", "你是一位专业领域助手，在特定领域具有深入的专业知识和经验。"),
            model=model,
            toolkit=toolkit,
            **self._rag_kwargs(config, toolkit),
        )

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
