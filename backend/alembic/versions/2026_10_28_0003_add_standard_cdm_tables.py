"""add standard CDM tables (7): catalog / object / attribute-ref / relation / table bind / history / relation check

标准三层语义模型（CDM）落库：目录/场景 → 对象标准 → 属性引用 + 关系标准，
外加表→对象绑定（镜像 meta_column_standard 评审语义）与关系校验结论。

实现方式沿用 007 迁移约定：直接以 ORM 元数据建表（``app/models/dataops/standard_cdm.py``
是唯一事实来源），避免在迁移里二次声明列定义造成漂移；``create_all``/``drop_all``
自带存在性判断，重复执行安全（幂等）。

种子数据不在迁移里做：对象/关系标准的租户内播种由服务层完成，保持 schema 纯净。

Revision ID: 2026_10_28_0003_add_standard_cdm_tables
Revises: 2026_10_28_0002_add_meta_table_db_name
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2026_10_28_0003_add_standard_cdm_tables"
down_revision: Union[str, None] = "2026_10_28_0002_add_meta_table_db_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables():
    from app.models.dataops.standard_cdm import (
        MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute,
        MetaRelationCheck, MetaStandardCatalog, MetaTableStandard,
        MetaTableStandardHistory,
    )

    # 顺序即建表顺序：catalog → object → attribute → relation → bind → history → check
    return [
        MetaStandardCatalog.__table__,
        MetaObjectStandard.__table__,
        MetaObjectStandardAttribute.__table__,
        MetaObjectRelation.__table__,
        MetaTableStandard.__table__,
        MetaTableStandardHistory.__table__,
        MetaRelationCheck.__table__,
    ]


def upgrade() -> None:
    from app.db.database import Base

    Base.metadata.create_all(bind=op.get_bind(), tables=_tables())


def downgrade() -> None:
    from app.db.database import Base

    # 逆序 drop：check → history → bind → relation → attribute → object → catalog
    Base.metadata.drop_all(bind=op.get_bind(), tables=list(reversed(_tables())))
