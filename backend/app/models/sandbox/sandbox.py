"""沙箱域 8 表（spec 2026-11-01-simulation-sandbox-design.md §3.1-§3.8）。

约定（与 app/models/ontology/ontology.py 同纪律）：TenantMixin、表名单数、
状态 String + comment、审计列；onto_sandbox_* 与生产域 onto_ontology* 物理分表，
本文件所有模型的任何写路径都不构成对生产表的写（V1 红线，验收 A7）。
"""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, Float, ForeignKey, Index,
    Integer, String, Text, TIMESTAMP, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SandboxScene(Base, TenantMixin):
    """推演场景（沙盘实例，spec §3.1）。"""

    __tablename__ = "onto_sandbox_scene"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    ontology_id = Column(
        BigInteger, ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False,
        comment="世界来源本体（只读引用）",
    )
    ontology_version = Column(Integer, nullable=False, comment="钉住的已发布版本")
    name = Column(String(200), nullable=False, comment="场景名")
    clone_scope_json = Column(
        JSONB, nullable=True,
        comment="{object_codes[],relation_codes[],max_entities,max_relations}",
    )
    exec_mode = Column(
        String(16), nullable=False, server_default="auto",
        comment="auto|stepwise|replay（语义 spec §5.4）",
    )
    tick_now = Column(Integer, nullable=False, server_default="0", comment="基线分支推进位")
    tick_max = Column(Integer, nullable=False, server_default="12", comment="推演窗口上限")
    status = Column(
        String(16), nullable=False, server_default="draft",
        comment="draft|cloning|running|completed|failed|archived",
    )
    clone_stats_json = Column(JSONB, nullable=True, comment="克隆统计 {entities,relations,masked_columns[]}")
    error_detail = Column(Text, nullable=True, comment="克隆失败摘要（≤2000）")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("exec_mode IN ('auto','stepwise','replay')", name="ck_sandbox_scene_exec_mode"),
        CheckConstraint(
            "status IN ('draft','cloning','running','completed','failed','archived')",
            name="ck_sandbox_scene_status",
        ),
        Index("idx_sandbox_scene_tenant_ontology_status", "tenant_id", "ontology_id", "status"),
    )


class SandboxBranch(Base, TenantMixin):
    """分支（平行世界线，spec §3.2）。"""

    __tablename__ = "onto_sandbox_branch"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    name = Column(String(200), nullable=False, comment="分支名")
    color = Column(String(16), nullable=True, comment="画布色")
    base_checkpoint_id = Column(
        BigInteger, ForeignKey("onto_sandbox_checkpoint.id", ondelete="SET NULL"), nullable=True,
        comment="空=基线分支；非空=检查点派生",
    )
    tick_now = Column(Integer, nullable=False, server_default="0", comment="分支推进位（真源）")
    status = Column(String(16), nullable=False, server_default="active", comment="active|sealed")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("status IN ('active','sealed')", name="ck_sandbox_branch_status"),
        UniqueConstraint("scene_id", "name", name="uq_sandbox_branch_name"),
        Index("idx_sandbox_branch_scene", "scene_id"),
    )


class SandboxCheckpoint(Base, TenantMixin):
    """检查点（不可变世界快照，场景级合计上限 5，spec §3.3）。"""

    __tablename__ = "onto_sandbox_checkpoint"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="来源分支"
    )
    tick = Column(Integer, nullable=False, comment="快照时点")
    seq = Column(Integer, nullable=False, server_default="0", comment="场景内序号（基线=0）")
    label = Column(String(200), nullable=False, comment="展示名，如 T5 快照")
    stats_json = Column(JSONB, nullable=True, comment="{entities,relations,kpi{}} 摘要")
    creator_id = Column(BigInteger, nullable=True, comment="创建者（基线自动快照=NULL）")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_sandbox_checkpoint_scene", "scene_id", "tick"),
        Index("idx_sandbox_checkpoint_branch", "branch_id"),
    )


class SandboxEntity(Base, TenantMixin):
    """世界实体行（当前态 checkpoint_id IS NULL；快照行非空，spec §3.4）。"""

    __tablename__ = "onto_sandbox_entity"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="分支"
    )
    checkpoint_id = Column(
        BigInteger, ForeignKey("onto_sandbox_checkpoint.id", ondelete="CASCADE"), nullable=True,
        comment="NULL=当前态行；非空=检查点快照行",
    )
    entity_code = Column(String(64), nullable=False, comment="沙箱代理键（SUP006 等，不暴露源库主键）")
    object_code = Column(String(200), nullable=False, comment="本体对象 code（逻辑引用，不建 FK）")
    props_json = Column(JSONB, nullable=False, server_default="{}", comment="属性载荷（数值一律字符串）")
    risk_score = Column(Float, nullable=False, server_default="0", comment="风险分 0~1")
    masked = Column(Boolean, nullable=False, server_default="false", comment="存在脱敏列（门禁输入）")
    source_ref_json = Column(
        JSONB, nullable=True, comment="{source_id,db,table,pk} 仅展示；禁止据此回查/回写（V1）"
    )
    origin = Column(String(8), nullable=False, server_default="clone", comment="clone|derived（引擎派生事件）")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("origin IN ('clone','derived')", name="ck_sandbox_entity_origin"),
        Index("uq_sandbox_entity_current", "branch_id", "entity_code", unique=True,
              postgresql_where=text("checkpoint_id IS NULL")),
        Index("uq_sandbox_entity_snapshot", "checkpoint_id", "entity_code", unique=True,
              postgresql_where=text("checkpoint_id IS NOT NULL")),
        Index("idx_sandbox_entity_scene_object", "scene_id", "object_code"),
    )


class SandboxRelation(Base, TenantMixin):
    """世界关系行（归属与快照机制同 entity，spec §3.5）。"""

    __tablename__ = "onto_sandbox_relation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="分支"
    )
    checkpoint_id = Column(
        BigInteger, ForeignKey("onto_sandbox_checkpoint.id", ondelete="CASCADE"), nullable=True,
        comment="NULL=当前态行；非空=检查点快照行",
    )
    rel_code = Column(String(64), nullable=False, comment="分支内唯一关系键")
    link_type_code = Column(String(200), nullable=False, comment="本体关系 code（逻辑引用）")
    from_entity_code = Column(String(64), nullable=False, comment="起点实体代理键")
    to_entity_code = Column(String(64), nullable=False, comment="终点实体代理键")
    props_json = Column(JSONB, nullable=False, server_default="{}", comment="属性载荷")
    origin = Column(String(8), nullable=False, server_default="clone", comment="clone|causal（因果边实例化）")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint("origin IN ('clone','causal')", name="ck_sandbox_relation_origin"),
        Index("uq_sandbox_relation_current", "branch_id", "rel_code", unique=True,
              postgresql_where=text("checkpoint_id IS NULL")),
        Index("uq_sandbox_relation_snapshot", "checkpoint_id", "rel_code", unique=True,
              postgresql_where=text("checkpoint_id IS NOT NULL")),
        Index("idx_sandbox_relation_scene_endpoints", "scene_id", "from_entity_code", "to_entity_code"),
    )


class SandboxElement(Base, TenantMixin):
    """统一配置元素（因果边/规则/目标/未来事件模板，spec §3.6）。

    D3 防线（V2/A8）：origin='llm' 只能 status='suggested'；仅 accepted 参与引擎求值。
    """

    __tablename__ = "onto_sandbox_element"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    kind = Column(
        String(16), nullable=False,
        comment="causal_edge|rule|goal|future_event",
    )
    code = Column(String(64), nullable=False, comment="场景内唯一标识（G-01/CE-003）")
    label = Column(String(200), nullable=False, comment="展示名；因果边语义 PRODUCES/MODIFIES/CAUSES/...")
    from_ref = Column(String(64), nullable=True, comment="起点（实体 code/对象 code/事件 kind）")
    to_ref = Column(String(64), nullable=True, comment="终点")
    condition_expr_json = Column(JSONB, nullable=True, comment="触发条件 AST（受控文法）")
    effect_expr_json = Column(JSONB, nullable=True, comment="效应公式 AST；goal 为判据公式")
    activation_tick = Column(Integer, nullable=True, comment="期望激活位（前瞻排序参考；求值以状态为准）")
    origin = Column(String(8), nullable=False, server_default="human", comment="rule|llm|human")
    status = Column(String(16), nullable=False, server_default="accepted", comment="suggested|accepted|rejected")
    confidence = Column(Float, nullable=True, comment="LLM 自评分（仅排序展示）")
    creator_id = Column(BigInteger, nullable=True, comment="创建者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("scene_id", "kind", "code", name="uq_sandbox_element_code"),
        CheckConstraint(
            "kind IN ('causal_edge','rule','goal','future_event')", name="ck_sandbox_element_kind",
        ),
        CheckConstraint("origin IN ('rule','llm','human')", name="ck_sandbox_element_origin"),
        CheckConstraint(
            "status IN ('suggested','accepted','rejected')", name="ck_sandbox_element_status",
        ),
        # D3 防线数据库级兜底：llm 元素只能 suggested（spec §0-V2）
        CheckConstraint(
            "NOT (origin = 'llm' AND status <> 'suggested')", name="ck_sandbox_element_llm_suggested",
        ),
        Index("idx_sandbox_element_scene_status", "scene_id", "status"),
        Index("idx_sandbox_element_scene_origin_status", "scene_id", "origin", "status"),
    )


class SandboxAction(Base, TenantMixin):
    """行动审计日志（allowed/denied/pending 全留痕，spec §3.7）。"""

    __tablename__ = "onto_sandbox_action"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="分支"
    )
    tick = Column(Integer, nullable=False, comment="施加时点")
    template_code = Column(String(64), nullable=False, comment="引用 onto_action_template.code")
    target_entity_code = Column(String(64), nullable=False, comment="沙箱代理键")
    params_json = Column(JSONB, nullable=False, server_default="{}", comment="强度/参数")
    gate_result = Column(String(8), nullable=False, comment="allowed|denied|pending")
    gate_reason = Column(String(64), nullable=True, comment="MASKED_TARGET|NO_ACTION_PERMISSION|MODE_READONLY|CONFIRM_EXPIRED")
    confirm_token = Column(String(64), nullable=True, comment="stepwise 待确认令牌")
    operator_id = Column(BigInteger, nullable=True, comment="操作者")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        CheckConstraint("gate_result IN ('allowed','denied','pending')", name="ck_sandbox_action_gate"),
        Index("idx_sandbox_action_scene_branch_tick", "scene_id", "branch_id", "tick"),
    )


class SandboxObservation(Base, TenantMixin):
    """引擎时序事实（主时间线/四 tab/KPI/对比的唯一数据源，spec §3.8）。"""

    __tablename__ = "onto_sandbox_observation"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    scene_id = Column(
        BigInteger, ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False, comment="场景"
    )
    branch_id = Column(
        BigInteger, ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False, comment="分支"
    )
    tick = Column(Integer, nullable=False, comment="观察时点")
    kind = Column(
        String(24), nullable=False,
        comment="observation|kpi_point|risk_point|rule_fired|goal_eval|action_effect|"
                "event_fired|edge_fired|deadline_missed",
    )
    severity = Column(String(8), nullable=False, server_default="info", comment="info|warn|err")
    title = Column(String(200), nullable=False, comment="展示标题")
    detail_json = Column(JSONB, nullable=False, server_default="{}", comment="结构化观察载荷（数值一律字符串）")
    source = Column(String(8), nullable=False, server_default="engine", comment="engine|advisor")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        CheckConstraint(
            "kind IN ('observation','kpi_point','risk_point','rule_fired','goal_eval',"
            "'action_effect','event_fired','edge_fired','deadline_missed')",
            name="ck_sandbox_observation_kind",
        ),
        CheckConstraint("severity IN ('info','warn','err')", name="ck_sandbox_observation_severity"),
        CheckConstraint("source IN ('engine','advisor')", name="ck_sandbox_observation_source"),
        Index("idx_sandbox_observation_branch_tick_kind", "branch_id", "tick", "kind"),
    )
