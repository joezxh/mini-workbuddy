"""权限申请单（spec §3.7）。形态取自 meta_data_write_request 的申请/审批/过期三段。

与写请求单的差异：批准产物是写入 twin_card_share，**不发一次性令牌**。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, String,
    Text, TIMESTAMP, func, text,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class TwinAccessRequest(Base, TenantMixin):
    __tablename__ = "twin_access_request"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    card_id = Column(BigInteger, ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False, comment="目标卡片")
    applicant_id = Column(BigInteger, nullable=False, comment="申请人")
    reason = Column(Text, nullable=True, comment="申请理由")
    required_role_code = Column(String(64), nullable=True, comment="卡片声明的所需角色（原型「安防管理员」）")
    status = Column(String(16), nullable=False, server_default="pending", comment="pending|approved|rejected|expired")
    approver_id = Column(BigInteger, nullable=True, comment="审批人")
    reviewed_at = Column(TIMESTAMP, nullable=True, comment="审批时刻")
    expires_at = Column(TIMESTAMP, nullable=True, comment="审批通过后的授予有效期")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_twin_access_status"),
        # 每人每卡只允许**一张在途**申请：用部分唯一索引（WHERE status='pending'）。
        # 若把 status 也放进整列唯一约束，同一人对同一卡的「历史 rejected + 新的 pending」
        # 或「续期后的第二条 approved」都会撞键，Task 9 的续期路径直接报 IntegrityError。
        Index("uq_twin_access_pending", "tenant_id", "card_id", "applicant_id",
              unique=True, postgresql_where=text("status = 'pending'")),
        Index("idx_twin_access_card", "card_id", "status"),
    )
