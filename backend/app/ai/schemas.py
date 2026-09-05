"""agentscope/schemas.py - Pydantic 模型"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    agent_id: str = Field(..., description="Agent ID")
    event_id: Optional[int] = Field(None, description="关联事件 ID")
    simulation_id: Optional[int] = Field(None, description="关联仿真 ID")
    session_title: Optional[str] = Field(None, description="会话标题")


class AiSendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容")


class ExecuteRequest(BaseModel):
    """直接执行请求"""
    agent_id: str = Field(..., description="Agent ID")
    prompt: str = Field(..., description="执行提示")
    event_id: Optional[int] = Field(None, description="关联事件 ID")
    tools: Optional[List[str]] = Field(None, description="指定使用的工具")
    skills: Optional[List[str]] = Field(None, description="指定使用的 Skill")


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: int
    agent_id: str
    agent_name: str
    agent_type: str
    context_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    """消息响应"""
    session_id: int
    message_id: int
    content: str
    tools_used: List[str] = Field(default_factory=list)
    skills_used: List[str] = Field(default_factory=list)
    execution_time_ms: int


class ExecuteResponse(BaseModel):
    """执行响应"""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    agent_id: str
    execution_time_ms: int
    skills_used: List[str] = Field(default_factory=list)


class AgentInfo(BaseModel):
    """Agent 信息"""
    agent_id: str
    name: str
    type: str
    session_type: str
    model: str
    tools: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)


class SessionListItem(BaseModel):
    """会话列表项"""
    session_id: int
    agent_id: str
    session_title: str
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
