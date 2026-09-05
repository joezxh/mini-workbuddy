"""MCP 客户端配置数据模型 - 关联 MCP API Key 的子表。"""
from sqlalchemy import Column, BigInteger, String, Integer, Text, Boolean, TIMESTAMP, JSON, Index, ForeignKey
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiMcpClient(Base, TenantMixin):
    """MCP 客户端配置表 - 关联 API Key 的客户端子表。"""
    __tablename__ = 'ai_mcp_client'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(100), nullable=False, comment='客户端名称')
    api_key_id = Column(BigInteger, ForeignKey('ai_mcp_api_key.id', ondelete='CASCADE'), nullable=False, comment='关联API Key')
    client_type = Column(String(20), nullable=False, comment='客户端类型: stdio/http/sse')
    mcp_type = Column(String(20), nullable=False, comment='应用类别: tool/resource')
    version = Column(String(20), nullable=True, comment='客户端版本')
    description = Column(String(2000), nullable=True, comment='描述')
    tools_config = Column(JSON, nullable=True, comment='工具配置')
    remark = Column(Text, nullable=True, comment='备注')
    status = Column(Integer, nullable=False, server_default='1', comment='1=启用,0=禁用')
    is_active = Column(Boolean, nullable=False, server_default='true', comment='是否启用')
    creator = Column(String(100), nullable=True, comment='创建人')
    updater = Column(String(100), nullable=True, comment='更新人')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_mcp_client_apikey', 'api_key_id'),
        Index('idx_mcp_client_active', 'is_active'),
    )

    def __repr__(self) -> str:
        return f"<AiMcpClient {self.name} {self.client_type}>"
