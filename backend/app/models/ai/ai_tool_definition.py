"""Tool 定义 ORM 模型 - 持久化注册的 Tool（工具管理功能）。

字段设计对齐 docs/ai-scene.md 测试场景：
- toolKey / displayName / category / type / className / methodName
- configSchema / configValue / inputSchema / outputSchema
- status (enabled/disabled) / isSystem (系统保护) / sort
"""
from sqlalchemy import (
    Column, BigInteger, String, Boolean, TIMESTAMP, JSON, Index,
)
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiToolDefinition(Base, TenantMixin):
    """Tool 定义表 - 存储 custom / skill / mcp / group 类 Tool 元数据。"""
    __tablename__ = "ai_tool_definition"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    tool_key = Column(String(100), nullable=False, unique=True, comment="工具标识 toolKey（唯一）")
    display_name = Column(String(200), nullable=False, comment="显示名称 displayName")
    category = Column(String(100), nullable=True, comment="分类 category（如：信息查询/数据处理/AI增强）")
    tool_type = Column(
        String(20), nullable=False, server_default="custom",
        comment="工具类型：custom/skill/mcp/group",
    )
    class_name = Column(String(500), nullable=True, comment="实现类全限定名 className（Python module.Class）")
    method_name = Column(String(200), nullable=True, comment="方法名 methodName")
    description = Column(String(2000), nullable=True, comment="描述")
    config_schema = Column(JSON, nullable=True, comment="配置 Schema（JSON）")
    config_value = Column(JSON, nullable=True, comment="配置值（JSON）")
    input_schema = Column(JSON, nullable=True, comment="输入参数 JSON Schema（用于测试表单动态渲染）")
    output_schema = Column(JSON, nullable=True, comment="输出参数 JSON Schema")
    status = Column(
        String(20), nullable=False, server_default="enabled",
        comment="状态：enabled / disabled",
    )
    is_system = Column(
        Boolean, nullable=False, server_default="false",
        comment="是否系统内置工具（系统工具不允许删除）",
    )
    sort = Column(BigInteger, nullable=False, server_default="0", comment="排序")
    creator = Column(String(100), nullable=True, comment="创建人")
    updater = Column(String(100), nullable=True, comment="更新人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_tool_definition_tool_key", "tool_key", unique=True),
        Index("idx_tool_definition_category", "category"),
        Index("idx_tool_definition_type", "tool_type"),
        Index("idx_tool_definition_status", "status"),
        Index("idx_tool_definition_is_system", "is_system"),
    )

    def __repr__(self) -> str:
        return f"<AiToolDefinition {self.tool_key} type={self.tool_type}>"
