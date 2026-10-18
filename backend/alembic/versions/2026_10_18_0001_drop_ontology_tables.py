"""drop ontology tables (semantica migration)

MinWorkBuddy 改用 PyPI ``semantica`` 提供语义/本体能力，删除自研本体层对应的 9 张表：
  ontology / ontology_class / ontology_annotation / ontology_object_type /
  ontology_property / ontology_link_type / ontology_mapping / ontology_cq /
  ontology_version

按子→父顺序 DROP（依赖 ontology_id 的外键由 ``CASCADE`` 一并清理）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_10_18_0001_drop_ontology_tables"
down_revision: Union[str, None] = "2026_10_18_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 子表（FK → ontology）在前，本体主表在后
_ONTOLOGY_TABLES = (
    "ontology_annotation",
    "ontology_class",
    "ontology_version",
    "ontology_cq",
    "ontology_mapping",
    "ontology_link_type",
    "ontology_property",
    "ontology_object_type",
    "ontology",
)


def upgrade() -> None:
    for tbl in _ONTOLOGY_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')


def downgrade() -> None:
    raise NotImplementedError(
        "不可回滚：本体能力已迁移至 semantica，ontology_* 表结构不再由本工程维护"
    )
