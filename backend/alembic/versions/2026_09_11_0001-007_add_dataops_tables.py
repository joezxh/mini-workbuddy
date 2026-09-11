"""add dataops tables (P2 Task 2)

9 张表，全部含 tenant_id。实现方式：直接以 ORM 元数据建表
（app/models/dataops/ 是唯一事实来源），避免在迁移里二次声明列定义造成漂移；
列注释 / 索引 / 唯一约束均随 ORM。

Revision ID: 007_dataops_tables
Revises: 006_kb_tables
"""
from alembic import op

revision = "007_dataops_tables"
down_revision = "006_kb_tables"
branch_labels = None
depends_on = None


def _tables():
    from app.models.dataops.data_source import DataSource
    from app.models.dataops.meta import MetaColumn, MetaScanJob, MetaTable
    from app.models.dataops.standard import (
        MetaColumnStandard, MetaColumnStandardHistory, MetaStandard, MetaStandardVersion,
    )
    from app.models.dataops.write_request import DataWriteRequest

    return [
        DataSource.__table__,
        MetaScanJob.__table__,
        MetaTable.__table__,
        MetaColumn.__table__,
        MetaStandard.__table__,
        MetaStandardVersion.__table__,
        MetaColumnStandard.__table__,
        MetaColumnStandardHistory.__table__,
        DataWriteRequest.__table__,
    ]


def upgrade() -> None:
    from app.db.database import Base

    Base.metadata.create_all(bind=op.get_bind(), tables=_tables())


def downgrade() -> None:
    from app.db.database import Base

    Base.metadata.drop_all(bind=op.get_bind(), tables=list(reversed(_tables())))
