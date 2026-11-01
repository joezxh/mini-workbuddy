"""tests/sandbox 测试基础设施（per-schema 隔离，复制 tests/ontology/conftest.py 三处修改）。

与 ontology 版的差异：
- ``_tables()`` 追加 sandbox 域模型 import（onto_sandbox_* / onto_action_template）；
- ``engine`` fixture 建表后插入内置行动模板种子（测试库不跑 alembic，
  与迁移 0011 共用 app.models.sandbox.template_seed 同一真源）；
- 测试客户端仍挂 dataops 父 router（sandbox router 将挂在同一父 router 下）。
"""
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
    # 清单与 tests/ontology 一致（最小依赖集），追加沙箱域两文件；
    # branch↔checkpoint 互 FK 成环由 create_all 的 cycle-ALTER 处理。
    import app.models.dataops.data_source  # noqa: F401
    import app.models.dataops.meta  # noqa: F401
    import app.models.dataops.standard  # noqa: F401
    import app.models.dataops.standard_cdm  # noqa: F401
    import app.models.dataops.meta_relation  # noqa: F401
    import app.models.dataops.write_request  # noqa: F401
    import app.models.ontology.asset_tag  # noqa: F401
    import app.models.ontology.ontology  # noqa: F401
    import app.models.sandbox.sandbox  # noqa: F401
    import app.models.sandbox.action_template  # noqa: F401
    import app.models.sys.sys_user  # noqa: F401

    # 与 main.py 同一纪律：检索三表由迁移 006 独占（pg_trgm/HNSW 索引），不进 create_all
    kb_retrieval = {"kms_collection", "kms_segment", "kms_ref"}
    return [t for t in Base.metadata.sorted_tables if t.name not in kb_retrieval]


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
    # schema_translate_map：把未限定 schema 的表路由到本测试随机 schema，杜绝落到 public 污染
    eng = create_engine(
        TEST_DB_URL, execution_options={"schema_translate_map": {None: db_target}}
    )

    @event.listens_for(eng, "connect")
    def _set_search_path(dbapi_conn, _record):  # noqa: ANN001, ANN202
        with dbapi_conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{db_target}", public')

    _ENGINES.append(eng)
    Base.metadata.create_all(eng, tables=_tables())
    _seed_action_templates(eng)
    try:
        yield eng
    finally:
        eng.dispose()


def _seed_action_templates(eng: Engine) -> None:
    """建表后插入内置模板种子（与迁移 0011 共用 template_seed 真源）。"""
    import json

    from app.models.sandbox.template_seed import ACTION_TEMPLATE_SEEDS

    with eng.begin() as conn:
        for code, name, domain, ps, es in ACTION_TEMPLATE_SEEDS:
            conn.execute(
                text(
                    "INSERT INTO onto_action_template "
                    "(code, name, domain_hint, param_schema_json, effect_spec_json, status) "
                    "VALUES (:c, :n, :d, CAST(:ps AS jsonb), CAST(:es AS jsonb), 'enabled') "
                    "ON CONFLICT (code) DO NOTHING"
                ),
                {
                    "c": code, "n": name, "d": domain,
                    "ps": json.dumps(ps), "es": json.dumps(es),
                },
            )


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
    """挂载 dataops 父 router（含 sandbox 子 router）的测试客户端。"""
    from app.routers.dataops.dataops import router

    app = FastAPI()
    app.include_router(router)

    # 与服务运行时同一错误契约：ApiError → {code, message, detail?}（main.py 亦如此注册）
    from app.core.api_error import register_api_error_handler

    register_api_error_handler(app)

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
