"""app.ai.mcp 模块 - MCP (Model Context Protocol) adapter + server"""
from app.ai.mcp.tool_adapter import MCPAdapter, MCPTool, MCPToolResult
from app.ai.mcp.server import (
    build_mcp_asgi_app,
    get_mcp_server,
    start_mcp_endpoint,
    stop_mcp_endpoint,
)

__all__ = [
    "MCPAdapter", "MCPTool", "MCPToolResult",
    "get_mcp_server", "build_mcp_asgi_app", "start_mcp_endpoint", "stop_mcp_endpoint",
]
