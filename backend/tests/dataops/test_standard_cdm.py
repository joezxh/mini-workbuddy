"""CDM 模型/服务 冒烟（B1）。"""
import pytest
from sqlalchemy import inspect, select

from app.models.dataops.meta import MetaTable
from app.models.dataops.meta_relation import MetaRelation
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaRelationCheck, MetaTableStandard,
)
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.object_standard_service import MetaObjectStandardService
from app.services.dataops.standard_binding_service import StandardBindingService
from app.services.dataops.standard_catalog_service import MetaStandardCatalogService
from app.services.dataops.standard_service import MetaStandardService

TENANT_A = 100


def test_cdm_tables_created(db, engine):
    names = set(inspect(engine).get_table_names())
    for t in [
        "meta_standard_catalog", "meta_object_standard",
        "meta_object_standard_attribute", "meta_object_relation",
        "meta_table_standard", "meta_table_standard_history", "meta_relation_check",
    ]:
        assert t in names, f"{t} 未建出（检查 conftest._tables 登记）"


def _attr(db):
    return MetaStandardService(db, TENANT_A).create("std_test_col", "测试列", aliases=["col"])


def test_catalog_tree_and_delete_restricted(db):
    svc = MetaStandardCatalogService(db, TENANT_A)
    root = svc.create("scene_ec", "电商场景")
    child = svc.create("trade", "交易", parent_id=root.id)
    tree = svc.list_tree()
    assert tree[0]["code"] == "scene_ec"
    assert tree[0]["children"][0]["code"] == "trade"
    with pytest.raises(ValueError):  # 有子节点
        svc.delete(root.id)
    svc.delete(child.id)  # 叶子可删
    svc.delete(root.id)


def test_catalog_delete_blocked_by_object(db):
    cat = MetaStandardCatalogService(db, TENANT_A).create("scene_log", "物流场景")
    MetaObjectStandardService(db, TENANT_A).create("obj_order", "订单", catalog_id=cat.id)
    with pytest.raises(ValueError):
        MetaStandardCatalogService(db, TENANT_A).delete(cat.id)


def test_object_set_attributes_replaces_and_resists_attr_delete(db):
    attr = _attr(db)
    obj_svc = MetaObjectStandardService(db, TENANT_A)
    obj = obj_svc.create("obj_customer", "客户")
    obj_svc.set_attributes(obj.id, [{"standard_id": attr.id, "required": True, "sort_order": 1}])
    attrs = obj_svc.get_attributes(obj.id)
    assert len(attrs) == 1 and attrs[0]["standard_id"] == attr.id
    # 全量替换为空
    obj_svc.set_attributes(obj.id, [])
    assert obj_svc.get_attributes(obj.id) == []
    # 属性被对象引用时删除属性标准应被拒（RESTRICT，服务层给可读原因）
    obj_svc.set_attributes(obj.id, [{"standard_id": attr.id}])
    db.flush()
    with pytest.raises(ValueError, match="对象标准"):
        MetaStandardService(db, TENANT_A).delete(attr.id)


def test_catalog_and_object_routes(client_a, db):
    r = client_a.post("/api/v1/dataops/standards/catalogs", json={"code": "r_scene", "name": "场景"})
    assert r.status_code == 201
    cid = r.json()["id"]
    r2 = client_a.post("/api/v1/dataops/standards/objects", json={"code": "r_obj", "name": "对象", "catalog_id": cid})
    assert r2.status_code == 201
    oid = r2.json()["id"]
    assert any(o["id"] == oid for o in client_a.get("/api/v1/dataops/standards/objects", params={"catalog_id": cid}).json())
    # 目录被引用→删除 409
    assert client_a.delete(f"/api/v1/dataops/standards/catalogs/{cid}").status_code == 409


# ---------------------------------------------------------------------- #
# B4：关系标准 + 关系校验
# ---------------------------------------------------------------------- #
def _make_source(db):
    return DataSourceService(db, TENANT_A).create(
        name="s", source_type="postgresql", host="h", port=5432,
        username="u", password="p", database="d",
    ).id


def _prep(db):
    """两个对象标准 + 两张已人工绑定的物理表 + 一条 A→B 关系标准。"""
    source_id = _make_source(db)
    a = MetaObjectStandard(tenant_id=TENANT_A, code="obj_a", name="A", aliases_json=[], status="published")
    b = MetaObjectStandard(tenant_id=TENANT_A, code="obj_b", name="B", aliases_json=[], status="published")
    db.add_all([a, b])
    db.flush()
    ta = MetaTable(tenant_id=TENANT_A, source_id=source_id, database="public", table_name="t_a")
    tb = MetaTable(tenant_id=TENANT_A, source_id=source_id, database="public", table_name="t_b")
    db.add_all([ta, tb])
    db.flush()
    db.add_all([
        MetaTableStandard(tenant_id=TENANT_A, table_id=ta.id, object_standard_id=a.id,
                          status="accepted", source="human"),
        MetaTableStandard(tenant_id=TENANT_A, table_id=tb.id, object_standard_id=b.id,
                          status="accepted", source="human"),
    ])
    rel = MetaObjectRelation(tenant_id=TENANT_A, code="rel_ab", name="A到B", from_object_id=a.id,
                             to_object_id=b.id, relation_type="1:N", status="published")
    db.add(rel)
    db.flush()
    return source_id, rel, ta, tb


def _inferred(source_id, left, right):
    return MetaRelation(tenant_id=TENANT_A, source_id=source_id, database="public",
                        left_table=left, left_column="id", right_table=right,
                        right_column="a_id", confidence=0.9, status="accepted", source="rule")


def test_relation_check_hit(db):
    source_id, rel, ta, tb = _prep(db)
    inf = _inferred(source_id, "t_a", "t_b")
    db.add(inf)
    db.flush()
    StandardBindingService(db, TENANT_A)._check_relations(source_id, "public")
    db.flush()
    chk = db.execute(
        select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)
    ).scalar_one()
    assert chk.verdict == "hit"
    assert chk.inferred_relation_id == inf.id


def test_relation_check_conflict_on_reverse(db):
    source_id, rel, ta, tb = _prep(db)
    # 只有 B→A 反方向推断 → conflict
    inf = _inferred(source_id, "t_b", "t_a")
    db.add(inf)
    db.flush()
    StandardBindingService(db, TENANT_A)._check_relations(source_id, "public")
    db.flush()
    chk = db.execute(
        select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)
    ).scalar_one()
    assert chk.verdict == "conflict"
    assert chk.inferred_relation_id == inf.id


def test_relation_check_missing(db):
    source_id, rel, ta, tb = _prep(db)
    StandardBindingService(db, TENANT_A)._check_relations(source_id, "public")
    db.flush()
    chk = db.execute(
        select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)
    ).scalar_one()
    assert chk.verdict == "missing"
    assert chk.inferred_relation_id is None


def test_relation_check_idempotent_upsert(db):
    """重复校验不新增行，而是在同一 (relation, source, database) 上收敛结论。"""
    source_id, rel, ta, tb = _prep(db)
    svc = StandardBindingService(db, TENANT_A)
    svc._check_relations(source_id, "public")
    db.flush()
    inf = _inferred(source_id, "t_a", "t_b")
    db.add(inf)
    db.flush()
    svc._check_relations(source_id, "public")
    db.flush()
    rows = db.execute(
        select(MetaRelationCheck).where(MetaRelationCheck.standard_relation_id == rel.id)
    ).scalars().all()
    assert len(rows) == 1 and rows[0].verdict == "hit"


def test_bind_source_tallies_relation_checks(db):
    """bind_source 跑完表→对象后顺手做关系校验并回填计数。"""
    source_id, rel, ta, tb = _prep(db)
    report = StandardBindingService(db, TENANT_A).bind_source(source_id)
    db.flush()
    assert report.relation_checked == 1
    assert report.missing == 1 and report.hit == 0 and report.conflict == 0


def test_relation_routes_and_cross_catalog_warning(client_a, db):
    c1 = client_a.post("/api/v1/dataops/standards/catalogs", json={"code": "sc1", "name": "场景1"}).json()["id"]
    c2 = client_a.post("/api/v1/dataops/standards/catalogs", json={"code": "sc2", "name": "场景2"}).json()["id"]
    o1 = client_a.post("/api/v1/dataops/standards/objects",
                       json={"code": "ro1", "name": "O1", "catalog_id": c1}).json()
    o2 = client_a.post("/api/v1/dataops/standards/objects",
                       json={"code": "ro2", "name": "O2", "catalog_id": c2}).json()

    created = client_a.post("/api/v1/dataops/standards/relations", json={
        "code": "rr1", "name": "O1到O2",
        "from_object_id": o1["id"], "to_object_id": o2["id"],
        "relation_type": "1:N",
    })
    assert created.status_code == 201
    assert created.json()["warning"]  # 跨场景软提醒
    rid = created.json()["id"]

    assert len(client_a.get("/api/v1/dataops/standards/relations").json()) == 1
    # 对象被关系引用 → 删除 409
    assert client_a.delete(f"/api/v1/dataops/standards/objects/{o1['id']}").status_code == 409
    # 尚未绑定比对 → 校验明细为空
    assert client_a.get(f"/api/v1/dataops/standards/relations/{rid}/checks").json() == []
    assert client_a.delete(f"/api/v1/dataops/standards/relations/{rid}").status_code == 200
    assert client_a.get("/api/v1/dataops/standards/relations").json() == []


def test_graph_and_stats_routes(client_a, db):
    client_a.post("/api/v1/dataops/standards/objects", json={"code": "g_o1", "name": "对象1"})
    graph = client_a.get("/api/v1/dataops/standards/graph").json()
    assert any(n["code"] == "g_o1" for n in graph["nodes"])
    stats = client_a.get("/api/v1/dataops/standards/stats").json()
    assert stats["objects"] >= 1 and "relation_check" in stats


def test_graph_scoped_to_catalog_subtree(client_a, db):
    root = client_a.post("/api/v1/dataops/standards/catalogs", json={"code": "g_root", "name": "根"}).json()["id"]
    child = client_a.post("/api/v1/dataops/standards/catalogs",
                          json={"code": "g_child", "name": "子", "parent_id": root}).json()["id"]
    client_a.post("/api/v1/dataops/standards/objects", json={"code": "g_in", "name": "子对象", "catalog_id": child})
    client_a.post("/api/v1/dataops/standards/objects", json={"code": "g_out", "name": "外部对象"})

    scoped = client_a.get("/api/v1/dataops/standards/graph", params={"catalog_id": root}).json()
    codes = {n["code"] for n in scoped["nodes"]}
    assert codes == {"g_in"}


def test_nl_query_degrades_without_llm(client_a, db, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("no llm")

    monkeypatch.setattr("app.ai.research.llm.llm_json", boom)
    resp = client_a.post("/api/v1/dataops/standards/nl-query", json={"question": "有哪些客户相关对象"})
    assert resp.status_code == 200
    assert resp.json()["degraded"] is True


# ---------------------------------------------------------------------- #
# 属性字典治理：删除保护（对象引用 / 关系连接键）+ 引用计数
# ---------------------------------------------------------------------- #
def test_attr_delete_blocked_by_relation_via_key(db):
    """属性作为关系连接键时，删除同样要被拒并给出关系 code。"""
    attr = MetaStandardService(db, TENANT_A).create("std_via_key", "客户号")
    a = MetaObjectStandard(tenant_id=TENANT_A, code="via_a", name="A", aliases_json=[], status="published")
    b = MetaObjectStandard(tenant_id=TENANT_A, code="via_b", name="B", aliases_json=[], status="published")
    db.add_all([a, b])
    db.flush()
    db.add(MetaObjectRelation(
        tenant_id=TENANT_A, code="rel_via", name="A到B", from_object_id=a.id,
        to_object_id=b.id, relation_type="N:1", via_attribute_ids=[attr.id],
        status="published",
    ))
    db.flush()
    with pytest.raises(ValueError, match="rel_via"):
        MetaStandardService(db, TENANT_A).delete(attr.id)


def test_attr_delete_route_returns_400_when_referenced(client_a, db):
    attr = client_a.post("/api/v1/dataops/standards", json={"code": "r_del_attr", "name": "待删属性"}).json()
    obj = client_a.post("/api/v1/dataops/standards/objects", json={"code": "r_del_obj", "name": "对象"}).json()
    put = client_a.put(f"/api/v1/dataops/standards/objects/{obj['id']}/attributes",
                       json={"items": [{"standard_id": attr["id"]}]})
    assert put.status_code == 200, put.text
    resp = client_a.delete(f"/api/v1/dataops/standards/{attr['id']}")
    assert resp.status_code == 400
    assert "对象标准" in resp.json()["detail"]


def test_std_list_with_usage_counts(client_a, db):
    """with_usage=true 时三类引用分别计数，未引用属性全 0。"""
    a1 = client_a.post("/api/v1/dataops/standards", json={"code": "u_obj", "name": "对象引用"}).json()
    a2 = client_a.post("/api/v1/dataops/standards", json={"code": "u_via", "name": "连接键"}).json()
    client_a.post("/api/v1/dataops/standards", json={"code": "u_orphan", "name": "孤儿属性"}).json()

    o1 = client_a.post("/api/v1/dataops/standards/objects", json={"code": "u_o1", "name": "O1"}).json()
    o2 = client_a.post("/api/v1/dataops/standards/objects", json={"code": "u_o2", "name": "O2"}).json()
    put = client_a.put(f"/api/v1/dataops/standards/objects/{o1['id']}/attributes",
                       json={"items": [{"standard_id": a1["id"]}]})
    assert put.status_code == 200, put.text
    rel = client_a.post("/api/v1/dataops/standards/relations", json={
        "code": "u_rel", "name": "O1到O2", "from_object_id": o1["id"],
        "to_object_id": o2["id"], "relation_type": "1:N",
        "via_attribute_ids": [a2["id"]],
    })
    assert rel.status_code == 201, rel.text
    assert rel.json()["via_attribute_ids"] == [a2["id"]]

    rows = {r["code"]: r for r in client_a.get("/api/v1/dataops/standards", params={"with_usage": True}).json()}
    assert rows["u_obj"]["usage"] == {"columns": 0, "objects": 1, "relations": 0}
    assert rows["u_via"]["usage"] == {"columns": 0, "objects": 0, "relations": 1}
    assert rows["u_orphan"]["usage"] == {"columns": 0, "objects": 0, "relations": 0}
    # 默认契约不变：不带 with_usage 时不返回 usage 字段
    plain = client_a.get("/api/v1/dataops/standards").json()
    assert all("usage" not in r for r in plain)
