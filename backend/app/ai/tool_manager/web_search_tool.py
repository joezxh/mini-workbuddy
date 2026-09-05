"""内置联网搜索工具 (Built-in Web Search Tool)。

把 ``app.ai.web_search.service.WebSearchToolService``（多供应商回退 + 调用日志）
封装为标准 AgentScope 2.0.4 ``ToolBase``，并作为系统内置工具注册进全局工具库
(``ToolManager``)，供 Skill 及任意业务模块统一调用。

设计要点:
- 单一事实来源：所有联网搜索能力集中在 WebSearchToolService，本 Tool 仅做协议适配。
- 与前端「AI 联网搜索管理」共用同一份 AiWebSearch 供应商配置，无需重复携带凭证。
- 只读且线程安全，权限默认 ALLOW（无副作用）。

SDK 2.0.4 ToolBase 协议:
- 类属性: name / description / input_schema / is_concurrency_safe / is_read_only
- 实例方法: async call(*args, **kwargs) -> ToolChunk
- 可选重写: async check_permissions(...) -> PermissionDecision
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)
from agentscope.tool import ToolBase, ToolChunk
from agentscope.message import TextBlock

logger = logging.getLogger(__name__)


# ── 工具元信息（全局工具库展示 / Skill allowed-tools 引用名） ──────────────────
WEB_SEARCH_TOOL_KEY = "web_search"
WEB_SEARCH_DISPLAY_NAME = "联网搜索"
WEB_SEARCH_CATEGORY = "信息查询"
WEB_SEARCH_TOOL_TYPE = "custom"
WEB_SEARCH_CLASS_PATH = "app.ai.tool_manager.web_search_tool.WebSearchTool"


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class WebSearchTool(ToolBase):
    """联网搜索内置工具 - 调用 AI 联网搜索管理后台配置的搜索引擎。

    统一入口对应管理后台「AI 联网搜索管理」页配置的供应商（博查 / 智谱 / 搜索
    引擎等），按优先级自动回退，并对每次调用落 ``WebSearchLog`` 日志。

    典型调用::

        tool = WebSearchTool()
        chunk = await tool.call(query="社会稳定风险评估 政策", top_k=5)
    """

    name: str = WEB_SEARCH_TOOL_KEY
    description: str = (
        "联网搜索工具：通过管理后台配置的搜索引擎（博查/智谱/搜索引擎等）"
        "查询实时互联网信息，返回标题、链接与摘要。用于获取最新资讯、政策、"
        "新闻与公开资料。只读、无副作用。"
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或自然语言查询",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量上限",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
            "prefer_platform": {
                "type": "string",
                "description": "优先使用的搜索供应商 platform（如 bocha/zhipu/google/bing）。"
                "不指定时按管理后台优先级自动选择",
                "default": None,
            },
        },
        "required": ["query"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = True

    def __init__(self, web_search_service: Any = None) -> None:
        super().__init__()
        # 未注入时惰性创建（无 DB 会话上下文场景，如部分测试 / 离线调用）
        from app.ai.web_search.service import WebSearchToolService

        self.web_search_service = web_search_service or WebSearchToolService()

    async def check_permissions(
        self,
        tool_input: dict,
        context: PermissionContext,
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Web search is read-only.",
        )

    async def call(
        self,
        query: str,
        top_k: int = 5,
        prefer_platform: Optional[str] = None,
    ) -> ToolChunk:
        """执行联网搜索并返回结构化结果。"""
        payload = await self.web_search_service.search(
            query=query,
            max_results=int(top_k),
            prefer_platform=prefer_platform,
        )
        results: List[Dict] = payload.get("results", [])
        total = payload.get("total", len(results))
        return _text_chunk(
            {
                "query": query,
                "results": results,
                "total": total,
                "provider": payload.get("provider"),
            }
        )


# 输出结构声明（供前端测试表单 / 文档展示）
WEB_SEARCH_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "原始查询词"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "snippet": {"type": "string"},
                    "score": {"type": "number"},
                },
            },
            "description": "搜索结果列表",
        },
        "total": {"type": "integer", "description": "结果总数"},
        "provider": {"type": "string", "description": "实际命中的供应商 platform"},
    },
}


def build_web_search_definition() -> "Any":
    """构造 web_search 的系统内置工具定义模型 (AiToolDefinition)。

    用于启动时写入 ``tool_definition`` 表 + 缓存，使其出现在「AI 工具管理」全局
    工具库中，且标记 ``is_system=True``（不允许删除），供 Skill 通过
    ``allowed-tools: [web_search]`` 引用。
    """
    from app.models.ai.ai_tool_definition import AiToolDefinition

    return AiToolDefinition(
        tool_key=WEB_SEARCH_TOOL_KEY,
        display_name=WEB_SEARCH_DISPLAY_NAME,
        category=WEB_SEARCH_CATEGORY,
        tool_type=WEB_SEARCH_TOOL_TYPE,
        class_name=WEB_SEARCH_CLASS_PATH,
        method_name="call",
        description=WebSearchTool.description,
        config_schema=None,
        config_value=None,
        input_schema=WebSearchTool.input_schema,
        output_schema=WEB_SEARCH_OUTPUT_SCHEMA,
        status="enabled",
        is_system=True,
        sort=1000,
    )


__all__ = [
    "WebSearchTool",
    "WEB_SEARCH_TOOL_KEY",
    "WEB_SEARCH_CLASS_PATH",
    "WEB_SEARCH_OUTPUT_SCHEMA",
    "build_web_search_definition",
]
