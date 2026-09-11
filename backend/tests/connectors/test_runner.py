"""P3 Task 7 测试：run_connector 编排（respx 模拟 HTTP + 真实 PG 落库）。"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.connectors.base import ConnectorConfig, FieldMapItem
from app.connectors.runner import run_connector
from app.models.connectors.connector_record import ConnectorIngest, ConnectorSyncState


@pytest.mark.asyncio
@respx.mock
async def test_run_connector_end_to_end(db):
    respx.get("http://api.example.com/").mock(return_value=httpx.Response(
        200, json={"data": {"items": [
            {"uid": "1", "ts": "100"}, {"uid": "2", "ts": "200"},
        ]}}
    ))
    cfg = ConnectorConfig(
        base_url="http://api.example.com",
        records_path="data.items",
        field_map=[
            FieldMapItem(target="id", source="uid"),
            FieldMapItem(target="ts", source="ts", transform="int"),
        ],
        incremental_field="ts",
    )
    result = await run_connector("http", cfg, db, tenant_id=100, id_field="id")
    assert result.written == 2

    rows = db.query(ConnectorIngest).filter_by(tenant_id=100, connector_type="http").all()
    assert len(rows) == 2
    # 增量游标已写入，供下次 since
    state = db.query(ConnectorSyncState).filter_by(tenant_id=100, connector_type="http").one()
    assert state.last_cursor == "200"

    # 第二次同步带 since=200 → 仅取更新（此处模拟端不变，验证游标被读取并传入）
    respx.get("http://api.example.com/").mock(return_value=httpx.Response(
        200, json={"data": {"items": [{"uid": "3", "ts": "300"}]}}
    ))
    result2 = await run_connector("http", cfg, db, tenant_id=100, id_field="id")
    assert result2.written == 1
    total = db.query(ConnectorIngest).filter_by(tenant_id=100, connector_type="http").count()
    assert total == 3
