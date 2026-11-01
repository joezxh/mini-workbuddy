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
