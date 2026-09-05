"""租户与租户套餐数据模型。

SysTenant: 租户表 — 每个租户是一个独立的组织/客户。
SysTenantPackage: 租户套餐表 — 定义租户可用的菜单权限集合。
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.database import Base


class SysTenantPackage(Base):
    """租户套餐表"""
    __tablename__ = "sys_tenant_package"

    package_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="套餐名称")
    status = Column(String(20), nullable=False, default="active", comment="状态(active/disabled)")
    remark = Column(String(500), comment="备注")
    menu_ids = Column(JSON, nullable=True, comment="关联菜单ID集合")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SysTenantPackage {self.name}>"


class SysTenant(Base):
    """租户表"""
    __tablename__ = "sys_tenant"

    tenant_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="租户名称")
    contact_name = Column(String(50), comment="联系人")
    contact_mobile = Column(String(20), comment="联系电话")
    status = Column(String(20), nullable=False, default="active", comment="状态(active/disabled)")
    package_id = Column(BigInteger, ForeignKey("sys_tenant_package.package_id"),
                        nullable=True, comment="租户套餐ID")
    expire_time = Column(DateTime, nullable=True, comment="过期时间")
    account_count = Column(Integer, default=0, comment="账号额度")
    websites = Column(JSON, nullable=True, comment="绑定域名列表")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SysTenant {self.name}>"
