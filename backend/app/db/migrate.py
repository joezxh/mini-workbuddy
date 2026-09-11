"""启动时确保 kb 表（迁移 006）存在。

设计：基础表由 ``Base.metadata.create_all`` 负责（见 ``app/main.py``），
kb_* 三表（及 HNSW/trgm 索引、pg_trgm 扩展）**独占**交由 alembic 迁移 006 创建。
因此这里只把 alembic 推到 head，让 006 执行；若 ``alembic_version`` 缺失/不一致，
先 stamp 到 005（基础表已被 create_all 建好），避免 001-005 重复建表冲突。
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _repair_half_installed_pg_trgm(engine) -> None:
    """修复本地开发库常见的 pg_trgm 半注册态。

    表现为：``set_limit`` 函数已存在但 ``pg_trgm`` 扩展未登记，导致
    ``CREATE EXTENSION IF NOT EXISTS pg_trgm`` 报 ``set_limit already exists``。
    仅当扩展确实未登记、却残留函数时才 DROP，不会动到健康的 pg_trgm。
    """
    with engine.connect() as c:
        is_registered = c.exec_driver_sql(
            "SELECT 1 FROM pg_extension WHERE extname='pg_trgm'"
        ).first()
        has_set_limit = c.exec_driver_sql(
            "SELECT 1 FROM pg_proc WHERE proname='set_limit'"
        ).first()
    if not is_registered and has_set_limit:
        with engine.begin() as c:
            c.execute(text("DROP EXTENSION IF EXISTS pg_trgm CASCADE"))
        logger.warning("检测到 pg_trgm 半注册态，已自动 DROP 修复（开发库环境怪象）")


def ensure_kb_schema(engine) -> None:
    """确保 kb 表（迁移 006）已应用。

    仅在 ``AUTO_CREATE_TABLES=True``（基础表由 create_all 建好）时由
    ``app/main.py`` 调用；生产环境应置 ``AUTO_CREATE_TABLES=False`` 并直接
    ``alembic upgrade head``（本函数不会在那种情况下被调用）。
    """
    from alembic.config import Config
    from alembic import command

    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))

    _repair_half_installed_pg_trgm(engine)

    with engine.connect() as c:
        has_tbl = c.exec_driver_sql(
            "SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version'"
        ).first()
        current = None
        if has_tbl:
            row = c.exec_driver_sql(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).first()
            current = row[0] if row else None

    # 若 alembic 版本缺失或停在非基础态，先把基线钉到 005（基础表已存在），
    # 让 upgrade head 只跑 006，避免 001-005 与 create_all 重复建表冲突。
    if current is None or current not in (
        "005_add_ontology_modeling_tables",
        "006_kb_tables",
    ):
        command.stamp(cfg, "005_add_ontology_modeling_tables")

    command.upgrade(cfg, "head")
