"""SuperAgent Tools 包 — MCP 对接 + 本地工具封装（规格 2.4/2.5）。"""
from .mcp_config import (
    MCPServerConfig, PlaywrightMCPConfig, WindowsDesktopMCPConfig, KiraMCPConfig,
)
from .mcp_adapter import MCPClient, MCPTool
from .toolkit import (
    Toolkit, MCPToolkitFactory, LocalTool,
    build_agent_toolkit, build_agent_toolkit_sync,
)
from .knowledge import KnowledgeTools
from .ontology import OntologyTools
from .sandbox import SandboxTools

__all__ = [
    "MCPServerConfig", "PlaywrightMCPConfig", "WindowsDesktopMCPConfig", "KiraMCPConfig",
    "MCPClient", "MCPTool",
    "Toolkit", "MCPToolkitFactory", "LocalTool",
    "build_agent_toolkit", "build_agent_toolkit_sync",
    "KnowledgeTools", "OntologyTools", "SandboxTools",
]
