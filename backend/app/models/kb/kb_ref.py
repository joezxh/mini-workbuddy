"""MWB 侧 KB 映射（权限/列表，继承 TenantMixin）。"""
from sqlalchemy import (
    BigInteger, Column, Integer, String, Text, TIMESTAMP, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbRef(Base, TenantMixin):
    """MWB 侧知识库引用：把本租户的 KB 映射到 AgentScope 的 user_id 命名空间。

    ``as_user_id`` = ``UserIdMapper.to_as_user_id(tenant_id)`` 的结果，是 AgentScope
    RAG Service 侧的隔离键（详见 P1 Task 6）。
    """

    __tablename__ = "kb_ref"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    kb_id = Column(String(64), nullable=False, unique=True, comment="KB 标识")
    name = Column(String(200), nullable=False, comment="名称")
    description = Column(Text, nullable=True, comment="描述")
    as_user_id = Column(String(64), nullable=False, comment="AgentScope 侧 user_id")
    doc_count = Column(
        Integer, nullable=False, server_default="0", comment="文档数"
    )
    segment_count = Column(
        Integer, nullable=False, server_default="0", comment="切片数"
    )
    creator_id = Column(BigInteger, nullable=True, comment="创建人")
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(),
        onupdate=func.now(), comment="更新时间"
    )
