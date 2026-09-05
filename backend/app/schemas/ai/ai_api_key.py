"""AI API Key and ChatModel schemas."""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field


class AiChatModelBase(BaseModel):
    """聊天模型基础字段"""
    code: Optional[str] = None
    key_id: int
    name: str
    model: str
    platform: Optional[str] = None
    sort: int = 0
    status: int = 1
    type: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    seed: Optional[int] = None
    max_contexts: Optional[int] = None
    max_turns: Optional[int] = None
    dimensions: Optional[int] = None
    retry: Optional[int] = None
    timeout: Optional[int] = None
    stream_timeout: Optional[int] = None
    enable_thinking: bool = False
    enable_search: bool = False
    is_default: bool = False


class AiChatModelCreate(AiChatModelBase):
    """创建聊天模型"""
    pass


class AiChatModelUpdate(BaseModel):
    """更新聊天模型"""
    id: int = Field(..., description="ID")
    code: Optional[str] = None
    name: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = None
    type: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    seed: Optional[int] = None
    max_contexts: Optional[int] = None
    max_turns: Optional[int] = None
    dimensions: Optional[int] = None
    retry: Optional[int] = None
    timeout: Optional[int] = None
    stream_timeout: Optional[int] = None
    enable_thinking: Optional[bool] = None
    enable_search: Optional[bool] = None
    is_default: Optional[bool] = None


class AiChatModelResp(AiChatModelBase):
    """聊天模型响应"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============= API Key Schemas =============

class AiApiKeyBase(BaseModel):
    """API Key 基础字段"""
    name: str
    api_key: str
    platform: str
    url: Optional[str] = ""
    app_id: Optional[str] = ""
    property: Optional[dict] = {}
    status: int = 1
    sort: int = 0


class AiApiKeyCreate(AiApiKeyBase):
    """创建 API Key"""
    pass


class AiApiKeyUpdate(BaseModel):
    """更新 API Key"""
    id: int = Field(..., description="ID")
    name: Optional[str] = None
    api_key: Optional[str] = None
    platform: Optional[str] = None
    url: Optional[str] = None
    app_id: Optional[str] = None
    property: Optional[dict] = None
    status: Optional[int] = None
    sort: Optional[int] = None


class AiApiKeyResp(AiApiKeyBase):
    """API Key 响应"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creator: Optional[str] = None
    updater: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AiApiKeySimpleResp(BaseModel):
    """API Key 简易响应（用于下拉选择）"""
    id: int
    name: str
    platform: str

    model_config = ConfigDict(from_attributes=True)


class AiApiKeyPageResp(BaseModel):
    """API Key 分页响应"""
    id: int
    name: str
    api_key: str
    platform: str
    url: Optional[str] = ""
    app_id: Optional[str] = ""
    status: int
    sort: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creator: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
