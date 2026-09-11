"""tests/dataops 测试基础设施（沿用 per-schema 隔离思路）。"""
from __future__ import annotations

import logging
import uuid
from typing import Iterator, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser

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

_ENGINES: List[Engine] = []


def dispose_all_engines() -> None:
    while _ENGINES:
        eng = _ENGINES.pop()
        try:
            eng.dispose()
        except Exception:  # noqa: BLE001
            pass


def _tables() -> List:
    from app.models.dataops.data_source import DataSource
    from app.models.dataops.meta import MetaColumn, MetaScanJob, MetaTable
    from app.models.dataops.standard import (
        MetaColumnStandard, MetaColumnStandardHistory, MetaStandard, MetaStandardVersion,
    )
    from app.models.dataops.write_request import DataWriteRequest
    from app.models.dataops.meta_relation import MetaRelation

    return [
        SysUser.__table__,
        DataSource.__table__,
        MetaScanJob.__table__,
        MetaTable.__table__,
        MetaColumn.__table__,
        MetaStandard.__table__,
        MetaStandardVersion.__table__,
        MetaColumnStandard.__table__,
        MetaColumnStandardHistory.__table__,
        DataWriteRequest.__table__,
        MetaRelation.__table__,
    ]


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    """测试环境注入 Fernet 密钥（.env 未配 DATAOPS_ENCRYPTION_KEY 时服务层会拒绝）。"""
    from cryptography.fernet import Fernet

    from app.config import settings

    monkeypatch.setattr(settings, "DATAOPS_ENCRYPTION_KEY", Fernet.generate_key().decode())


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
def schema_name() -> str:
    return f"t_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db_target(schema_name: str, _test_database: None) -> Iterator[str]:
    admin = create_engine(TEST_DB_URL)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    admin.dispose()
    try:
        yield schema_name
    finally:
        dispose_all_engines()
        admin = create_engine(TEST_DB_URL)
        try:
            with admin.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        finally:
            admin.dispose()


@pytest.fixture
def engine(db_target: str) -> Iterator[Engine]:
    # schema_translate_map：把未限定 schema 的表（含 create_all 的 DDL）路由到本测试随机 schema，
    # 杜绝落到 public 造成跨测试污染；search_path 事件：供 inspect/反射按 schema 定位表。
    eng = create_engine(
        TEST_DB_URL, execution_options={"schema_translate_map": {None: db_target}}
    )

    @event.listens_for(eng, "connect")
    def _set_search_path(dbapi_conn, _record):  # noqa: ANN001, ANN202
        with dbapi_conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{db_target}", public')

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


def build_client(db: Session, tenant_id: Optional[int]) -> TestClient:
    """只挂载 dataops 路由的测试客户端（依赖覆盖到测试会话）。"""
    from app.routers.dataops.dataops import router

    app = FastAPI()
    app.include_router(router)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user(tenant_id)
    return TestClient(app)


@pytest.fixture
def client_a(db: Session) -> TestClient:
    return build_client(db, TENANT_A)


@pytest.fixture
def client_b(db: Session) -> TestClient:
    return build_client(db, TENANT_B)
