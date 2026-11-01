"""E33 draft-scope 服务端单源实查 + 回显剔除失效表（AF-08，spec §3.4 / Q4 裁决）。"""
import pytest

from app.core.api_error import (
    ApiError, BUILD_SCOPE_SINGLE_SOURCE, DRAFT_SCOPE_EMPTY,
)
from app.services.ontology.ontology_asset_service import OntologyAssetService


def _source(db, tenant=100, name="s"):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=tenant, name=name, source_type="mysql",
                    external_type="rdbms", host="h", port=3306)
    db.add(ds)
    db.flush()
    return ds


def _table(db, source_id, name, tenant=100):
    from app.models.dataops.meta import MetaTable

    mt = MetaTable(tenant_id=tenant, source_id=source_id, db_name="d",
                   database="d", table_name=name)
    db.add(mt)
    db.flush()
    return mt


def _ontology(db, tenant=100, code="ont1", **kw):
    from app.models.ontology.ontology import MetaOntology

    o = MetaOntology(tenant_id=tenant, code=code, name=code, status="draft", **kw)
    db.add(o)
    db.flush()
    return o


def test_put_rejects_cross_source(db):
    """表 t1 属源 A，scope 锁定源 B → BUILD_SCOPE_SINGLE_SOURCE。"""
    a = _source(db, name="A")
    b = _source(db, name="B")
    _table(db, a.id, "t1")
    ont = _ontology(db)
    svc = OntologyAssetService(db, 100)
    with pytest.raises(ApiError) as ei:
        svc.put_draft_scope(ont.id, {"mode": "tables", "source_id": b.id, "tables": ["t1"]})
    assert ei.value.code == BUILD_SCOPE_SINGLE_SOURCE


def test_put_rejects_missing_table(db):
    """tables 含该源不存在的表 → 同码，detail.missing 列出。"""
    a = _source(db)
    _table(db, a.id, "real")
    ont = _ontology(db)
    svc = OntologyAssetService(db, 100)
    with pytest.raises(ApiError) as ei:
        svc.put_draft_scope(ont.id, {"mode": "tables", "source_id": a.id,
                                     "tables": ["real", "ghost"]})
    assert ei.value.code == BUILD_SCOPE_SINGLE_SOURCE
    assert ei.value.detail["missing"] == ["ghost"]
    assert ei.value.detail["source_id"] == a.id


def test_put_rejects_missing_source_id(db):
    a = _source(db)
    _table(db, a.id, "t1")
    ont = _ontology(db)
    svc = OntologyAssetService(db, 100)
    with pytest.raises(ApiError) as ei:
        svc.put_draft_scope(ont.id, {"mode": "tables", "tables": ["t1"]})
    assert ei.value.code == BUILD_SCOPE_SINGLE_SOURCE


def test_put_ok_single_source(db):
    a = _source(db)
    _table(db, a.id, "t1")
    _table(db, a.id, "t2")
    ont = _ontology(db)
    svc = OntologyAssetService(db, 100)
    resp = svc.put_draft_scope(ont.id, {"mode": "tables", "source_id": a.id,
                                        "tables": ["t1", "t2"]})
    assert resp["draft_scope"]["tables"] == ["t1", "t2"]


def test_get_removes_stale_tables(db):
    """Q4 裁决：回显静默剔除失效表并回传 removed_stale，落库同步。"""
    a = _source(db)
    _table(db, a.id, "live")
    ont = _ontology(db, draft_scope_json={"mode": "tables", "source_id": a.id,
                                          "tables": ["live", "vanished"]})
    svc = OntologyAssetService(db, 100)
    resp = svc.get_draft_scope(ont.id)
    assert resp["removed_stale"] == 1
    assert resp["draft_scope"]["tables"] == ["live"]
    db.refresh(ont)
    assert ont.draft_scope_json["tables"] == ["live"]


def test_get_noop_without_tables(db):
    a = _source(db)
    ont = _ontology(db, draft_scope_json={"mode": "catalogs", "catalog_ids": [7]})
    svc = OntologyAssetService(db, 100)
    resp = svc.get_draft_scope(ont.id)
    assert resp["removed_stale"] == 0
    assert resp["draft_scope"]["mode"] == "catalogs"


def test_put_empty_still_blocked(db):
    """DRAFT_SCOPE_EMPTY 不回归；显式 clear 仍可清空。"""
    ont = _ontology(db)
    svc = OntologyAssetService(db, 100)
    with pytest.raises(ApiError) as ei:
        svc.put_draft_scope(ont.id, {})
    assert ei.value.code == DRAFT_SCOPE_EMPTY
    resp = svc.put_draft_scope(ont.id, {"clear": True})
    assert resp["draft_scope"] is None
