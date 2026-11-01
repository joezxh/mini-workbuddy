"""E28 三段确定性打分口径（AF-02，spec §3.6 原型口径）+ SQL 守卫。"""
from types import SimpleNamespace

import pytest

from app.services.ontology.ontology_asset_service import OntologyAssetService

T = lambda name="", db="", cmt="": SimpleNamespace(  # noqa: E731 - 纯函数打分行测试用轻量替身
    table_name=name, database=db, table_comment=cmt, id=1)


def matrix_cases():
    return [
        (T(name="sales_order"), "订单", False, False, 0),    # 全不命中
        (T(cmt="销售订单主表"), "订单", False, False, 3),     # 表注释=3（原 1 分档纠正）
        (T(db="orders"), "orders", False, False, 3),         # 库名=3（现状缺失）
        (T(name="order_x"), "order", False, False, 3),       # 表名包含=3
        (T(name="zzz"), "ord", True, False, 2),              # 仅列名
        (T(name="zzz"), "ord", False, True, 1),              # 仅列注释
        (T(name="order_x"), "order", True, True, 3),         # 表名压过列
    ]


@pytest.mark.parametrize("t,q,ch,cch,expect", matrix_cases())
def test_three_tier_score(t, q, ch, cch, expect):
    assert OntologyAssetService._score(t, q, "table", (ch, cch)) == expect


def _add_table(db, source_id, name, comment=None, database="d1", table_type=None, row_count=None):
    from app.models.dataops.meta import MetaTable

    mt = MetaTable(tenant_id=100, source_id=source_id, db_name=database,
                   database=database, table_name=name, table_comment=comment,
                   table_type=table_type, row_count=row_count)
    db.add(mt)
    db.flush()
    return mt


def _add_col(db, table_id, name, comment=None):
    from app.models.dataops.meta import MetaColumn

    mc = MetaColumn(tenant_id=100, table_id=table_id, column_name=name, column_comment=comment)
    db.add(mc)
    db.flush()
    return mc


def _source(db, name="s"):
    from app.models.dataops.data_source import DataSource

    ds = DataSource(tenant_id=100, name=name, source_type="mysql",
                    external_type="rdbms", host="h", port=3306)
    db.add(ds)
    db.flush()
    return ds


def test_tie_sorted_by_table_name(db):
    """同分恒按 table_name 字典序（Global Constraint 3，结果可复现）。"""
    ds = _source(db)
    _add_table(db, ds.id, "zeta_order", comment="订单表Z")
    _add_table(db, ds.id, "alpha_order", comment="订单表A")
    svc = OntologyAssetService(db, 100)
    resp = svc.search(kw="订单")
    names = [i["table_name"] for i in resp["items"]]
    assert names == ["alpha_order", "zeta_order"]
    assert resp["items"][0]["score"] == 3


def test_db_name_and_column_hits(db):
    """库名命中=3；仅列名命中=2；仅列注释命中=1；批量预载不分 N+1。"""
    ds = _source(db)
    t_db = _add_table(db, ds.id, "t1", database="orders")
    t_col = _add_table(db, ds.id, "t2", database="d1")
    t_cmt = _add_table(db, ds.id, "t3", database="d1")
    _add_col(db, t_col.id, "order_id")
    _add_col(db, t_cmt.id, "x", comment="order_no")
    svc = OntologyAssetService(db, 100)
    resp = svc.search(kw="order")
    scores = {i["table_name"]: i["score"] for i in resp["items"]}
    assert scores == {"t1": 3, "t2": 2, "t3": 1}


def test_no_similarity_in_sql(db):
    """守卫（Global Constraint 1）：search 全程 SQL 不得出现 similarity(。"""
    from sqlalchemy import event

    ds = _source(db)
    t = _add_table(db, ds.id, "sales_order", comment="销售订单")
    _add_col(db, t.id, "order_no", comment="订单号")
    stmt_capture: list = []

    engine = db.get_bind()

    @event.listens_for(engine, "before_cursor_execute")
    def _capture(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
        stmt_capture.append(statement)

    svc = OntologyAssetService(db, 100)
    resp = svc.search(kw="订单")
    assert resp["total"] >= 1
    joined = "\n".join(stmt_capture).lower()
    assert "similarity(" not in joined
    assert "word_similarity(" not in joined


# ── Task 5：table_type 过滤 + sort 三档（AF-02/07）──

def test_table_type_filter(db):
    ds = _source(db)
    _add_table(db, ds.id, "v_ord", table_type="VIEW")
    _add_table(db, ds.id, "t_ord", table_type="BASE TABLE")
    _add_table(db, ds.id, "n_ord")  # NULL 类型
    svc = OntologyAssetService(db, 100)
    assert [i["table_name"] for i in svc.search(kw="ord", table_type="VIEW")["items"]] == ["v_ord"]
    # BASE TABLE 过滤下 NULL 行视同基表（扫描器历史行未落 table_type）
    assert [i["table_name"] for i in svc.search(kw="ord", table_type="BASE TABLE")["items"]] == ["n_ord", "t_ord"]
    assert svc.search(kw="ord")["total"] == 3


def test_sort_rows_and_updated(db):
    from datetime import datetime, timedelta

    ds = _source(db)
    t1 = _add_table(db, ds.id, "a_tab", row_count=10)
    t2 = _add_table(db, ds.id, "b_tab", row_count=500)
    t3 = _add_table(db, ds.id, "c_tab", row_count=500)
    svc = OntologyAssetService(db, 100)
    names = [i["table_name"] for i in svc.search(sort="rows")["items"]]
    assert names == ["b_tab", "c_tab", "a_tab"]  # 行数降序，同数按字典序

    now = datetime.now()
    t1.updated_at = now - timedelta(days=1)
    t2.updated_at = now
    t3.updated_at = now - timedelta(hours=1)
    db.flush()
    names = [i["table_name"] for i in svc.search(sort="updated")["items"]]
    assert names == ["b_tab", "c_tab", "a_tab"]  # 新→旧
    names = [i["table_name"] for i in svc.search(sort="score")["items"]]
    assert names == ["a_tab", "b_tab", "c_tab"]  # 零分同分→字典序（T4 行为）


def test_route_rejects_bad_table_type_and_sort(client_a, db):
    ds = _source(db)
    _add_table(db, ds.id, "x1")
    assert client_a.get("/api/v1/dataops/assets/search", params={"table_type": "INDEX"}).status_code == 422
    assert client_a.get("/api/v1/dataops/assets/search", params={"sort": "bogus"}).status_code == 422
    # 空格经 URL 编码传参（httpx 对空格的编码形式均接受）
    assert client_a.get("/api/v1/dataops/assets/search",
                        params={"table_type": "BASE TABLE"}).status_code == 200
    r = client_a.get("/api/v1/dataops/assets/search", params={"table_type": "VIEW", "sort": "rows"})
    assert r.status_code == 200
