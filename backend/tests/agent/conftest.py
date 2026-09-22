"""tests/agent 测试基础设施（per-schema 隔离，对齐 dataops/ontology）。

默认连 PostgreSQL 测试库 `minworkbuddy_test`（与生产方言一致，是验收目标）。
若设置 ``MINWORKBUDDY_TEST_DB_URL`` 指向 SQLite，则退化为文件库，便于无 PG 环境
本地验证逻辑（仅方言兜底，不改变生产行为）。

仅挂载 `agent_run` 路由（/api/v1/agents/executions），依赖覆盖到测试会话与假用户。
"""
from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import Iterator, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, event, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.deps import get_current_user, get_db
from app.models.agent.agent_execution_event import AgentExecutionEvent
from app.models.sys.sys_user import SysUser

TENANT_A = 100
TEST_DB_NAME = "minworkbuddy_test"

logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "JSON"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "INTEGER"


def _test_db_url() -> str:
    override = os.getenv("MINWORKBUDDY_TEST_DB_URL")
    if override:
        return override
    from urllib.parse import quote_plus

    from app.config import settings

    password = quote_plus(settings.DB_PASSWORD)
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{TEST_DB_NAME}"
    )


TEST_DB_URL = _test_db_url()
IS_POSTGRES = make_url(TEST_DB_URL).get_backend_name() == "postgresql"

_ENGINES: List[Engine] = []


def dispose_all_engines() -> None:
    while _ENGINES:
        eng = _ENGINES.pop()
        try:
            eng.dispose()
        except Exception:  # noqa: BLE001
            pass


def _tables() -> List:
    return [SysUser.__table__, AgentExecutionEvent.__table__]


@pytest.fixture(scope="session")
def _test_database() -> Iterator[None]:
    if not IS_POSTGRES:
        yield
        return
    maint = create_engine(make_url(TEST_DB_URL).set(database="postgres"), isolation_level="AUTOCOMMIT")
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
def db_target(_test_database: None) -> Iterator[str]:
    if IS_POSTGRES:
        name = f"t_{uuid.uuid4().hex[:12]}"
        admin = create_engine(TEST_DB_URL)
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{name}"'))
        admin.dispose()
        try:
            yield name
        finally:
            dispose_all_engines()
            admin = create_engine(TEST_DB_URL)
            try:
                with admin.begin() as conn:
                    conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
            finally:
                admin.dispose()
    else:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            yield f"sqlite:///{path}"
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


@pytest.fixture
def engine(db_target: str) -> Iterator[Engine]:
    if IS_POSTGRES:
        eng = create_engine(
            TEST_DB_URL, execution_options={"schema_translate_map": {None: db_target}}
        )

        @event.listens_for(eng, "connect")
        def _set_search_path(dbapi_conn, _record):  # noqa: ANN001, ANN202
            with dbapi_conn.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{db_target}", public')
    else:
        eng = create_engine(db_target)
    _ENGINES.append(eng)
    Base.metadata.create_all(eng, tables=_tables())
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


def _fake_user(tenant_id: Optional[int]) -> SysUser:
    user = SysUser()
    user.user_id = abs(tenant_id) + 1 if tenant_id is not None else 1
    user.username = f"user-{tenant_id}"
    user.status = "active"
    user.is_admin = False
    user.tenant_id = tenant_id
    return user


def build_client(session: Session, tenant_id: Optional[int] = None) -> TestClient:
    """挂载 agent_run 路由的测试客户端（依赖覆盖到测试会话）。"""
    from app.routers.agent.agent_run import router

    app = FastAPI()
    # router 自身带 prefix=/agents/executions，注册处再叠加 /api/v1
    app.include_router(router, prefix="/api/v1")

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user(tenant_id)
    return TestClient(app)


@pytest.fixture
def client(db: Session) -> TestClient:
    return build_client(db, TENANT_A)
