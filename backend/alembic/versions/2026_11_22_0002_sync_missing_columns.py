"""sync_missing_columns — 补齐 sa_ticket.mandate_id 与 agent_hitl_pause 暂停上下文字段。

开发库由 create_all 建表，模型后加的列不会自动 ALTER 到已存在的表，导致
`column sa_ticket.mandate_id does not exist` 一类 500。本迁移以 information_schema
守卫做幂等补列，对纯 alembic 部署亦安全（这些列本已存在则跳过）。

Revision ID: 2026_11_22_0002_synccols
Revises: 2026_11_22_0001_filestorage
Create Date: 2026-11-22 19:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_11_22_0002_synccols"
down_revision = "2026_11_22_0001_filestorage"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first() is not None


def _has_table(bind, table: str) -> bool:
    return bind.execute(
        sa.text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}
    ).scalar() is not None


def _add_column(table: str, column: str, type_sql: str, comment: str | None = None) -> None:
    bind = op.get_bind()
    if not _has_table(bind, table) or _has_column(bind, table, column):
        return
    op.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_sql}")
    if comment:
        op.execute(f"COMMENT ON COLUMN {table}.{column} IS '{comment}'")


def upgrade() -> None:
    # Ticket ↔ Mandate（accept 时创建）——list_tickets 等查询直接依赖该列
    _add_column("sa_ticket", "mandate_id", "VARCHAR(32)", "Mandate 编号（accept 时回填）")
    if _has_column(op.get_bind(), "sa_ticket", "mandate_id"):
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sa_ticket_mandate_id_fkey') THEN
                    ALTER TABLE sa_ticket
                        ADD CONSTRAINT sa_ticket_mandate_id_fkey
                        FOREIGN KEY (mandate_id) REFERENCES sa_mandate (id);
                END IF;
            END $$;
            """
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_sa_ticket_mandate_id ON sa_ticket (mandate_id)")

    # HITL 暂停上下文（同 execution_id 内多轮暂停）
    _add_column("agent_hitl_pause", "round_no", "INTEGER DEFAULT 1", "同 execution_id 内的暂停轮次（从 1 递增）")
    _add_column("agent_hitl_pause", "pause_type", "VARCHAR(30)", "暂停类型: tool_confirm/plan_approval/ask_user")
    _add_column("agent_hitl_pause", "pause_payload", "JSON", "暂停附加载荷（如 AskUser 问题、计划快照）")


def downgrade() -> None:
    for table, column in (
        ("agent_hitl_pause", "pause_payload"),
        ("agent_hitl_pause", "pause_type"),
        ("agent_hitl_pause", "round_no"),
    ):
        if _has_column(op.get_bind(), table, column):
            op.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    if _has_column(op.get_bind(), "sa_ticket", "mandate_id"):
        op.execute("DROP INDEX IF EXISTS ix_sa_ticket_mandate_id")
        op.execute("ALTER TABLE sa_ticket DROP CONSTRAINT IF EXISTS sa_ticket_mandate_id_fkey")
        op.execute("ALTER TABLE sa_ticket DROP COLUMN mandate_id")