"""外部知识库检索代理端点（spec §10.2，type=3 / kb_format='proxy'）。

不拉数据、无文档管理；仅检索时转发外部 API。``auth_key`` 存 Fernet 密文
（沿用 DataOps crypto 惯例）。
"""
from sqlalchemy import (
    BigInteger, Column, ForeignKey, String, Text, TIMESTAMP, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class ExternalKbEndpoint(Base, TenantMixin):
    __tablename__ = "kms_external_kb_endpoint"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    knowledge_id = Column(BigInteger, ForeignKey("kms_knowledge.id", ondelete="SET NULL"),
                          nullable=True, index=True, comment="所属统一容器（type=3/proxy）")
    name = Column(String(200), nullable=False, comment="显示名")
    endpoint_url = Column(String(500), nullable=False, comment="外部检索 API 地址（https）")
    auth_key = Column(String(500), nullable=True, comment="鉴权密钥（Fernet 密文）")
    index_name = Column(String(128), nullable=True, comment="外部索引/集合名")
    metadata_mapping = Column(String(500), nullable=True, comment="元数据映射说明/JSON 字符串")
    status = Column(String(32), nullable=False, server_default="active",
                    comment="active|error|disabled")
    error_detail = Column(Text, nullable=True, comment="最近错误")
    creator_id = Column(BigInteger, nullable=True, comment="创建人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(),
                        onupdate=func.now(), comment="更新时间")
