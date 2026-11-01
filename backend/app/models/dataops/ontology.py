"""本体治理表（8 张）：注册 / 版本 / 构建任务 / 候选明细 / 能力问题 / 证据 / 语义 / 发布登记。

设计真源：docs/superpowers/specs/2026-10-31-ontology-capability-design.md §3.2。
决策基线：D1（CDM 升格模式层）、D2（实例不落库）、D3 rev.2（LLM 只能以未采纳态进审阅台）、D4（P0 闭环）。

约定（沿用现状，不新发明）：
- 全部继承 ``TenantMixin``（租户行级隔离），表名单数、状态用 ``String`` + comment；
- 审计列 ``creator_id/updater_id/created_at/updated_at``；
- 结构表只读口径：下游一律只取 ``review_status=accepted AND status=published``；
- D3 rev.2：``llm`` 取值永远非法；LLM 结构候选只落 ``build_item(origin='llm', status='suggested')``。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, Float, ForeignKey, Index, Integer,
    String, Text, TIMESTAMP, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class MetaOntology(Base, TenantMixin):
    """本体注册（模式层归属锚点，spec §3.2）。"""

    __tablename__ = "meta_ontology"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(64), nullable=False, comment="租户内唯一，同时作为 TenantScope.ontology_code")
    name = Column(String(200), nullable=False, comment="本体名称")
    description = Column(Text, nullable=True, comment="说明")
    namespace_uri = Column(String(255), nullable=True, comment="RDF 导出用，默认 urn:mwb:ontology:{code}")
    # AF-09：stopped = 不再接受构建，但历史版本仍可消费
    status = Column(
        String(16), nullable=False, server_default="draft",
        comment="生命周期: draft|published|archived|stopped",
    )
    current_version = Column(Integer, nullable=False, server_default="0", comment="0=未发布")
    root_catalog_id = Column(
        BigInteger, ForeignKey("meta_standard_catalog.id", ondelete="SET NULL"), nullable=True,
        comment="本体的目录根（归属锚点，可空）",
    )
    # AF-08：资产送数后的作用域草稿（形状同 build_job.scope_json），使“勾选→离开→回来仍能构建”成立
    draft_scope_json = Column(JSONB, nullable=True, comment="AF-08 作用域草稿")
    # P2 预留，本期降为兼容缓存（发布登记已拆至 meta_ontology_publish）
    publish_targets_json = Column(JSONB, nullable=True, comment="P2 预留: [skill,mcp,http]")

    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    updater_id = Column(BigInteger, nullable=True, comment="最后更新者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_meta_ontology_code"),
        CheckConstraint("status IN ('draft','published','archived','stopped')", name="ck_meta_ontology_status"),
        Index("idx_meta_ontology_tenant_status", "tenant_id", "status"),
    )


class MetaOntologyVersion(Base, TenantMixin):
    """版本快照（发布时冻结全量结构 + 门禁结论，spec §3.2）。"""

    __tablename__ = "meta_ontology_version"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("meta_ontology.id", ondelete="CASCADE"), nullable=False, comment="本体 ID"
    )
    version = Column(Integer, nullable=False, comment="本体内自增")
    snapshot_json = Column(JSONB, nullable=True, comment="冻结：对象/属性/关系/映射/CQ 全量")
    diff_json = Column(JSONB, nullable=True, comment="{added[],removed[],changed[],regressions[]} 含明细")
    gate_json = Column(JSONB, nullable=True, comment="发布门禁结论 {passed,checks[],blocked_reasons[]}")
    change_note = Column(Text, nullable=True, comment="变更说明")
    author_user_id = Column(BigInteger, nullable=True, comment="操作人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("ontology_id", "version", name="uq_meta_ontology_version"),
        Index("idx_meta_ontology_version_list", "ontology_id", "created_at"),
    )


class MetaOntologyBuildJob(Base, TenantMixin):
    """构建任务（幂等 + mode + 进度，spec §3.2）。"""

    __tablename__ = "meta_ontology_build_job"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("meta_ontology.id", ondelete="CASCADE"), nullable=False, comment="本体 ID"
    )
    idempotency_key = Column(String(128), nullable=False, comment="幂等关键列（见 §4.2）")
    # D3 rev.2 不扩 mode：LLM 结构候选由助手端点直接产 build_item(origin='llm')，不改写构建任务 mode
    mode = Column(
        String(16), nullable=False, server_default="rules",
        comment="rules|rules+semantic（是否叠加 LLM 语义补全，从不参与 source 计算）",
    )
    scope_json = Column(
        JSONB, nullable=True,
        comment="{mode:tables|tags|catalog, source_id, db_name, database, tables[], tag_ids[], catalog_ids[]}",
    )
    status = Column(
        String(16), nullable=False, server_default="pending",
        comment="pending|running|succeeded|failed|cancelled",
    )
    phase = Column(String(16), nullable=True, comment="extract|align|judge|merge|done")
    progress = Column(Float, nullable=False, server_default="0", comment="0~1")
    stats_json = Column(JSONB, nullable=True, comment="{tables,objects_created,...,semantic,degraded}")
    error_code = Column(String(64), nullable=True, comment="错误码")
    error_detail = Column(Text, nullable=True, comment="失败摘要（≤2000，完整轨迹放 item）")
    duration_ms = Column(Integer, nullable=True, comment="耗时毫秒")
    started_at = Column(TIMESTAMP, nullable=True, comment="开始时间")
    finished_at = Column(TIMESTAMP, nullable=True, comment="结束时间")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_meta_build_job_idem"),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_meta_build_job_status",
        ),
        Index("idx_meta_build_job_tenant_ontology_status", "tenant_id", "ontology_id", "status"),
        Index("idx_meta_build_job_idem", "idempotency_key"),
    )


class MetaOntologyBuildItem(Base, TenantMixin):
    """候选明细（替代 delta_json 大字段，rejected/dropped 照样落库可复盘，spec §3.2）。"""

    __tablename__ = "meta_ontology_build_item"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    job_id = Column(
        BigInteger, ForeignKey("meta_ontology_build_job.id", ondelete="CASCADE"), nullable=False, comment="任务 ID"
    )
    batch_index = Column(Integer, nullable=True, comment="批次序号")
    element_kind = Column(String(24), nullable=False, comment="object|property|relation|mapping")
    element_code = Column(String(200), nullable=False, comment="对象 code、obj.prop、关系 code")
    action = Column(String(16), nullable=False, comment="insert|update|skip|reject")
    # D3 rev.2 新增：候选产出通道；LLM 候选固定 origin='llm' 且 status 只能 suggested，与结构表 source 解耦
    origin = Column(
        String(8), nullable=False, server_default="rule", comment="rule|llm（防线①：llm 永不自动采纳）",
    )
    delta_json = Column(JSONB, nullable=True, comment="该条候选完整载荷（display_name/definition/aliases/target）")
    verdict = Column(String(8), nullable=True, comment="pass|warn|fail|no_verdict")
    verdict_reason = Column(Text, nullable=True, comment="来自 8 类机械校验的具体原因")
    confidence = Column(Float, nullable=True, comment="规则置信度（不含 LLM）")
    status = Column(
        String(16), nullable=False, server_default="suggested",
        comment="suggested|accepted|rejected|dropped",
    )
    element_id = Column(BigInteger, nullable=True, comment="落库后元素主键（回填，便于跳转检视）")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("job_id", "element_kind", "element_code", name="uq_meta_ontology_build_item"),
        CheckConstraint("origin IN ('rule','llm')", name="ck_meta_build_item_origin"),
        Index("idx_meta_build_item_job_status", "job_id", "status"),
        Index("idx_meta_build_item_job_origin", "job_id", "origin"),
    )


class MetaOntologyCq(Base, TenantMixin):
    """能力问题（question_hash 去重，spec §3.2）。"""

    __tablename__ = "meta_ontology_cq"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("meta_ontology.id", ondelete="CASCADE"), nullable=False, comment="本体 ID"
    )
    version = Column(Integer, nullable=False, server_default="0", comment="生成时绑定版本（0=未发布态）")
    question = Column(Text, nullable=False, comment="CQ 文本")
    question_hash = Column(String(64), nullable=False, comment="去重键（承载唯一约束）")
    category = Column(String(32), nullable=True, comment="存在性/计数/关系遍历/聚合/时间/条件")
    related_codes_json = Column(JSONB, nullable=True, comment="涉及的对象/关系 code")
    verify_status = Column(
        String(16), nullable=False, server_default="pending", comment="pending|passed|failed",
    )
    verify_detail_json = Column(JSONB, nullable=True, comment="{concept_hits[],path[],reachable,mapping_coverage}")
    # D3 rev.2 不扩展到 CQ：结构候选只走 build_item，CQ 文本仍由规则+模板生成
    source = Column(String(16), nullable=False, server_default="rule", comment="rule|human")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("ontology_id", "version", "question_hash", name="uq_meta_ontology_cq"),
        Index("idx_meta_ontology_cq_verify", "ontology_id", "verify_status"),
    )


class MetaOntologyEvidence(Base, TenantMixin):
    """证据（一等公民，可复核原始依据，spec §3.2）。"""

    __tablename__ = "meta_ontology_evidence"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("meta_ontology.id", ondelete="CASCADE"), nullable=False, comment="本体 ID"
    )
    element_kind = Column(String(24), nullable=False, comment="object|property|relation|mapping")
    element_code = Column(String(200), nullable=False, comment="指向元素 code")
    evidence_kind = Column(
        String(24), nullable=False, comment="naming|comment|profile|overlap|binding|human",
    )
    payload_json = Column(JSONB, nullable=True, comment="{rule,score,matched[],overlap_ratio,sample_tables[]}")
    confidence = Column(Float, nullable=True, comment="置信度")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_meta_evidence_lookup", "tenant_id", "ontology_id", "element_kind", "element_code"),
    )


class MetaOntologySemantic(Base, TenantMixin):
    """LLM 语义产出（独立落表，永不直写结构表，D3 落地形态，spec §3.2）。"""

    __tablename__ = "meta_ontology_semantic"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("meta_ontology.id", ondelete="CASCADE"), nullable=False, comment="本体 ID"
    )
    build_job_id = Column(
        BigInteger, ForeignKey("meta_ontology_build_job.id", ondelete="SET NULL"), nullable=True, comment="来源任务",
    )
    element_kind = Column(String(24), nullable=False, comment="object|property|relation|mapping")
    element_code = Column(String(200), nullable=False, comment="指向元素 code")
    field = Column(
        String(32), nullable=False, comment="display_name|definition|semantic_type|aliases|review_hint",
    )
    value = Column(Text, nullable=True, comment="语义文本值")
    aliases_json = Column(JSONB, nullable=True, comment="别名数组（field=aliases 时）")
    confidence = Column(Float, nullable=True, comment="LLM 自评（仅排序展示，不参与 review_status）")
    model = Column(String(128), nullable=True, comment="模型名（可追溯）")
    prompt_version = Column(String(32), nullable=True, comment="提示词版本（可重放）")
    status = Column(
        String(16), nullable=False, server_default="suggested", comment="suggested|accepted|rejected",
    )
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint(
            "ontology_id", "element_kind", "element_code", "field", "model",
            name="uq_meta_ontology_semantic",
        ),
        Index("idx_meta_semantic_status", "ontology_id", "status"),
    )


class MetaOntologyPublish(Base, TenantMixin):
    """本体应用发布登记（只做登记与绑定，不重复建设运行时，spec §3.2 补 AF-17/AF-18）。"""

    __tablename__ = "meta_ontology_publish"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("meta_ontology.id", ondelete="CASCADE"), nullable=False, comment="本体 ID"
    )
    # 钉在哪个发布版本（=0 表示引用草稿态，仅允许 status=disabled）
    version = Column(Integer, nullable=False, server_default="0", comment="钉住的发布版本")
    target_type = Column(String(16), nullable=False, comment="skill|http|mcp")
    code = Column(String(64), nullable=False, comment="目标侧唯一标识（ai_skill.code / MCP 工具名）")
    name = Column(String(200), nullable=True, comment="展示名")
    description = Column(Text, nullable=True, comment="说明")
    payload_json = Column(JSONB, nullable=True, comment="{tools[],input_schema,output_schema,endpoint,usage_hint}")
    status = Column(String(16), nullable=False, server_default="enabled", comment="enabled|disabled")

    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("tenant_id", "target_type", "code", name="uq_meta_ontology_publish_code"),
        CheckConstraint("target_type IN ('skill','http','mcp')", name="ck_meta_publish_target"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_meta_publish_status"),
        Index("idx_meta_publish_ontology_version", "ontology_id", "version"),
    )
