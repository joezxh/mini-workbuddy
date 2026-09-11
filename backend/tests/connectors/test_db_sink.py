"""P3 Task 7 测试：DBSink 幂等 upsert + 增量游标持久化（真实 PostgreSQL）。"""
from __future__ import annotations

import pytest

from app.connectors.sinks.db_sink import DBSink
from app.models.connectors.connector_record import ConnectorIngest, ConnectorSyncState


@pytest.mark.asyncio
async def test_db_sink_upsert_and_incremental(db):
    sink = DBSink(db, tenant_id=100, connector_type="http", id_field="id")

    recs = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    res = await sink.write(recs, {"incremental_field": "id", "last_cursor": "2"})
    assert res.written == 2

    rows = db.query(ConnectorIngest).all()
    assert len(rows) == 2

    # 增量游标已持久化
    state = db.query(ConnectorSyncState).filter_by(tenant_id=100, connector_type="http").one()
    assert state.last_cursor == "2"

    # 重新拉到同 id 的新数据 → upsert（行数不变，内容更新）
    res2 = await sink.write(
        [{"id": 1, "name": "a-updated"}, {"id": 3, "name": "c"}],
        {"incremental_field": "id", "last_cursor": "3"},
    )
    assert res2.written == 2
    # Core 层 upsert 不走 ORM 身份映射，需 expire 才能看到落库后的最新值
    db.expire_all()
    rows = db.query(ConnectorIngest).order_by(ConnectorIngest.external_id).all()
    assert len(rows) == 3  # 1 更新 + 2 + 3
    names = {r.external_id: r.payload["name"] for r in rows}
    assert names["1"] == "a-updated"

    # 游标推进到 3
    assert sink.get_last_cursor() == "3"


@pytest.mark.asyncio
async def test_db_sink_tenant_isolation(db):
    sink_a = DBSink(db, tenant_id=100, connector_type="http", id_field="id")
    sink_b = DBSink(db, tenant_id=200, connector_type="http", id_field="id")
    await sink_a.write([{"id": 1, "v": "a"}], {})
    await sink_b.write([{"id": 1, "v": "b"}], {})
    # 同 external_id 跨租户互不覆盖
    assert sink_a.get_last_cursor() is None
    ra = db.query(ConnectorIngest).filter_by(tenant_id=100, external_id="1").one()
    rb = db.query(ConnectorIngest).filter_by(tenant_id=200, external_id="1").one()
    assert ra.payload["v"] == "a"
    assert rb.payload["v"] == "b"


@pytest.mark.asyncio
async def test_db_sink_no_id_field_hashes_payload(db):
    sink = DBSink(db, tenant_id=100, connector_type="http", id_field="id")
    await sink.write([{"name": "x"}], {})
    row = db.query(ConnectorIngest).one()
    assert row.external_id  # 由 payload 哈希生成，非空
