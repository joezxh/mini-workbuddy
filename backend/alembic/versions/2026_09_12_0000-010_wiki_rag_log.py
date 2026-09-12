"""wiki rag log + version operation_type (G1/G2)

新增 kms_search_log 检索审计表；为 kms_article_version 添加 operation_type 列。

幂等实现：先检查表/列/索引是否已存在，避免与既有 create_all 初始化冲突。

Revision ID: 010_wiki_rag_log
Revises: 009_meta_relation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "010_wiki_rag_log"
down_revision = "009_meta_relation"
branch_labels = None
depends_on = None


def _existing(bind):
    insp = inspect(bind)
    tables = set(insp.get_table_names())
    idx = {}
    for t in ("kms_search_log", "kms_article_version"):
        if t in tables:
            idx[t] = {i["name"] for i in insp.get_indexes(t)}
        else:
            idx[t] = set()
    cols = {}
    for t in ("kms_search_log", "kms_article_version"):
        if t in tables:
            cols[t] = {c["name"] for c in insp.get_columns(t)}
        else:
            cols[t] = set()
    return tables, cols, idx


def upgrade() -> None:
    bind = op.get_bind()
    tables, cols, idx = _existing(bind)

    # ── kms_search_log（检索审计）──────────────────────────────────────────────
    if "kms_search_log" not in tables:
        op.create_table(
            "kms_search_log",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_kms_search_log_tenant", "kms_search_log", ["tenant_id", "created_at"]
        )
        op.create_index("idx_kms_search_log_tenant_id", "kms_search_log", ["tenant_id"])
    else:
        if "idx_kms_search_log_tenant" not in idx["kms_search_log"]:
            op.create_index(
                "idx_kms_search_log_tenant", "kms_search_log", ["tenant_id", "created_at"]
            )
        if "idx_kms_search_log_tenant_id" not in idx["kms_search_log"]:
            op.create_index("idx_kms_search_log_tenant_id", "kms_search_log", ["tenant_id"])

    # ── kms_article_version.operation_type ─────────────────────────────────────
    if "operation_type" not in cols["kms_article_version"]:
        op.add_column(
            "kms_article_version",
            sa.Column(
                "operation_type",
                sa.String(20),
                nullable=False,
                server_default="edit",
                comment="操作类型：create | edit | rollback",
            ),
        )
    if "idx_kms_version_article" not in idx["kms_article_version"]:
        op.create_index(
            "idx_kms_version_article",
            "kms_article_version",
            ["article_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables, cols, idx = _existing(bind)

    if "idx_kms_version_article" in idx["kms_article_version"]:
        op.drop_index("idx_kms_version_article", table_name="kms_article_version")
    if "operation_type" in cols["kms_article_version"]:
        op.drop_column("kms_article_version", "operation_type")
    if "kms_search_log" in tables:
        if "idx_kms_search_log_tenant" in idx["kms_search_log"]:
            op.drop_index("idx_kms_search_log_tenant", table_name="kms_search_log")
        if "idx_kms_search_log_tenant_id" in idx["kms_search_log"]:
            op.drop_index("idx_kms_search_log_tenant_id", table_name="kms_search_log")
        op.drop_table("kms_search_log")
