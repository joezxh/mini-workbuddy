"""参数化的三条硬约束：方言渲染归一、越界拒绝、无参数时行为不变（spec §4.2、W15）。"""
import pytest

from app.services.dataops.sql_placeholder import MAX_PARAMS, normalize_placeholders, validate_params


def test_normalize_postgres_style_to_named():
    # sqlglot postgres 方言把 :p_1 渲染成 %(p_1)s，而 SQLAlchemy text() 要 :name
    assert normalize_placeholders(
        "SELECT a FROM t WHERE a = %(p_1)s AND b > %(p_2)s"
    ) == "SELECT a FROM t WHERE a = :p_1 AND b > :p_2"


def test_normalize_keeps_plain_sql_untouched():
    s = "SELECT a FROM t WHERE a = 1"
    assert normalize_placeholders(s) == s


def test_normalize_does_not_touch_percent_arithmetic():
    # 50 % 2 之类的取模不得被误改写（只有 %(name)s 形态才替换）
    assert normalize_placeholders("SELECT 50 % 2 AS m, 1 = ANY(%(p_1)s) AS f") == \
        "SELECT 50 % 2 AS m, 1 = ANY(:p_1) AS f"


def test_validate_params_rejects_unknown_name_and_count():
    declared = [{"name": "p_1", "type": "int", "default": 0}]
    with pytest.raises(ValueError, match="未声明"):
        validate_params(declared, {"p_9": 1})
    with pytest.raises(ValueError, match="参数个数"):
        validate_params([], {f"p_{i}": i for i in range(MAX_PARAMS + 1)})


def test_validate_params_type_mismatch():
    declared = [{"name": "p_1", "type": "int", "default": 0}]
    with pytest.raises(ValueError, match="类型"):
        validate_params(declared, {"p_1": "abc"})


def test_validate_params_int_accepts_bool_rejects_float():
    # bool 是 int 子类但进 SQL 语义不同，显式拒绝，避免 True→1 静默改写
    declared = [{"name": "p_1", "type": "int", "default": 0}]
    with pytest.raises(ValueError, match="类型"):
        validate_params(declared, {"p_1": True})
    assert validate_params(declared, {"p_1": 7}) == {"p_1": 7}


# ── run() 参数化（需真实 PG：另起引擎连本机 minworkbuddy_test）──────────────
from sqlalchemy import text

from app.services.dataops.query_service import ReadonlyQueryService

DECLARED = [{"name": "p_1", "type": "int"}]


@pytest.fixture
def param_table(db, schema_name) -> str:
    """在 per-test schema 里建一张实表，返回**限定名**。

    ``run()`` 会按 DataSource 另起一个引擎，那个连接的 search_path 是默认值，
    看不到本用例的随机 schema，所以 SQL 必须带 schema 限定（与 Task 0b 已记的
    「build_engine 不传 config，dbSchema 不生效」同一陷阱）。
    """
    qualified = f'"{schema_name}".p_t'
    db.execute(text(f"CREATE TABLE {qualified} (a int, b text)"))
    db.execute(text(f"INSERT INTO {qualified} VALUES (7, 'x'), (8, 'y')"))
    db.commit()
    return qualified


def test_run_binds_params_against_real_pg(db, tenant_factory, source_factory, param_table):
    """params 走绑定而非字面量拼接。"""
    tid = tenant_factory()
    sid = source_factory(tid)
    svc = ReadonlyQueryService(db, tid)
    out = svc.run(sid, f"SELECT a FROM {param_table} WHERE a = :p_1",
                  params={"p_1": 7}, params_declared=DECLARED)
    assert out["rows"] == [[7]] and out["row_count"] == 1


def test_run_rejects_injected_value_by_type(db, tenant_factory, source_factory, param_table):
    """注入串先被类型校验拦下，不会走到执行（因此也不可能在结果里看到行）。"""
    tid = tenant_factory()
    sid = source_factory(tid)
    svc = ReadonlyQueryService(db, tid)
    with pytest.raises(ValueError, match="类型"):
        svc.run(sid, f"SELECT a FROM {param_table} WHERE a = :p_1",
                params={"p_1": "7 OR 1=1"}, params_declared=DECLARED)


def test_run_rejects_unknown_placeholder_before_guard(db, tenant_factory, source_factory, param_table):
    """参数校验前置于 SqlGuard：未声明名直接拒（即使 SQL 本身合法）。"""
    tid = tenant_factory()
    sid = source_factory(tid)
    svc = ReadonlyQueryService(db, tid)
    with pytest.raises(ValueError, match="未声明"):
        svc.run(sid, f"SELECT a FROM {param_table} WHERE x = :p_1",
                params={"p_2": 1}, params_declared=DECLARED)


def test_run_params_without_declaration_are_rejected(db, tenant_factory, source_factory, param_table):
    """参数白名单只来自 params_declared，不接受隐式参数（防绕过声明直接绑定）。"""
    tid = tenant_factory()
    sid = source_factory(tid)
    svc = ReadonlyQueryService(db, tid)
    with pytest.raises(ValueError, match="未声明"):
        svc.run(sid, f"SELECT a FROM {param_table} WHERE a = :p_1", params={"p_1": 7})


def test_run_without_params_is_byte_equivalent(db, tenant_factory, source_factory, param_table):
    """W15：params=None 时与扩展前完全一致（现有三个调用方不受影响）。"""
    tid = tenant_factory()
    sid = source_factory(tid)
    svc = ReadonlyQueryService(db, tid)
    out = svc.run(sid, f"SELECT a, b FROM {param_table} ORDER BY a")
    assert out["columns"] == ["a", "b"]
    assert out["rows"] == [[7, "x"], [8, "y"]]
    assert out["row_count"] == 2 and out["truncated"] is False
