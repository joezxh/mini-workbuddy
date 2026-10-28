"""add config_json to meta_data_source (数据源类型特有参数)

数据源类型体系扩展（11 类，对齐 SQLBot）：类型特有连接参数（PG/Kingbase 的
dbSchema、Oracle 的 mode、ES 的认证方式、连接 timeout 等）收进一个 JSON 列，
仿 SQLBot ``DatasourceConf``，避免为每种类型散落新增列。

- config_json: 可空 JSON，永不含密码（密码仍走 password_enc Fernet 列）。
- 存量数据零迁移（均为 NULL，按各自类型默认参数解释）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2026_10_28_0000_add_data_source_config_json"
down_revision: Union[str, None] = "2026_10_18_0002_add_external_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meta_data_source",
        sa.Column("config_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meta_data_source", "config_json")
