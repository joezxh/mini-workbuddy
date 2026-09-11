"""tests/kb 测试基础设施（镜像 tests/ontology/conftest 的 per-schema 隔离思路）。

每个用例一个独立 PostgreSQL schema（t_<uuid>），用例结束 DROP SCHEMA ... CASCADE，
用例间完全隔离；只建 kb 三张表（不加迁移里的 HNSW/trgm 索引，那些留给 Task 4/5）。

连接串来自 ``app.config.settings``，库名固定为 ``minworkbuddy_test``。
"""
from __future__ import annotations

import logging
import uuid
from typing import Iterator, List, Optional

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url, URL
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.kb.kb_collection import KbCollection
from app.models.kb.kb_segment import KbSegment
from app.models.kb.kb_ref import KbRef

TENANT_A = 100
TENANT_B = 200

TEST_DB_NAME = "minworkbuddy_test"

logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def _test_db_url() -> str:
    from urllib.parse import quote_plus

    from app.config import settings

    password = quote_plus(settings.DB_PASSWORD)
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{TEST_DB_NAME}"
    )


TEST_DB_URL = _test_db_url()
IS_POSTGRES = make_url(TEST_DB_URL).get_backend_name() == "postgresql"

KB_TABLES = [KbCollection.__table__, KbSegment.__table__, KbRef.__table__]


def _maintenance_url() -> URL:
    return make_url(TEST_DB_URL).set(database="postgres")


_ENGINES: List[Engine] = []


def dispose_all_engines() -> None:
    while _ENGINES:
        eng = _ENGINES.pop()
        try:
            eng.dispose()
        except Exception:  # noqa: BLE001
            pass


@pytest.fixture(scope="session")
def _test_database() -> Iterator[None]:
    if not IS_POSTGRES:
        yield
        return

    maint = create_engine(_maintenance_url(), isolation_level="AUTOCOMMIT")
    try:
        with maint.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DB_NAME},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        maint.dispose()

    bootstrap = create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT")
    try:
        with bootstrap.connect() as conn:
            # kb_segment.embedding 是 pgvector 列，需 vector 扩展
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # pg_trgm：Task 5 中文混合检索（similarity + gin_trgm_ops）依赖
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        bootstrap.dispose()
    yield


@pytest.fixture
def schema_name() -> str:
    return f"t_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db_target(schema_name: str, _test_database: None) -> Iterator[str]:
    target = schema_name
    admin = create_engine(TEST_DB_URL)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{target}"'))
    admin.dispose()
    try:
        yield target
    finally:
        dispose_all_engines()
        admin = create_engine(TEST_DB_URL)
        try:
            with admin.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{target}" CASCADE'))
        finally:
            admin.dispose()


def _bind_schema(eng: Engine, schema: str) -> None:
    @event.listens_for(eng, "connect")
    def _set_search_path(dbapi_conn, _record):  # noqa: ANN001, ANN202
        with dbapi_conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}", public')


@pytest.fixture
def engine(db_target: str) -> Iterator[Engine]:
    eng = create_engine(TEST_DB_URL)
    _bind_schema(eng, db_target)
    _ENGINES.append(eng)
    Base.metadata.create_all(eng, tables=KB_TABLES)
    # 镜像迁移 006：为 content 列建 GIN trigram 索引（Task 5 中文混合检索）
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_kb_segment_content_trgm "
                "ON kb_segment USING gin (content gin_trgm_ops)"
            )
        )
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
