"""add kms_knowledge.external_type (外部知识库平台绑定)

外部知识库（type=3 / connector）需要在知识库容器上固化其平台类型（飞书/语雀/
钉钉/企业微信/notion/web），以便文档导入时跳过「选择平台 / 配置凭据」两步，
直接按已配置的外部类型读取凭据并浏览文档。

- external_type: 可空 String(32)，type=3/connector 时必填，取值见
  app.connectors.doc_sources.supported_source_types()；proxy 与 type≠3 必须为 NULL。
- 存量数据零迁移（均为 NULL）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_10_18_0002_add_external_type"
down_revision: Union[str, None] = "2026_10_18_0001_drop_ontology_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 kms_knowledge 增加 external_type 列 + 索引。"""
    op.add_column(
        "kms_knowledge",
        sa.Column("external_type", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_kms_knowledge_external_type", "kms_knowledge", ["external_type"]
    )


def downgrade() -> None:
    """回滚：移除索引 + 列（存量 external_type 随列删除，不可恢复）。"""
    op.drop_index("ix_kms_knowledge_external_type", table_name="kms_knowledge")
    op.drop_column("kms_knowledge", "external_type")
