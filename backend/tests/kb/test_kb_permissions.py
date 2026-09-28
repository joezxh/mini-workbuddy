"""KB RBAC 权限点单测（Phase 3 T3）：管理员直通 / 无权限 403 / 有权限放行。

用替身 Session 隔离（系统权限表不在 kb 测试 schema 内），只校验鉴权语义。
"""

from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.services.kb.kb_permissions import (
    ALL_PERMISSIONS,
    KB_ADMIN,
    KB_UPLOAD,
    require_kb_permission,
    user_permissions,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    """替身：按传入权限集返回查询结果。"""

    def __init__(self, perms):
        self._perms = perms

    def execute(self, _stmt):
        return _FakeResult(self._perms)


def _client(perms, user):
    app = FastAPI()

    @app.post("/probe")
    def probe(_p=Depends(require_kb_permission(KB_UPLOAD))):
        return {"ok": True}

    app.dependency_overrides[get_db] = lambda: _FakeSession(perms)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_admin_bypasses_permission_check():
    admin = SimpleNamespace(user_id=1, is_admin=True, tenant_id=100)
    with _client([], admin) as client:
        assert client.post("/probe").status_code == 200  # 管理员直通，不查权限


def test_missing_permission_rejected_403():
    user = SimpleNamespace(user_id=999, is_admin=False, tenant_id=100)
    with _client(["kb:view"], user) as client:
        r = client.post("/probe")
        assert r.status_code == 403
        assert KB_UPLOAD in r.json()["detail"]


def test_permission_granted_passes():
    user = SimpleNamespace(user_id=999, is_admin=False, tenant_id=100)
    with _client([KB_UPLOAD], user) as client:
        assert client.post("/probe").status_code == 200


def test_kb_admin_grants_everything():
    """kb:admin 隐含全部知识库权限。"""
    user = SimpleNamespace(user_id=999, is_admin=False, tenant_id=100)
    with _client([KB_ADMIN], user) as client:
        assert client.post("/probe").status_code == 200


def test_user_permissions_and_constants():
    assert user_permissions(_FakeSession([KB_UPLOAD, None]), 1) == {KB_UPLOAD}
    assert user_permissions(_FakeSession([]), 1) == set()  # 无权限 → 空集（fail-closed）
    assert KB_UPLOAD == "kb:upload" and KB_ADMIN == "kb:admin"
    assert len(ALL_PERMISSIONS) == 5
