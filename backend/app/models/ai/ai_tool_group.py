"""Tool 分组 ORM 模型 - 用于 ToolGroup 持久化与工具分组成员关系。"""
from sqlalchemy import Column, BigInteger, String, Boolean, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiToolGroup(Base, TenantMixin):
    """Tool 分组表 - 一组 Tool 的集合，可整体启用/停用。"""
    __tablename__ = "ai_tool_group"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(100), nullable=False, unique=True, comment="分组名")
    display_name = Column(String(200), nullable=True, comment="分组显示名称")
    description = Column(String(2000), nullable=True, comment="描述")
    instructions = Column(String(4000), nullable=True, comment="给 Agent 的使用说明")
    is_active = Column(Boolean, nullable=False, server_default="false", comment="是否启用")
    sort = Column(BigInteger, nullable=False, server_default="0", comment="排序")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_tool_group_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<AiToolGroup {self.name} active={self.is_active}>"


class AiToolGroupMember(Base, TenantMixin):
    """Tool 分组成员表 - 关联分组与 Tool（多对多）。"""
    __tablename__ = "ai_tool_group_member"

    group_id = Column(
        BigInteger, ForeignKey("ai_tool_group.id", ondelete="CASCADE"),
        primary_key=True, comment="分组 ID",
    )
    tool_key = Column(
        String(100), ForeignKey("ai_tool_definition.tool_key", ondelete="CASCADE"),
        primary_key=True, comment="工具标识 toolKey",
    )
    sort_order = Column(BigInteger, nullable=True, server_default="0", comment="组内排序")

    __table_args__ = (
        Index("idx_tool_group_member_tool", "tool_key"),
    )

    def __repr__(self) -> str:
        return f"<AiToolGroupMember group={self.group_id} tool={self.tool_key}>"
