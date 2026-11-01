"""T12 权限申请闭环（spec §4.5 / §6.1 / 验收 W5+W13）。

两个身份：owner = TENANT_A 推导出的 101（`_fake_user`），applicant = `OTHER_USER_ID`。
夹具自带：`published_version` / `card_a` 是 `test_twin_crud.py` 的**模块局部**夹具，
跨文件不共享，所以这里只重写所需的最小一份（本体 + 已发布版本 + live 卡）。

一个必须知道的测试库事实：`db` 夹具的 Session 是 `autoflush=False`
（`tests/ontology/conftest.py:150`），所以本服务**不得依赖「写完还没 commit 就能查回来」**；
每个用例的 schema 由 `schema_name` 随机生成并 `create_all`（`:104-141`），跨用例不串数据。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from app.core.api_error import ApiError
from app.models.twin import TwinAccessRequest, TwinCardShare
from app.services.twin.twin_access_service import (
    DEFAULT_GRANT_DAYS, STATUS_APPROVED, STATUS_EXPIRED, STATUS_PENDING, STATUS_REJECTED,
    TwinAccessService,
)
from tests.twin.conftest import OTHER_USER_ID, TENANT_A, TENANT_B

OWNER = 101          # = abs(TENANT_A) + 1，即 twin_client_a 背后的用户


@pytest.fixture
def card_factory(db, ontology_factory):
    """建一张默认属于 OWNER 的卡（默认 **live**：他人的 draft 对 applicant 不可见，走不到申请）。"""
    oid = ontology_factory()

    def _make(name: str = '园区安防孪生', state: str = "live", owner_id: int = OWNER) -> int:
        cid = db.execute(
            text("INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, "
                 "runtime_state, owner_id) VALUES (:t, :n, :o, 1, :s, :u) RETURNING id"),
            {"t": TENANT_A, "n": name, "o": oid, "s": state, "u": owner_id}).scalar_one()
        db.commit()
        return int(cid)

    return _make


@pytest.fixture
def live_card(card_factory) -> int:
    return card_factory()


def svc(db, user_id: int, tenant_id=TENANT_A) -> TwinAccessService:
    return TwinAccessService(db, tenant_id, user_id)


def apply_as_other(client, card_id: int, reason: str = "需要查看安防态势"):
    return client.post(f"/api/v1/twins/cards/{card_id}/access-request", json={"reason": reason})


def shares_of(db, card_id: int):
    return db.execute(select(TwinCardShare).where(TwinCardShare.card_id == card_id)).scalars().all()


def request_ids_of_card(db, card_id: int):
    return db.execute(select(func.count()).select_from(TwinAccessRequest).where(
        TwinAccessRequest.card_id == card_id)).scalar_one()


# ---------------------------------------------------------------- 申请（T12 入口）


def test_apply_returns_201_and_stores_pending_row(twin_client_a_as_other, db, live_card):
    r = apply_as_other(twin_client_a_as_other, live_card)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == STATUS_PENDING
    assert body["card_id"] == live_card and body["applicant_id"] == OTHER_USER_ID
    assert body["reason"] and body["approver_id"] is None and body["reviewed_at"] is None
    row = db.get(TwinAccessRequest, int(body["id"]))
    db.refresh(row)                       # 测试 Session 是 autoflush=False，refresh 才能拿到库里的值
    assert int(row.tenant_id) == TENANT_A and int(row.applicant_id) == OTHER_USER_ID


def test_owner_cannot_apply_for_its_own_card(twin_client_a, db, live_card):
    """已可读就不得申请（自决项 6）：否则抽屉会堆满注定自动批准的单子。"""
    r = twin_client_a.post(f"/api/v1/twins/cards/{live_card}/access-request", json={})
    assert r.status_code == 400
    assert r.json()["code"] == "TWIN_ACCESS_ALREADY_GRANTED"
    assert r.json()["detail"]["access"] == "owner"
    assert request_ids_of_card(db, live_card) == 0


def test_read_share_holder_cannot_apply(twin_client_a_as_other, db, live_card):
    """已持有效 read 授予的人再申请→ 400（access=read 也算已授权）。"""
    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, granted_by) "
        "VALUES (:t, :c, 'user', :u, 'read', 'manual', :o)"),
        {"t": TENANT_A, "c": live_card, "u": OTHER_USER_ID, "o": OWNER})
    db.commit()
    r = apply_as_other(twin_client_a_as_other, live_card)
    assert r.status_code == 400 and r.json()["code"] == "TWIN_ACCESS_ALREADY_GRANTED"
    assert r.json()["detail"]["access"] == "read"


def test_duplicate_pending_apply_is_409_with_pending_id(twin_client_a_as_other, live_card):
    first = apply_as_other(twin_client_a_as_other, live_card).json()
    r = apply_as_other(twin_client_a_as_other, live_card)
    assert r.status_code == 409 and r.json()["code"] == "TWIN_REQUEST_DUPLICATE"
    assert r.json()["detail"]["pending_id"] == int(first["id"])


def test_apply_for_others_draft_is_404_not_403(twin_client_a_as_other, card_factory):
    """draft 卡对他人根本不入列（§4.5），申请它得与不存在的卡同一信号。"""
    draft = card_factory(name="私人草稿", state="draft")
    r = apply_as_other(twin_client_a_as_other, draft)
    assert r.status_code == 404 and r.json()["code"] == "TWIN_CARD_NOT_FOUND"


def test_apply_for_cross_tenant_card_is_404(twin_client_b, live_card):
    """B 租户用户申请 A 租户的卡：租户闸在可见性里，不得用 403 泄露存在性。"""
    r = twin_client_b.post(f"/api/v1/twins/cards/{live_card}/access-request", json={})
    assert r.status_code == 404 and r.json()["code"] == "TWIN_CARD_NOT_FOUND"


def test_required_role_code_snapshots_first_role_publish(twin_client_a_as_other, db, live_card):
    """所需角色从**已启用发布行**取首码（自决项 2）：申请单留的是当时的快照。"""
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t, :c, '总览', 0) RETURNING id"),
                     {"t": TENANT_A, "c": live_card}).scalar_one()
    db.execute(
        text("INSERT INTO twin_publish (tenant_id, card_id, page_id, slug, access, role_codes_json, "
             "version, status, published_by) VALUES (:t, :c, :p, 'sl-role', 'role', "
             "CAST('[\"SEC_ADMIN\", \"NIGHT_WATCH\"]' AS jsonb), 1, 'enabled', :o)"),
        {"t": TENANT_A, "c": live_card, "p": int(pid), "o": OWNER})
    db.commit()
    body = apply_as_other(twin_client_a_as_other, live_card).json()
    assert body["required_role_code"] == "SEC_ADMIN"


def test_required_role_code_is_null_without_role_publish(twin_client_a_as_other, live_card):
    """未发布或 `access=org` 的卡没有「所需角色」可声明，就是 NULL，**不得编造**。"""
    assert apply_as_other(twin_client_a_as_other, live_card).json()["required_role_code"] is None


# ---------------------------------------------------------------- 审批与驳回


def test_only_card_owner_can_approve(db, live_card):
    """§10 Q1-A：同租户非 owner 是 403（无权），跨租户是 404（不存在）。"""
    rid = int(svc(db, OTHER_USER_ID).request_access(live_card, "审批门")["id"])
    with pytest.raises(ApiError) as miss:
        svc(db, 8080).approve(rid)
    assert miss.value.code == "TWIN_ACCESS_REQUIRED" and miss.value.http_status == 403
    with pytest.raises(ApiError) as cross:
        svc(db, OWNER, tenant_id=TENANT_B).approve(rid)
    assert cross.value.code == "TWIN_REQUEST_NOT_FOUND" and cross.value.http_status == 404
    db.rollback()


def test_approve_moves_card_to_shared_with_expiry(twin_client_a, twin_client_a_as_other,
                                                  db, live_card):
    """**W13 主判据**：申请 → owner 批 → 转入「共享给我的（只读）」并含过期时间。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    r = twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={})
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == STATUS_APPROVED and approved["approver_id"] == OWNER
    assert approved["reviewed_at"] and approved["expires_at"]

    g = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["shared"]} == {live_card}
    assert g["shared"][0]["access"] == "read" and g["shared"][0]["restricted"] is False
    # Step 7 新增的键：前端要渲染「剩余 N 天」，没它就只好看得到卡、看不到期限
    assert g["shared"][0]["share_expires_at"] == approved["expires_at"]

    rows = shares_of(db, live_card)
    assert len(rows) == 1 and rows[0].source == "request" and rows[0].perm == "read"
    assert int(rows[0].granted_by) == OWNER and int(rows[0].grantee_id) == OTHER_USER_ID


def test_approve_expiry_window_is_configurable(db, card_factory):
    """缺省 30 天（W13 的「含过期时间」不能是永久），也可 1–365 天自定。"""
    def _days_ahead(iso: str) -> timedelta:
        return datetime.fromisoformat(iso) - datetime.now()

    c1 = card_factory(name="默认期")
    d1 = svc(db, OWNER).approve(int(svc(db, OTHER_USER_ID).request_access(c1, "默认")["id"]))
    assert abs(_days_ahead(d1["expires_at"]) - timedelta(days=DEFAULT_GRANT_DAYS)) < timedelta(minutes=5)

    c2 = card_factory(name="短期")
    d2 = svc(db, OWNER).approve(int(svc(db, OTHER_USER_ID).request_access(c2, "一周")["id"]),
                               expires_in_days=7)
    assert abs(_days_ahead(d2["expires_at"]) - timedelta(days=7)) < timedelta(minutes=5)


def test_approve_after_decision_is_400_not_pending(twin_client_a, twin_client_a_as_other, live_card):
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    assert twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={}).status_code == 200
    r = twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_REQUEST_NOT_PENDING"
    assert r.json()["detail"]["status"] == STATUS_APPROVED
    # 批过的单子也不能再驳（两个动作共用同一个前置闸）
    assert twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/reject", json={}).status_code == 400


def test_reject_grants_nothing(twin_client_a, twin_client_a_as_other, db, live_card):
    """驳回不落授予：卡片仍属 🔒 受限（W5 三态可回退）。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    r = twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/reject", json={})
    assert r.status_code == 200 and r.json()["status"] == STATUS_REJECTED
    assert r.json()["expires_at"] is None and r.json()["approver_id"] == OWNER
    assert shares_of(db, live_card) == []
    g = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert g["shared"] == [] and {c["id"] for c in g["restricted"]} == {live_card}


def test_reapply_after_reject_and_upsert_single_share_row(twin_client_a, twin_client_a_as_other,
                                                          db, live_card):
    """rejected 不挡重申（部分唯一索引只管 pending），且续期复用同一行 share。

    这一条就是在钉住 `uq_twin_share` 未落库带来的风险：上一轮的**过期**授予行已存在，
    再批一次必须是 UPDATE 而不是插出第二行。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/reject", json={})
    rid2 = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    assert rid2 != rid

    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, "
        "expires_at, granted_by) VALUES (:t, :c, 'user', :u, 'edit', 'manual', :e, :o)"),
        {"t": TENANT_A, "c": live_card, "u": OTHER_USER_ID,
         "e": datetime.now() - timedelta(days=1), "o": OWNER})
    db.commit()

    twin_client_a.post(f"/api/v1/twins/access-requests/{rid2}/approve", json={"expires_in_days": 7})
    rows = shares_of(db, live_card)
    assert len(rows) == 1, f"同一 (card, user) 只应留一行授予，实得 {len(rows)} 行"
    assert rows[0].perm == "read" and rows[0].source == "request"
    assert rows[0].expires_at > datetime.now()


def test_approve_writes_share_and_request_in_one_transaction(db, live_card, monkeypatch):
    """半批准（单子 approved 但 share 没写）等于用户看到成功却仍看不了——必须同事务。"""
    rid = int(svc(db, OTHER_USER_ID).request_access(live_card, "原子性")["id"])

    def boom(*args, **kwargs):
        raise RuntimeError("share 写入失败")

    monkeypatch.setattr(TwinAccessService, "_upsert_share", boom)
    with pytest.raises(RuntimeError):
        svc(db, OWNER).approve(rid)
    db.rollback()                          # 只 commit 一次，回滚就能整体作废

    row = db.get(TwinAccessRequest, rid)
    db.refresh(row)
    assert row.status == STATUS_PENDING and row.approver_id is None
    assert shares_of(db, live_card) == []


# ---------------------------------------------------------------- 列表与过期


def test_lazy_expire_flips_stale_approved_rows(db, live_card):
    """approved 单过期后翻 expired（仅记账，不删 share 行）。"""
    rid = int(svc(db, OTHER_USER_ID).request_access(live_card, "过期")["id"])
    svc(db, OWNER).approve(rid)
    past = datetime.now() - timedelta(minutes=1)
    db.execute(text("UPDATE twin_access_request SET expires_at = :e WHERE id = :i"),
               {"e": past, "i": rid})
    db.commit()

    out = svc(db, OWNER).list_requests()   # 读列表时顺带清
    assert {d["status"] for d in out["incoming"] if d["id"] == rid} == {STATUS_EXPIRED}
    row = db.get(TwinAccessRequest, rid)
    db.refresh(row)
    assert row.status == STATUS_EXPIRED and int(row.card_id) == live_card


def test_expired_grant_returns_card_to_restricted(twin_client_a, twin_client_a_as_other,
                                                  db, live_card):
    """授予到期→ 卡片从 shared 回到 restricted：可见性闸在 `_my_shares()` 里，不依赖申请单。"""
    rid = int(apply_as_other(twin_client_a_as_other, live_card).json()["id"])
    twin_client_a.post(f"/api/v1/twins/access-requests/{rid}/approve", json={})
    g = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["shared"]} == {live_card}

    db.execute(text("UPDATE twin_card_share SET expires_at = :e WHERE card_id = :c"),
               {"e": datetime.now() - timedelta(seconds=1), "c": live_card})
    db.commit()
    after = twin_client_a_as_other.get("/api/v1/twins/cards").json()
    assert after["shared"] == [] and {c["id"] for c in after["restricted"]} == {live_card}


def test_list_requests_splits_incoming_and_outgoing(twin_client_a, twin_client_a_as_other,
                                                    card_factory):
    """一次请求同时给两组（卡片管理页的待办计数与「我的申请」列表共用它）。"""
    c1 = card_factory(name="安防孪生")
    c2 = card_factory(name="能耗孪生")
    r1 = int(apply_as_other(twin_client_a_as_other, c1).json()["id"])
    r2 = int(apply_as_other(twin_client_a_as_other, c2).json()["id"])

    inc = twin_client_a.get("/api/v1/twins/access-requests").json()
    assert {d["id"] for d in inc["incoming"]} == {r1, r2}
    assert inc["outgoing"] == [] and inc["incoming_pending"] == 2
    assert {d["card_name"] for d in inc["incoming"]} == {"安防孪生", "能耗孪生"}

    out = twin_client_a_as_other.get("/api/v1/twins/access-requests").json()
    assert {d["id"] for d in out["outgoing"]} == {r1, r2} and out["incoming"] == []
    assert out["incoming_pending"] == 0      # 计数只算 incoming，申请方看不到别人的单
