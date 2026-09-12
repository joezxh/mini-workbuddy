"""推断的表/列间关系（P2 Task 13，三方投票产出）。

三方投票来自：`vote_key`（主键/外键命名法）、`vote_name`（同名属性法）、
`vote_overlap`（采样重叠率法）。综合置信度取各票最大值；低于
``CONF_SUGGEST_MIN`` 的关系不入库。评审状态沿用 suggested/accepted/rejected。
"""
from sqlalchemy import (
    BigInteger, Column, Float, ForeignKey, Index, String, TIMESTAMP, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaRelation(Base, TenantMixin):
    """推断的表间关系（列对级）。"""

    __tablename__ = "meta_relation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    source_id = Column(
        BigInteger, ForeignKey("meta_data_source.id", ondelete="CASCADE"), nullable=False, comment="数据源 ID"
    )
    database = Column(String(128), nullable=False, comment="库/schema")

    left_table = Column(String(256), nullable=False, comment="左表")
    left_column = Column(String(256), nullable=False, comment="左列")
    right_table = Column(String(256), nullable=False, comment="右表")
    right_column = Column(String(256), nullable=False, comment="右列")

    # 三路投票置信度（None 表示该路未参与）
    vote_key = Column(Float, nullable=True, comment="键/外键命名法投票")
    vote_name = Column(Float, nullable=True, comment="同名属性法投票")
    vote_overlap = Column(Float, nullable=True, comment="采样重叠率法投票")
    method_votes_json = Column(JSONB, nullable=True, comment="各方法依据明细")
    confidence = Column(Float, nullable=False, comment="综合置信度（取各票最大）")

    # suggested（待评审）| accepted（采纳）| rejected（驳回）
    status = Column(
        String(32), nullable=False, server_default="suggested",
        comment="评审状态: suggested|accepted|rejected",
    )
    source = Column(String(32), nullable=False, server_default="rule", comment="来源: rule")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    __table_args__ = (
        Index("idx_meta_relation_source_db", "source_id", "database"),
        Index("idx_meta_relation_lr", "left_table", "right_table"),
    )
