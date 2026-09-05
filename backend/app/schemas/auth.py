from pydantic import BaseModel, Field
from typing import Optional, List, Any


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    tenant_id: int = Field(default=0, description="租户ID")


class LoginResponse(BaseModel):
    """登录响应"""
    token: str = Field(..., description="JWT Token")
    userId: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    realName: str = Field(..., description="真实姓名")
    tenantId: int = Field(default=0, description="租户ID")


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    userId: int
    username: str
    realName: str
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    # 按当前用户权限下发的菜单树（嵌套结构，含 id/name/path/icon/i18nKey/children 等）
    menus: List[Any] = []
    regionCode: str = ""
    regionName: str = ""
    regionLevel: str = ""


class UpdateProfileRequest(BaseModel):
    """更新个人信息请求"""
    realName: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None


