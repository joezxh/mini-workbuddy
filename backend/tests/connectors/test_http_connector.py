"""P3 Task 1 测试：HTTP 连接器（respx 模拟，无需真实网络）。"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.connectors.base import ConnectorConfig, InMemorySink, PaginationConfig
from app.connectors.http import HttpConnector
from app.connectors.mapping import FieldMapItem
from app.connectors.registry import get_connector


def _cfg(**over) -> ConnectorConfig:
    base = dict(base_url="http://api.example.com", records_path="data.items")
    base.update(over)
    return ConnectorConfig(**base)


@pytest.mark.asyncio
@respx.mock
async def test_pull_single_page_with_auth():
    respx.get("http://api.example.com/").mock(return_value=httpx.Response(
        200, json={"data": {"items": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}}
    ))
    conn = HttpConnector(_cfg(auth_token="SECRET"))
    recs = await conn.pull()
    assert len(recs) == 2
    assert recs[0]["name"] == "a"
    assert respx.calls.last.request.headers["Authorization"] == "Bearer SECRET"


@pytest.mark.asyncio
@respx.mock
async def test_pull_page_pagination():
    # 第 1 页 2 条，第 2 页 1 条，第 3 页空 → 停止
    respx.get("http://api.example.com/").mock(
        side_effect=[
            httpx.Response(200, json={"data": {"items": [{"id": 1}, {"id": 2}]}}),
            httpx.Response(200, json={"data": {"items": [{"id": 3}]}}),
            httpx.Response(200, json={"data": {"items": []}}),
        ]
    )
    cfg = _cfg(pagination=PaginationConfig(type="page", param="page", start=1, step=2))
    conn = HttpConnector(cfg)
    recs = await conn.pull()
    assert [r["id"] for r in recs] == [1, 2, 3]


@pytest.mark.asyncio
@respx.mock
async def test_pull_root_is_list():
    respx.get("http://api.example.com/").mock(
        return_value=httpx.Response(200, json=[{"x": 1}, {"x": 2}])
    )
    conn = HttpConnector(ConnectorConfig(base_url="http://api.example.com", records_path=None))
    recs = await conn.pull()
    assert len(recs) == 2


@pytest.mark.asyncio
@respx.mock
async def test_test_connection_ok_and_fail():
    ok = respx.get("http://up.example.com/").mock(return_value=httpx.Response(200))
    conn_ok = HttpConnector(ConnectorConfig(base_url="http://up.example.com"))
    assert await conn_ok.test_connection() is True
    assert ok.called

    respx.get("http://down.example.com/").mock(return_value=httpx.Response(500))
    conn_down = HttpConnector(ConnectorConfig(base_url="http://down.example.com"))
    assert await conn_down.test_connection() is False


@pytest.mark.asyncio
@respx.mock
async def test_sync_to_sink():
    respx.get("http://api.example.com/").mock(
        return_value=httpx.Response(200, json={"data": {"items": [{"id": 1}]}})
    )
    conn = HttpConnector(_cfg())
    sink = InMemorySink()
    result = await conn.sync(sink)
    assert result.written == 1
    assert sink.store == [{"id": 1}]


def test_registry_get_connector():
    conn = get_connector("http", _cfg())
    assert isinstance(conn, HttpConnector)


def test_registry_unknown_type():
    with pytest.raises(ValueError):
        get_connector("websocket", ConnectorConfig(base_url="http://x"))


@pytest.mark.asyncio
@respx.mock
async def test_pull_applies_field_map():
    respx.get("http://api.example.com/").mock(return_value=httpx.Response(
        200, json={"data": {"items": [{"u": {"name": "Alice", "age": "30"}}]}}
    ))
    cfg = _cfg(field_map=[
        FieldMapItem(target="name", source="u.name"),
        FieldMapItem(target="age", source="u.age", transform="int"),
    ])
    conn = HttpConnector(cfg)
    recs = await conn.pull()
    assert recs == [{"name": "Alice", "age": 30}]


@pytest.mark.asyncio
@respx.mock
async def test_pull_incremental_param_sent():
    route = respx.get("http://api.example.com/").mock(return_value=httpx.Response(
        200, json={"data": {"items": [{"id": 1}]}}
    ))
    cfg = _cfg(
        incremental_field="id",
        incremental_param="since_id",
    )
    conn = HttpConnector(cfg)
    await conn.pull(since="100")
    assert route.called
    # respx 把 query 编码进 URL；since_id=100 应随请求发出
    assert "since_id=100" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_pull_last_cursor_set():
    respx.get("http://api.example.com/").mock(return_value=httpx.Response(
        200, json={"data": {"items": [{"id": 5}, {"id": 12}, {"id": 9}]}}
    ))
    cfg = _cfg(incremental_field="id")
    conn = HttpConnector(cfg)
    recs = await conn.pull()
    assert recs == [{"id": 5}, {"id": 12}, {"id": 9}]
    assert conn.last_cursor == "12"
