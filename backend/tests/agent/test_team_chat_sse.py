# -*- coding: utf-8 -*-
"""/ai-team/{team_id}/chat SSE：UserMsg 必须携带 name（agentscope 2.x 必填）。"""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db


def test_chat_sse_user_msg_has_name(monkeypatch):
    import app.ai.agent_factory as factory_mod
    import app.routers.agent.agent_team as team_router

    captured = {}

    class FakeTeamAgent:
        def __init__(self, db=None, team_id=None, model_id=None, name=None):
            pass

        async def reply_stream(self, user_msg):
            captured["name"] = getattr(user_msg, "name", None)
            captured["content"] = user_msg.content
            yield {"type": "message", "data": {"text": "ok"}}

    class FakeSvc:
        def __init__(self, db=None):
            pass

        def get_team(self, team_id):
            return SimpleNamespace(id=team_id, name="外贸询盘报价")

    monkeypatch.setattr(factory_mod, "TeamAgent", FakeTeamAgent)
    monkeypatch.setattr(team_router, "AgentTeamService", FakeSvc)

    app = FastAPI()
    app.include_router(team_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id=1)
    client = TestClient(app)

    r = client.post("/api/v1/ai-team/3/chat", json={"message": "你好"})
    assert r.status_code == 200
    assert "event: message" in r.text
    assert captured["name"] == "user"