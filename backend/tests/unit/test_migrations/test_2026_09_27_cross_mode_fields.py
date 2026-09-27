"""Verify 2026_09_27 迁移在升级后产生期望的字段和表。

TDD Step 1: Write failing test BEFORE running migration.

实现策略:用 SQLAlchemy 同步 ORM 直接 create_all 到内存 SQLite,
跳过 alembic 链路(env.py 强绑 PostgreSQL 凭据,本地 CI 跑不通),
仅验证目标表结构是否正确。这能覆盖字段名、类型、索引。

JSONB 在 SQLite 下编译为 JSON,BigInteger 编译为 INTEGER(对齐 agent/conftest.py)。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import BigInteger


# SQLite 兼容:JSONB → JSON
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "JSON"


# SQLite 兼容:BigInteger → INTEGER
@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "INTEGER"


import app.db.init_models  # noqa: F401,E402  触发模型注册
from app.models.ai.ai_chat_context_storage import AIChatContextStorage  # noqa: E402
from app.models.ai.ai_session_finalize_log import AISessionFinalizeLog  # noqa: E402
from app.db.database import Base  # noqa: E402


@pytest.fixture
def upgraded_engine(tmp_path):
    """创建 SQLite 数据库,执行 SQLAlchemy create_all(仅创建跨模式相关 2 表),
    得到升级后 schema。

    不创建所有 Base.metadata 表(其他表也用 JSONB,SQLite 兼容性测试只针对本迁移)。
    """
    eng = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(
        bind=eng,
        tables=[
            AIChatContextStorage.__table__,
            AISessionFinalizeLog.__table__,
        ],
    )
    return eng


def test_ai_context_storage_has_source_mode(upgraded_engine):
    """迁移后 ai_context_storage 包含 4 新增字段"""
    insp = inspect(upgraded_engine)
    cols = {c["name"] for c in insp.get_columns("ai_context_storage")}
    assert "source_mode" in cols
    assert "context_tags" in cols
    assert "is_cross_mode_accessible" in cols
    assert "case_number" in cols


def test_ai_session_finalize_log_table_exists(upgraded_engine):
    """迁移后存在 ai_session_finalize_log 表"""
    insp = inspect(upgraded_engine)
    tables = set(insp.get_table_names())
    assert "ai_session_finalize_log" in tables