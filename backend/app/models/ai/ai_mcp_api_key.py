"""MCP API Key 数据模型 - MCP 服务发布凭证管理。"""
from sqlalchemy import Column, BigInteger, String, Integer, Text, TIMESTAMP, JSON, Index
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiMcpApiKey(Base, TenantMixin):
    """MCP API Key 表 - 记录 MCP 服务发布凭证配置。"""
    __tablename__ = 'ai_mcp_api_key'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(100), nullable=False, comment='密钥名称')
    service_type = Column(String(20), nullable=False, comment='服务类型: nacos2/nacos3/http/sse')
    platform = Column(String(50), nullable=True, comment='平台: local/remote')
    protocol_type = Column(String(50), nullable=True, comment='协议类型(自动推导)')
    version = Column(String(20), nullable=True, comment='MCP协议版本')
    description = Column(String(2000), nullable=True, comment='描述信息')
    service_url = Column(String(500), nullable=True, comment='服务地址')
    service_name = Column(String(200), nullable=True, comment='Nacos服务名')
    api_key = Column(String(500), nullable=True, comment='鉴权密钥')
    namespace = Column(String(200), nullable=True, comment='Nacos命名空间')
    group_key = Column(String(200), nullable=True, comment='Nacos分组')
    access_path = Column(String(500), nullable=True, comment='HTTP/SSE访问路径')
    properties = Column(JSON, nullable=True, comment='扩展属性')
    capabilities = Column(JSON, nullable=True, comment='能力列表')
    remark = Column(Text, nullable=True, comment='备注')
    status = Column(Integer, nullable=False, server_default='1', comment='1=启用,0=禁用')
    sort = Column(Integer, nullable=False, server_default='0', comment='排序')
    template_id = Column(BigInteger, nullable=False, server_default='0', comment='广场模板ID')
    health_status = Column(String(20), nullable=False, server_default='unknown', comment='健康状态: healthy/unhealthy/unknown')
    last_check_at = Column(TIMESTAMP, nullable=True, comment='最近一次连接检测时间')
    creator = Column(String(100), nullable=True, comment='创建人')
    updater = Column(String(100), nullable=True, comment='更新人')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_mcp_apikey_status', 'status'),
        Index('idx_mcp_apikey_template', 'template_id'),
    )

    def __repr__(self) -> str:
        return f"<AiMcpApiKey {self.name} {self.service_type}>"
