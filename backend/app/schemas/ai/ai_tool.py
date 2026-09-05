"""Tool / ToolGroup 管理 Schemas（字段命名对齐前端测试场景，使用 camelCase）。

字段清单（来自 docs/ai-scene.md 测试场景 1-11）：
toolKey / displayName / category / type / className / methodName /
description / configSchema / configValue / inputSchema / outputSchema /
status / isSystem / sort
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

TOOL_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
VALID_TYPES = {"custom", "skill", "mcp", "group", "sqlbot", "agentscope_builtin", "custom_dev"}
VALID_STATUS = {"enabled", "disabled"}


class AiToolCreate(BaseModel):
    """创建工具"""
    toolKey: str = Field(..., min_length=1, max_length=100, description="工具标识")
    displayName: str = Field(..., min_length=1, max_length=200, description="显示名称")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    type: str = Field("custom", description="工具类型 custom/skill/mcp/group")
    className: Optional[str] = Field(None, max_length=500, description="实现类全限定名")
    methodName: Optional[str] = Field(None, max_length=200, description="方法名")
    description: Optional[str] = Field(None, max_length=2000)
    configSchema: Optional[Dict[str, Any]] = Field(default=None, description="配置 Schema")
    configValue: Optional[Dict[str, Any]] = Field(default=None, description="配置值")
    inputSchema: Optional[Dict[str, Any]] = Field(default=None, description="输入参数 JSON Schema")
    outputSchema: Optional[Dict[str, Any]] = Field(default=None, description="输出参数 JSON Schema")
    status: str = Field("enabled", description="状态 enabled/disabled")
    isSystem: bool = Field(False, description="是否系统内置")
    sort: int = Field(0, description="排序")

    @field_validator("toolKey")
    @classmethod
    def _check_tool_key(cls, v: str) -> str:
        if not TOOL_KEY_RE.match(v):
            raise ValueError("toolKey 只能包含字母、数字、下划线，且以字母开头")
        return v

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"type 必须是 {sorted(VALID_TYPES)} 之一")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in VALID_STATUS:
            raise ValueError(f"status 必须是 {sorted(VALID_STATUS)} 之一")
        return v


class AiToolUpdate(BaseModel):
    """更新工具（全字段可选，id 必填）"""
    id: int = Field(..., description="主键 ID")
    toolKey: Optional[str] = Field(None, min_length=1, max_length=100)
    displayName: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None)
    className: Optional[str] = Field(None, max_length=500)
    methodName: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    configSchema: Optional[Dict[str, Any]] = None
    configValue: Optional[Dict[str, Any]] = None
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    isSystem: Optional[bool] = None
    sort: Optional[int] = None

    @field_validator("toolKey")
    @classmethod
    def _check_tool_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not TOOL_KEY_RE.match(v):
            raise ValueError("toolKey 只能包含字母、数字、下划线，且以字母开头")
        return v

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_TYPES:
            raise ValueError(f"type 必须是 {sorted(VALID_TYPES)} 之一")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUS:
            raise ValueError(f"status 必须是 {sorted(VALID_STATUS)} 之一")
        return v


class AiToolResp(BaseModel):
    """工具响应"""
    id: int
    toolKey: str
    displayName: str
    category: Optional[str] = None
    type: str
    className: Optional[str] = None
    methodName: Optional[str] = None
    description: Optional[str] = None
    configSchema: Optional[Dict[str, Any]] = None
    configValue: Optional[Dict[str, Any]] = None
    inputSchema: Optional[Dict[str, Any]] = None
    outputSchema: Optional[Dict[str, Any]] = None
    status: str
    isSystem: bool
    sort: int
    creator: Optional[str] = None
    updater: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class AiToolSimpleResp(BaseModel):
    """工具简易响应（下拉选择用）"""
    id: int
    toolKey: str
    displayName: str
    category: Optional[str] = None


# ============= ToolGroup =============

class AiToolGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    displayName: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    instructions: Optional[str] = Field(None, max_length=4000)
    isActive: bool = Field(False)
    sort: int = Field(0)


class AiToolGroupUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    displayName: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    instructions: Optional[str] = Field(None, max_length=4000)
    isActive: Optional[bool] = None
    sort: Optional[int] = None


class AiToolGroupResp(BaseModel):
    id: int
    name: str
    displayName: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    isActive: bool
    sort: int
    toolCount: int = 0
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class AiToolGroupMemberAdd(BaseModel):
    toolKeys: List[str] = Field(..., min_length=1, description="要加入分组的 toolKey 列表")


class AiToolTestRequest(BaseModel):
    """工具测试请求"""
    toolKey: Optional[str] = Field(None, description="按 toolKey 测试（优先）")
    id: Optional[int] = Field(None, description="按 id 测试")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="测试输入参数")
    className: Optional[str] = None
    methodName: Optional[str] = None
