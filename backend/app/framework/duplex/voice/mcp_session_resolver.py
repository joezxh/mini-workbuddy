"""会话级 MCP 动态注入（差距分析 §3.3/§2.2.3）。"""
from typing import List, Optional


class McpSessionResolver:
    """按 Agent 绑定的工具/MCP 服务拉取工具并装配到会话 Toolkit。

    复用 app/ai/mcp 既有 MCPAdapter（不新建），此处仅做会话级装配：
    - `tool_bindings`（工具名列表）非空时，按名单过滤 adapter 工具集；
    - `mcp_bindings`（MCP 服务列表）当前仅作预留透传（adapter 尚无
      按服务组织的工具源），后续接入外部 MCP 服务时在此扩展。
    """

    def __init__(self, mcp_service_ids: Optional[List[str]] = None,
                 tool_bindings: Optional[List[str]] = None):
        self._ids = mcp_service_ids or []
        self._tool_bindings = tool_bindings or []

    async def resolve_tools(self) -> List[dict]:
        """返回 {name, description, inputSchema} 列表；无配置时返回空（零改动可用知识工具）。"""
        if not self._ids and not self._tool_bindings:
            return []
        try:
            from app.ai.mcp.tool_adapter import MCPAdapter
            adapter = MCPAdapter()
            schemas = adapter.get_tool_schemas()
        except Exception:
            # 降级：注入失败不阻塞语音链路
            return []
        if self._tool_bindings:
            allowed = set(self._tool_bindings)
            schemas = [s for s in schemas if s.get("name") in allowed]
        return schemas

    def build_toolkit_spec(self) -> dict:
        return {"mcp_tool_ids": self._ids, "tool_bindings": self._tool_bindings}
