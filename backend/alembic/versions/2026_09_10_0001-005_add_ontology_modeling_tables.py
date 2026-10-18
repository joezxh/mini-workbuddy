"""add ontology modeling tables (P4.2) —— DEPRECATED / NO-OP

⚠️ 本迁移已废弃：2026-10 MinWorkBuddy 改用 PyPI 包 ``semantica`` 提供语义/本体能力，
自研建模六表（object_type/property/link_type/mapping/cq/version）随本体层一同删除。

为保持 alembic revision 图完整（``006_add_kb_tables``、``011_rename_legacy_tables`` 的
down_revision 均指向本节点），本文件保留为 revision 节点，但 upgrade/downgrade 为空操作。
真正的表删除见 ``2026_10_18_0001_drop_ontology_tables.py``。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005_add_ontology_modeling_tables"
down_revision: Union[str, None] = "004_add_ontology_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DEPRECATED no-op：ontology_* 表由 2026_10_18_0001_drop_ontology_tables 负责删除
    pass


def downgrade() -> None:
    # 已废弃的自研本体层不可回滚
    pass
