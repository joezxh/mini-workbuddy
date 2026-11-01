"""本体查询定义（onto_ontology_query）：跨端复用的一等公民查询，spec 孪生方案 §3.1。

决策 T2：查询定义属语义层，落 onto_ 域而非 twin_ 域，使探索/智能体/孪生共用同一条查询。
约束沿用现状：TenantMixin 租户隔离、状态用 String + comment、显式 CHECK/UQ/Index。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin

_RESULT_SHAPES = ("kpi", "trend", "bar", "donut", "table", "entity_set", "graph")


class MetaOntologyQuery(Base, TenantMixin):
    """已保存的本体查询（编译产物钉版本，不存数据）。"""

    __tablename__ = "onto_ontology_query"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False, comment="所属本体",
    )
    version = Column(Integer, nullable=False, server_default="0", comment="钉住的发布版本；0=草稿，禁止编译")
    code = Column(String(64), nullable=False, comment="本体+版本内唯一")
    name = Column(String(200), nullable=False, comment="查询名称")
    description = Column(Text, nullable=True, comment="说明")
    result_shape = Column(
        String(16), nullable=False,
        comment="结果形状: kpi|trend|bar|donut|table|entity_set|graph ← 组件配对契约",
    )
    spec_json = Column(JSONB, nullable=False, comment="声明式查询: {objects[], attributes[], agg, group_by[], filters[], time_window, limit}；attributes 为标准项 code")
    params_json = Column(JSONB, nullable=True, comment="参数声明: [{name,type,default,control}]；编译期追写生成占位符 [{name,type,source:'compiled'}]")
    compiled_sql = Column(Text, nullable=True, comment="编译产物：无注释单语句模板，含 :p_xxx 占位符")
    sql_sha256 = Column(String(64), nullable=True, comment="编译产物摘要（锚点沿用 meta_data_write_request 做法）")
    source_id = Column(BigInteger, nullable=True, comment="编译期确定的直连数据源（meta_data_source.id）；运行期不再重复解析快照")
    mask_rules_json = Column(JSONB, nullable=True, comment="出口脱敏配置，直接可 MaskingConfig.model_validate：{enabled, rules:[{field,strategy,keep_prefix,keep_suffix,exempt_roles}]}")
    verify_status = Column(String(16), nullable=False, server_default="pending", comment="pending|verified|failed")
    verify_detail_json = Column(JSONB, nullable=True, comment="{columns[], row_count, elapsed_ms, blocked_columns[]}")
    status = Column(String(16), nullable=False, server_default="disabled", comment="enabled|disabled")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "ontology_id", "version", "code", name="uq_onto_query_code"),
        CheckConstraint(
            "result_shape IN ('kpi','trend','bar','donut','table','entity_set','graph')",
            name="ck_onto_query_shape",
        ),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_onto_query_status"),
        CheckConstraint("verify_status IN ('pending','verified','failed')", name="ck_onto_query_verify"),
        Index("idx_onto_query_ontology", "ontology_id", "version", "status"),
    )
