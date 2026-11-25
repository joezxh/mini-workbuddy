"""本体领域字典（分组维度）。

``onto_domain`` 用于把元数据表（meta_table）与本体（onto_ontology）按业务领域归类，
例如 HR人力资源、供应链管理。领域是可选标注：删除领域时通过外键 ON DELETE SET NULL
仅解除分组，不影响已关联的表与本体。

与本体治理其他模型一致：继承 TenantMixin（租户行级隔离），状态用 String + CHECK，
审计列 creator_id/updater_id/created_at/updated_at。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, Index, Integer, String, Text,
    TIMESTAMP, UniqueConstraint, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class OntoDomain(Base, TenantMixin):
    """本体领域。"""

    __tablename__ = "onto_domain"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(64), nullable=False, comment="领域编码（租户内唯一，如 hr / supply_chain）")
    name = Column(String(200), nullable=False, comment="领域名称（如 HR人力资源 / 供应链管理）")
    description = Column(Text, nullable=True, comment="说明")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="排序权重")
    status = Column(
        String(16), nullable=False, server_default="active",
        comment="状态: active|disabled",
    )

    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_onto_domain_code"),
        CheckConstraint("status IN ('active','disabled')", name="ck_onto_domain_status"),
        Index("idx_onto_domain_tenant_status", "tenant_id", "status"),
    )
