"""租户与租户套餐 Pydantic 请求/响应模型。"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- 租户套餐 ---
class SysTenantPackageCreate(BaseModel):
    name: str = Field(..., max_length=100, description="套餐名称")
    status: str = Field(default="active", description="状态")
    remark: Optional[str] = Field(None, max_length=500, description="备注")
    menu_ids: Optional[List[int]] = Field(default=None, description="关联菜单ID集合")


class SysTenantPackageUpdate(BaseModel):
    package_id: int
    name: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    remark: Optional[str] = Field(None, max_length=500)
    menu_ids: Optional[List[int]] = None


class SysTenantPackageResp(BaseModel):
    package_id: int
    name: str
    status: str
    remark: Optional[str] = None
    menu_ids: Optional[List[int]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SysTenantPackageSimple(BaseModel):
    package_id: int
    name: str

    class Config:
        from_attributes = True


# --- 租户 ---
class SysTenantCreate(BaseModel):
    name: str = Field(..., max_length=100, description="租户名称")
    package_id: Optional[int] = Field(None, description="租户套餐ID")
    contact_name: Optional[str] = Field(None, max_length=50)
    contact_mobile: Optional[str] = Field(None, max_length=20)
    status: str = Field(default="active")
    account_count: int = Field(default=0, ge=0)
    expire_time: Optional[datetime] = None
    websites: Optional[List[str]] = None
    # 创建时专属：管理员账号
    username: str = Field(..., max_length=50, description="管理员用户名")
    password: str = Field(..., min_length=6, description="管理员密码")


class SysTenantUpdate(BaseModel):
    tenant_id: int
    name: Optional[str] = Field(None, max_length=100)
    package_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    status: Optional[str] = None
    account_count: Optional[int] = None
    expire_time: Optional[datetime] = None
    websites: Optional[List[str]] = None


class SysTenantResp(BaseModel):
    tenant_id: int
    name: str
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    status: str
    package_id: Optional[int] = None
    expire_time: Optional[datetime] = None
    account_count: int = 0
    websites: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantSimple(BaseModel):
    tenant_id: int
    name: str

    class Config:
        from_attributes = True


class TenantPageQuery(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    status: Optional[str] = None
    page_no: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
