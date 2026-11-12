"""语音模型配置 CRUD 端点测试。

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
    """语音模型 CRUD / 默认解析 / 可用性标记。

    注意：模型名必须使用官方实时目录内的有效名称——后端 resolve_voice_config
    （实际连接时）会过滤不可用行（DashScope 模型名无效或密钥为空），无效名
    选中后连接必 401。但 list_voice_models（下拉列表）会返回所有 type=7 模型，
    不可用模型携带 usable=False，便于前端提示用户去「语音模型配置」修复。
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
        # 创建默认语音模型（有效模型名，取自 dashscope 厂商目录）
        mid1 = _create("通义千问 Realtime", "qwen3.8-omni-flash-realtime", True)

        # 列表应包含该模型且为默认
        lst = client.get(f"{BASE}/voice-models").json()
        row = next(x for x in lst if x["id"] == mid1)
        assert row["is_default"] is True
        assert row["model"] == "qwen3.8-omni-flash-realtime"
        assert row["usable"] is True

        # 默认解析应命中该模型
        d = client.get(f"{BASE}/voice-models/default").json()
        assert d["configured"] is True
        assert d["model"] == "qwen3.8-omni-flash-realtime"

        # 创建第二个有效模型并设为默认，旧默认应被清除
        mid2 = _create("通义千问 Realtime Flash", "qwen-audio-3.1-realtime-flash", False)
        sd = client.post(f"{BASE}/voice-models/set-default", json={"model_id": mid2})
        assert sd.status_code == 200
        assert sd.json()["is_default"] is True

        d2 = client.get(f"{BASE}/voice-models/default").json()
        assert d2["model"] == "qwen-audio-3.1-realtime-flash"

        lst2 = client.get(f"{BASE}/voice-models").json()
        by_id = {x["id"]: x for x in lst2}
        assert by_id[mid1]["is_default"] is False
        assert by_id[mid2]["is_default"] is True

        # 可用性标记：无效模型名（如 qwen-realtime-v2）仍会出现在列表中，
        # 但 usable=False，前端可据此提示用户去「语音模型配置」修复；
        # 默认解析（resolve_voice_config）仍不会命中不可用模型。
        mid_invalid = _create("无效模型名", "qwen-realtime-v2", False)
        lst3 = client.get(f"{BASE}/voice-models").json()
        invalid_row = next((x for x in lst3 if x["id"] == mid_invalid), None)
        assert invalid_row is not None
        assert invalid_row["usable"] is False
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
