"""tests/ontology 测试基础设施（per-schema 隔离，仿 tests/dataops/conftest.py）。

与 dataops 版的差异（spec 2026-11-01 §8 测试计划）：
- 建表清单用 ``Base.metadata.sorted_tables`` 排除迁移 006 独占的检索三表
  （``kms_collection``/``kms_segment``/``kms_ref``），与 main.py AUTO_CREATE 同一纪律；
- import ``app.models.ontology.*`` 保证 onto_* 元数据注册；
- 测试客户端挂载 dataops 父 router（已含 ontology 子 router，前缀 /api/v1/dataops）。
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
    # 本体层模型 import 即注册元数据（asset_tag 与 ontology 覆盖全部 onto_* 表）
    import app.models.dataops.data_source  # noqa: F401
    import app.models.dataops.meta  # noqa: F401
    import app.models.dataops.standard  # noqa: F401
    import app.models.dataops.standard_cdm  # noqa: F401
    import app.models.dataops.meta_relation  # noqa: F401
    import app.models.dataops.write_request  # noqa: F401
    import app.models.ontology.asset_tag  # noqa: F401
    import app.models.ontology.ontology  # noqa: F401
    import app.models.ontology.query  # noqa: F401  ← onto_ontology_query
    import app.models.twin  # noqa: F401            ← twin_* 六表（bound_widget 夹具需要）
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


def _fake_user(tenant_id: Optional[int]) -> SysUser:
    user = SysUser()
    user.user_id = abs(tenant_id) + 1 if tenant_id is not None else 1
    user.username = f"user-{tenant_id}"
    user.status = "active"
    user.is_admin = False
    user.tenant_id = tenant_id
    return user


def build_client(db: Session, tenant_id: Optional[int]) -> TestClient:
    """挂载 dataops 父 router（含 ontology 子 router）的测试客户端。"""
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


@pytest.fixture
def seeded_ontology(db: Session, schema_name: str) -> dict:
    """最小可编译本体：真实形状的版本快照 + accepted 映射 + 三张可查的 demo 表。

    设该夹具的三个硬约束：
    1. demo 表建在**本测试的随机 schema**（db 连接的 search_path 已指向它），
       而 MetaTable.database 也写该 schema——编译产物因此带限定名，
       能被 ReadonlyQueryService 另建的引擎（默认 search_path）直接看到；
    2. DataSource 密码必须用 ``encrypt_secret`` 写 ``password_enc``，
       因为建连走 ``DataSourceService.reveal_password`` 会解密（Fernet 密钥由
       本文件 autouse 夹具 ``_encryption_key`` 注入）；
    3. 一个对象一张表、一个列一个标准项：``uq_meta_table_standard_table`` 与
       ``uq_meta_column_standard_column`` 都是单列 UNIQUE，所以 o_site 有自己的
       demo_site_stat、a_pending 占自己的 note 列，共用会撞 UniqueViolation。
    """
    import json

    from app.ai.dataops.crypto import encrypt_secret
    from app.config import settings

    tid = TENANT_A
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731

    # ---------- 1. 三张真实可查的 demo 表（落在本测试 schema） ----------
    ex(f'CREATE TABLE "{schema_name}".demo_device_stat '
       f'(dev_code text, oee numeric, id_card text, ts_posted timestamp, note text)')
    ex(f'CREATE TABLE "{schema_name}".demo_line_stat (line_code text, dev_code text)')
    # o_site 必须有自己的物理表：uq_meta_table_standard_table 是 UNIQUE(table_id)，
    # 一张表只能绑一个对象标准，「多个对象共用同一张表」在真实系统里根本建不出来。
    ex(f'CREATE TABLE "{schema_name}".demo_site_stat (site_code text, dev_code text)')
    ex(f'INSERT INTO "{schema_name}".demo_device_stat '
       f'(dev_code, oee, id_card, ts_posted, note) VALUES (\'D1\', 0.85, \'310101199001011234\', now(), NULL)')
    ex(f'INSERT INTO "{schema_name}".demo_line_stat VALUES (\'L1\', \'D1\')')
    ex(f'INSERT INTO "{schema_name}".demo_site_stat VALUES (\'S1\', \'D1\')')

    dsid = ex(
        "INSERT INTO meta_data_source (tenant_id, name, source_type, external_type, host, port, "
        "username, password_enc, database, status) "
        "VALUES (:t,'twin-demo','postgresql','rdbms',:h,:p,:u,:pw,:db,'online') RETURNING id",
        {"t": tid, "h": settings.DB_HOST, "p": int(settings.DB_PORT), "u": settings.DB_USER,
         "pw": encrypt_secret(str(settings.DB_PASSWORD)), "db": TEST_DB_NAME},
    ).scalar_one()

    def table(name: str) -> int:
        return ex(
            "INSERT INTO meta_table (tenant_id, source_id, db_name, database, table_name) "
            "VALUES (:t,:s,:db,:sc,:n) RETURNING id",
            {"t": tid, "s": dsid, "db": TEST_DB_NAME, "sc": schema_name, "n": name},
        ).scalar_one()

    tb_dev, tb_line = table("demo_device_stat"), table("demo_line_stat")
    tb_site = table("demo_site_stat")

    def column(table_id: int, name: str, ordinal: int, pii: str) -> int:
        return ex(
            "INSERT INTO meta_column (tenant_id, table_id, column_name, ordinal, pii_level) "
            "VALUES (:t,:tb,:n,:o,:p) RETURNING id",
            {"t": tid, "tb": table_id, "n": name, "o": ordinal, "p": pii},
        ).scalar_one()

    c_dev_code = column(tb_dev, "dev_code", 1, "L0")
    c_oee = column(tb_dev, "oee", 2, "L1")
    c_id_card = column(tb_dev, "id_card", 3, "L2")     # 敏感且标准无 mask_rule → 触发敏感闸
    column(tb_dev, "ts_posted", 4, "L0")
    c_note = column(tb_dev, "note", 5, "L0")
    c_line_code = column(tb_line, "line_code", 1, "L0")
    c_line_dev = column(tb_line, "dev_code", 2, "L0")  # 与 dev 侧同名，是 JOIN 的连接键
    c_site_dev = column(tb_site, "dev_code", 2, "L0")  # o_site 侧的 JOIN 连接键

    # ---------- 2. 模式层：对象 / 标准项 ----------
    def obj(code: str, name: str, review: str = "accepted") -> int:
        return ex(
            "INSERT INTO meta_object_standard (tenant_id, code, name, status, review_status, source) "
            "VALUES (:t,:c,:n,'published',:r,'human') RETURNING id",
            {"t": tid, "c": code, "n": name, "r": review},
        ).scalar_one()

    def std(code: str, name: str, mask: str = "keep_first2", level: str = "L1") -> int:
        return ex(
            "INSERT INTO meta_standard (tenant_id, code, name, status, security_level, mask_rule) "
            "VALUES (:t,:c,:n,'published',:l,:m) RETURNING id",
            {"t": tid, "c": code, "n": name, "l": level, "m": mask},
        ).scalar_one()

    dev, line, site = obj("o_dev", "设备"), obj("o_line", "产线"), obj("o_site", "园区")
    obj("o_nomap", "未映射对象")                        # accepted 但未绑表 → ③ 失败路径
    a_oee = std("a_oee", "设备OEE")
    a_idcard = std("a_idcard", "身份证号", mask=None)      # 无脱敏规则 → ④ 敏感闸拦截
    a_devcode = std("a_devcode", "设备编码")
    a_linecode = std("a_linecode", "产线编码")
    a_pending = std("a_pending", "待采纳属性")

    # ---------- 3. 对象↔属性（快照里的 properties） ----------
    prop_rows = []

    def prop(object_id: int, standard_id: int, review: str = "accepted") -> None:
        pid = ex(
            "INSERT INTO meta_object_standard_attribute (tenant_id, object_id, standard_id, "
            "required, sort_order, review_status) "
            "VALUES (:t,:o,:s,false,0,:r) RETURNING id",
            {"t": tid, "o": object_id, "s": standard_id, "r": review},
        ).scalar_one()
        prop_rows.append({"id": int(pid), "object_id": int(object_id),
                          "standard_id": int(standard_id), "required": False,
                          "review_status": review})

    prop(dev, a_devcode)
    prop(dev, a_oee)
    prop(dev, a_idcard)
    prop(dev, a_pending, review="suggested")            # ② 未采纳路径
    prop(line, a_linecode)
    prop(line, a_devcode)
    prop(site, a_devcode)

    # ---------- 4. 物理映射（status=accepted） ----------
    table_map_rows = []

    def bind_table(object_id: int, table_id: int) -> None:
        mid = ex(
            "INSERT INTO meta_table_standard (tenant_id, table_id, object_standard_id, status, source) "
            "VALUES (:t,:tb,:o,'accepted','human') RETURNING id",
            {"t": tid, "tb": table_id, "o": object_id},
        ).scalar_one()
        table_map_rows.append({"id": int(mid), "table_id": int(table_id),
                               "object_standard_id": int(object_id), "source": "human"})

    column_map_rows = []

    def bind_column(column_id: int, standard_id: int) -> None:
        mid = ex(
            "INSERT INTO meta_column_standard (tenant_id, column_id, standard_id, status, source) "
            "VALUES (:t,:c,:s,'accepted','human') RETURNING id",
            {"t": tid, "c": column_id, "s": standard_id},
        ).scalar_one()
        column_map_rows.append({"id": int(mid), "column_id": int(column_id),
                                "standard_id": int(standard_id), "source": "human"})

    bind_table(dev, tb_dev)          # o_nomap 故意不绑
    bind_table(line, tb_line)
    bind_table(site, tb_site)
    bind_column(c_dev_code, a_devcode)
    bind_column(c_oee, a_oee)
    bind_column(c_id_card, a_idcard)
    bind_column(c_line_code, a_linecode)
    bind_column(c_line_dev, a_devcode)
    bind_column(c_site_dev, a_devcode)
    bind_column(c_note, a_pending)  # 列侧已绑，但属性 review_status=suggested
    # 注：uq_meta_column_standard_column 是 UNIQUE(column_id)——一个物理列只能绑
    # 一个标准项，故 a_pending 必须占自己的列，不能搭 c_dev_code 的车。

    # ---------- 5. 关系：o_dev→o_line 唯一路径；o_dev↔o_site 两条→歧义 ----------
    rel_rows = []

    def relation(code: str, from_id: int, to_id: int, via: list, review: str = "accepted") -> int:
        rid = ex(
            "INSERT INTO meta_object_relation (tenant_id, code, name, from_object_id, to_object_id, "
            "relation_type, via_attribute_ids, status, source, review_status) "
            "VALUES (:t,:c,:n,:f,:to,'N:1',CAST(:v AS jsonb),'published','human',:r) RETURNING id",
            {"t": tid, "c": code, "n": code, "f": from_id, "to": to_id,
             "v": json.dumps([int(x) for x in via]), "r": review},
        ).scalar_one()
        rel_rows.append({"id": int(rid), "code": code, "name": code,
                         "from_object_id": int(from_id), "to_object_id": int(to_id),
                         "relation_type": "N:1", "source": "human", "review_status": review})
        return int(rid)

    relation("r_dev_line", dev, line, [a_devcode])
    relation("r_dev_site_a", dev, site, [a_devcode])
    relation("r_dev_site_b", site, dev, [a_devcode])   # 同一对对象的第二条路径
    db.commit()

    # ---------- 6. 版本快照（逐字段对齐 build_snapshot 输出） ----------
    snap = {
        "objects": [
            {"id": int(dev), "code": "o_dev", "name": "设备", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
            {"id": int(line), "code": "o_line", "name": "产线", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
            {"id": int(site), "code": "o_site", "name": "园区", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
            {"id": int(ex("SELECT id FROM meta_object_standard WHERE tenant_id=:t AND code='o_nomap'",
                          {"t": tid}).scalar_one()),
             "code": "o_nomap", "name": "未映射对象", "domain": None, "aliases": [],
             "source": "human", "review_status": "accepted", "confidence": None},
        ],
        "relations": rel_rows,
        "properties": prop_rows,
        "mappings": {"table": table_map_rows, "column": column_map_rows},
        "cq": [],
    }
    oid = ex(
        "INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
        "VALUES (:t,'twin_demo','孪生演示本体','published',1) RETURNING id", {"t": tid}
    ).scalar_one()
    vid = ex(
        "INSERT INTO onto_ontology_version (tenant_id, ontology_id, version, snapshot_json) "
        "VALUES (:t,:o,1,CAST(:s AS jsonb)) RETURNING id",
        {"t": tid, "o": oid, "s": json.dumps(snap, ensure_ascii=False)},
    ).scalar_one()
    db.commit()

    return {
        "id": int(oid), "version": int(vid), "source_id": int(dsid),
        "schema": schema_name, "table": "demo_device_stat", "table_line": "demo_line_stat",
        "table_site": "demo_site_stat",
        "objects": {"o_dev": int(dev), "o_line": int(line), "o_site": int(site)},
        "attributes": {"a_oee": int(a_oee), "a_idcard": int(a_idcard),
                       "a_devcode": int(a_devcode), "a_linecode": int(a_linecode)},
    }


@pytest.fixture
def bound_widget(db: Session, seeded_ontology) -> dict:
    """一条真实引用 query_id 的孪生组件，用于验证 Q5 的 WIDGET_IN_USE 拦截。

    列名逐字对齐 Task 1 模型：卡片用 ``ontology_version``/``runtime_state``/``owner_id``
    （没有 ``version``/``status`` 列），页面只有 ``sort_order``/``refresh_json``（无布局列）。
    ``owner_id`` 无外键，取 101——即 ``_fake_user(TENANT_A)`` 的 user_id，与 client_a 同一人。
    """
    from sqlalchemy import text

    from tests.ontology.conftest import TENANT_A
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    qid = ex(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, "
        "result_shape, spec_json, status) VALUES (:t,:o,1,'q_bound','绑定中','kpi',"
        "CAST(:s AS jsonb),'enabled') RETURNING id",
        {"t": TENANT_A, "o": seeded_ontology["id"], "s": '{"objects":["o_dev"],"attributes":["a_oee"]}'},
    ).scalar_one()
    cid = ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
             "runtime_state, owner_id) VALUES (:t,'卡',:o,1,'draft',101) RETURNING id",
             {"t": TENANT_A, "o": seeded_ontology["id"]}).scalar_one()
    pid = ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
             "VALUES (:t,:c,'页',0) RETURNING id", {"t": TENANT_A, "c": cid}).scalar_one()
    wid = ex("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
             "VALUES (:t,:p,'kpi','组件',:q,0) RETURNING id",
             {"t": TENANT_A, "p": pid, "q": qid}).scalar_one()
    db.commit()
    return {"query_id": int(qid), "widget_id": int(wid)}
