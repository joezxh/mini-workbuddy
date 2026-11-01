"""批量取数：四态、扇出超时、出口脱敏与**缓存键含角色签名**（spec §4.3 / W8 / W11）。

测试分两层：
- **服务层**（直接 `TwinDataService(...)`）：凡是与**角色**有关的断言全部在此层——
  `tests/twin/conftest.py` 的 `_fake_user()` 不落 `sys_role` 行，走 HTTP 拿到的
  `role_codes` 恒为空，无法构造“豁免 / 不豁免”两个用户（为了不往测试库里灌权限表，
  也不把 `build_user_context()` monkeypatch 成说谎的样子）。
- **HTTP 层**（`twin_client_a`）：只验端点形状、逐组件隔离与权限门。

执行层 `ReadonlyQueryService` 整体打桩（本任务测的是**编排**，不是 SQL 执行；
真实直连已由 Task 4 的 `demo_env` 夹具覆盖）。
"""
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import ToolUserContext
from app.models.twin import TwinWidget
from app.services.twin import twin_data_service as td
from app.services.twin.twin_data_service import (
    TwinDataService, data_cache_key, param_sha, reset_data_cache, role_signature,
)
from tests.twin.conftest import TENANT_A, TENANT_B


class FakeQueryService:
    """执行层桩：按类属性返回固定结果，并把每次调用记进 `calls`。"""

    calls = []
    payload = {"columns": ["oee"], "rows": [[0.85]], "row_count": 1, "truncated": False}
    raise_for = None      # sql 含此子串 → 抛异常（单组件失败不拖垮整页）
    sleep_for = None      # sql 含此子串 → 睡 0.3s（命中超时闸门）

    def __init__(self, db, tenant_id):
        self.db, self.tenant_id = db, tenant_id

    def run(self, source_id, sql, limit=100, params=None, params_declared=None):
        cls = FakeQueryService
        cls.calls.append({"source_id": source_id, "sql": sql, "params": params or {}, "limit": limit})
        if cls.raise_for and cls.raise_for in sql:
            raise RuntimeError("源库连接失败")
        if cls.sleep_for and cls.sleep_for in sql:
            time.sleep(0.3)
        return dict(cls.payload)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """每个用例一份干净缓存 + 零调用记录 + 桩上执行层。"""
    reset_data_cache()
    FakeQueryService.calls, FakeQueryService.payload = [], {"columns": ["oee"], "rows": [[0.85]],
                                                            "row_count": 1, "truncated": False}
    FakeQueryService.raise_for = FakeQueryService.sleep_for = None
    monkeypatch.setattr(td, "ReadonlyQueryService", FakeQueryService)
    yield
    reset_data_cache()


@pytest.fixture
def env(db):
    """卡（owner=101）+ 页 + 3 组件：kpi 绑 q_kpi、trend 绑 q_trend、scene2d 未绑定。"""
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    oid = int(ex("INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
                 "VALUES (:t, gen_random_uuid()::text, '本体', 'published', 1) RETURNING id",
                 {"t": TENANT_A}).scalar_one())
    cid = int(ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, '设别卡', :o, 1, 'live', 101) RETURNING id",
                 {"t": TENANT_A, "o": oid}).scalar_one())
    pid = int(ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order, refresh_json) "
                 "VALUES (:t, :c, '总览', 0, CAST(:r AS jsonb)) RETURNING id",
                 {"t": TENANT_A, "c": cid,
                  "r": '{"mode":"interval","interval_seconds":10}'}).scalar_one())

    def add_query(code, shape, sql, **kw):
        return int(ex(
            "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, "
            "result_shape, spec_json, params_json, compiled_sql, sql_sha256, source_id, "
            "mask_rules_json, verify_status, status) VALUES "
            "(:t, :o, 1, :code, :name, :shape, CAST('{}' AS jsonb), CAST(:pj AS jsonb), :sql, "
            ":sha, 999, CAST(:mr AS jsonb), :verify, :status) RETURNING id",
            {"t": TENANT_A, "o": oid, "code": code, "name": code, "shape": shape,
             "pj": kw.get("params_json", '[{"name":"line","type":"string"}]'),
             "sql": sql, "sha": f"sha-{code}",
             "mr": kw.get("mask_rules", "null"),
             "verify": kw.get("verify", "verified"), "status": kw.get("status", "enabled")},
        ).scalar_one())

    def add_widget(page_id, key, qid, order, params=None):
        return int(ex(
            "INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, "
            "param_values_json, grid_json, sort_order) VALUES "
            "(:t, :p, :k, :n, :q, CAST(:pv AS jsonb), CAST(:g AS jsonb), :s) RETURNING id",
            {"t": TENANT_A, "p": page_id, "k": key, "n": f"{key}-{order}", "q": qid,
             "pv": params or "null", "g": '{"x":0,"y":0,"w":6,"h":4}', "s": order}).scalar_one())

    q_kpi = add_query("q_kpi", "kpi", "SELECT oee FROM demo_device_stat")
    q_trend = add_query("q_trend", "trend", "SELECT ts FROM demo_line_trend",
                        params_json='[{"name":"line","type":"string"},'
                                    '{"name":"site","type":"string"}]')
    w_kpi = add_widget(pid, "kpi", q_kpi, 0, '{"line":"L1"}')
    w_trend = add_widget(pid, "trend", q_trend, 1)
    w_scene = add_widget(pid, "scene2d", None, 2)
    db.commit()
    return {"ontology_id": oid, "card_id": cid, "page_id": pid, "q_kpi": q_kpi,
            "q_trend": q_trend, "w_kpi": w_kpi, "w_trend": w_trend, "w_scene": w_scene}


def svc(db, ctx=None, tenant_id=TENANT_A, user_id=101):
    """绑定到**测试引擎**的会话工厂：工作线程不得复用 `db`（Session 非线程安全）。"""
    bind = db.get_bind()
    return TwinDataService(db, tenant_id, user_id, ctx,
                           session_factory=lambda: Session(bind, expire_on_commit=False))


def ctx_of(*roles, is_admin=False):
    return ToolUserContext(user_id=101, username="u-101", is_admin=is_admin, role_codes=roles)


def by_widget(items):
    return {i["widget_id"]: i for i in items}


# ------------------------------------------------------------------ 四态

def specs_of(db, env, *wids):
    """把库里的组件行转成取数请求（Task 8 的快照通道走同一类型）。"""
    return [td.WidgetSpec.from_row(db.get(TwinWidget, w)) for w in wids]


def set_query(db, qid, col, value, as_json=False):
    """改一行查询定义。JSONB 列必须显式 CAST，否则 PG 报“表达式类型是 varchar”。"""
    cast = "CAST(:v AS jsonb)" if as_json else ":v"
    db.execute(text(f"UPDATE onto_ontology_query SET {col} = {cast} WHERE id = :i"),
               {"v": value, "i": qid})
    db.commit()


def test_unbound_widget_is_empty_with_reason(db, env):
    """query_id=NULL → empty/unbound（原型「待绑定」），不得抛异常也不得进 error。"""
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, env["w_scene"])))
    assert it[env["w_scene"]]["state"] == "empty"
    assert it[env["w_scene"]]["reason"] == "unbound"
    assert FakeQueryService.calls == []


def test_zero_rows_is_empty_not_error(db, env):
    """empty/zero_rows 与 error 必须可区分：W6 要求文案不同。"""
    FakeQueryService.payload = {"columns": ["oee"], "rows": [], "row_count": 0, "truncated": False}
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, env["w_kpi"])))
    assert it[env["w_kpi"]]["state"] == "empty"
    assert it[env["w_kpi"]]["reason"] == "zero_rows"
    assert it[env["w_kpi"]]["error"] is None


def test_disabled_or_unverified_query_is_error(db, env):
    """停用与无编译产物都是 error，且错误码不同（owner 得知道自己该做什么）。"""
    set_query(db, env["q_kpi"], "status", "disabled")
    set_query(db, env["q_trend"], "verify_status", "pending")
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, env["w_kpi"], env["w_trend"])))
    assert it[env["w_kpi"]]["error"]["code"] == "TWIN_QUERY_DISABLED"
    assert it[env["w_trend"]]["error"]["code"] == "QUERY_COMPILE_FAILED"
    assert FakeQueryService.calls == []            # 不合法的定义根本不进执行层


def test_query_defined_in_another_tenant_is_not_runnable(db, env):
    """组件绑了 B 租户的查询（FK 允许）：租户过滤后当作不存在，不泄内容也不执行。"""
    other = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, sql_sha256, source_id, verify_status, status) VALUES "
        "(:t, :o, 1, 'q_b', '它租', 'kpi', CAST('{}' AS jsonb), 'SELECT 1', 'sha-b', 999, 'verified', 'enabled') "
        "RETURNING id"), {"t": TENANT_B, "o": env["ontology_id"]}).scalar_one()
    wid = int(db.execute(text(
        "INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
        "VALUES (:t, :p, 'kpi', '跳租', :q, 9) RETURNING id"),
        {"t": TENANT_A, "p": env["page_id"], "q": int(other)}).scalar_one())
    db.commit()
    it = by_widget(svc(db, ctx_of()).execute_specs(specs_of(db, env, wid)))
    assert it[wid]["state"] == "error" and it[wid]["error"]["code"] == "QUERY_NOT_FOUND"
    assert FakeQueryService.calls == []


# ---------------------------------------------------- 整页扇出（HTTP 层 W8）

def test_page_data_returns_all_widgets_in_one_request(twin_client_a, db, env):
    """W8：整页刷新只发 1 个端点请求，回体按 sort_order 覆盖全部组件。"""
    r = twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page_id"] == env["page_id"] and body["card_id"] == env["card_id"]
    assert [i["widget_id"] for i in body["items"]] == [env["w_kpi"], env["w_trend"], env["w_scene"]]
    assert body["count"] == 3
    assert all(len(i) == 15 for i in body["items"])     # 15 个统一键，无缺列


def test_one_failing_widget_does_not_fail_the_page(twin_client_a, db, env):
    FakeQueryService.raise_for = "demo_line_trend"
    body = twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={}).json()
    it = by_widget(body["items"])
    assert it[env["w_trend"]]["state"] == "error"
    assert it[env["w_trend"]]["error"]["code"] == "TWIN_DATA_FAILED"
    assert "源库连接失败" in it[env["w_trend"]]["error"]["message"]
    assert it[env["w_kpi"]]["state"] == "ok"


def test_slow_widget_times_out_others_survive(twin_client_a, db, env, monkeypatch):
    monkeypatch.setattr(td, "QUERY_TIMEOUT_S", 0.05)
    FakeQueryService.sleep_for = "demo_line_trend"
    body = twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={}).json()
    it = by_widget(body["items"])
    assert it[env["w_trend"]]["error"]["code"] == "TWIN_DATA_TIMEOUT"
    assert it[env["w_kpi"]]["state"] == "ok"


def test_page_params_apply_only_where_declared(twin_client_a, db, env):
    """页面级参数是**可选覆盖**，不是广播：

    1. 只灌进在本查询 `params_json` 里声明过的同名参数（否则一个页面级 `site`
       会把未声明它的组件全部打成“未知参数”error）；
    2. 组件已存实值优先（设计期 preview 确认过的值不得被运行期刷新静默改写）。
    """
    twin_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/data",
                       json={"params": {"line": "L9", "site": "S1"}})
    got = {c["sql"]: c["params"] for c in FakeQueryService.calls}
    assert got["SELECT oee FROM demo_device_stat"] == {"line": "L1"}            # site 未声明→丢，L1 覆盖 L9
    assert got["SELECT ts FROM demo_line_trend"] == {"line": "L9", "site": "S1"}  # 两个都声明了→均落地


def test_single_widget_endpoint_reuses_stored_params(twin_client_a, db, env):
    """T9 无请求体：只用已存 param_values_json（不偏离 spec）。"""
    r = twin_client_a.get(f"/api/v1/twins/widgets/{env['w_kpi']}/data")
    assert r.status_code == 200 and r.json()["widget_id"] == env["w_kpi"]
    assert FakeQueryService.calls[0]["params"] == {"line": "L1"}


# ---------------------------------------------------- 出口脱敏与缓存安全（W11）

ID_CARD = "310101199001011234"
MASK_RULES = ('{"enabled": true, "rules": [{"field": "id_card", "strategy": "mask", '
              '"keep_prefix": 3, "keep_suffix": 2, "exempt_roles": ["SEC_ADMIN"]}]}')


def prepare_masked_kpi(db, env):
    """把 q_kpi 换成“全掩规则 + 工号列”（keep 3/2 避开 `guess_strategy_for_field` 的预设干扰）。

    计划缺陷修正（执行时实测，2026-11-01）：`id_card` **必须排在第一列**。
    `shape_result("kpi")` 的 `value` 只读 `columns[0]`（ontology_query_service.py:109），
    计划原稿的 `["dev_code", "id_card"]` 使 `value` 永远是未脱敏的工号，
    两条脱敏断言以假失败；保留第二列是为了继续测“原值不得出现在 `records` 里”。
    """
    set_query(db, env["q_kpi"], "mask_rules_json", MASK_RULES, as_json=True)
    FakeQueryService.payload = {"columns": ["id_card", "dev_code"], "rows": [[ID_CARD, "D1"]],
                                "row_count": 1, "truncated": False}


def test_masked_column_switches_state_to_masked(db, env):
    prepare_masked_kpi(db, env)
    it = by_widget(svc(db, ctx_of("VIEWER")).execute_specs(specs_of(db, env, env["w_kpi"])))
    item = it[env["w_kpi"]]
    assert item["state"] == "masked" and item["masked_fields"] == ["id_card"]
    assert ID_CARD not in str(item["data"])        # 原值不得出现在任何返回位置
    assert item["data"]["value"] == "310" + "*" * 13 + "34"


def test_exempt_role_gets_raw_value_and_ok(db, env):
    prepare_masked_kpi(db, env)
    it = by_widget(svc(db, ctx_of("SEC_ADMIN")).execute_specs(specs_of(db, env, env["w_kpi"])))
    assert it[env["w_kpi"]]["state"] == "ok"
    assert it[env["w_kpi"]]["data"]["value"] == ID_CARD


def test_cache_key_includes_role_signature(db, env):
    """W11 安全回归（R3）：豁免与不豁免交替请求同一查询，后者不得命中前者的缓存。"""
    prepare_masked_kpi(db, env)
    sql_of = lambda cs: [c for c in FakeQueryService.calls if "demo_device_stat" in c["sql"]]  # noqa: E731
    a = by_widget(svc(db, ctx_of("SEC_ADMIN")).load_page(env["page_id"])["items"])
    b = by_widget(svc(db, ctx_of("VIEWER")).load_page(env["page_id"])["items"])
    assert a[env["w_kpi"]]["state"] == "ok" and b[env["w_kpi"]]["state"] == "masked"
    assert len(sql_of(FakeQueryService.calls)) == 2          # 两个角色各跑一次，零串味
    # 键本身：角色不同→不同；同角色不同排列→相同（否则无豁免用户会拿到无豁免用户的键 miss 不是安全问题，而是拖平缓存）
    base = (TENANT_A, env["q_kpi"], param_sha({"line": "L1"}), "sha-q_kpi")
    assert data_cache_key(*base, role_signature(ctx_of("SEC_ADMIN"))) != \
        data_cache_key(*base, role_signature(ctx_of("VIEWER")))
    assert role_signature(ctx_of("A", "B")) == role_signature(ctx_of("B", "A"))


def test_cache_hit_skips_second_execution(db, env):
    kpi_calls = lambda: len([c for c in FakeQueryService.calls if "demo_device_stat" in c["sql"]])  # noqa: E731
    first = by_widget(svc(db, ctx_of("VIEWER")).load_page(env["page_id"])["items"])
    second = by_widget(svc(db, ctx_of("VIEWER")).load_page(env["page_id"])["items"])
    assert kpi_calls() == 1 and first[env["w_kpi"]]["cached"] is False
    assert second[env["w_kpi"]]["cached"] is True


def test_error_result_is_not_cached(db, env):
    """失败不入缓存：否则一次抽风会把 error 态钉住 10s，↻ 重试永远重试不了。"""
    FakeQueryService.raise_for = "demo_device_stat"
    for _ in range(2):
        svc(db, ctx_of("VIEWER")).load_page(env["page_id"])
    assert len([c for c in FakeQueryService.calls if "demo_device_stat" in c["sql"]]) == 2


def test_invalid_mask_rules_fail_closed_before_execution(db, env):
    """脱敏配置坏 → **宁可 error 也不返回真值**（降级不脱敏等于没闸）。"""
    set_query(db, env["q_kpi"], "mask_rules_json", '{"enabled": true, "rules": [{"field": ""}]}',
              as_json=True)
    it = by_widget(svc(db, ctx_of("VIEWER")).execute_specs(specs_of(db, env, env["w_kpi"])))
    assert it[env["w_kpi"]]["state"] == "error"
    assert it[env["w_kpi"]]["error"]["code"] == "TWIN_DATA_FAILED"
    assert FakeQueryService.calls == []


# ---------------------------------------------------------------- 权限门

def test_restricted_card_cannot_fetch_data(twin_client_a, db, env):
    """🔒 受限卡只能看徽标与申请入口，取数直接 403（§4.5）。"""
    cid = int(db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t, '园区安防', :o, 1, 'live', 999) RETURNING id"),
        {"t": TENANT_A, "o": env["ontology_id"]}).scalar_one())
    pid = int(db.execute(text(
        "INSERT INTO twin_page (tenant_id, card_id, name, sort_order) VALUES (:t, :c, '页', 0) RETURNING id"),
        {"t": TENANT_A, "c": cid}).scalar_one())
    db.execute(text("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
                    "VALUES (:t, :p, 'kpi', 'OEE', :q, 0)"),
               {"t": TENANT_A, "p": pid, "q": env["q_kpi"]})
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{pid}/data", json={})
    assert r.status_code == 403 and r.json()["code"] == "TWIN_ACCESS_REQUIRED"


def test_cross_tenant_page_is_404(twin_client_b, db, env):
    r = twin_client_b.post(f"/api/v1/twins/pages/{env['page_id']}/data", json={})
    assert r.status_code == 404 and r.json()["code"] == "TWIN_PAGE_NOT_FOUND"
