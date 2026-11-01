"""E-编辑：表/列说明元数据编辑端点（AF-06 编辑，写扫描元数据表非结构表）。"""
import pytest

from app.core.api_error import ApiError


def _source(db, tenant=100, name="s"):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=tenant, name=name, source_type="mysql",
                    external_type="rdbms", host="h", port=3306)
    db.add(ds)
    db.flush()
    return ds


def _table(db, source_id, name="t1", tenant=100, **kw):
    from app.models.dataops.meta import MetaTable

    mt = MetaTable(tenant_id=tenant, source_id=source_id, db_name="d",
                   database="d", table_name=name, **kw)
    db.add(mt)
    db.flush()
    return mt


def _column(db, table_id, name, tenant=100, **kw):
    from app.models.dataops.meta import MetaColumn

    c = MetaColumn(tenant_id=tenant, table_id=table_id, column_name=name, **kw)
    db.add(c)
    db.flush()
    return c


def test_update_table_fields(db):
    ds = _source(db)
    t = _table(db, ds.id, table_comment="旧说明", biz_name=None)
    from app.services.ontology.ontology_asset_service import OntologyAssetService

    r = OntologyAssetService(db, 100).update_table_meta(
        t.id, source_id=ds.id, table_comment="新表说明", biz_name="订单主表")
    db.flush()
    assert r["table_comment"] == "新表说明"
    assert r["biz_name"] == "订单主表"
    db.refresh(t)
    assert t.table_comment == "新表说明"
    assert t.biz_name == "订单主表"


def test_update_columns_and_skip_unknown(db):
    ds = _source(db)
    t = _table(db, ds.id)
    c1 = _column(db, t.id, "a")
    c2 = _column(db, t.id, "b")
    from app.services.ontology.ontology_asset_service import OntologyAssetService

    r = OntologyAssetService(db, 100).update_table_meta(t.id, columns=[
        {"column_name": "a", "column_comment": "列A"},
        {"column_name": "b", "column_comment": "列B"},
        {"column_name": "zzz", "column_comment": "忽略"},
    ])
    db.flush()
    assert r["skipped"] == ["zzz"]
    assert r["columns_updated"] == 2
    db.refresh(c1)
    db.refresh(c2)
    assert c1.column_comment == "列A"
    assert c2.column_comment == "列B"


def test_noop_when_all_none(db):
    ds = _source(db)
    t = _table(db, ds.id, table_comment="保持不变")
    from app.services.ontology.ontology_asset_service import OntologyAssetService

    r = OntologyAssetService(db, 100).update_table_meta(t.id)
    db.flush()
    db.refresh(t)
    assert t.table_comment == "保持不变"
    assert r["columns_updated"] == 0


def test_cross_tenant_404(db):
    ds = _source(db, tenant=100)
    t = _table(db, ds.id, tenant=100)
    from app.services.ontology.ontology_asset_service import OntologyAssetService

    with pytest.raises(ApiError) as ei:
        OntologyAssetService(db, 200).update_table_meta(t.id, table_comment="x")
    assert ei.value.http_status == 404


def test_wrong_source_404(db):
    ds_a = _source(db, name="A")
    ds_b = _source(db, name="B")
    t = _table(db, ds_a.id)
    from app.services.ontology.ontology_asset_service import OntologyAssetService

    with pytest.raises(ApiError) as ei:
        OntologyAssetService(db, 100).update_table_meta(
            t.id, source_id=ds_b.id, table_comment="x")
    assert ei.value.http_status == 404


def test_route_put(client_a, db):
    ds = _source(db)
    t = _table(db, ds.id)
    _column(db, t.id, "a")
    r = client_a.put(
        f"/api/v1/dataops/sources/{ds.id}/tables/{t.id}",
        json={"table_comment": "路由说明", "columns": [
            {"column_name": "a", "column_comment": "列A"},
            {"column_name": "nope", "column_comment": "x"},
        ]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["table_comment"] == "路由说明"
    assert body["skipped"] == ["nope"]
