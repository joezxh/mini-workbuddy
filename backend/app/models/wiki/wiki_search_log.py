"""Wiki 检索审计日志（G1：混合检索使用记录）。

每次语义/关键词/混合检索或「问 AI」都会落一条记录，用于运营分析与降级监控。
继承 ``TenantMixin`` 以纳入行级多租户隔离。
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, TIMESTAMP, Index
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class WikiSearchLog(Base, TenantMixin):
    """Wiki 检索审计日志。"""

    __tablename__ = "kms_search_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(BigInteger, nullable=True, comment="检索用户 ID")
    knowledge_id = Column(
        BigInteger,
        nullable=True,
        index=True,
        comment="检索的知识库 ID (null=全库检索)",
    )
    query = Column(Text, nullable=False, comment="检索词")
    mode = Column(
        String(20),
        nullable=False,
        comment="检索模式：semantic | keyword | hybrid | llm_wiki",
    )
    result_count = Column(Integer, nullable=False, server_default="0", comment="命中数量")
    latency_ms = Column(Integer, nullable=True, comment="检索耗时(毫秒)")
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )

    __table_args__ = (
        Index("idx_kms_search_log_tenant", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WikiSearchLog mode={self.mode} q={self.query!r}>"
