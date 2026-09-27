"""Task 8 (PR-2): ai_context.py 新增 3 个前端路由的单元测试。

覆盖范围:
1. POST /entries:跨模式上下文条目检索(L2 列表 + 过滤)
2. POST /breakdown:按 source_mode 聚合统计
3. GET /strategies:返回 STRATEGY_TABLE 给前端(9 模式)

每个端点至少 3 个测试:
- 成功路径(返回 200 + 期望数据结构)
- 鉴权失败(未注入 user 时拒绝)
- 关闭 flag 行为(仅 entries + breakdown 受影响,strategies 总是 200)

测试策略:
- 用 FastAPI TestClient + 最小化 test_app(避免启动 lifespan)
- get_current_user 在 ai_context 模块级被 MagicMock 替换
- DB 用临时 SQLite(create_all + SQLite JSONB/JSON 兼容编译)
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


# --- SQLite 兼容性(沿用 test_2026_09_27_cross_mode_fields 模式) ---
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "JSON"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "INTEGER"


# 触发所有模型注册(包括跨模式相关表)
import app.db.init_models  # noqa: F401,E402
from app.db.database import Base  # noqa: E402
from app.models.ai.ai_chat_context_storage import AIChatContextStorage  # noqa: E402


# --- 共享 fixture ---

@pytest.fixture
def sqlite_engine(tmp_path):
    """创建内存 SQLite + create_all 跨模式相关表。"""
    eng = create_engine(f"sqlite:///{tmp_path / 'ctx_test.db'}")
    Base.metadata.create_all(
        bind=eng,
        tables=[AIChatContextStorage.__table__],
    )
    return eng


@pytest.fixture
def sqlite_session_local(sqlite_engine):
    """返回可注入 monkeypatched SessionLocal(sessionmaker 实例)。"""
    return sessionmaker(bind=sqlite_engine, autoflush=False, autocommit=False)


@pytest.fixture
def auth_user():
    """构造模拟当前登录用户。"""
    u = MagicMock()
    u.user_id = 1
    u.tenant_id = 1
    u.status = "active"
    u.username = "test_user"
    return u


@pytest.fixture
def client(sqlite_session_local, auth_user):
    """构建最小化 test_app + TestClient,绕过 lifespan / 主路由表。

    - 隔离 SessionLocal → 让端点落到测试 SQLite
    - 用 FastAPI dependency_overrides 替换 get_current_user → 绕过 JWT
    - 默认开启 ENABLE_CROSS_MODE_RECORDER,flag-off 测试再用 patch 关闭
    """
    import app.routers.ai.ai_context as ai_context_module
    from app.deps import get_current_user

    original_session_local = ai_context_module.SessionLocal
    ai_context_module.SessionLocal = sqlite_session_local

    test_app = FastAPI()
    test_app.include_router(ai_context_module.router)
    test_app.dependency_overrides[get_current_user] = lambda: auth_user

    flag_patcher = patch(
        "app.config.settings.ENABLE_CROSS_MODE_RECORDER", True
    )
    flag_patcher.start()

    try:
        with TestClient(test_app) as c:
            yield c
    finally:
        flag_patcher.stop()
        ai_context_module.SessionLocal = original_session_local


# ─────────────────────── POST /entries ───────────────────────

class TestEntriesEndpoint:
    """POST /entries 跨模式上下文条目检索。"""

    def _seed_rows(self, sqlite_session_local) -> None:
        s = sqlite_session_local()
        try:
            s.add(AIChatContextStorage(
                tenant_id=1, session_id=20, user_id=1, mode="skill",
                source_mode="skill", context_key="k1",
                context_data={"v": 1}, context_tags=["skill", "report_gen"],
                is_cross_mode_accessible=False,
            ))
            s.add(AIChatContextStorage(
                tenant_id=1, session_id=20, user_id=1, mode="deep_research",
                source_mode="deep_research", context_key="k2",
                context_data={"v": 2}, context_tags=["deep_research"],
                is_cross_mode_accessible=True,
            ))
            s.commit()
        finally:
            s.close()

    def test_entries_success_returns_items_and_total(self, client, sqlite_session_local):
        """成功路径:返回 items + total 字段,默认行为过滤跨模式条目。"""
        self._seed_rows(sqlite_session_local)
        r = client.post("/ai/context/entries", json={"session_id": 20})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert "total" in body
        # 默认 allow_cross_mode=False → 跨模式条目被排除,仅返回 skill
        source_modes = {item["source_mode"] for item in body["items"]}
        assert source_modes == {"skill"}

    def test_entries_with_source_mode_and_tags(self, client, sqlite_session_local):
        """成功路径:source_mode + include_tags 过滤生效。"""
        self._seed_rows(sqlite_session_local)
        r = client.post(
            "/ai/context/entries",
            json={
                "session_id": 20,
                "source_mode": "skill",
                "include_tags": ["report_gen"],
                "limit": 10,
            },
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert len(items) >= 1
        assert all(i["source_mode"] == "skill" for i in items)

    def test_entries_disallowed_when_flag_off(self, client, sqlite_session_local):
        """关闭 flag(ENABLE_CROSS_MODE_RECORDER=False)时,/entries 返回 503。"""
        self._seed_rows(sqlite_session_local)
        with patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", False):
            r = client.post("/ai/context/entries", json={"session_id": 20})
        assert r.status_code == 503
        assert r.json()["detail"] == "cross-mode recorder disabled"


# ─────────────────────── POST /breakdown ───────────────────────

class TestBreakdownEndpoint:
    """POST /breakdown 按 source_mode 聚合统计。"""

    def _seed_rows(self, sqlite_session_local) -> None:
        s = sqlite_session_local()
        try:
            for i in range(3):
                s.add(AIChatContextStorage(
                    tenant_id=1, session_id=10, user_id=1, mode="skill",
                    source_mode="skill", context_key=f"k{i}",
                    context_data={"v": i}, is_cross_mode_accessible=False,
                ))
            s.add(AIChatContextStorage(
                tenant_id=1, session_id=10, user_id=1, mode="agent",
                source_mode="agent", context_key="k_ag",
                context_data={"v": 99}, is_cross_mode_accessible=True,
            ))
            s.commit()
        finally:
            s.close()

    def test_breakdown_groups_by_source_mode(self, client, sqlite_session_local):
        """成功路径:返回 items,按 source_mode 聚合 entry_count。"""
        self._seed_rows(sqlite_session_local)
        r = client.post("/ai/context/breakdown", json={"session_id": 10})
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        # 转成 dict 以便查找
        counts = {row["source_mode"]: row["entry_count"] for row in items}
        assert counts.get("skill") == 3
        assert counts.get("agent") == 1

    def test_breakdown_empty_session_returns_empty_items(self, client):
        """成功路径:无数据时返回空 items(不报错)。"""
        r = client.post("/ai/context/breakdown", json={"session_id": 999})
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_breakdown_disallowed_when_flag_off(self, client, sqlite_session_local):
        """关闭 flag 时,/breakdown 返回 503。"""
        self._seed_rows(sqlite_session_local)
        with patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", False):
            r = client.post("/ai/context/breakdown", json={"session_id": 10})
        assert r.status_code == 503
        assert r.json()["detail"] == "cross-mode recorder disabled"


# ─────────────────────── GET /strategies ───────────────────────

EXPECTED_SESSION_TYPES = {
    "general", "react", "thinking", "deep_research",
    "skill", "agent", "team", "scheduled", "shared",
}


class TestStrategiesEndpoint:
    """GET /strategies 返回 STRATEGY_TABLE(9 模式)。"""

    def test_strategies_returns_9_session_types(self, client):
        """成功路径:返回 9 个 session_type。"""
        r = client.get("/ai/context/strategies")
        assert r.status_code == 200, r.text
        items = r.json()["strategies"]
        assert len(items) == 9
        types = {s["session_type"] for s in items}
        assert types == EXPECTED_SESSION_TYPES

    def test_strategies_have_full_fields(self, client):
        """成功路径:每条策略包含全部字段。"""
        r = client.get("/ai/context/strategies")
        assert r.status_code == 200
        for s in r.json()["strategies"]:
            required = {
                "session_type", "source_mode", "priority", "ttl_hours",
                "write_mem0", "is_cross_mode_accessible",
                "display_label", "display_color",
            }
            assert required.issubset(s.keys()), (
                f"missing fields in {s['session_type']}: {required - s.keys()}"
            )
            assert isinstance(s["priority"], int)
            assert isinstance(s["ttl_hours"], int)
            assert isinstance(s["write_mem0"], bool)
            assert isinstance(s["is_cross_mode_accessible"], bool)
            assert isinstance(s["display_label"], str)
            assert isinstance(s["display_color"], str)

    def test_strategies_always_available_even_when_flag_off(self, client):
        """关闭 flag 时,/strategies 仍然返回 200(前端可 fallback)。"""
        with patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", False):
            r = client.get("/ai/context/strategies")
        assert r.status_code == 200
        assert len(r.json()["strategies"]) == 9


# ─────────────────────── 鉴权失败路径 ───────────────────────

class TestAuthFailure:
    """未通过认证时,所有 3 个端点返回 401(或 403,见具体说明)。"""

    def _client_no_auth(self, sqlite_session_local):
        """构造无 get_current_user 覆盖的 test_app → 触发 HTTPBearer 403。"""
        import app.routers.ai.ai_context as ai_context_module
        ai_context_module.SessionLocal = sqlite_session_local
        test_app = FastAPI()
        test_app.include_router(ai_context_module.router)
        return test_app

    def test_entries_requires_auth(self, sqlite_session_local):
        """未注入 auth user → /entries 返回 403(HTTPBearer 拒绝)。"""
        test_app = self._client_no_auth(sqlite_session_local)
        with TestClient(test_app) as c:
            r = c.post("/ai/context/entries", json={"session_id": 1})
        # HTTPBearer auto_error=True 时返回 403
        assert r.status_code in (401, 403), r.text

    def test_breakdown_requires_auth(self, sqlite_session_local):
        """未注入 auth user → /breakdown 返回 403(HTTPBearer 拒绝)。"""
        test_app = self._client_no_auth(sqlite_session_local)
        with TestClient(test_app) as c:
            r = c.post("/ai/context/breakdown", json={"session_id": 1})
        assert r.status_code in (401, 403), r.text

    def test_strategies_public_endpoint(self, sqlite_session_local):
        """/strategies 是公开端点(无 Depends(get_current_user)),前端可匿名访问。

        plan 中也未给该端点加 auth 依赖,前端 fallback 路径必须能命中。
        """
        import app.routers.ai.ai_context as ai_context_module
        ai_context_module.SessionLocal = sqlite_session_local
        test_app = FastAPI()
        test_app.include_router(ai_context_module.router)
        with TestClient(test_app) as c:
            r = c.get("/ai/context/strategies")
        assert r.status_code == 200, r.text
        assert len(r.json()["strategies"]) == 9
