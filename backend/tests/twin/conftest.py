"""tests/twin 测试基础设施（per-schema 隔离，模板为 tests/ontology/conftest.py）。

与 ontology 版的三处差异（计划 Task 1 Step 2）：
1. ``_tables()`` 追加 ``app.models.ontology.query`` 与 ``app.models.twin``（import 即注册元数据，
   否则 ``Base.metadata.sorted_tables`` 看不到新表，create_all 不建）；
2. ``build_client()`` 增 ``with_twin`` 开关：孪生 router 到 Task 6 才诞生，
   用函数内延迟 import，Task 1–5 的用例不触碰它；
3. 追加 ``ontology_factory`` 夹具（建一条 current_version=1 的本体，返回 id）。
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
OTHER_USER_ID = 9001     # 同租户内的第二个身份：T12 的申请人（与 TENANT_A 推导出的 101 不撞）
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
    # 本体层 + 孪生层模型 import 即注册元数据
    import app.models.dataops.data_source  # noqa: F401
    import app.models.dataops.meta  # noqa: F401
    import app.models.dataops.standard  # noqa: F401
    import app.models.dataops.standard_cdm  # noqa: F401
    import app.models.dataops.meta_relation  # noqa: F401
    import app.models.dataops.write_request  # noqa: F401
    import app.models.ontology.asset_tag  # noqa: F401
    import app.models.ontology.ontology  # noqa: F401
    import app.models.ontology.query  # noqa: F401  ← onto_ontology_query
    import app.models.twin  # noqa: F401            ← twin_* 六表
    import app.models.sys.sys_dictionary  # noqa: F401

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


def _fake_user(tenant_id: Optional[int], user_id: Optional[int] = None) -> SysUser:
    user = SysUser()
    # 不传 user_id 时保持 Task 1/6/7/8 的行为逐字不变（TENANT_A → 101、TENANT_B → 201），
    # 否则那两个任务的夹具与断言（写死 owner_id=101）会整批错。
    user.user_id = int(user_id) if user_id is not None else (
        abs(tenant_id) + 1 if tenant_id is not None else 1)
    user.username = f"user-{tenant_id}"
    user.status = "active"
    user.is_admin = False
    user.tenant_id = tenant_id
    return user


def build_client(db: Session, tenant_id: Optional[int], *, with_twin: bool = False,
                 with_publish: bool = False,
                 as_user_id: Optional[int] = None) -> TestClient:
    """挂载 dataops 父 router（含 ontology 子 router）的测试客户端。

    ``with_twin=True`` 额外挂 ``/api/v1/twins`` 路由（Task 6 起可用）；
    ``with_publish=True`` 再挂 ``/api/v1/twin-p`` 只读页路由（Task 8 起可用）；
    ``as_user_id`` 只换身份不换租户（Task 9 的申请人/审批人两人同租）；
    默认均为 False，故 Task 1–5 阶段不会去 import 尚不存在的孪生 router。
    """
    from app.routers.dataops.dataops import router as dataops_router

    app = FastAPI()
    app.include_router(dataops_router)
    if with_twin or with_publish:
        from app.routers.twin.twin import router as twin_router
        app.include_router(twin_router)
    if with_publish:
        # 只读页要取数，而取数在**主 router** 上（T8/T9）；发布端点 T10 也在主 router。
        # 所以 with_publish 必须把两个 router 都挂上，而不是只挂 publish_router。
        from app.routers.twin.twin import publish_router
        app.include_router(publish_router)

    # 与服务运行时同一错误契约：ApiError → {code, message, detail?}（main.py 亦如此注册）
    from app.core.api_error import register_api_error_handler

    register_api_error_handler(app)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user(tenant_id, as_user_id)
    return TestClient(app)


@pytest.fixture
def client_a(db: Session) -> TestClient:
    return build_client(db, TENANT_A)


@pytest.fixture
def client_b(db: Session) -> TestClient:
    return build_client(db, TENANT_B)


@pytest.fixture
def twin_client_a(db: Session) -> TestClient:
    """带 /api/v1/twins/* 与 /twin-p/* 的客户端（Task 6 起使用）。"""
    return build_client(db, TENANT_A, with_twin=True)


@pytest.fixture
def twin_client_b(db: Session) -> TestClient:
    return build_client(db, TENANT_B, with_twin=True)


@pytest.fixture
def publish_client_a(db: Session) -> TestClient:
    """同时挂 `/api/v1/twins/*`（T10 发布 + T8 取数）与 `/api/v1/twin-p/*`（T11 只读页）。"""
    return build_client(db, TENANT_A, with_publish=True)


@pytest.fixture
def publish_client_b(db: Session) -> TestClient:
    return build_client(db, TENANT_B, with_publish=True)


@pytest.fixture
def twin_client_a_as_other(db: Session) -> TestClient:
    """B 身份看 A 租户：T12 的申请人与审批人必须是两个不同 `user_id`。"""
    return build_client(db, TENANT_A, with_twin=True, as_user_id=OTHER_USER_ID)


@pytest.fixture
def ontology_factory(db: Session):
    """创建一个 current_version=1 的本体，返回其 id。"""
    def _make() -> int:
        oid = db.execute(
            text("INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
                 "VALUES (:t, gen_random_uuid()::text, '演示本体', 'published', 1) "
                 "RETURNING id"),
            {"t": TENANT_A},
        ).scalar_one()
        db.commit()
        return int(oid)

    return _make
