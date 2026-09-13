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
from typing import Any

from agentscope.tool import ToolChunk
from agentscope.message import TextBlock

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