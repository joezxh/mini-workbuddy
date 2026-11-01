"""E4 默认幂等键展开防御（spec §3.3）：tags/catalog 模式入键前先解析为 tables 列表。"""
from app.routers.ontology.ontology import _default_idem_key


def test_default_key_expansion_changes_key():
    base = dict(mode="rules", scope={"mode": "tags", "source_id": 1, "tag_ids": [7]})
    k_plain = _default_idem_key(1, dict(base["scope"]), base["mode"])
    k_expanded = _default_idem_key(1, {**base["scope"], "tables": ["a", "b"]}, base["mode"])
    assert k_plain != k_expanded                      # 展开集必须影响键（防御生效）
    assert _default_idem_key(1, {"mode": "tables", "source_id": 1,
                                 "tables": ["b", "a"]}, "rules") == k_expanded  # 顺序无关


def _source(db):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=100, name="s", source_type="mysql",
                    external_type="rdbms", host="h", port=3306)
    db.add(ds)
    db.flush()
    return ds


def _table(db, source_id, name):
    from app.models.dataops.meta import MetaTable

    mt = MetaTable(tenant_id=100, source_id=source_id, db_name="d",
                   database="d", table_name=name)
    db.add(mt)
    db.flush()
    return mt


def _ontology(db):
    from app.models.ontology.ontology import MetaOntology

    o = MetaOntology(tenant_id=100, code="o1", name="o1", status="draft")
    db.add(o)
    db.flush()
    return o


def test_tags_and_tables_modes_share_key(client_a, db, monkeypatch):
    """同一标签集与直接表清单命中同表集 → 默认键一致，第二次请求命中幂等 200（§3.3 防御）。"""
    import app.routers.ontology.ontology as ont_mod
    from app.models.ontology.asset_tag import MetaAssetTag, MetaAssetTagBinding

    monkeypatch.setattr(ont_mod, "submit_build", lambda *a, **k: None)
    ds = _source(db)
    t1 = _table(db, ds.id, "t1")
    t2 = _table(db, ds.id, "t2")
    ont = _ontology(db)
    tag = MetaAssetTag(tenant_id=100, code="biz", name="业务", tag_kind="biz")
    db.add(tag)
    db.flush()
    for t in (t1, t2):
        db.add(MetaAssetTagBinding(tenant_id=100, tag_id=tag.id,
                                   asset_kind="table", asset_id=t.id, source="human"))
    db.flush()

    url = f"/api/v1/dataops/ontologies/{ont.id}/build-jobs"
    tags_req = {"mode": "rules", "scope": {"mode": "tags", "source_id": ds.id, "tag_ids": [tag.id]}}
    tables_req = {"mode": "rules", "scope": {"mode": "tables", "source_id": ds.id,
                                             "tables": ["t2", "t1"]}}
    assert client_a.post(url, json=tags_req).status_code == 201
    # 修复前：tags 模式键不含表名 → 此处会 201（双任务）
    assert client_a.post(url, json=tables_req).status_code == 200
    # 同标签集再来一次 → 仍命中同一任务
    assert client_a.post(url, json=tags_req).status_code == 200
