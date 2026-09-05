from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, ForeignKey, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SysUser(Base, TenantMixin):
    """用户表"""
    __tablename__ = "sys_user"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    avatar_url = Column(String(500))
    status = Column(String(20), default='active', nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime)
    last_login_ip = Column(String(50))
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # 关系 - 使用字符串引用避免循环导入
    user_roles = relationship("SysUserRole", back_populates="user", lazy="select")

    def __repr__(self):
        return f"<SysUser {self.username}>"


class SysRole(Base, TenantMixin):
    """角色表"""
    __tablename__ = "sys_role"

    role_id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_name = Column(String(100), nullable=False)
    role_code = Column(String(50), unique=True, nullable=False)
    region_code = Column(String(20))
    region_level = Column(String(20))
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    status = Column(String(20), default='active', nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # 关系
    user_roles = relationship("SysUserRole", back_populates="role", lazy="select")
    role_menus = relationship("SysRoleMenu", back_populates="role", lazy="select", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SysRole {self.role_name}>"


class SysUserRole(Base, TenantMixin):
    """用户角色关联表"""
    __tablename__ = "sys_user_role"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('sys_user.user_id'), nullable=False)
    role_id = Column(BigInteger, ForeignKey('sys_role.role_id'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # 关系
    user = relationship("SysUser", back_populates="user_roles")
    role = relationship("SysRole", back_populates="user_roles")

    def __repr__(self):
        return f"<SysUserRole user_id={self.user_id} role_id={self.role_id}>"


class SysRegion(Base):
    """地区字典表"""
    __tablename__ = "sys_region"

    region_id = Column(BigInteger, primary_key=True, autoincrement=True)
    region_code = Column(String(20), unique=True, nullable=False)
    region_name = Column(String(100), nullable=False)
    parent_code = Column(String(20))
    region_level = Column(String(20), nullable=False)
    full_path = Column(String(500))
    sort_order = Column(Integer, default=0)
    longitude = Column(String(20))
    latitude = Column(String(20))
    status = Column(String(20), default='active', nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SysRegion {self.region_name}>"


class SysMenu(Base):
    """菜单权限表（统一存储菜单和按钮权限）"""
    __tablename__ = "sys_menu"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    permission = Column(String(100), index=True)  # 权限标识，用于鉴权（如 admin:users:delete）
    path = Column(String(255))  # 路由地址（如 /system/users）
    type = Column(Integer, default=2)  # 1=目录, 2=菜单, 3=按钮
    sort = Column(Integer, default=0)  # 显示顺序
    parent_id = Column(BigInteger, index=True)  # 父菜单ID，0或NULL表示顶级
    icon = Column(String(100))  # 菜单图标
    component = Column(String(255))  # 前端组件路径
    component_name = Column(String(100))  # 组件名
    status = Column(Integer, default=0)  # 状态: 0=开启 1=关闭
    visible = Column(Integer, default=1)  # 是否可见: 1=显示 0=隐藏
    keep_alive = Column(Integer, default=0)  # 是否缓存: 1=缓存 0=不缓存
    always_show = Column(Integer, default=0)  # 是否总是显示: 1=总是 0=不是
    i18n_key = Column(String(100))  # 多语言翻译 key（如 sys.menu.users）
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    role_menus = relationship("SysRoleMenu", back_populates="menu", lazy="select", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SysMenu {self.name}>"


# 向后兼容别名
Permission = SysMenu


class SysRoleMenu(Base):
    """角色菜单关联表"""
    __tablename__ = "sys_role_menu"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_id = Column(BigInteger, ForeignKey('sys_role.role_id'), nullable=False)
    menu_id = Column(BigInteger, ForeignKey('sys_menu.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # 关系
    role = relationship("SysRole", back_populates="role_menus")
    menu = relationship("SysMenu", back_populates="role_menus")

    def __repr__(self):
        return f"<SysRoleMenu role_id={self.role_id} menu_id={self.menu_id}>"


# 向后兼容别名
RolePermission = SysRoleMenu


class SysAuditLog(Base, TenantMixin):
    """系统审计日志表"""
    __tablename__ = "sys_audit_log"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String(50))
    operation_type = Column(String(50), nullable=False)
    operation_module = Column(String(50))
    operation_desc = Column(Text)
    request_method = Column(String(10))
    request_url = Column(String(500))
    request_params = Column(JSONB)
    request_ip = Column(String(50), index=True)
    user_agent = Column(String(500))
    response_status = Column(Integer)
    response_time_ms = Column(Integer)
    old_data = Column(JSONB)
    new_data = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index('idx_audit_operation', 'operation_type', 'operation_module'),
    )

    def __repr__(self):
        return f"<SysAuditLog {self.log_id} {self.operation_type}>"

