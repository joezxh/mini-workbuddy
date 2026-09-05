"""Workspace 模型 - 工作空间管理。"""
from sqlalchemy import String, JSON, Integer, BigInteger, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiWorkspace(Base, TenantMixin):
    """工作空间表"""
    __tablename__ = "ai_workspace"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True, comment="业务唯一标识(UUID)")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="工作空间名称")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="描述")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="private", comment="public/private")
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="remote", comment="remote/local")
    workspace_type: Mapped[str] = mapped_column(String(30), nullable=False, default="local", comment="local/docker/opensandbox")
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.user_id"), nullable=True, comment="私有空间绑定用户")
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, comment="后端特定配置")
    mcp_ids: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True, comment="引用的MCP服务ID列表")
    skill_ids: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True, comment="引用的技能ID列表")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否为用户默认工作空间")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", comment="active/disabled")
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="创建者")
    created_at = mapped_column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = mapped_column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="软删除")

    def __repr__(self):
        return f"<AiWorkspace {self.workspace_id} {self.name}>"