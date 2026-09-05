"""AI Web Search 供应商 Schema。"""
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class AiWebSearchBase(BaseModel):
    """搜索供应商基础字段"""
    name: str
    api_key: str
    platform: str
    url: Optional[str] = ""
    app_id: Optional[str] = ""
    property: Optional[dict] = {}
    # 扩展配置字段
    timeout: int = 30
    max_results: int = 10
    daily_quota: int = 0
    priority: int = 50
    status: int = 1
    sort: int = 0


class AiWebSearchCreate(AiWebSearchBase):
    """创建搜索供应商"""
    pass


class WebSearchUpdate(BaseModel):
    """更新搜索供应商"""
    id: int = Field(..., description="ID")
    name: Optional[str] = None
    api_key: Optional[str] = None
    platform: Optional[str] = None
    url: Optional[str] = None
    app_id: Optional[str] = None
    property: Optional[dict] = None
    timeout: Optional[int] = None
    max_results: Optional[int] = None
    daily_quota: Optional[int] = None
    priority: Optional[int] = None
    status: Optional[int] = None
    sort: Optional[int] = None


class WebSearchResp(AiWebSearchBase):
    """搜索供应商响应"""
    id: int
    used_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    creator: Optional[str] = None
    updater: Optional[str] = None

    model_config = {"from_attributes": True}


class WebSearchQuotaItem(BaseModel):
    """配额/用量统计项（含进度信息）"""
    id: int
    name: str
    platform: str
    daily_quota: int
    used_count: int
    remaining: int
    usage_percent: float

    model_config = {"from_attributes": True}


class WebSearchHealthItem(BaseModel):
    """健康检查项"""
    id: int
    name: str
    platform: str
    status: str  # normal / warning / error
    message: str = ""
    response_time: float = 0.0


class WebSearchLogResp(BaseModel):
    """搜索日志响应"""
    id: int
    web_search_id: int
    service_name: str
    platform: str
    query: str
    response_time: float
    results_count: int
    success: bool
    error: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebSearchSimpleResp(BaseModel):
    """简易响应（下拉选择）"""
    id: int
    name: str
    platform: str

    model_config = {"from_attributes": True}


class WebSearchTestRequest(BaseModel):
    """搜索测试请求"""
    id: int = Field(..., description="搜索供应商 ID")
    query: str = Field(..., min_length=1, description="搜索关键词")
