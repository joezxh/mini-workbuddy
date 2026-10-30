"""kms_segment 图谱两阶段状态机列（type=4 图谱库）

Spec §3.7：

* ``graph_structure_indexed`` —— 阶段 1 完成：实体/三元组已落 PG 且已投影 Neo4j
* ``graph_indexed``           —— 阶段 2 完成：实体/三元组向量已写入 pgvector
* ``graph_extraction_details`` —— 抽取详情：实体数 / 关系数 / 丢弃数 / 错误 / 耗时

两阶段分离的目的：LLM 抽取最贵，Neo4j 与嵌入服务失败都**不需要重抽**，
按标志位跳过已完成阶段即可断点续跑（Yuxi ``service.py:447-457`` 同款）。

三列均可空：存量切片（type≠4 或图谱构建前）不参与该状态机，
``None`` 语义为「未开始」，与 ``False``（进行中/失败）区分。

Revision ID: 2026_10_31_0005_add_kms_segment_graph_columns
Revises: 2026_10_30_0004_add_kg_tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "2026_10_31_0005_add_kms_segment_graph_columns"
down_revision: Union[str, None] = "2026_10_30_0004_add_kg_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kms_segment",
        sa.Column("graph_structure_indexed", sa.Boolean(), nullable=True,
                  comment="阶段1完成: 实体/三元组已落 PG 并投影 Neo4j"),
    )
    op.add_column(
        "kms_segment",
        sa.Column("graph_indexed", sa.Boolean(), nullable=True,
                  comment="阶段2完成: 实体/三元组向量已写入 pgvector"),
    )
    op.add_column(
        "kms_segment",
        sa.Column("graph_extraction_details", postgresql.JSONB(), nullable=True,
                  comment="抽取详情: 实体数/关系数/丢弃数/错误/耗时"),
    )


def downgrade() -> None:
    op.drop_column("kms_segment", "graph_extraction_details")
    op.drop_column("kms_segment", "graph_indexed")
    op.drop_column("kms_segment", "graph_structure_indexed")
