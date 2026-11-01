"""E40 assets_tree：按 external_type 的 10 分组目录树（AF-01，Q1 裁决 B / Q2）。"""
from app.services.dataops import source_types as st


def _add_source(db, name, source_type, external_type, status="online"):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=100, name=name, source_type=source_type,
                    external_type=external_type, host="h", port=8123, status=status)
    db.add(ds)
    db.flush()
    return ds


def _tree(db):
    from app.services.ontology.ontology_service import OntologyService

    return OntologyService(db, 100).assets_tree()


def test_tree_ten_nodes_with_other(db):
    """固定 10 个分组节点，顺序=EXTERNAL_TYPE_CODES；空组保留、未知落 other。"""
    _add_source(db, "ch1", "clickhouse", "warehouse")
    tree = _tree(db)
    assert [g["code"] for g in tree] == list(st.EXTERNAL_TYPE_CODES)
    assert [g["label"] for g in tree] == [st.EXTERNAL_TYPE_LABELS[c] for c in st.EXTERNAL_TYPE_CODES]
    wh = next(g for g in tree if g["code"] == "warehouse")
    assert wh["count"] == 0  # 未扫描 → 表数 0，但节点在
    assert wh["children"][0]["id"]
    assert wh["children"][0]["status"] == "online"
    assert wh["children"][0]["external_type"] == "warehouse"
    assert next(g for g in tree if g["code"] == "graph")["children"] == []


def test_child_fields_and_group_count(db):
    """子节点携带 source_type/external_type/status；组 count=子节点表数之和。"""
    from app.models.dataops.meta import MetaTable

    ds = _add_source(db, "pg1", "postgresql", "rdbms", status="offline")
    db.add_all([
        MetaTable(tenant_id=100, source_id=ds.id, database="d", table_name="t1"),
        MetaTable(tenant_id=100, source_id=ds.id, database="d", table_name="t2"),
    ])
    db.flush()
    rdbms = next(g for g in _tree(db) if g["code"] == "rdbms")
    assert rdbms["count"] == 2
    child = rdbms["children"][0]
    assert child["label"] == "pg1" and child["source_type"] == "postgresql"
    assert child["status"] == "offline" and child["count"] == 2


def test_bucket_code_defensive_normalisation():
    """读侧防御归一：缺失/空白/未知枚举落 other，合法值原样保留（CHECK 已拦写侧，双保险）。"""
    from app.services.ontology.ontology_service import _bucket_code

    assert _bucket_code(None) == "other"
    assert _bucket_code("") == "other"
    assert _bucket_code("timecube") == "other"
    assert _bucket_code(" RDBMS ") == "rdbms"
    assert _bucket_code("warehouse") == "warehouse"


def test_tenant_isolation(db):
    from app.models.dataops.data_source import DataSource

    db.add(DataSource(tenant_id=200, name="other-tenant", source_type="mysql",
                      external_type="rdbms", host="h", port=3306))
    db.flush()
    tree = _tree(db)
    assert all(g["children"] == [] for g in tree)
