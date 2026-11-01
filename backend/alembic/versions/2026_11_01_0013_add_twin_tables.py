"""孪生应用 P0 数据模型：语义层 onto_ontology_query + 编排层 twin_* 六表（spec §3）。

- onto_ontology_query：一等公民「本体查询」，钉住本体+版本、只存编译产物不存数据（T2 决策：
  查询属语义层，探索/智能体/孪生共用同一条）；
- twin_card / twin_page / twin_widget：卡片-页面-组件三级画布，widget.query_id 用 SET NULL
  （删查询不打碎画面，打回「待绑定」空态）；
- twin_publish：与 onto_ontology_publish 刻意分表（那张是「本体→契约」，这张是「页面→只读路由」）；
- twin_card_share / twin_access_request：可见性授予与申请闭环；在途申请唯一用**部分**唯一索引
  （WHERE status='pending'），整列唯一会挡住同一人的「历史 rejected + 新 pending」。

Revision ID: 2026_11_01_0013_add_twin_tables
Revises: 2026_11_01_0012_seed_twin_demo_mapping
Create Date: 2026-11-01 00:13:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_11_01_0013_add_twin_tables"
down_revision: Union[str, None] = "2026_11_01_0012_seed_twin_demo_mapping"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUDIT_TS = [
    sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
]


def upgrade() -> None:
    op.create_table(
        "onto_ontology_query",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("ontology_id", sa.BigInteger(), sa.ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result_shape", sa.String(16), nullable=False),
        sa.Column("spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(), nullable=True),
        sa.Column("compiled_sql", sa.Text(), nullable=True),
        sa.Column("sql_sha256", sa.String(64), nullable=True),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("mask_rules_json", postgresql.JSONB(), nullable=True),
        sa.Column("verify_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("verify_detail_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="disabled"),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        *_AUDIT_TS,
        sa.UniqueConstraint("tenant_id", "ontology_id", "version", "code", name="uq_onto_query_code"),
        sa.CheckConstraint("result_shape IN ('kpi','trend','bar','donut','table','entity_set','graph')", name="ck_onto_query_shape"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_onto_query_status"),
        sa.CheckConstraint("verify_status IN ('pending','verified','failed')", name="ck_onto_query_verify"),
    )
    op.create_index("idx_onto_query_ontology", "onto_ontology_query", ["ontology_id", "version", "status"])

    op.create_table(
        "twin_card",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_template_key", sa.String(64), nullable=True),
        sa.Column("ontology_id", sa.BigInteger(), sa.ForeignKey("onto_ontology.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ontology_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scene_key", sa.String(64), nullable=True),
        sa.Column("scene_config_json", postgresql.JSONB(), nullable=True),
        sa.Column("runtime_state", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        *_AUDIT_TS,
        sa.UniqueConstraint("tenant_id", "owner_id", "name", name="uq_twin_card_name"),
        sa.CheckConstraint("runtime_state IN ('draft','live','paused')", name="ck_twin_card_state"),
    )
    op.create_index("idx_twin_card_owner", "twin_card", ["tenant_id", "owner_id", "runtime_state"])

    op.create_table(
        "twin_page",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refresh_json", postgresql.JSONB(), nullable=True),
        *_AUDIT_TS,
        sa.UniqueConstraint("card_id", "name", name="uq_twin_page_name"),
    )
    op.create_index("idx_twin_page_card", "twin_page", ["card_id", "sort_order"])

    op.create_table(
        "twin_widget",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("page_id", sa.BigInteger(), sa.ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False),
        sa.Column("widget_key", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("query_id", sa.BigInteger(), sa.ForeignKey("onto_ontology_query.id", ondelete="SET NULL"), nullable=True),
        sa.Column("param_values_json", postgresql.JSONB(), nullable=True),
        sa.Column("display_json", postgresql.JSONB(), nullable=True),
        # 纯字符串而非 sa.text()：text() 会把 JSON 里的 ":0"/":6"/":4" 当作绑定参数吞掉，
        # 渲染出 DEFAULT '{"x"NULL,...}' → psycopg2 InvalidTextRepresentation（实测踩过）。
        sa.Column("grid_json", postgresql.JSONB(), nullable=False, server_default='{"x":0,"y":0,"w":6,"h":4}'),
        sa.Column("refresh_json", postgresql.JSONB(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_AUDIT_TS,
        sa.CheckConstraint("widget_key IN ('kpi','trend','bar','donut','alert_table','graph','scene2d','scene3d')", name="ck_twin_widget_key"),
    )
    op.create_index("idx_twin_widget_page", "twin_widget", ["page_id", "sort_order"])
    op.create_index("idx_twin_widget_query", "twin_widget", ["query_id"])

    op.create_table(
        "twin_publish",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", sa.BigInteger(), sa.ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("access", sa.String(16), nullable=False, server_default="org"),
        sa.Column("role_codes_json", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled"),
        sa.Column("published_by", sa.BigInteger(), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_twin_publish_slug"),
        sa.CheckConstraint("access IN ('org','role')", name="ck_twin_publish_access"),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_twin_publish_status"),
    )
    op.create_index("idx_twin_publish_page", "twin_publish", ["page_id", "status"])

    op.create_table(
        "twin_card_share",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantee_type", sa.String(16), nullable=False),
        sa.Column("grantee_id", sa.BigInteger(), nullable=True),
        sa.Column("grantee_code", sa.String(64), nullable=True),
        sa.Column("perm", sa.String(16), nullable=False, server_default="read"),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("granted_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("grantee_type IN ('user','role')", name="ck_twin_share_type"),
        sa.CheckConstraint("perm IN ('read','edit')", name="ck_twin_share_perm"),
        sa.CheckConstraint("source IN ('manual','request')", name="ck_twin_share_source"),
    )
    op.create_index("idx_twin_share_card", "twin_card_share", ["card_id", "grantee_type"])

    op.create_table(
        "twin_access_request",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("twin_card.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("required_role_code", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("approver_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_twin_access_status"),
    )
    op.create_index(
        "uq_twin_access_pending", "twin_access_request",
        ["tenant_id", "card_id", "applicant_id"],
        unique=True, postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("idx_twin_access_card", "twin_access_request", ["card_id", "status"])


def downgrade() -> None:
    # 逆序 drop：twin_* 先删，onto_ontology_query 最后（被 twin_widget 引用）
    for tbl in (
        "twin_access_request", "twin_card_share", "twin_publish",
        "twin_widget", "twin_page", "twin_card", "onto_ontology_query",
    ):
        op.drop_table(tbl)
