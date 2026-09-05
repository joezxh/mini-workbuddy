"""
AI助理相关Schema
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from enum import Enum


class MessageRole(str, Enum):
    """消息角色"""
    user = "user"
    assistant = "assistant"


class AiChatMessageBase(BaseModel):
    """聊天消息基础模型"""
    role: MessageRole = Field(..., description="角色")
    content: str = Field(..., description="内容")


class AiChatMessageResponse(AiChatMessageBase):
    """聊天消息响应"""
    messageId: str
    timestamp: str

    model_config = ConfigDict(from_attributes=True)


class AiChatSessionBase(BaseModel):
    """会话基础模型"""
    title: Optional[str] = Field(None, description="会话标题")


class AiChatSessionCreate(AiChatSessionBase):
    """创建会话"""
    pass


class AiChatSessionResponse(AiChatSessionBase):
    """会话响应"""
    sessionId: str
    messages: List[AiChatMessageResponse] = []
    createTime: str
    updateTime: str

    model_config = ConfigDict(from_attributes=True)


class AiSendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容")


class TraceKeywordRequest(BaseModel):
    """关键词溯源请求"""
    keyword: str = Field(..., description="关键词")

