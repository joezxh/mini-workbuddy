"""MCP 广场模板数据模型 - 预配置 MCP 服务模板。"""
from sqlalchemy import Column, BigInteger, String, Integer, Text, TIMESTAMP, JSON, Index
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiMcpSquareTemplate(Base, TenantMixin):
    """MCP 广场模板表 - 预配置的法律服务 MCP 模板。"""
    __tablename__ = 'ai_mcp_square_template'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(100), nullable=False, comment='模板名称')
    icon = Column(String(200), nullable=True, comment='图标标识')
    category = Column(String(50), nullable=True, comment='分类')
    platform = Column(String(50), nullable=True, comment='平台类型')
    description = Column(String(2000), nullable=True, comment='描述')
    service_type = Column(String(20), nullable=False, comment='服务类型')
    service_url = Column(String(500), nullable=True, comment='服务地址模板')
    access_path = Column(String(500), nullable=True, comment='访问路径')
    version = Column(String(20), nullable=True, comment='协议版本')
    capabilities = Column(JSON, nullable=True, comment='能力列表')
    default_client_config = Column(JSON, nullable=True, comment='默认客户端配置模板')
    sort = Column(Integer, nullable=False, server_default='0', comment='排序')
    status = Column(Integer, nullable=False, server_default='1', comment='1=启用,0=禁用')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_mcp_template_status', 'status'),
        Index('idx_mcp_template_category', 'category'),
    )

    def __repr__(self) -> str:
        return f"<AiMcpSquareTemplate {self.name}>"
