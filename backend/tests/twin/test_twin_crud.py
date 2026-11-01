"""编排层：结构、可见性分组与形状配对（spec §4.5 卡片三态、§5.2 第 3 闸、W5/W9）。"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session  # 计划缺陷修正：夹具注解 db: Session 需显式 import

from tests.twin.conftest import TENANT_A, TENANT_B


@pytest.fixture
def published_version(db: Session, ontology_factory) -> dict:
    """本体 + 一个已发布版本行（卡片只能钉已发布版本）。"""
    oid = ontology_factory()
    db.execute(
        text("INSERT INTO onto_ontology_version (tenant_id, ontology_id, version, snapshot_json) "
             "VALUES (:t, :o, 1, CAST(:s AS jsonb))"),
        {"t": TENANT_A, "o": oid, "s": '{"objects": [], "relations": [], "properties": [],'
                                       '"mappings": {"table": [], "column": []}, "cq": []}'},
    )
    db.commit()
    return {"ontology_id": int(oid), "version": 1}


@pytest.fixture
def card_a(twin_client_a, published_version) -> int:
    r = twin_client_a.post("/api/v1/twins/cards", json={
        "name": "智慧工厂产线", "ontology_id": published_version["ontology_id"],
        "ontology_version": 1, "scene_key": "factory"})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def test_list_cards_groups_mine_shared_and_restricted(twin_client_a, db, card_a, published_version):
    """三组分派：自己的 draft 卡进 mine；他人 live 卡无授予进 restricted（🔒）。"""
    other = db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t,'园区安防',:o,1,'live',999) RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.commit()
    g = twin_client_a.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["mine"]} == {card_a}
    assert g["shared"] == []
    assert {c["id"] for c in g["restricted"]} == {int(other)}
    assert g["restricted"][0]["restricted"] is True


def test_shared_card_moves_to_shared_group(twin_client_a, db, published_version):
    """user 型 share → shared；draft 卡不共享给任何人都不可见（草稿是私人作业区）。"""
    cid = db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t,'他人草稿',:o,1,'draft',999) RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, granted_by) "
        "VALUES (:t,:c,'user',101,'read','manual',999)"), {"t": TENANT_A, "c": int(cid)})
    db.commit()
    g = twin_client_a.get("/api/v1/twins/cards").json()
    assert {c["id"] for c in g["shared"]} == {int(cid)} and g["restricted"] == []
    assert g["shared"][0]["access"] == "read"


def test_cross_tenant_card_is_404_not_403(twin_client_b, card_a):
    """租户不命中一律 404，不得用 403 泄露存在性。"""
    r = twin_client_b.get(f"/api/v1/twins/cards/{card_a}")
    assert r.status_code == 404
    assert r.json()["code"] == "TWIN_CARD_NOT_FOUND"


def test_card_can_only_pin_published_version(twin_client_a, ontology_factory):
    r = twin_client_a.post("/api/v1/twins/cards", json={
        "name": "钉未发布", "ontology_id": ontology_factory(), "ontology_version": 7})
    assert r.status_code == 400
    assert r.json()["code"] == "ONTOLOGY_NOT_FOUND"


def test_readonly_share_cannot_write(twin_client_a, twin_client_b, db, published_version):
    """read 授予可看不可写：回 403 + TWIN_ACCESS_REQUIRED（而非静默成功）。"""
    cid = db.execute(text(
        "INSERT INTO twin_card (tenant_id, name, ontology_id, ontology_version, runtime_state, owner_id) "
        "VALUES (:t,'可分享',:o,1,'live',999) RETURNING id"),
        {"t": TENANT_B, "o": published_version["ontology_id"]}).scalar_one()
    db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) VALUES (:t,:c,'页',0)"),
               {"t": TENANT_B, "c": int(cid)})
    db.execute(text(
        "INSERT INTO twin_card_share (tenant_id, card_id, grantee_type, grantee_id, perm, source, granted_by) "
        "VALUES (:t,:c,'user',:u,'read','manual',999)"),
        {"t": TENANT_B, "c": int(cid), "u": abs(TENANT_B) + 1})
    db.commit()
    pages = twin_client_b.get(f"/api/v1/twins/cards/{int(cid)}/pages").json()
    r = twin_client_b.post(f"/api/v1/twins/pages/{pages[0]['id']}/widgets",
                           json={"widget_key": "kpi", "title": "越权"})
    assert r.status_code == 403 and r.json()["code"] == "TWIN_ACCESS_REQUIRED"


def test_widget_shape_mismatch_rejected_with_readable_reason(twin_client_a, db, card_a, published_version):
    """W9：kpi 组件绑 entity_set 查询 → 服务端拒，原因必须可读。"""
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"),
                     {"t": TENANT_A, "c": card_a}).scalar_one()
    # compiled_sql 必须给出：verify_status='verified' 而无产物在生产上不可能存在（编译成功才写产物），
    # 缺它会被绑定三验的「已编译」闸先拒成 QUERY_COMPILE_FAILED，走不到形状配对。
    qid = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, verify_status, status) VALUES (:t,:o,1,'q_e','实体集','entity_set',"
        "CAST('{\"objects\":[]}' AS jsonb),'SELECT 1','verified','enabled') RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets",
                           json={"widget_key": "kpi", "title": "OEE", "query_id": int(qid)})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "QUERY_SHAPE_MISMATCH"
    assert body["detail"]["result_shape"] == "entity_set"
    assert "alert_table" in body["detail"]["compatible_widgets"]


def test_widget_binding_must_match_card_ontology_and_version(twin_client_a, db, card_a, ontology_factory):
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"), {"t": TENANT_A, "c": card_a}).scalar_one()
    other = ontology_factory()
    qid = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, verify_status, status) VALUES (:t,:o,1,'q_x','跳本体','kpi',"
        "CAST('{\"objects\":[]}' AS jsonb),'SELECT 1','verified','enabled') RETURNING id"),
        {"t": TENANT_A, "o": other}).scalar_one()
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets",
                           json={"widget_key": "kpi", "title": "X", "query_id": int(qid)})
    assert r.status_code == 400 and r.json()["code"] == "TWIN_BINDING_MISMATCH"


def test_scene_widget_cannot_bind_query(twin_client_a, db, card_a, published_version):
    """scene2d 吃卡片自身的 scene_key，绑查询即拒——不给它开“看起来能用”的后门。"""
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"), {"t": TENANT_A, "c": card_a}).scalar_one()
    qid = db.execute(text(
        "INSERT INTO onto_ontology_query (tenant_id, ontology_id, version, code, name, result_shape, "
        "spec_json, compiled_sql, verify_status, status) VALUES (:t,:o,1,'q_s','实体','entity_set',"
        "CAST('{\"objects\":[]}' AS jsonb),'SELECT 1','verified','enabled') RETURNING id"),
        {"t": TENANT_A, "o": published_version["ontology_id"]}).scalar_one()
    db.commit()
    r = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets",
                           json={"widget_key": "scene2d", "title": "园区", "query_id": int(qid)})
    assert r.status_code == 400 and r.json()["code"] == "QUERY_SHAPE_MISMATCH"


def test_layout_batch_write_is_atomic(twin_client_a, db, card_a):
    pid = db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                          "VALUES (:t,:c,'页',0) RETURNING id"), {"t": TENANT_A, "c": card_a}).scalar_one()
    ids = [int(db.execute(text("INSERT INTO twin_widget (tenant_id, page_id, widget_key, title, sort_order) "
                               "VALUES (:t,:p,'kpi',:n,:s) RETURNING id"),
                          {"t": TENANT_A, "p": int(pid), "n": f"w{i}", "s": i}).scalar_one())
           for i in range(2)]
    db.commit()
    ok = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets/layout", json={
        "items": [{"widget_id": ids[0], "grid_json": {"x": 0, "y": 0, "w": 12, "h": 4}}]})
    assert ok.status_code == 200 and ok.json()[0]["grid_json"]["w"] == 12
    bad = twin_client_a.post(f"/api/v1/twins/pages/{int(pid)}/widgets/layout", json={
        "items": [{"widget_id": ids[0], "grid_json": {"x": 0, "y": 0, "w": 5, "h": 4}},
                  {"widget_id": ids[1], "grid_json": {"x": 0, "y": 4, "w": 6, "h": 4}}]})
    assert bad.status_code == 400 and bad.json()["code"] == "TWIN_LAYOUT_INVALID"
    # 原子性：第二条合法也不得落库（整批回滚）
    after = twin_client_a.get(f"/api/v1/twins/pages/{int(pid)}/widgets").json()
    assert next(w for w in after if w["id"] == ids[1])["grid_json"]["y"] == 0


def test_page_reorder_rejects_foreign_page_id(twin_client_a, db, card_a):
    pids = [int(db.execute(text("INSERT INTO twin_page (tenant_id, card_id, name, sort_order) "
                                "VALUES (:t,:c,:n,:s) RETURNING id"),
                           {"t": TENANT_A, "c": card_a, "n": f"p{s}", "s": s}).scalar_one())
            for s in (0, 1)]
    db.commit()
    ok = twin_client_a.post(f"/api/v1/twins/cards/{card_a}/pages/reorder", json={"page_ids": list(reversed(pids))})
    assert ok.status_code == 200 and [p["id"] for p in ok.json()] == list(reversed(pids))
    r = twin_client_a.post(f"/api/v1/twins/cards/{card_a}/pages/reorder",
                           json={"page_ids": pids + [999999]})
    assert r.status_code == 400 and r.json()["detail"]["unknown"] == [999999]


def test_from_template_creates_unbound_widgets(twin_client_a, published_version):
    """模板只搭骨架：全部组件 query_id=NULL，回到原型「待绑定」空态。"""
    r = twin_client_a.post("/api/v1/twins/cards/from-template",
                           json={"template_key": "ops-line", "name": "产线看板"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_template_key"] == "ops-line" and body["runtime_state"] == "draft"
    pages = twin_client_a.get(f"/api/v1/twins/cards/{body['id']}/pages").json()
    widgets = twin_client_a.get(f"/api/v1/twins/pages/{pages[0]['id']}/widgets").json()
    assert len(widgets) == 3 and all(w["query_id"] is None for w in widgets)
    assert twin_client_a.post("/api/v1/twins/cards/from-template",
                             json={"template_key": "nope", "name": "x"}).json()["code"] == "TWIN_TEMPLATE_UNKNOWN"


def test_stale_flag_when_ontology_publishes_newer_version(twin_client_a, db, card_a):
    db.execute(text("UPDATE onto_ontology SET current_version = 2 WHERE id = "
                    "(SELECT ontology_id FROM twin_card WHERE id = :c)"), {"c": card_a})
    db.commit()
    assert twin_client_a.get(f"/api/v1/twins/cards/{card_a}").json()["stale"] is True
