"""CDM 模型/服务 冒烟（B1）。"""
import pytest
from sqlalchemy import inspect

from app.services.dataops.object_standard_service import MetaObjectStandardService
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
    # 属性被引用时删除属性标准应被拒（RESTRICT）
    obj_svc.set_attributes(obj.id, [{"standard_id": attr.id}])
    db.flush()
    with pytest.raises(Exception):
        MetaStandardService(db, TENANT_A).delete(attr.id)
        db.flush()
    db.rollback()


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
