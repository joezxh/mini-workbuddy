"""rename legacy tables to meta_/kms_ prefixes (production safe).

开发环境由 ``app/main.py`` 的 ``_rename_map`` 在启动时就地改名；本迁移面向
``alembic upgrade head`` 的**生产路径**，必须在 006 之前执行：将历史旧名表
（connector_* / data_source / data_write_request / kb_* / wiki_*）重命名为新的
``meta_`` / ``kms_`` 前缀，使后续 006-010（均已幂等）跳过、并保留既有数据。

为何放在 006 之前：006-010 引用的是新表名（如 010 直接 ``ALTER kms_article_version``），
若旧名表先经过 006-010 会因找不到新名表而失败。故改名必须先于 006。

幂等：仅当「旧表存在且新表不存在」时重命名；新表已存在（全新库或已被
``_rename_map`` 改名）则跳过。索引/约束/序列名保留历史命名（不影响功能）。

生产库若已停在 006（重构前的旧链），本迁移不可达，需先：
    alembic stamp 005 && alembic upgrade head
（stamp 不执行 downgrade，旧表数据保留，随后本迁移改名、006-010 跳过。）

Revision ID: 011_rename_legacy_tables
Revises: 005_add_ontology_modeling_tables
"""
from alembic import op
from sqlalchemy import inspect

revision = "011_rename_legacy_tables"
down_revision = "005_add_ontology_modeling_tables"
branch_labels = None
depends_on = None

# (old_name, new_name) —— 与 app/main.py 的 _rename_map 对齐
RENAMES = [
    ("connector_ingest", "meta_connector_ingest"),
    ("connector_sync_state", "meta_connector_sync_state"),
    ("connector_instance", "meta_connector_instance"),
    ("connector_sync_log", "meta_connector_sync_log"),
    ("data_source", "meta_data_source"),
    ("data_write_request", "meta_data_write_request"),
    ("kb_collection", "kms_collection"),
    ("kb_ref", "kms_ref"),
    ("kb_segment", "kms_segment"),
    ("wiki_article", "kms_article"),
    ("wiki_article_version", "kms_article_version"),
    ("wiki_category", "kms_category"),
    ("wiki_knowledge", "kms_knowledge"),
    ("wiki_search_log", "kms_search_log"),
]


def upgrade() -> None:
    existing = {t.lower() for t in inspect(op.get_bind()).get_table_names()}
    for old, new in RENAMES:
        if old in existing and new not in existing:
            op.rename_table(old, new)


def downgrade() -> None:
    existing = {t.lower() for t in inspect(op.get_bind()).get_table_names()}
    for new, old in RENAMES:
        if new in existing and old not in existing:
            op.rename_table(new, old)
