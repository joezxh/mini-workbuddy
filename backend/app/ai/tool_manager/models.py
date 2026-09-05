"""Tool / ToolGroup Pydantic 数据模型 - SDK 无关的业务结构。"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolType(str, Enum):
    """Tool 来源类型。"""
    MCP = "mcp"
    SKILL = "skill"
    CUSTOM = "custom"
    GROUP = "group"


class SourceRef(BaseModel):
    """Tool 来源引用 - 三选一 / 多选。"""
    mcp_server: Optional[str] = None
    skill_path: Optional[str] = None
    class_path: Optional[str] = None


class ToolDefinition(BaseModel):
    """Tool 业务定义 (DB / API 用)。"""
    tool_name: str = Field(..., min_length=1, max_length=100)
    tool_type: ToolType
    source_ref: SourceRef = Field(default_factory=SourceRef)
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    group_name: Optional[str] = None
    is_concurrency_safe: bool = True
    is_read_only: bool = False
    is_external_tool: bool = False
    is_active: bool = True
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class ToolGroupConfig(BaseModel):
    """Tool 分组配置 (DB / API 用)。"""
    name: str
    description: str = ""
    instructions: str = ""
    tool_names: List[str] = Field(default_factory=list)
    is_active: bool = False