"""推演沙盘沙箱域 9 表 + 内置行动模板种子（spec 2026-11-01-simulation-sandbox-design.md §3）。

- onto_sandbox_* 8 张：scene/branch/checkpoint/entity/relation/element/action/observation；
- onto_action_template 1 张：平台级（无 tenant 维度），种子 4 条（supply_cut/delay/price_up/reroute）；
- 与生产域 onto_ontology*/meta_* 物理分表（V1 沙箱域例外物化，生产红线不变）；
- entity/relation 当前态/快照行两段式唯一用部分唯一索引（WHERE checkpoint_id IS [NOT] NULL）；
- element 的 D3 防线数据库级兜底 CHECK：origin='llm' 只能 status='suggested'。

Revision ID: 2026_11_01_0011_add_sandbox_tables
Revises: 2026_11_01_0010_add_source_external_type
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_11_01_0011_add_sandbox_tables"
down_revision: Union[str, None] = "2026_11_01_0010_add_source_external_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUDIT_TS = sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    # --- 场景 ---
    op.create_table(
        "onto_sandbox_scene",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("ontology_id", sa.BigInteger(), sa.ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ontology_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("clone_scope_json", postgresql.JSONB(), nullable=True),
        sa.Column("exec_mode", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("tick_now", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tick_max", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("clone_stats_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        _AUDIT_TS,
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("exec_mode IN ('auto','stepwise','replay')", name="ck_sandbox_scene_exec_mode"),
        sa.CheckConstraint("status IN ('draft','cloning','running','completed','failed','archived')", name="ck_sandbox_scene_status"),
        sa.Index("idx_sandbox_scene_tenant_ontology_status", "tenant_id", "ontology_id", "status"),
    )

    # --- 检查点（branch_id 环 FK 延后 ALTER 补建） ---
    op.create_table(
        "onto_sandbox_checkpoint",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("stats_json", postgresql.JSONB(), nullable=True),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        _AUDIT_TS,
        sa.Index("idx_sandbox_checkpoint_scene", "scene_id", "tick"),
        sa.Index("idx_sandbox_checkpoint_branch", "branch_id"),
    )

    # --- 分支（base_checkpoint_id → checkpoint 可直接建 FK；checkpoint.branch_id 反向 FK 此处补 ALTER） ---
    op.create_table(
        "onto_sandbox_branch",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("base_checkpoint_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_checkpoint.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tick_now", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        _AUDIT_TS,
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_foreign_key("fk_sandbox_checkpoint_branch", "onto_sandbox_checkpoint", "onto_sandbox_branch", ["branch_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("uq_sandbox_branch_name", "onto_sandbox_branch", ["scene_id", "name"])
    op.create_check_constraint("ck_sandbox_branch_status", "onto_sandbox_branch", "status IN ('active','sealed')")
    op.create_index("idx_sandbox_branch_scene", "onto_sandbox_branch", ["scene_id"])

    # --- 实体（两段式部分唯一索引） ---
    op.create_table(
        "onto_sandbox_entity",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_checkpoint.id", ondelete="CASCADE"), nullable=True),
        sa.Column("entity_code", sa.String(64), nullable=False),
        sa.Column("object_code", sa.String(200), nullable=False),
        sa.Column("props_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("masked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_ref_json", postgresql.JSONB(), nullable=True),
        sa.Column("origin", sa.String(8), nullable=False, server_default="clone"),
        _AUDIT_TS,
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("origin IN ('clone','derived')", name="ck_sandbox_entity_origin"),
        sa.Index("uq_sandbox_entity_current", "branch_id", "entity_code", unique=True,
                 postgresql_where=sa.text("checkpoint_id IS NULL")),
        sa.Index("uq_sandbox_entity_snapshot", "checkpoint_id", "entity_code", unique=True,
                 postgresql_where=sa.text("checkpoint_id IS NOT NULL")),
        sa.Index("idx_sandbox_entity_scene_object", "scene_id", "object_code"),
    )

    # --- 关系 ---
    op.create_table(
        "onto_sandbox_relation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_checkpoint.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rel_code", sa.String(64), nullable=False),
        sa.Column("link_type_code", sa.String(200), nullable=False),
        sa.Column("from_entity_code", sa.String(64), nullable=False),
        sa.Column("to_entity_code", sa.String(64), nullable=False),
        sa.Column("props_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("origin", sa.String(8), nullable=False, server_default="clone"),
        _AUDIT_TS,
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("origin IN ('clone','causal')", name="ck_sandbox_relation_origin"),
        sa.Index("uq_sandbox_relation_current", "branch_id", "rel_code", unique=True,
                 postgresql_where=sa.text("checkpoint_id IS NULL")),
        sa.Index("uq_sandbox_relation_snapshot", "checkpoint_id", "rel_code", unique=True,
                 postgresql_where=sa.text("checkpoint_id IS NOT NULL")),
        sa.Index("idx_sandbox_relation_scene_endpoints", "scene_id", "from_entity_code", "to_entity_code"),
    )

    # --- 配置元素（含 D3 防线 CHECK） ---
    op.create_table(
        "onto_sandbox_element",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("from_ref", sa.String(64), nullable=True),
        sa.Column("to_ref", sa.String(64), nullable=True),
        sa.Column("condition_expr_json", postgresql.JSONB(), nullable=True),
        sa.Column("effect_expr_json", postgresql.JSONB(), nullable=True),
        sa.Column("activation_tick", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(8), nullable=False, server_default="human"),
        sa.Column("status", sa.String(16), nullable=False, server_default="accepted"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        _AUDIT_TS,
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scene_id", "kind", "code", name="uq_sandbox_element_code"),
        sa.CheckConstraint("kind IN ('causal_edge','rule','goal','future_event')", name="ck_sandbox_element_kind"),
        sa.CheckConstraint("origin IN ('rule','llm','human')", name="ck_sandbox_element_origin"),
        sa.CheckConstraint("status IN ('suggested','accepted','rejected')", name="ck_sandbox_element_status"),
        sa.CheckConstraint("NOT (origin = 'llm' AND status <> 'suggested')", name="ck_sandbox_element_llm_suggested"),
        sa.Index("idx_sandbox_element_scene_status", "scene_id", "status"),
        sa.Index("idx_sandbox_element_scene_origin_status", "scene_id", "origin", "status"),
    )

    # --- 行动审计 ---
    op.create_table(
        "onto_sandbox_action",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("template_code", sa.String(64), nullable=False),
        sa.Column("target_entity_code", sa.String(64), nullable=False),
        sa.Column("params_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("gate_result", sa.String(8), nullable=False),
        sa.Column("gate_reason", sa.String(64), nullable=True),
        sa.Column("confirm_token", sa.String(64), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        _AUDIT_TS,
        sa.CheckConstraint("gate_result IN ('allowed','denied','pending')", name="ck_sandbox_action_gate"),
        sa.Index("idx_sandbox_action_scene_branch_tick", "scene_id", "branch_id", "tick"),
    )

    # --- 引擎时序事实 ---
    op.create_table(
        "onto_sandbox_observation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("scene_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_scene.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), sa.ForeignKey("onto_sandbox_branch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(8), nullable=False, server_default="engine"),
        _AUDIT_TS,
        sa.CheckConstraint(
            "kind IN ('observation','kpi_point','risk_point','rule_fired','goal_eval',"
            "'action_effect','event_fired','edge_fired','deadline_missed')",
            name="ck_sandbox_observation_kind",
        ),
        sa.CheckConstraint("severity IN ('info','warn','err')", name="ck_sandbox_observation_severity"),
        sa.CheckConstraint("source IN ('engine','advisor')", name="ck_sandbox_observation_source"),
        sa.Index("idx_sandbox_observation_branch_tick_kind", "branch_id", "tick", "kind"),
    )

    # --- 平台内置行动模板（无 tenant） + 种子 ---
    op.create_table(
        "onto_action_template",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain_hint", sa.String(64), nullable=True),
        sa.Column("param_schema_json", postgresql.JSONB(), nullable=False),
        sa.Column("effect_spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled"),
        _AUDIT_TS,
        sa.UniqueConstraint("code", name="uq_action_template_code"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_action_template_status"),
    )
    _seed_templates()


def _seed_templates() -> None:
    """种子与 app/models/sandbox/template_seed.py 同一真源（测试 conftest 共用）。"""
    import json

    from app.models.sandbox.template_seed import ACTION_TEMPLATE_SEEDS

    bind = op.get_bind()
    for code, name, domain, ps, es in ACTION_TEMPLATE_SEEDS:
        exists = bind.execute(
            sa.text("SELECT 1 FROM onto_action_template WHERE code = :c"), {"c": code}
        ).scalar()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO onto_action_template "
                    "(code, name, domain_hint, param_schema_json, effect_spec_json, status) "
                    "VALUES (:c, :n, :d, CAST(:ps AS jsonb), CAST(:es AS jsonb), 'enabled')"
                ),
                {"c": code, "n": name, "d": domain, "ps": json.dumps(ps), "es": json.dumps(es)},
            )


def downgrade() -> None:
    for tbl in (
        "onto_action_template",
        "onto_sandbox_observation",
        "onto_sandbox_action",
        "onto_sandbox_element",
        "onto_sandbox_relation",
        "onto_sandbox_entity",
        "onto_sandbox_branch",
        "onto_sandbox_checkpoint",
        "onto_sandbox_scene",
    ):
        op.drop_table(tbl)
