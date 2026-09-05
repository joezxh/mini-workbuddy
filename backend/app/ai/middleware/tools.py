"""Graphiti 图查询工具 - 暴露给 Agent 的图数据库查询能力

包含：
- SearchGraphTool: 语义搜索图知识
- GetRelationsTool: 获取实体间关系
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional, TYPE_CHECKING

from agentscope.tool._base import ToolBase
from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior

if TYPE_CHECKING:
    from app.ai.middleware.graphiti_memory import GraphitiMiddleware

logger = logging.getLogger(__name__)


class SearchGraphTool(ToolBase):
    """语义搜索 Graphiti 图知识库

    Agent 可调用此工具主动搜索历史知识、实体关系等。
    """
    is_concurrency_safe: bool = True
    is_read_only: bool = True

    def __init__(self, middleware: "GraphitiMiddleware"):
        super().__init__()
        self._middleware = middleware

    @property
    def name(self) -> str:
        return "search_graph"

    @property
    def description(self) -> str:
        return "搜索图知识库中的历史知识和实体关系。输入查询关键词，返回相关的历史事实和关系。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询关键词",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量（默认5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext
    ) -> PermissionDecision:
        """图搜索工具始终允许"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Graph search is always allowed",
        )

    async def call(self, query: str, top_k: int = 5, **kwargs: Any) -> Any:
        """执行图搜索"""
        graphiti = self._middleware._get_graphiti()
        if graphiti is None:
            return {"error": "图数据库不可用", "results": []}

        try:
            results = await graphiti.search(
                query,
                num_results=top_k,
                group_ids=[self._middleware.group_id],
            )
            formatted = []
            for r in results:
                if hasattr(r, "fact"):
                    formatted.append({"fact": r.fact})
                elif hasattr(r, "content"):
                    formatted.append({"content": r.content})
                else:
                    formatted.append({"raw": str(r)})
            return {"results": formatted, "count": len(formatted)}
        except Exception as e:
            logger.warning("SearchGraphTool failed: %s", e)
            return {"error": str(e), "results": []}


class GetRelationsTool(ToolBase):
    """获取 Graphiti 图中实体间的关系

    Agent 可调用此工具查询特定实体的关联关系。
    """
    is_concurrency_safe: bool = True
    is_read_only: bool = True

    def __init__(self, middleware: "GraphitiMiddleware"):
        super().__init__()
        self._middleware = middleware

    @property
    def name(self) -> str:
        return "get_relations"

    @property
    def description(self) -> str:
        return "获取图知识库中实体的关联关系。输入实体名称，返回该实体的相关关系列表。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "要查询关系的实体名称",
                },
            },
            "required": ["entity_name"],
        }

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext
    ) -> PermissionDecision:
        """关系查询工具始终允许"""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Graph relations query is always allowed",
        )

    async def call(self, entity_name: str, **kwargs: Any) -> Any:
        """获取实体关系"""
        graphiti = self._middleware._get_graphiti()
        if graphiti is None:
            return {"error": "图数据库不可用", "relations": []}

        try:
            # 使用 search 查找实体相关的 episodes
            results = await graphiti.search(
                entity_name,
                num_results=10,
                group_ids=[self._middleware.group_id],
            )
            relations = []
            for r in results:
                if hasattr(r, "fact"):
                    relations.append({"fact": r.fact})
                elif hasattr(r, "content"):
                    relations.append({"content": r.content})
            return {"entity": entity_name, "relations": relations, "count": len(relations)}
        except Exception as e:
            logger.warning("GetRelationsTool failed: %s", e)
            return {"error": str(e), "relations": []}
