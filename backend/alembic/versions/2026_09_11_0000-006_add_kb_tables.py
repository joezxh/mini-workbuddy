"""add kb_collection/kb_segment/kb_ref tables (P1 Task 1)

Revision ID: 006_kb_tables
Revises: 005_add_ontology_modeling_tables
Create Date: 2026-09-11
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "006_kb_tables"
down_revision = "005_add_ontology_modeling_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "kb_collection",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kb_collection_tenant_id", "kb_collection", ["tenant_id"])

    op.create_table(
        "kb_segment",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("collection", sa.String(128), nullable=False),
        sa.Column("document_id", sa.String(128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("class_uris", postgresql.JSONB(), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("collection", "document_id", "chunk_index", name="uq_kb_segment"),
    )
    op.create_index("ix_kb_segment_collection", "kb_segment", ["collection"])
    op.create_index("ix_kb_segment_tenant_id", "kb_segment", ["tenant_id"])
    op.create_index(
        "ix_kb_segment_embedding",
        "kb_segment",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.execute(
        "CREATE INDEX ix_kb_segment_content_trgm ON kb_segment "
        "USING gin (content gin_trgm_ops)"
    )

    op.create_table(
        "kb_ref",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("kb_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("as_user_id", sa.String(64), nullable=False),
        sa.Column("doc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("segment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kb_ref_tenant_id", "kb_ref", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_kb_segment_content_trgm", table_name="kb_segment")
    op.drop_index("ix_kb_segment_embedding", table_name="kb_segment")
    op.drop_table("kb_segment")
    op.drop_table("kb_ref")
    op.drop_table("kb_collection")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
