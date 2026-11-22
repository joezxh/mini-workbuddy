"""RealtimeAgent Toolkit 构建（spec §2.4）。

MCPAdapter 工具 schema（{name, description, inputSchema}）→ AgentScope
ToolBase 包装，执行回调 call_fn（默认 MCPAdapter.call_tool）；权限确认由
RealtimeAgent 内建 PermissionEngine + RequireUserConfirmEvent 完成。

已核实事实（agentscope 2.0.8）：
- ToolResultState 从 agentscope.message 导入，完成态成员 SUCCESS；
- RegisteredTool.__post_init__ 强制 input_schema 含 type=object 且
  properties 为 dict（_normalize_schema 保证）；
- Toolkit.call_tool 经 ToolBase.__call__ → call() 执行；权限引擎需要
  基类的 check_permissions/check_read_only（继承即获得默认实现）。
"""
import json
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from agentscope.tool import ToolBase


def _dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(obj)


def _normalize_schema(raw: Any) -> dict:
    """保证 input_schema 满足 RegisteredTool 契约（type=object + properties dict）。"""
    if isinstance(raw, dict) and raw.get("type") == "object" and isinstance(
        raw.get("properties"), dict
    ):
        return raw
    return {"type": "object", "properties": {}}


class McpToolWrapper(ToolBase):
    """MCP 工具的 AgentScope ToolBase 包装（继承以获得权限/调用契约）。"""

    def __init__(self, schema: Dict[str, Any],
                 call_fn: Optional[Callable] = None) -> None:
        super().__init__()
        self.name = schema["name"]
        self.description = schema.get("description", "")
        self.input_schema = _normalize_schema(schema.get("inputSchema"))
        self.is_concurrency_safe = False
        self.is_read_only = False
        self.is_mcp = True
        self.mcp_name = "mwb-voice-mcp"
        self._call_fn = call_fn

    async def check_permissions(self, tool_input: dict, context):
        """交由 PermissionEngine 规则匹配（tool_policy 映射）；
        未命中规则时由引擎发起 RequireUserConfirmEvent 走用户确认流。"""
        from agentscope.permission import PermissionBehavior, PermissionDecision
        return PermissionDecision(
            behavior=PermissionBehavior.PASSTHROUGH,
            message="语音 MCP 工具：交由权限引擎规则匹配",
        )

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
