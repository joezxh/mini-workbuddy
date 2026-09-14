"""T21: 调解语音配置 CRUD 端点测试。

注：本测试需导入 app.main（触发完整应用装配）。置于 tests/duplex 下，
复用该目录 conftest 对 gssapi 的 mock（Windows 缺 Kerberos 时 celery 导入会失败）。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

BASE = "/api/v1/admin/duplex/config"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_upsert_and_list_voice_role(client):
    payload = {
        "role_id": "mediator",
        "role_name": "调解员",
        "greeting": "您好，我是本次调解的调解员",
        "voice_identity": "female-1",
    }
    r = client.post(f"{BASE}/voice-roles", json=payload)
    assert r.status_code == 200
    assert r.json()["role_id"] == "mediator"

    lst = client.get(f"{BASE}/voice-roles").json()
    assert any(x["role_id"] == "mediator" for x in lst)


def test_get_voice_role_by_id(client):
    client.post(f"{BASE}/voice-roles", json={
        "role_id": "party_a", "role_name": "甲方", "greeting": "我是甲方",
    })
    r = client.get(f"{BASE}/voice-roles/party_a")
    assert r.status_code == 200
    assert r.json()["role_name"] == "甲方"


def test_get_missing_role_returns_404(client):
    assert client.get(f"{BASE}/voice-roles/__not_exist__").status_code == 404


def test_upsert_and_list_agent(client):
    payload = {
        "agent_id": "duplex-agent-1",
        "name": "调解 Agent",
        "type": "agentscope",
        "model": "qwen-plus",
        "system_prompt": "你是调解员",
        "max_react_iters": 3,
        "enable_plan": False,
    }
    r = client.post(f"{BASE}/agents", json=payload)
    assert r.status_code == 200
    assert r.json()["agent_id"] == "duplex-agent-1"

    lst = client.get(f"{BASE}/agents").json()
    row = next(x for x in lst if x["agent_id"] == "duplex-agent-1")
    assert row["max_react_iters"] == 3
    assert row["enable_plan"] is False


def test_upsert_and_list_tool_policy(client):
    payload = {
        "tool_name": "search_law",
        "enabled": True,
        "timeout_ms": 5000,
        "max_calls_per_turn": 1,
        "max_result_bytes": 16384,
    }
    r = client.post(f"{BASE}/tool-policy", json=payload)
    assert r.status_code == 200
    assert r.json()["tool_name"] == "search_law"

    lst = client.get(f"{BASE}/tool-policy").json()
    row = next(x for x in lst if x["tool_name"] == "search_law")
    assert row["timeout_ms"] == 5000
    assert row["max_calls_per_turn"] == 1


def test_upsert_is_idempotent(client):
    """同 key 重复写入应更新而非新增。"""
    payload = {"role_id": "party_b", "role_name": "乙方 v1"}
    client.post(f"{BASE}/voice-roles", json=payload)
    client.post(f"{BASE}/voice-roles", json={**payload, "role_name": "乙方 v2"})

    lst = client.get(f"{BASE}/voice-roles").json()
    matched = [x for x in lst if x["role_id"] == "party_b"]
    assert len(matched) == 1
    assert matched[0]["role_name"] == "乙方 v2"


def _create_api_key(client) -> int:
    """直接插入一条 DashScope 密钥，供语音模型测试使用。"""
    from app.db.database import SessionLocal
    from app.models.ai.ai_api_key import AiApiKey

    db = SessionLocal()
    try:
        key = AiApiKey(
            name="测试-DashScope",
            platform="DashScope",
            api_key="sk-test-voice-config",
            status=1,
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        return key.id
    finally:
        db.close()


def test_voice_model_crud_and_default(client):
    """语音模型 CRUD / 默认解析 / 可用性过滤。

    注意：模型名必须使用官方实时目录内的有效名称——后端 list_voice_models 与
    默认解析会过滤不可用行（DashScope 模型名无效或密钥为空），无效名选中后
    连接必 401（见 46 号 SQL 与 voice_config.VALID_DASHSCOPE_REALTIME_MODELS）。
    测试结束自清理创建的密钥与模型，避免污染共享数据库。
    """
    key_id = _create_api_key(client)
    created_model_ids = []

    def _create(name: str, model: str, is_default: bool) -> int:
        r = client.post(f"{BASE}/voice-models", json={
            "key_id": key_id, "name": name, "model": model, "is_default": is_default,
        })
        assert r.status_code == 200
        created_model_ids.append(r.json()["id"])
        return r.json()["id"]

    try:
        # 创建默认语音模型（有效模型名）
        mid1 = _create("通义千问 Realtime", "qwen-audio-3.0-realtime-plus", True)

        # 列表应包含该模型且为默认
        lst = client.get(f"{BASE}/voice-models").json()
        row = next(x for x in lst if x["id"] == mid1)
        assert row["is_default"] is True
        assert row["model"] == "qwen-audio-3.0-realtime-plus"

        # 默认解析应命中该模型
        d = client.get(f"{BASE}/voice-models/default").json()
        assert d["configured"] is True
        assert d["model"] == "qwen-audio-3.0-realtime-plus"

        # 创建第二个有效模型并设为默认，旧默认应被清除
        mid2 = _create("通义千问 Realtime Flash", "qwen-audio-3.0-realtime-flash", False)
        sd = client.post(f"{BASE}/voice-models/set-default", json={"model_id": mid2})
        assert sd.status_code == 200
        assert sd.json()["is_default"] is True

        d2 = client.get(f"{BASE}/voice-models/default").json()
        assert d2["model"] == "qwen-audio-3.0-realtime-flash"

        lst2 = client.get(f"{BASE}/voice-models").json()
        by_id = {x["id"]: x for x in lst2}
        assert by_id[mid1]["is_default"] is False
        assert by_id[mid2]["is_default"] is True

        # 可用性过滤：无效模型名（如历史测试数据 qwen-realtime-v2）不进入列表，
        # 默认解析也不应命中它
        mid_invalid = _create("无效模型名", "qwen-realtime-v2", False)
        lst3 = client.get(f"{BASE}/voice-models").json()
        assert all(x["id"] != mid_invalid for x in lst3)
        d3 = client.get(f"{BASE}/voice-models/default").json()
        assert d3.get("model_id") != mid_invalid
    finally:
        # 自清理：删除本测试创建的模型与密钥（共享数据库防污染）
        from app.db.database import SessionLocal
        from app.models.ai.ai_api_key import AiApiKey, AiChatModel

        db = SessionLocal()
        try:
            if created_model_ids:
                db.query(AiChatModel).filter(
                    AiChatModel.id.in_(created_model_ids)
                ).delete(synchronize_session=False)
            db.query(AiApiKey).filter(AiApiKey.id == key_id).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()


def test_set_default_missing_model_returns_400(client):
    r = client.post(f"{BASE}/voice-models/set-default", json={"model_id": 999999})
    assert r.status_code == 400
