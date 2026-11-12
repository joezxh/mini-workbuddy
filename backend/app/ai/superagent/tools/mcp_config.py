"""MCP Server 配置 —— Pydantic models。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """MCP Server 基础配置。"""
    service_type: Literal["playwright", "windows-mcp", "kira-mcp", "stdio-custom"]
    cmd: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout: int = 30


class PlaywrightMCPConfig(MCPServerConfig):
    """Playwright MCP Server —— 浏览器自动化。"""
    service_type: Literal["playwright"] = "playwright"
    max_browsers: int = 5


class WindowsDesktopMCPConfig(MCPServerConfig):
    """Windows Desktop MCP —— UI 自动化。"""
    service_type: Literal["windows-mcp"] = "windows-mcp"
    default_tool_type: str = "uia"


class KiraMCPConfig(MCPServerConfig):
    """Kira MCP —— YOLO + OCR 视觉识别。"""
    service_type: Literal["kira-mcp"] = "kira-mcp"
    default_tool_type: str = "yolo+ocr"
