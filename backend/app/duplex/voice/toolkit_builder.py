"""RealtimeAgent Toolkit 构建（spec §2.4）。

MCPAdapter 工具 schema（{name, description, inputSchema}）→ AgentScope
ToolBase 包装，执行回调 call_fn（默认 MCPAdapter.call_tool）；权限确认由
RealtimeAgent 内建 PermissionEngine + RequireUserConfirmEvent 完成。

已核实事实（agentscope 2.0.8）：ToolResultState 从 agentscope.message 导入
（agentscope.tool 不导出），完成态成员为 SUCCESS。
"""
import json
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


def _dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(obj)


class McpToolWrapper:
    """MCP 工具的 AgentScope ToolBase 包装。"""

    name: str
    description: str
    input_schema: dict
    is_concurrency_safe: bool = False
    is_read_only: bool = False
    is_mcp: bool = True
    mcp_name: str = "mwb-voice-mcp"

    def __init__(self, schema: Dict[str, Any],
                 call_fn: Optional[Callable] = None) -> None:
        self.name = schema["name"]
        self.description = schema.get("description", "")
        self.input_schema = schema.get("inputSchema") or {"type": "object"}
        self._call_fn = call_fn

    def _resolve_call_fn(self) -> Callable:
        if self._call_fn is not None:
            return self._call_fn
        from app.ai.mcp.tool_adapter import get_mcp_adapter
        adapter = get_mcp_adapter()

        async def call(name: str, args: dict):
            return await adapter.call_tool(name, args)
        return call

    async def call(self, **kwargs):
        from agentscope.message import TextBlock, ToolResultState
        from agentscope.tool import ToolChunk
        try:
            result = await self._resolve_call_fn()(self.name, kwargs)
            text = result if isinstance(result, str) else _dumps(result)
            return ToolChunk(content=[TextBlock(type="text", text=text)],
                             state=ToolResultState.SUCCESS)
        except Exception as e:  # noqa: BLE001 - 工具失败不中断语音流
            logger.warning(f"语音工具 {self.name} 执行失败: {e}")
            return ToolChunk(
                content=[TextBlock(type="text", text=f"工具执行失败: {e}")],
                state=ToolResultState.ERROR)


def build_toolkit(tool_schemas: List[Dict[str, Any]],
                  call_fn: Optional[Callable] = None):
    """构建 RealtimeAgent 所需 Toolkit；空 schema 返回空 Toolkit。"""
    from agentscope.tool import Toolkit
    return Toolkit(tools=[McpToolWrapper(s, call_fn) for s in tool_schemas])
