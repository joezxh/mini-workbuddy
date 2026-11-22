"""0000_add_menu_color_icon — sys_menu 增加 color_icon 列（菜单彩色图标）。

存 data URL（base64 图片），与现有 antd icon 名共存；彩色图标优先渲染。
不动 icon 字段，避免启动 seed 覆盖彩色图标。

Revision ID: 2026_11_22_0000_menucolor
Revises: 2026_11_08_0002_wsconfig
Create Date: 2026-11-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_11_22_0000_menucolor"
down_revision = "2026_11_08_0002_wsconfig"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sys_menu")}
    if "color_icon" in cols:
        return
    op.add_column(
        "sys_menu",
        sa.Column("color_icon", sa.Text(), nullable=True, comment="菜单彩色图标 data URL（base64）"),
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sys_menu DROP COLUMN IF EXISTS color_icon")
