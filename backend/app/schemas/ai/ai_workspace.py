"""Workspace Schemas - 工作空间管理。"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class AiWorkspaceCreate(BaseModel):
    """创建工作空间"""
    name: str = Field(..., max_length=200, description="工作空间名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    scope: str = Field("private", pattern="^(public|private)$", description="public/private")
    execution_mode: str = Field("remote", pattern="^(remote|local)$", description="remote/local")
    workspace_type: str = Field("local", pattern="^(local|docker|opensandbox)$", description="local/docker/opensandbox")
    config: Optional[dict] = Field(default_factory=dict, description="后端特定配置")
    mcp_ids: Optional[List[int]] = Field(default_factory=list, description="引用的MCP服务ID列表")
    skill_ids: Optional[List[int]] = Field(default_factory=list, description="引用的技能ID列表")


class AiWorkspaceUpdate(BaseModel):
    """更新工作空间"""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    scope: Optional[str] = Field(None, pattern="^(public|private)$")
    execution_mode: Optional[str] = Field(None, pattern="^(remote|local)$")
    workspace_type: Optional[str] = Field(None, pattern="^(local|docker|opensandbox)$")
    config: Optional[dict] = None
    mcp_ids: Optional[List[int]] = None
    skill_ids: Optional[List[int]] = None
    status: Optional[str] = Field(None, pattern="^(active|disabled)$")


class AiWorkspaceResp(BaseModel):
    """工作空间响应"""
    id: int
    workspace_id: str
    name: str
    description: Optional[str] = None
    scope: str
    execution_mode: str
    workspace_type: str
    user_id: Optional[int] = None
    config: dict
    mcp_ids: Optional[List[int]] = None
    skill_ids: Optional[List[int]] = None
    is_default: bool
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AiWorkspaceSimpleResp(BaseModel):
    """工作空间简易响应（用于下拉选择）"""
    id: int
    workspace_id: str
    name: str
    scope: str
    workspace_type: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class AiWorkspaceLinkMcpReq(BaseModel):
    """关联 MCP 服务请求"""
    mcp_id: int = Field(..., description="MCP 服务 ID")


class AiWorkspaceLinkSkillReq(BaseModel):
    """关联技能请求"""
    skill_id: int = Field(..., description="技能 ID")
