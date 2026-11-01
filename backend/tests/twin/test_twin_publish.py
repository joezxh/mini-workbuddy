"""发布与只读运行（spec §4.4 / P0-7 / W12）：slug 随机、反枚举 403、快照语义、访问审计。

两层测试，分工与 `test_twin_data.py` 一致：
- **HTTP 层**（`publish_client_a`）：端点形状、访问校验链、快照与实时的边界；
- **服务层**（直接构造 `TwinPublishService`）：凡是与**角色**有关的判定——
  `conftest._fake_user()` 不落 `sys_role`，HTTP 拿到的 `role_codes` 恒为空，
  造不出「命中角色的访客」。

执行层沿用 Task 7 的打桩点（`twin_data_service.ReadonlyQueryService`）：本任务测的是
**发布与放行**，取数链路本身已由 `test_twin_data.py` 覆盖，不在这里重测一遍。
"""
import re

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import ToolUserContext
from app.core.api_error import ApiError
from app.services.twin import twin_data_service as td
from app.services.twin import twin_publish_service as tp
from app.services.twin.twin_publish_service import TwinPublishService
from tests.twin.conftest import TENANT_A


class FakeRun:
    """执行层桩：只关心「跑了什么 SQL、带了什么参数」。"""

    calls = []
    payload = {"columns": ["oee"], "rows": [[0.85]], "row_count": 1, "truncated": False}

    def __init__(self, db, tenant_id):
        self.db, self.tenant_id = db, tenant_id

    def run(self, source_id, sql, limit=100, params=None, params_declared=None):
        FakeRun.calls.append({"sql": sql, "params": params or {}})
        return dict(FakeRun.payload)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """每用例一份干净缓存：Task 7 的缓存是进程级全局，不清就会跨用例串结果。"""
    td.reset_data_cache()
    FakeRun.calls = []
    FakeRun.payload = {"columns": ["oee"], "rows": [[0.85]], "row_count": 1, "truncated": False}
    monkeypatch.setattr(td, "ReadonlyQueryService", FakeRun)
    yield
    td.reset_data_cache()


@pytest.fixture
def env(db):
    """卡（owner=101, live）+ 页 + 两条已 preview 的查询 + 两个组件。"""
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    oid = int(ex("INSERT INTO onto_ontology (tenant_id, code, name, status, current_version) "
                 "VALUES (:t, gen_random_uuid()::text, '本体', 'published', 1) RETURNING id",
                 {"t": TENANT_A}).scalar_one())
    cid = int(ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, '设备卡', :o, 1, 'live', 101) RETURNING id",
                 {"t": TENANT_A, "o": oid}).scalar_one())
    pid = int(ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order, refresh_json) "
                 "VALUES (:t, :c, '总览', 0, CAST(:r AS jsonb)) RETURNING id",
                 {"t": TENANT_A, "c": cid,
                  "r": '{"mode":"interval","interval_seconds":10}'}).scalar_one())

    def add_query(code, shape, sql):
        return int(ex(
            "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, "
            "result_shape, spec_json, params_json, compiled_sql, sql_sha256, source_id, "
            "verify_status, status) VALUES "
            "(:t, :o, 1, :code, :name, :shape, CAST('{}' AS jsonb), "
            "CAST(:pj AS jsonb), :sql, :sha, 999, 'verified', 'enabled') RETURNING id",
            {"t": TENANT_A, "o": oid, "code": code, "name": code, "shape": shape,
             "pj": '[{"name":"line","type":"string"}]', "sql": sql, "sha": f"sha-{code}"},
        ).scalar_one())

    def add_widget(page_id, key, qid, order, params=None):
        return int(ex(
            "INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, "
            "param_values_json, grid_json, sort_order) VALUES "
            "(:t, :p, :k, :n, :q, CAST(:pv AS jsonb), CAST(:g AS jsonb), :s) RETURNING id",
            {"t": TENANT_A, "p": page_id, "k": key, "n": f"{key}-{order}", "q": qid,
             "pv": params or '{"line":"L1"}', "g": '{"x":0,"y":0,"w":6,"h":4}',
             "s": order}).scalar_one())

    q_kpi = add_query("q_kpi", "kpi", "SELECT oee FROM demo_device_stat")
    q_trend = add_query("q_trend", "trend", "SELECT ts FROM demo_line_trend")
    w_kpi = add_widget(pid, "kpi", q_kpi, 0)
    w_trend = add_widget(pid, "trend", q_trend, 1)
    db.commit()
    return {"ontology_id": oid, "card_id": cid, "page_id": pid, "q_kpi": q_kpi,
            "q_trend": q_trend, "w_kpi": w_kpi, "w_trend": w_trend,
            "add_page": lambda name: int(ex(
                "INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                "VALUES (:t, :c, :n, 1) RETURNING id",
                {"t": TENANT_A, "c": cid, "n": name}).scalar_one()),
            "add_widget": add_widget, "add_query": add_query}


def pub(db, ctx=None, tenant_id=TENANT_A, user_id=101):
    bind = db.get_bind()
    return TwinPublishService(db, tenant_id, user_id, ctx,
                              session_factory=lambda: Session(bind, expire_on_commit=False))


def ctx_of(*roles, is_admin=False, user_id=101):
    return ToolUserContext(user_id=user_id, username=f"u-{user_id}",
                           is_admin=is_admin, role_codes=roles)


def publish_a(publish_client_a, env, **kw):
    """走 T10 发布并断言 200，返回响应体（多数用例只需要 slug）。"""
    r = publish_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/publish", json=kw)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- slug 与发布

def test_new_slug_is_random_and_unpredictable():
    """边界 1：单调有序是自增派生的指纹，随机串 8 个全排序的概率是 1/40320。"""
    slugs = [tp.new_slug() for _ in range(8)]
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{24}", s) for s in slugs)
    assert len(set(slugs)) == 8
    assert slugs != sorted(slugs) and slugs != sorted(slugs, reverse=True)


def test_publish_returns_both_frontend_url_and_api_path(publish_client_a, db, env):
    """T10 回体：`url` 给前端路由用，`api_path` 给 HTTP 调用用——两者不同前缀，必须都回。"""
    b = publish_a(publish_client_a, env)
    assert b["version"] == 1 and b["status"] == "enabled" and b["widget_count"] == 2
    assert b["url"] == f"/twin-p/{b['slug']}"
    assert b["api_path"] == f"/api/v1/twin-p/{b['slug']}"
    assert b["page_id"] == env["page_id"] and b["card_id"] == env["card_id"]


def test_republish_reuses_slug_and_bumps_version(publish_client_a, db, env):
    """同一页面重复发布 = 同一资源的版本推进：slug 不变（外链不失效）、version+1、快照刷新。"""
    first = publish_a(publish_client_a, env)
    db.execute(text("UPDATE twin_widget SET title = '新标题' WHERE id = :i"), {"i": env["w_kpi"]})
    db.commit()
    second = publish_a(publish_client_a, env)
    assert second["slug"] == first["slug"] and second["version"] == 2
    meta = publish_client_a.get(f"/api/v1/twin-p/{second['slug']}").json()
    assert meta["version"] == 2
    assert [w["title"] for w in meta["widgets"]] == ["新标题", "trend-1"]


def test_empty_page_cannot_be_published(publish_client_a, db, env):
    """空页发布出去只是一张白页——直接在 T10 拒掉（400，不是 403）。"""
    pid = env["add_page"]("空白页")
    db.commit()
    r = publish_client_a.post(f"/api/v1/twins/pages/{pid}/publish", json={})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_PUBLISH_FORBIDDEN"
    assert r.json()["detail"]["widget_count"] == 0


def test_unverified_binding_blocks_publish(publish_client_a, db, env):
    """发布是对外承诺：绑了但没 preview 过的查询不得进入只读页（spec §7.2 闭环顺序）。

    未绑定（`query_id IS NULL`）**合法**——`scene2d` 天生不吃查询（Task 6 配对表里形状集为空），
    拒未绑定会把整个场景模块打成不可发布；运行期由四态里的 empty/unbound 表达。
    """
    db.execute(text("UPDATE onto_ontology_query SET verify_status = 'pending' WHERE id = :i"),
               {"i": env["q_kpi"]})
    db.commit()
    r = publish_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/publish", json={})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_PUBLISH_FORBIDDEN"
    bad = r.json()["detail"]["widgets"]
    assert [x["widget_id"] for x in bad] == [env["w_kpi"]]
    assert "preview" in bad[0]["reason"]


def test_unbound_widget_does_not_block_publish(publish_client_a, db, env):
    env["add_widget"](env["page_id"], "scene2d", None, 2, "null")
    db.commit()
    assert publish_a(publish_client_a, env)["widget_count"] == 3


def test_role_access_requires_non_empty_roles(publish_client_a, db, env):
    """access=role 却不给角色码 = 谁都不能看，属于发布参数非法，当场拒（而不是留到访问时 403）。"""
    r = publish_client_a.post(f"/api/v1/twins/pages/{env['page_id']}/publish",
                              json={"access": "role", "role_codes": []})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_PUBLISH_FORBIDDEN"


def test_org_publish_stores_no_role_codes(publish_client_a, db, env):
    """access=org 时 `role_codes_json` 必须为 NULL：留着值会被误读成「还有角色限制」。"""
    b = publish_a(publish_client_a, env, role_codes=["SEC_ADMIN"])
    assert b["access"] == "org" and b["role_codes"] is None


# ------------------------------------------------------------ 访问校验链

def test_every_denial_shares_one_code_and_message(publish_client_a, publish_client_b, db, env):
    """边界 2（反枚举）：未知 slug / 跨租户 / 已停用 / 角色不命中，四种失败**逐字相同**。

    差异只写进审计记录（`reason`），绝不上响应体——否则调用方可以用返回码差把
    「存在但无权」与「不存在」区分出来，等于给了枚举预言机。
    """
    b = publish_a(publish_client_a, env, access="role", role_codes=["SEC_ADMIN"])
    role_miss = publish_client_a.get(f"/api/v1/twin-p/{b['slug']}")   # 存在，但访客无角色
    cross = publish_client_b.get(f"/api/v1/twin-p/{b['slug']}")       # 存在于 A 租，B 租看不到
    unknown = publish_client_a.get("/api/v1/twin-p/definitely-not-a-slug")
    data_denied = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={})
    for r in (role_miss, cross, unknown, data_denied):
        assert r.status_code == 403, r.text
        assert r.json()["code"] == "TWIN_ACCESS_REQUIRED"
        assert r.json()["message"] == tp.DENY_MESSAGE      # 同一句话，无差异信号


def test_role_gate_is_fail_closed_at_service_layer(db, env):
    """角色命中→放行；不命中→403；`ctx is None`→403（`tool_context.py:13-15` 的安全红线）。"""
    row = pub(db, ctx_of()).publish(env["page_id"], access="role", role_codes=["SEC_ADMIN"])
    assert pub(db, ctx_of("SEC_ADMIN")).get_by_slug(row["slug"])["slug"] == row["slug"]
    with pytest.raises(ApiError) as miss:
        pub(db, ctx_of("VIEWER")).get_by_slug(row["slug"])
    assert miss.value.code == "TWIN_ACCESS_REQUIRED" and miss.value.http_status == 403
    with pytest.raises(ApiError) as anon:
        pub(db, None).get_by_slug(row["slug"])
    assert anon.value.code == "TWIN_ACCESS_REQUIRED"


def test_admin_bypasses_role_gate(db, env):
    row = pub(db, ctx_of()).publish(env["page_id"], access="role", role_codes=["SEC_ADMIN"])
    assert pub(db, ctx_of(is_admin=True)).get_by_slug(row["slug"])["version"] == 1


def test_unpublish_revokes_and_keeps_row(publish_client_a, db, env):
    """停用=改 status，**留行**（审计链与版本史不断档），slug 不回收；重复停用 404。"""
    b = publish_a(publish_client_a, env)
    r = publish_client_a.delete(f"/api/v1/twins/publish/{b['publish_id']}")
    assert r.status_code == 204
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 403
    kept = db.execute(text("SELECT status, version FROM twin_publish WHERE slug = :s"),
                      {"s": b["slug"]}).first()
    assert kept[0] == "disabled" and int(kept[1]) == 1
    assert publish_client_a.delete(f"/api/v1/twins/publish/{b['publish_id']}").status_code == 404


def test_republish_after_unpublish_revokes_back(publish_client_a, db, env):
    """停用后重发布：**沿用同 slug**（对外已分发出去的链接不该因一次误停而永久作废）、
    version 继续 +1、status 回到 enabled。"""
    b = publish_a(publish_client_a, env)
    publish_client_a.delete(f"/api/v1/twins/publish/{b['publish_id']}")
    second = publish_a(publish_client_a, env)
    assert second["slug"] == b["slug"] and second["version"] == 2
    assert publish_client_a.get(f"/api/v1/twin-p/{second['slug']}").status_code == 200


def test_delete_page_cascades_publish_row(publish_client_a, db, env):
    """删页面 → FK CASCADE 带走发布行 → slug 立即失效（无需「先取消发布」的口头约定）。"""
    b = publish_a(publish_client_a, env)
    assert publish_client_a.delete(f"/api/v1/twins/pages/{env['page_id']}").status_code == 204
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 403


def test_paused_card_still_serves_readonly_page(publish_client_a, db, env):
    """边界 3：`runtime_state` 管轮询与工作台可见性，`twin_publish.status` 管只读页可用性，
    两者正交。暂停卡片不得静默打断已经分发的只读链接。"""
    b = publish_a(publish_client_a, env)
    db.execute(text("UPDATE twin_card SET runtime_state = 'paused' WHERE id = :c"),
               {"c": env["card_id"]})
    db.commit()
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 200


# ---------------------------------------------------- 快照语义 vs 实时数据

def test_metadata_and_params_come_from_snapshot(publish_client_a, db, env):
    """发布冻的是**结构**：发布后改组件标题与参数实值，只读页仍按快照回。"""
    b = publish_a(publish_client_a, env)
    db.execute(text("UPDATE twin_widget SET title = '改过名', "
                    "param_values_json = CAST(:p AS jsonb) WHERE id = :i"),
               {"p": '{"line":"ZZ"}', "i": env["w_kpi"]})
    db.commit()
    meta = publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").json()
    assert [w["title"] for w in meta["widgets"]] == ["kpi-0", "trend-1"]
    publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={"params": {"line": "L9"}})
    got = {c["sql"]: c["params"] for c in FakeRun.calls}
    # 快照值：既不是发布后改的 ZZ，也不是请求里传来的 L9（快照已存的实值优先）
    assert got["SELECT oee FROM demo_device_stat"] == {"line": "L1"}


def test_run_returns_current_query_output(publish_client_a, db, env):
    """数据**恒实时**：快照只冻结构、不冻行业务数据（发布时不物化，遵守上游 D2）。

    换一次执行层返回值并清缓存，只读页立刻看到新值——10s TTL 是性能措施，不是数据快照。
    """
    b = publish_a(publish_client_a, env)
    first = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={}).json()
    FakeRun.payload = {"columns": ["oee"], "rows": [[0.42]], "row_count": 1, "truncated": False}
    td.reset_data_cache()
    second = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={}).json()
    assert first["items"][0]["data"]["value"] == 0.85
    assert second["items"][0]["data"]["value"] == 0.42


def test_run_items_share_the_15_key_contract(publish_client_a, db, env):
    """T11 与 T8 共用同一个结果契约：前端因此只有一套 `WidgetShell`（§6.3 承重原则）。"""
    b = publish_a(publish_client_a, env)
    body = publish_client_a.post(f"/api/v1/twin-p/{b['slug']}/data", json={}).json()
    assert body["slug"] == b["slug"] and body["version"] == 1 and body["count"] == 2
    assert all(len(i) == 15 for i in body["items"])
    assert [i["state"] for i in body["items"]] == ["ok", "ok"]


# ---------------------------------------------------------- 审计埋点（§4.4）

def test_access_audit_fires_on_both_allow_and_deny(publish_client_a, db, env, monkeypatch):
    """只读页的访问审计由服务层自己埋，**成功与失败都记**，差异只进 `reason`。"""
    seen: list = []
    monkeypatch.setattr(tp, "_record_access", lambda _db, **kw: seen.append(kw))
    b = publish_a(publish_client_a, env)
    assert publish_client_a.get(f"/api/v1/twin-p/{b['slug']}").status_code == 200
    assert publish_client_a.get("/api/v1/twin-p/nope-nope-nope-nope").status_code == 403
    assert [s["reason"] for s in seen] == ["granted", "not-found"]
    assert [s["allowed"] for s in seen] == [True, False]
    assert [s["action"] for s in seen] == ["metadata", "metadata"]
    assert seen[0]["version"] == 1 and seen[1]["version"] is None


def test_record_access_never_raises(db, env):
    """审计写是**尽力而为**：失败必须吞掉，不能把只读页打成 500，也不能弄坏请求 Session。"""
    tp._record_access(db, tenant_id=TENANT_A, user_id=101, username="u-101",
                      slug="x" * 24, action="metadata", allowed=False,
                      reason="not-found", version=None)          # 不得抛
    assert db.execute(text("SELECT 1")).scalar_one() == 1        # 请求 Session 仍可用


# ---------------------------------------------------------- 发布权限门

def _other_card(db, env, perm):
    """builder：owner=999 的卡 + 1 个已绑查询的组件 + 给 101 的 `perm` 授予，返回 page_id。"""
    ex = lambda s, p=None: db.execute(text(s), p or {})  # noqa: E731
    cid = int(ex("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, '他人卡', :o, 1, 'live', 999) RETURNING id",
                 {"t": TENANT_A, "o": env["ontology_id"]}).scalar_one())
    pid = int(ex("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                 "VALUES (:t, :c, '页', 0) RETURNING id", {"t": TENANT_A, "c": cid}).scalar_one())
    ex("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, query_id, sort_order) "
       "VALUES (:t, :p, 'kpi', 'OEE', :q, 0)", {"t": TENANT_A, "p": pid, "q": env["q_kpi"]})
    ex("INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, granted_by) "
       "VALUES (:t, :c, 'user', 101, :perm, 999)", {"t": TENANT_A, "c": cid, "perm": perm})
    db.commit()
    return pid


def test_read_share_is_not_enough_to_publish(publish_client_a, db, env):
    """T10 是**写操作**：只有 read 授予的人能看这一张卡，不能把它发布出去。"""
    pid = _other_card(db, env, "read")
    r = publish_client_a.post(f"/api/v1/twins/pages/{pid}/publish", json={})
    assert r.status_code == 403 and r.json()["code"] == "TWIN_ACCESS_REQUIRED"


def test_edit_share_may_publish(publish_client_a, db, env):
    r = publish_client_a.post(f"/api/v1/twins/pages/{_other_card(db, env, 'edit')}/publish", json={})
    assert r.status_code == 200, r.text


def test_cross_tenant_publish_is_404(publish_client_b, db, env):
    """跨租户发布：页面不存在于 B 租 → 404（与「无权发布」的 403 不同，因为资源本身不可见）。"""
    r = publish_client_b.post(f"/api/v1/twins/pages/{env['page_id']}/publish", json={})
    assert r.status_code == 404 and r.json()["code"] == "TWIN_PAGE_NOT_FOUND"
