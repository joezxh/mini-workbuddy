"""add ai_chat_model.api_version / extra_headers

为模型表增加 API 版本与额外请求头配置字段，供模型连通性检测与测试调用时注入。

幂等：列已存在则跳过。

Revision ID: 012_chat_model_api_fields
Revises: 010_wiki_rag_log
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "012_chat_model_api_fields"
down_revision = "010_wiki_rag_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("ai_chat_model")}
    if "api_version" not in cols:
        op.add_column(
            "ai_chat_model",
            sa.Column("api_version", sa.String(50), nullable=True, comment="API 版本（如 v1 / 2024-02-01）"),
        )
    if "extra_headers" not in cols:
        op.add_column(
            "ai_chat_model",
            sa.Column("extra_headers", sa.JSON(), nullable=True, comment="额外请求头 {Key: Value}"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("ai_chat_model")}
    if "extra_headers" in cols:
        op.drop_column("ai_chat_model", "extra_headers")
    if "api_version" in cols:
        op.drop_column("ai_chat_model", "api_version")
