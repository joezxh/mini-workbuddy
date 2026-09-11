"""tests/ontology 测试基础设施。

数据库
------
默认连接 **PostgreSQL**（独立测试库 `minworkbuddy_test`），与生产方言一致：

* 测试库不存在时自动创建（连到 `postgres` 维护库执行 `CREATE DATABASE`）；
* 库内创建 `vector` 扩展（`wiki_article.content_vector` 是 pgvector 列）；
* 每个用例一个**独立 schema**（`t_<uuid>`），用例结束 `DROP SCHEMA ... CASCADE`，
  用例之间完全隔离；
* 「重启不丢」通过在同一 schema 上**再建一个 engine + session**（全新连接）来模拟，
  而不是复用同一个 engine；
* 只建测试需要的表（ontology 三张表 + wiki_article + sys_user），不做整库 create_all。

连接串来自 `app.config.settings`（DB_HOST/DB_PORT/DB_USER/DB_PASSWORD），
只把库名换成 `minworkbuddy_test`；也可用环境变量整体覆盖：

    MINWORKBUDDY_TEST_DB_URL=postgresql+psycopg2://user:pwd@host:5432/minworkbuddy_test
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Iterator, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.models.wiki.wiki_article import WikiArticle

TENANT_A = 100
TENANT_B = 200

TEST_DB_NAME = "minworkbuddy_test"
"""独立测试库名：与开发库 `minworkbuddy` 分开，避免测试 DDL/DML 污染开发数据。"""


# 测试环境降噪：应用启动配置把 sqlalchemy 提到了 DEBUG/INFO，会淹没 pytest 输出
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def _test_db_url() -> str:
    """解析测试库连接串（默认 PostgreSQL；可用环境变量覆盖）。"""
    import os

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


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    """让 JSONB 列能在 SQLite 上建表（仅 `MINWORKBUDDY_TEST_DB_URL` 指向 SQLite 时生效）。

    PostgreSQL 是验收数据库，这里只是方言兜底，不改变生产行为。
    """
    return "JSON"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_for_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    """让 BigInteger 主键在 SQLite 上具备自增能力（同上，仅方言兜底）。"""
    return "INTEGER"


# ── 需要建表的模型 ────────────────────────────────────────────────────────────
def _tables() -> List:
    """测试需要创建的表。"""
    from app.models.ontology.model import (
        OntologyCq,
        OntologyLinkType,
        OntologyMapping,
        OntologyObjectType,
        OntologyProperty,
        OntologyVersion,
    )
    from app.models.ontology.ontology import (
        Ontology,
        OntologyAnnotation,
        OntologyClass,
    )

    return [
        SysUser.__table__,
        WikiArticle.__table__,
        Ontology.__table__,
        OntologyClass.__table__,
        OntologyAnnotation.__table__,
        OntologyObjectType.__table__,
        OntologyProperty.__table__,
        OntologyLinkType.__table__,
        OntologyMapping.__table__,
        OntologyCq.__table__,
        OntologyVersion.__table__,
    ]


# ── PostgreSQL 测试库引导 ─────────────────────────────────────────────────────
def _maintenance_url() -> URL:
    """维护库（postgres）连接串：`CREATE DATABASE` 不能在该库自身上执行。"""
    return make_url(TEST_DB_URL).set(database="postgres")


#: 所有通过 `engine_for()` 创建的 engine。
#: teardown 删 schema 前必须全部 dispose —— 未释放的连接若还开着事务，
#: 会持有 schema 内对象的锁，让 `DROP SCHEMA ... CASCADE` 一直等下去。
_ENGINES: List[Engine] = []


def dispose_all_engines() -> None:
    """释放本轮用例创建的所有 engine（用于删 schema 之前）。"""
    while _ENGINES:
        eng = _ENGINES.pop()
        try:
            eng.dispose()
        except Exception:  # noqa: BLE001 - 清理阶段不应因单个 engine 失败中断
            pass


def _describe_other_backends() -> str:
    """列出测试库里其它后端的状态，用于 DROP 超时时给出线索。"""
    try:
        probe = create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT")
    except Exception:  # noqa: BLE001
        return "<无法建立诊断连接>"
    try:
        with probe.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT pid, state, wait_event_type, "
                    "coalesce(now() - xact_start, interval '0'), left(query, 80) "
                    "FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "ORDER BY xact_start NULLS LAST LIMIT 10"
                )
            ).all()
    except Exception as exc:  # noqa: BLE001
        return f"<查询后端失败: {exc}>"
    finally:
        probe.dispose()
    if not rows:
        return "<其它后端为空>"
    return "; ".join(
        f"pid={r[0]} state={r[1]} wait={r[2]} xact_age={r[3]} q={r[4]!r}" for r in rows
    )


def _drop_leftover_schemas() -> None:
    """清掉历史遗留的测试 schema（上一次运行被中断时会留下）。

    这些残留 schema 里若还有未提交事务，`DROP SCHEMA` 期间的锁竞争会显著变慢，
    甚至让 teardown 看上去像卡死。测试库是专用的，按前缀删除是安全的。
    """
    admin = create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT nspname FROM pg_namespace "
                    "WHERE nspname LIKE 't\\_%' OR nspname LIKE 'probe\\_%'"
                )
            ).all()
        for (name,) in rows:
            with admin.connect() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        if rows:
            print(f"ℹ️  清理了 {len(rows)} 个遗留测试 schema")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  清理遗留测试 schema 失败（不影响用例执行）: {exc}")
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def _test_database() -> Iterator[None]:
    """确保测试库存在且 pgvector 扩展可用（仅 PostgreSQL 分支执行）。"""
    if not IS_POSTGRES:
        yield
        return

    _drop_leftover_schemas()

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
            # wiki_article.content_vector 需要 pgvector；缺扩展时建表会直接失败
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    finally:
        bootstrap.dispose()
    yield


def _admin_engine() -> Engine:
    """用于建/删 schema 的 engine（不绑定具体 schema）。"""
    return create_engine(TEST_DB_URL)


# ── 每个用例一个独立 schema / 文件库 ──────────────────────────────────────────
@pytest.fixture
def schema_name() -> str:
    """PostgreSQL 隔离单元：schema 名。"""
    return f"t_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """SQLite 兜底时的临时文件库路径（PG 模式下不使用）。"""
    return tmp_path / "ontology_test.db"


@pytest.fixture
def db_target(schema_name: str, db_path: Path, _test_database: None) -> Iterator[str]:
    """测试库「目标」：PG 为 schema 名，SQLite 为文件库路径。

    PostgreSQL 下负责 schema 的建/删；engine 与建表由 `engine` fixture 完成，
    因此只依赖 `db_target`（自行建 engine 的「重启」用例）也能拿到干净 schema。
    """
    target = schema_name if IS_POSTGRES else db_path.as_posix()
    if IS_POSTGRES:
        admin = _admin_engine()
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{target}"'))
        admin.dispose()
    try:
        yield target
    finally:
        if IS_POSTGRES:
            # 先释放本轮创建的所有连接，避免自身持有锁导致 DROP 自锁
            dispose_all_engines()
            admin = _admin_engine()
            try:
                with admin.begin() as conn:
                    # PostgreSQL 的 lock_timeout 默认为 0（无限等待）。一旦有其它连接
                    # 持有该 schema 内对象的锁（上次中断的进程、DB 客户端开着事务等），
                    # 不设超时就会表现为「卡死」而不是失败。这里让它快速失败并说明原因。
                    conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                    conn.execute(text("SET LOCAL statement_timeout = '30s'"))
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{target}" CASCADE'))
            except OperationalError as exc:
                raise RuntimeError(
                    f"DROP SCHEMA {target} 等待锁超时（5s），"
                    f"可能有其它连接正占用该 schema；当前其它后端: {_describe_other_backends()}"
                ) from exc
            finally:
                admin.dispose()


def engine_for(target: str, *, create_tables: bool = False) -> Engine:
    """为同一个 target 再建一个 engine。

    用于模拟「进程重启」：新 engine ⇒ 新连接池 ⇒ 新连接，
    数据必须来自数据库而不是任何进程内缓存。

    :param create_tables: 顺带建表（`create_all` 幂等，重复调用安全）
    """
    if IS_POSTGRES:
        # schema_translate_map 把未限定 schema 的表（含 create_all 的 DDL）路由到本测试随机 schema，
        # 杜绝落到 public 造成跨测试污染；search_path 事件供 inspect/反射按 schema 定位表。
        eng = create_engine(
            TEST_DB_URL, execution_options={"schema_translate_map": {None: target}}
        )
        _bind_schema(eng, target)
    else:
        eng = create_engine(f"sqlite:///{target}")
    _ENGINES.append(eng)
    if create_tables:
        Base.metadata.create_all(eng, tables=_tables())
    return eng


def _bind_schema(eng: Engine, schema: str) -> None:
    """把 engine 的所有连接固定到指定 schema（含 public，供 pgvector 类型解析与反射）。"""

    @event.listens_for(eng, "connect")
    def _set_search_path(dbapi_conn, _record):  # noqa: ANN001, ANN202
        with dbapi_conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}", public')


def open_session(eng: Engine) -> Session:
    """在指定 engine 上开一个会话（与 `db` fixture 同参数）。"""
    factory = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    return factory()


@pytest.fixture
def engine(db_target: str) -> Iterator[Engine]:
    """测试库 engine（每个用例一个独立 schema / 文件库）。"""
    eng = engine_for(db_target)
    Base.metadata.create_all(eng, tables=_tables())
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """测试库会话。"""
    session = open_session(engine)
    try:
        yield session
    finally:
        session.close()


def _fake_user(tenant_id: Optional[int]) -> SysUser:
    """构造一个未落库的 SysUser，仅用于依赖覆盖。

    `tenant_id=None` 用于模拟「无租户用户」（如 API Key 场景），
    改造后这类请求应被路由以 `400 tenant_required` 拒绝（评审 IM-07）。
    """
    user = SysUser()
    user.user_id = abs(tenant_id) + 1 if tenant_id is not None else 1
    user.username = f"user-{tenant_id}"
    user.status = "active"
    user.is_admin = False
    user.tenant_id = tenant_id
    return user


def build_client(db: Session, tenant_id: Optional[int]) -> TestClient:
    """构造一个只挂载 /api/v1/wiki/owl 路由的测试客户端。"""
    app = FastAPI()
    app.include_router(
        __import__("app.routers.wiki.wiki_owl", fromlist=["router"]).router,
        prefix="/api/v1",
    )

    def _override_db() -> Iterator[Session]:
        yield db

    def _override_user() -> SysUser:
        return _fake_user(tenant_id)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app)


@pytest.fixture
def client_a(db: Session) -> TestClient:
    """租户 A 的客户端。"""
    return build_client(db, TENANT_A)


@pytest.fixture
def client_b(db: Session) -> TestClient:
    """租户 B 的客户端。"""
    return build_client(db, TENANT_B)
