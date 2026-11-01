"""AF-01 资产分组物化列（spec §1.1，Q1 裁决 B / Q2 映射矩阵）。"""
from app.services.dataops import source_types as st


def test_matrix_per_adjudication():
    """Q2 裁决：clickhouse/doris/starrocks→warehouse；六大关系库→rdbms；es→search；excel→file。"""
    for code in ("mysql", "oracle", "postgresql", "sqlserver", "dm", "kingbase"):
        assert st.external_type_for(code) == "rdbms"
    for code in ("clickhouse", "doris", "starrocks"):
        assert st.external_type_for(code) == "warehouse"
    assert st.external_type_for("es") == "search"
    assert st.external_type_for("excel") == "file"


def test_unknown_falls_to_other():
    """Q2 裁决：未知 source_type 兜底显式 other（不再默默落 rdbms）。"""
    assert st.external_type_for("some_future_type") == "other"
    assert st.external_type_for("") == "other"
    assert st.external_type_for(None) == "other"


def test_enumeration_labels_cover_all_codes():
    assert set(st.EXTERNAL_TYPE_LABELS) == set(st.EXTERNAL_TYPE_CODES)
    assert st.EXTERNAL_TYPE_CODES[-1] == "other"


def test_model_column_exists():
    from app.models.dataops.data_source import DataSource

    col = DataSource.__table__.c.external_type
    assert col.type.length == 32
    assert not col.nullable


# ── Task 2：服务层派生（手改优先，spec §1.1）──

def _create(db, **kw):
    from app.services.dataops.data_source_service import DataSourceService

    base = dict(name="s1", source_type="clickhouse", host="h", port=8123,
                username="u", password="p", database="d")
    base.update(kw)
    return DataSourceService(db, tenant_id=100).create(**base)


def test_create_derives_external_type(db):
    ds = _create(db)
    assert ds.external_type == "warehouse"


def test_create_manual_override_wins(db):
    ds = _create(db, name="s2", external_type="tsdb")
    assert ds.external_type == "tsdb"


def test_create_invalid_external_type_rejected(db):
    import pytest

    with pytest.raises(ValueError):
        _create(db, name="s3", external_type="not_a_code")


def test_update_external_type_manual(db):
    from app.services.dataops.data_source_service import DataSourceService

    ds = _create(db)
    svc = DataSourceService(db, tenant_id=100)
    got = svc.update(ds.id, external_type="warehouse")
    assert got.external_type == "warehouse"
    got = svc.update(ds.id, external_type="graph")
    assert got.external_type == "graph"


def test_update_without_external_type_keeps_value(db):
    from app.services.dataops.data_source_service import DataSourceService

    ds = _create(db, external_type="tsdb")
    svc = DataSourceService(db, tenant_id=100)
    got = svc.update(ds.id, name="renamed")
    assert got.external_type == "tsdb"  # 未传不重派生、不清空
