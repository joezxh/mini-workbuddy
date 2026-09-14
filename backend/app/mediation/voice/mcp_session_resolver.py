"""会话级 MCP 动态注入（差距分析 §3.3/§2.2.3）。"""
from typing import List


class McpSessionResolver:
    """按 Agent 绑定的 MCP 服务 ID 拉取工具并注册到会话 Toolkit。

    复用 app/ai/mcp 既有 MCPAdapter（不新建），此处仅做会话级装配。
    """

    def __init__(self, mcp_service_ids: List[str] | None = None):
        self._ids = mcp_service_ids or []

    async def resolve_tools(self) -> List[dict]:
        """返回 {name, description, inputSchema} 列表；无配置时返回空（零改动可用知识工具）。"""
        if not self._ids:
            return []
        try:
            from app.ai.mcp.tool_adapter import MCPAdapter
            adapter = MCPAdapter()
            return adapter.get_tool_schemas()
        except Exception:
            # 降级：注入失败不阻塞语音链路
            return []

    def build_toolkit_spec(self) -> dict:
        return {"mcp_tool_ids": self._ids}
