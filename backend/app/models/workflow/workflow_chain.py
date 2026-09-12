"""工作流链式编排定义"""
from sqlalchemy import Column, BigInteger, String, Boolean, Text, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WorkflowChain(Base, TenantMixin):
    """工作流链式编排定义"""
    __tablename__ = "workflow_chain"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chain_code = Column(String(100), nullable=False, comment="链唯一标识码")
    chain_name = Column(String(200), nullable=False)
    steps = Column(JSONB, nullable=False, server_default="[]",
                   comment="步骤列表 JSON")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("uq_workflow_chain_code_tenant", "chain_code", "tenant_id", unique=True),
    )

    def __repr__(self):
        return f"<WorkflowChain {self.chain_code}:{self.chain_name}>"
