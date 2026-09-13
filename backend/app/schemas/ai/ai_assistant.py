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


class ExampleQuestionRecommendRequest(BaseModel):
    """示例提问推荐请求（根据会话关键词在服务端进行匹配检索）"""
    keywords: List[str] = Field(default_factory=list, description="来源于当前会话的关键词")
    session_type: Optional[str] = Field(None, description="会话类型，用于按场景过滤/加权")
    limit: int = Field(3, ge=1, le=10, description="返回的最大条数")


class ExampleQuestionRecommendResponse(BaseModel):
    """示例提问推荐响应"""
    questions: List[str] = Field(default_factory=list, description="匹配检索得到的示例提问")
    matched: bool = Field(False, description="是否命中关键词匹配（未命中则回退默认题库）")
    source_keywords: List[str] = Field(default_factory=list, description="实际用于匹配的关键词")

