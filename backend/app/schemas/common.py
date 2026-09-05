"""
通用响应模型
"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List, Any
from datetime import datetime

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")


class PageParams(BaseModel):
    """分页请求参数"""
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")


class PageData(BaseModel, Generic[T]):
    """分页响应数据"""
    list: List[T] = Field([], description="数据列表")
    total: int = Field(0, description="总数")
    page: int = Field(1, description="当前页")
    pageSize: int = Field(10, description="每页数量")


class TimeRange(BaseModel):
    """时间范围"""
    startTime: Optional[str] = Field(None, description="开始时间")
    endTime: Optional[str] = Field(None, description="结束时间")


class IdRequest(BaseModel):
    """ID请求"""
    id: str = Field(..., description="ID")


class IdsRequest(BaseModel):
    """批量ID请求"""
    ids: List[str] = Field(..., description="ID列表")

