"""add kms_document.collection_id (表格知识库多集合归属)

Revision ID: 2026_10_18_0000
Revises: 2026_09_27_0000
Create Date: 2026-10-18 10:00:00.000000

表格知识库支持一个知识库配置多个 kms_collection 后，kms_document 需要显式
记录所属集合：

- collection_id: FK → kms_collection.id（可空，保证历史文档与文档型知识库兼容）
- 回填：历史文档按 collection 名反查 kms_collection.id 写入，无法匹配则留空
- 索引：ix_kms_document_collection_id 加速「按集合取文档」
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_10_18_0000"
down_revision: Union[str, None] = "2026_09_27_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """1) kms_document 增 collection_id + FK + 索引;2) 按 collection 名回填历史文档。"""
    op.add_column(
        "kms_document",
        sa.Column("collection_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_kms_document_collection_id",
        "kms_document",
        "kms_collection",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_kms_document_collection_id", "kms_document", ["collection_id"]
    )

    # 回填：按 collection 名（kms_collection.name）反查 id；同名缺失则保持 NULL。
    # 单语句幂等，可重复执行。
    op.execute(
        """
        UPDATE kms_document AS d
        SET collection_id = c.id
        FROM kms_collection AS c
        WHERE d.collection_id IS NULL
          AND d.collection = c.name
        """
    )


def downgrade() -> None:
    """回滚：移除索引 + 外键 + 列（回填数据随列删除，不可恢复）。"""
    op.drop_index("ix_kms_document_collection_id", table_name="kms_document")
    op.drop_constraint(
        "fk_kms_document_collection_id", "kms_document", type_="foreignkey"
    )
    op.drop_column("kms_document", "collection_id")
