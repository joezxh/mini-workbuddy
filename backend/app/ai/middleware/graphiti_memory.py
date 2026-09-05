"""GraphitiMiddleware - Graphiti 图数据长期记忆中间件

唯一长期记忆方案，废弃旧的 ShortTermMemory + LongTermMemoryService 双轨制。

工作机制：
- on_reply 前：search + retrieve_episodes → 注入相关知识到 agent context
- on_reply 后：add_episode → 自动积累对话知识到图数据库
- list_tools()：暴露 search_graph / get_relations 工具给 Agent
- 降级逻辑：Neo4j 不可用时 skip，不阻塞 reply

依赖：
- graphiti-core >= 0.5
- Neo4j 5.x (bolt://)
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Callable, List, Optional

from agentscope.middleware import MiddlewareBase
from agentscope.message import Msg, TextBlock

logger = logging.getLogger(__name__)


class GraphitiMiddleware(MiddlewareBase):
    """Graphiti 图数据长期记忆 — 唯一长期记忆方案

    Usage:
        middleware = GraphitiMiddleware(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="neo4j",
            group_id="miniworkbuddy",
        )
        agent = Agent(..., middlewares=[middleware])
    """

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "neo4j",
        group_id: str = "miniworkbuddy",
        auto_extract: bool = True,
        top_k: int = 5,
        enabled: bool = True,
    ):
        super().__init__()
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.group_id = group_id
        self.auto_extract = auto_extract
        self.top_k = top_k
        self.enabled = enabled
        self._graphiti = None
        self._initialized = False

    def _get_graphiti(self):
        """延迟初始化 Graphiti 客户端（避免启动时阻塞）"""
        if self._graphiti is None:
            try:
                from graphiti_core import Graphiti
                self._graphiti = Graphiti(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                )
                self._initialized = True
                logger.info("GraphitiMiddleware connected to Neo4j: %s", self.neo4j_uri)
            except Exception as e:
                logger.warning("GraphitiMiddleware init failed (will degrade): %s", e)
                self._initialized = False
        return self._graphiti

    async def on_reply(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        """reply 前：检索相关图知识注入上下文；reply 后：自动积累"""
        if not self.enabled:
            async for item in next_handler(**input_kwargs):
                yield item
            return

        graphiti = self._get_graphiti()
        if graphiti is None:
            # 降级：Neo4j 不可用，直接 passthrough
            async for item in next_handler(**input_kwargs):
                yield item
            return

        # ── reply 前：检索相关知识 ──
        query = self._extract_query(input_kwargs)
        if query:
            try:
                knowledge_text = await self._search_knowledge(graphiti, query)
                if knowledge_text:
                    self._inject_knowledge(agent, knowledge_text)
            except Exception as e:
                logger.warning("GraphitiMiddleware search failed (degrade): %s", e)

        # ── 执行 reply ──
        async for item in next_handler(**input_kwargs):
            yield item

        # ── reply 后：自动积累 ──
        if self.auto_extract and query:
            try:
                await self._record_episode(graphiti, agent, query)
            except Exception as e:
                logger.warning("GraphitiMiddleware record failed (non-fatal): %s", e)

    async def list_tools(self) -> list:
        """暴露给 Agent 的图查询工具"""
        if not self.enabled:
            return []
        from app.ai.middleware.tools import SearchGraphTool, GetRelationsTool
        return [
            SearchGraphTool(middleware=self),
            GetRelationsTool(middleware=self),
        ]

    def get_middleware_key(self) -> str:
        return "graphiti_memory"

    # ── 内部方法 ─────────────────────────────────────────────────────────────

    def _extract_query(self, input_kwargs: dict) -> str:
        """从 input_kwargs 中提取用户查询文本"""
        # Agent.reply() 的 input_kwargs 通常包含 msgs 或 x
        msgs = input_kwargs.get("msgs") or input_kwargs.get("x")
        if msgs is None:
            return ""
        if isinstance(msgs, list) and msgs:
            last_msg = msgs[-1]
            if isinstance(last_msg, Msg):
                return self._msg_to_text(last_msg)
            return str(last_msg)
        if isinstance(msgs, Msg):
            return self._msg_to_text(msgs)
        return str(msgs) if msgs else ""

    @staticmethod
    def _msg_to_text(msg: Msg) -> str:
        """将 Msg.content (List[TextBlock]) 转为纯文本"""
        if isinstance(msg.content, str):
            return msg.content
        if isinstance(msg.content, list):
            parts = []
            for block in msg.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, str):
                    parts.append(block)
            return " ".join(parts)
        return str(msg.content) if msg.content else ""

    async def _search_knowledge(self, graphiti, query: str) -> str:
        """从 Graphiti 检索相关知识"""
        results = await graphiti.search(
            query,
            num_results=self.top_k,
            group_ids=[self.group_id],
        )
        if not results:
            return ""
        # 将检索结果格式化为文本
        parts = []
        for r in results[:self.top_k]:
            if hasattr(r, "fact"):
                parts.append(f"- {r.fact}")
            elif hasattr(r, "content"):
                parts.append(f"- {r.content}")
            else:
                parts.append(f"- {str(r)}")
        return "\n".join(parts)

    def _inject_knowledge(self, agent: Any, knowledge_text: str) -> None:
        """将检索到的知识注入 Agent 的 middle_context"""
        if hasattr(agent, "state") and agent.state is not None:
            agent.state.middle_context["graphiti_knowledge"] = knowledge_text
            logger.debug(
                "GraphitiMiddleware injected %d chars knowledge",
                len(knowledge_text),
            )

    async def _record_episode(self, graphiti, agent: Any, query: str) -> None:
        """将对话记录为 Graphiti Episode"""
        # 获取 agent 最近的回复
        reply_text = ""
        if hasattr(agent, "state") and agent.state is not None:
            context = agent.state.context
            if context:
                last_msg = context[-1]
                reply_text = self._msg_to_text(last_msg) if isinstance(last_msg, Msg) else str(last_msg)

        episode_content = f"用户: {query}\n助手: {reply_text}" if reply_text else f"用户: {query}"
        agent_name = getattr(agent, "name", "unknown")

        await graphiti.add_episode(
            name=f"{agent_name}_interaction",
            episode_body=episode_content,
            source="message",
            group_id=self.group_id,
        )
        logger.debug("GraphitiMiddleware recorded episode for agent=%s", agent_name)

    async def close(self) -> None:
        """关闭 Graphiti 连接"""
        if self._graphiti is not None:
            try:
                await self._graphiti.close()
            except Exception:
                pass
            self._graphiti = None
