"""app.ai.mcp 模块 - MCP (Model Context Protocol) adapter + server"""
from app.ai.mcp.tool_adapter import MCPAdapter, MCPTool, MCPToolResult
from app.ai.mcp.server import get_mcp_server

__all__ = [
    "MCPAdapter", "MCPTool", "MCPToolResult",
    "get_mcp_server",
]
