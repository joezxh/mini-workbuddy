"""P3 Task 2~5 测试：钉钉/飞书/企业微信 OAuth2 连接器（respx 模拟，无需真实账号）。"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.connectors.base import ConnectorConfig, FieldMapItem
from app.connectors.types import (
    DingtalkConnector,
    FeishuConnector,
    WeComConnector,
)
from app.connectors.registry import get_connector


def _dingtalk_cfg(**over) -> ConnectorConfig:
    base = dict(
        base_url="https://oapi.dingtalk.com",
        client_id="appkey123",
        client_secret="appsecret456",
        data_path="/attendance/list",
        records_path="recordresult",
        field_map=[
            FieldMapItem(target="user_id", source="userId"),
            FieldMapItem(target="check_time", source="checkTime", transform="int"),
        ],
        incremental_field="check_time",
    )
    base.update(over)
    return ConnectorConfig(**base)


@pytest.mark.asyncio
@respx.mock
async def test_dingtalk_pull_with_token_and_mapping():
    # 令牌端点：query appkey/appsecret
    respx.get("https://oapi.dingtalk.com/gettoken").mock(return_value=httpx.Response(
        200, json={"access_token": "TOK", "errcode": 0}
    ))
    # 数据端点：带 access_token 查询参数
    respx.get(url__regex=r"https://oapi.dingtalk.com/attendance/list.*access_token=TOK").mock(
        return_value=httpx.Response(200, json={
            "recordresult": [
                {"userId": "u1", "checkTime": "1700000000000"},
                {"userId": "u2", "checkTime": "1700000000001"},
            ]
        })
    )
    conn = DingtalkConnector(_dingtalk_cfg())
    recs = await conn.pull()
    assert len(recs) == 2
    assert recs[0] == {"user_id": "u1", "check_time": 1700000000000}
    assert conn.last_cursor == "1700000000001"


@pytest.mark.asyncio
@respx.mock
async def test_dingtalk_test_connection_ok():
    respx.get("https://oapi.dingtalk.com/gettoken").mock(
        return_value=httpx.Response(200, json={"access_token": "TOK"})
    )
    respx.get(url__regex=r"https://oapi.dingtalk.com/attendance/list.*").mock(
        return_value=httpx.Response(200, json={"recordresult": []})
    )
    conn = DingtalkConnector(_dingtalk_cfg())
    assert await conn.test_connection() is True


@pytest.mark.asyncio
@respx.mock
async def test_feishu_pull_token_in_body():
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=httpx.Response(200, json={"tenant_access_token": "FEITOK", "code": 0})
    )
    respx.get(url__regex=r"https://open.feishu.cn/open-apis/.*").mock(return_value=httpx.Response(
        200, json={"data": {"items": [{"id": 1}]}}
    ))
    cfg = ConnectorConfig(
        base_url="https://open.feishu.cn",
        client_id="cli_abc",
        client_secret="sec_xyz",
        data_path="/open-apis/contact/v3/users",
        records_path="data.items",
    )
    conn = FeishuConnector(cfg)
    recs = await conn.pull()
    assert recs == [{"id": 1}]
    # 令牌以 JSON 体发送 app_id/app_secret
    token_req = respx.calls[0].request
    assert "cli_abc" in (token_req.content or b"").decode()


@pytest.mark.asyncio
@respx.mock
async def test_wecom_pull_token_query():
    respx.get(url__regex=r"https://qyapi.weixin.qq.com/cgi-bin/gettoken.*corpid=corp1").mock(
        return_value=httpx.Response(200, json={"access_token": "WCTOK", "errcode": 0})
    )
    respx.get(url__regex=r"https://qyapi.weixin.qq.com/cgi-bin/.*access_token=WCTOK").mock(
        return_value=httpx.Response(200, json=[{"id": 9}])
    )
    cfg = ConnectorConfig(
        base_url="https://qyapi.weixin.qq.com",
        client_id="corp1",
        client_secret="secret1",
        data_path="/cgi-bin/externalcontact/list",
        records_path=None,
    )
    conn = WeComConnector(cfg)
    recs = await conn.pull()
    assert recs == [{"id": 9}]


def test_registry_oauth2_types():
    assert isinstance(get_connector("dingtalk", _dingtalk_cfg()), DingtalkConnector)
    cfg = ConnectorConfig(base_url="x", client_id="a", client_secret="b")
    assert isinstance(get_connector("feishu", cfg), FeishuConnector)
    assert isinstance(get_connector("wecom", cfg), WeComConnector)
