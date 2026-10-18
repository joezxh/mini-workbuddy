"""add ontology tables (P4.1) —— DEPRECATED / NO-OP

⚠️ 本迁移已废弃：2026-10 MinWorkBuddy 改用 PyPI 包 ``semantica`` 提供语义/本体能力，
自研 rdflib 本体层（owl_engine / OntologyRepository / modeling_service 等）已全部删除。
本体持久化改为 semantica 的 PostgreSQL(pgvector) + Neo4j 后端，工程内不再维护 ontology_* 表。

为保持 alembic revision 图完整（``006_add_kb_tables``、``011_rename_legacy_tables`` 的
down_revision 均指向本节点），本文件保留为 revision 节点，但 upgrade/downgrade 为空操作。
真正的表删除见 ``2026_10_18_0001_drop_ontology_tables.py``。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004_add_ontology_tables"
down_revision: Union[str, None] = "003_add_sys_dictionary_tenant_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DEPRECATED no-op：ontology_* 表由 2026_10_18_0001_drop_ontology_tables 负责删除
    pass


def downgrade() -> None:
    # 已废弃的自研本体层不可回滚
    pass
