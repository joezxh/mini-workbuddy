"""seed data_source_type 字典（数据源类型统一配置）

数据源模块类型体系扩展：11 种类型（Excel/CSV、MySQL、Oracle、PostgreSQL、
SQL Server、ClickHouse、达梦、Apache Doris、ElasticSearch、Kingbase、StarRocks）
落到 ``sys_dictionary`` / ``sys_dictionary_item``（dict_code=data_source_type），
由「系统管理 → 数据字典」统一维护；``extra_data`` 携带连接参数声明
（family/default_port/fields），前端表单按此动态渲染。

- seed 数据源 = app/services/dataops/source_types.py 的 TYPE_META（单一事实来源）；
- 幂等：字典或字典项已存在则跳过（管理员可能已手工配置）；
- tenant_id 置 NULL（全局字典，与既有字典行为一致）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_10_28_0001_seed_data_source_type_dict"
down_revision: Union[str, None] = "2026_10_28_0000_add_data_source_config_json"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DICT_CODE = "data_source_type"

_dictionary = sa.table(
    "sys_dictionary",
    sa.column("dict_code", sa.String),
    sa.column("dict_name", sa.String),
    sa.column("dict_type", sa.String),
    sa.column("description", sa.Text),
    sa.column("sort_order", sa.Integer),
    sa.column("is_active", sa.Boolean),
    sa.column("is_deleted", sa.Boolean),
)
_dictionary_item = sa.table(
    "sys_dictionary_item",
    sa.column("dict_code", sa.String),
    sa.column("item_code", sa.String),
    sa.column("item_name", sa.String),
    sa.column("item_value", sa.String),
    sa.column("level", sa.Integer),
    sa.column("color", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("is_active", sa.Boolean),
    sa.column("extra_data", sa.JSON),
    sa.column("is_deleted", sa.Boolean),
)


def upgrade() -> None:
    from app.services.dataops.source_types import seed_rows

    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM sys_dictionary WHERE dict_code = :c LIMIT 1"), {"c": DICT_CODE}
    ).first()
    if exists is None:
        op.bulk_insert(_dictionary, [{
            "dict_code": DICT_CODE,
            "dict_name": "数据源类型",
            "dict_type": "dataops",
            "description": "数据源管理可选类型；启用/停用即时生效于新建表单下拉",
            "sort_order": 0,
            "is_active": True,
            "is_deleted": False,
        }])
    for row in seed_rows():
        dup = bind.execute(
            sa.text("SELECT 1 FROM sys_dictionary_item WHERE dict_code = :c AND item_code = :i LIMIT 1"),
            {"c": DICT_CODE, "i": row["item_code"]},
        ).first()
        if dup is None:
            op.bulk_insert(_dictionary_item, [row])


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM sys_dictionary_item WHERE dict_code = :c"), {"c": DICT_CODE})
    bind.execute(sa.text("DELETE FROM sys_dictionary WHERE dict_code = :c"), {"c": DICT_CODE})
