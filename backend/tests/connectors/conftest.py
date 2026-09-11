"""tests/connectors 测试基础设施（per-schema 隔离，schema_translate_map 路由）。"""
from __future__ import annotations

import uuid
from typing import Iterator, List

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.connectors.connector_record import ConnectorIngest, ConnectorSyncState
from app.models.sys.sys_user import SysUser

TEST_DB_NAME = "minworkbuddy_test"


def _test_db_url() -> str:
    from urllib.parse import quote_plus
    from app.config import settings

    password = quote_plus(settings.DB_PASSWORD)
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{TEST_DB_NAME}"
    )


def _tables() -> List:
    return [
        SysUser.__table__,
        ConnectorIngest.__table__,
        ConnectorSyncState.__table__,
    ]


@pytest.fixture(scope="session")
def _test_database() -> Iterator[None]:
    url = _test_db_url()
    if make_url(url).get_backend_name() != "postgresql":
        yield
        return
    maint = create_engine(make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with maint.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        maint.dispose()
    yield


@pytest.fixture
def schema_name() -> str:
    return f"t_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def engine(schema_name: str, _test_database: None) -> Iterator[Engine]:
    url = _test_db_url()
    # schema_translate_map 把未限定 schema 的表统一路由到本次测试的随机 schema，
    # 比 SET search_path 事件更可靠（create_all 的 DDL 也走此映射，不会落到 public）。
    eng = create_engine(
        url, execution_options={"schema_translate_map": {None: schema_name}}
    )
    with eng.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    Base.metadata.create_all(eng, tables=_tables())
    try:
        yield eng
    finally:
        eng.dispose()
        admin = create_engine(url)
        try:
            with admin.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        finally:
            admin.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
