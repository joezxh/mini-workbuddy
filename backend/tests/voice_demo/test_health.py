"""voice-demo REST 层测试：独立 app + dependency_overrides，不拉起 main.py 重型依赖。

依据 spec docs/superpowers/specs/2026-11-10-voice-demo-design.md §3.2/§5.1。
"""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.routers import voice_demo

FAKE_USER = SimpleNamespace(user_id=1, tenant_id=1, status="active", is_admin=False)


def make_client(use_auth_override: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(voice_demo.router, prefix="/api/v1/voice-demo")
    if use_auth_override:
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def test_health_requires_auth():
    client = make_client(use_auth_override=False)
    # 缺失凭证：HTTPBearer(auto_error) → 403（工程既有行为）
    resp = client.get("/api/v1/voice-demo/health")
    assert resp.status_code == 403
    # 无效 JWT：get_current_user 内部 JWTError → 401（spec §3.6；decode 先于查库，不触库）
    resp = client.get(
        "/api/v1/voice-demo/health",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401


def test_health_shape():
    resp = make_client().get("/api/v1/voice-demo/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"].startswith("http://127.0.0.1:8765")
    assert body["realtime_ws_url"] == "ws://127.0.0.1:8765/v1/realtime"
    # 真实模式探测 /v1/pool：上游在线为 dict，不可达降级 None
    assert body["pool"] is None or isinstance(body["pool"], dict)
