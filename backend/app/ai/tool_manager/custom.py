"""内置自定义 ToolBase 子类 - 基于 AgentScope 2.0.4 ToolBase 协议。

联网搜索工具的实现已统一收敛到 :mod:`app.ai.tool_manager.web_search_tool`
（``WebSearchTool``）。``WebSearch`` 保留为兼容别名，直接复用内置联网搜索工具
的能力，避免逻辑分叉。

每个子类必须满足 SDK 2.0.4 的 ToolBase 协议:
- 类属性: name / description / input_schema / is_concurrency_safe / is_read_only
- 实例方法: async call(*args, **kwargs) -> ToolChunk | AsyncGenerator[ToolChunk, None]
"""
from __future__ import annotations
import json
import logging
from typing import Any, AsyncGenerator

from agentscope.tool import ToolBase, ToolChunk
from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)

from app.ai.tool_manager.web_search_tool import WebSearchTool

logger = logging.getLogger(__name__)


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


# 历史兼容别名：早期代码通过 ``from app.ai.tool_manager.custom import WebSearch`` 引用。
# 现统一指向内置联网搜索工具，保证 name=web_search / 完整 input_schema 一致。
WebSearch = WebSearchTool


class CaseRetrieve(ToolBase):
    """类案检索 - 从法律案例库检索相似案例。"""
    name: str = "case_retrieve"
    description: str = "从法律类案库检索相似调解 / 诉讼案例"
    input_schema: dict = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词或案情描述"},
            "top_k": {"type": "integer", "description": "返回数量", "default": 5},
            "filter": {"type": "object", "description": "过滤条件 (年份/地域/案由)"},
        },
        "required": ["query"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = True

    def __init__(self, case_service: Any = None) -> None:
        super().__init__()
        self.case_service = case_service

    async def check_permissions(
        self,
        tool_input: dict,
        context: PermissionContext,
    ) -> PermissionDecision:
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Case retrieval is read-only.",
        )

    async def call(
        self,
        query: str,
        top_k: int = 5,
        filter: dict | None = None,
    ) -> ToolChunk:
        if self.case_service is None:
            cases = [
                {"case_id": f"CASE-{i}", "title": f"示例案例 {i}", "score": 0.9 - i * 0.05}
                for i in range(top_k)
            ]
        else:
            try:
                cases = await self.case_service.search(query=query, top_k=top_k, filter=filter or {})
            except Exception as exc:  # noqa: BLE001
                logger.warning("case_retrieve service failed: %s", exc)
                cases = []
        return _text_chunk({"query": query, "cases": cases})