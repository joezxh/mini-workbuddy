"""E-自动打标：pii>=L2 敏感标签规则自动打标（AF-03，rule/human 分治，可限源范围）。

不连真库：直接构造 ``meta_table``/``meta_column`` 快照 + ``pii`` security 标签，
验证 :meth:`OntologyTagService.apply_security_rule` 的幂等重绑、human 免疫、无标签跳过、按源过滤。
"""
from sqlalchemy import func, select

from app.models.ontology.asset_tag import MetaAssetTag, MetaAssetTagBinding


def _tag(db, tenant=100, code="pii", kind="security"):
    t = MetaAssetTag(tenant_id=tenant, code=code, name="敏感", tag_kind=kind)
    db.add(t)
    db.flush()
    return t


def _source(db, tenant=100, name="s"):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=tenant, name=name, source_type="mysql",
                    external_type="rdbms", host="h", port=3306)
    db.add(ds)
    db.flush()
    return ds


def _table(db, source_id, name, tenant=100):
    from app.models.dataops.meta import MetaTable

    t = MetaTable(tenant_id=tenant, source_id=source_id, db_name="d",
                  database="d", table_name=name)
    db.add(t)
    db.flush()
    return t


def _col(db, table_id, name, pii, tenant=100):
    from app.models.dataops.meta import MetaColumn

    c = MetaColumn(tenant_id=tenant, table_id=table_id, column_name=name, pii_level=pii)
    db.add(c)
    db.flush()
    return c


def _bind(db, tag_id, asset_id, source, tenant=100):
    b = MetaAssetTagBinding(tenant_id=tenant, tag_id=tag_id, asset_kind="table",
                            asset_id=asset_id, source=source)
    db.add(b)
    db.flush()
    return b


def _bindings(db, tag_id, tenant=100):
    return list(db.execute(
        select(MetaAssetTagBinding).where(
            MetaAssetTagBinding.tenant_id == tenant,
            MetaAssetTagBinding.tag_id == tag_id)
    ).scalars().all())


def _svc(tenant=100):
    from app.services.ontology.ontology_tag_service import OntologyTagService

    return OntologyTagService


def test_rule_rebind_idempotent(db):
    tag = _tag(db)
    ds = _source(db)
    t = _table(db, ds.id, "t")
    _col(db, t.id, "phone", "L3")
    svc = _svc()(db, 100)
    svc.apply_security_rule(source_id=ds.id)
    db.flush()
    svc.apply_security_rule(source_id=ds.id)
    db.flush()
    rules = [b for b in _bindings(db, tag.id) if b.source == "rule"]
    assert len(rules) == 1


def test_human_binding_survives(db):
    tag = _tag(db)
    ds = _source(db)
    t = _table(db, ds.id, "t")
    _col(db, t.id, "id_card", "L2")
    _bind(db, tag.id, t.id, "human")
    _svc()(db, 100).apply_security_rule(source_id=ds.id)
    db.flush()
    bs = _bindings(db, tag.id)
    assert len(bs) == 1 and bs[0].source == "human"


def test_no_tag_skips(db):
    ds = _source(db)
    t = _table(db, ds.id, "t")
    _col(db, t.id, "x", "L3")
    r = _svc()(db, 100).apply_security_rule(source_id=ds.id)
    assert r == {"tag": None, "bound": 0, "removed": 0}


def test_below_L2_not_bound(db):
    _tag(db)
    ds = _source(db)
    t = _table(db, ds.id, "t")
    _col(db, t.id, "name", "L1")
    r = _svc()(db, 100).apply_security_rule(source_id=ds.id)
    assert r["bound"] == 0


def test_scope_by_source(db):
    tag = _tag(db)
    ds_a = _source(db, name="A")
    ds_b = _source(db, name="B")
    t_a = _table(db, ds_a.id, "a")
    t_b = _table(db, ds_b.id, "b")
    _col(db, t_a.id, "phone", "L3")
    _col(db, t_b.id, "phone", "L3")
    _svc()(db, 100).apply_security_rule(source_id=ds_a.id)
    db.flush()
    bound_ids = {b.asset_id for b in _bindings(db, tag.id)}
    assert bound_ids == {t_a.id}


def test_reclassify_route(client_a, db):
    _tag(db)
    ds = _source(db)
    t = _table(db, ds.id, "t")
    _col(db, t.id, "phone", "L3")
    r = client_a.post("/api/v1/dataops/asset-tags/reclassify")
    assert r.status_code == 200
    assert r.json()["bound"] == 1
