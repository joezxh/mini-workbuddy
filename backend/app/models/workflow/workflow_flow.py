"""工作流定义表 — 多平台统一接入"""
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import TIMESTAMP

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WorkflowFlow(Base, TenantMixin):
    """多平台工作流定义表"""
    __tablename__ = "workflow_flow"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    flow_code = Column(String(100), nullable=False, comment="业务唯一标识码")
    flow_name = Column(String(200), nullable=False, comment="工作流名称")
    platform_type = Column(String(50), nullable=False, server_default="dify",
                           comment="平台类型: dify / coze / custom_http")
    flow_type = Column(String(50), nullable=False,
                       comment="流程类型: Workflow / Chatflow / Chatbot / Agent / Completion")
    base_url = Column(String(500), nullable=False, comment="平台 API 基地址")
    api_key_enc = Column(Text, nullable=False, comment="加密后的 API Key")
    input_schema = Column(JSONB, nullable=False, server_default="{}", comment="入参 JSON Schema")
    output_schema = Column(JSONB, nullable=True, comment="出参 JSON Schema")
    config = Column(JSONB, nullable=True, comment="平台扩展配置")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    sort_order = Column(Integer, nullable=False, server_default="0")
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        Index("uq_workflow_flow_code_tenant", "flow_code", "tenant_id", unique=True),
        Index("idx_workflow_flow_platform", "platform_type"),
    )

    def __repr__(self):
        return f"<WorkflowFlow {self.flow_code}:{self.flow_name}>"
