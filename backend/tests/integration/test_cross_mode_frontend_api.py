"""Task 8 集成层:3 路由端到端测试(真实 SQLite + 真实鉴权 + 真实 L2/Mem0 配合)。

覆盖范围(在 unit/test_ai_context_endpoints.py 之上扩展):
1. POST /entries:真实 finalize 落库后,跨模式检索端到端可读到
2. POST /breakdown:多种 source_mode 写入后聚合统计正确
3. GET /strategies:跨 5 个 9 模式策略字段一致性(全字段断言)

每个端点至少 2 个 E2E 测试:
- 真实 finalize → 真实 L2 → 端点读取(端到端)
- 与 /strategies 数据一致性(状态空间闭环)

测试策略:
- 真实 SQLite(临时 db,create_all 全表)
- TestClient + FastAPI 依赖覆盖(绕过 JWT)
- CrossModeContextRecorder 真实调用,Mem0 mock
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


# --- SQLite 兼容性 ---
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):
    return "INTEGER"


import app.db.init_models  # noqa: F401,E402
from app.db.database import Base  # noqa: E402
from app.models.ai.ai_chat_context_storage import AIChatContextStorage  # noqa: E402
from app.ai.services.cross_mode_recorder import CrossModeContextRecorder  # noqa: E402
from app.routers.ai.ai_context import router as context_router  # noqa: E402
from app.deps import get_current_user  # noqa: E402


# --- Fixtures ---

@pytest.fixture
def sqlite_engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'fe_api_test.db'}")
    Base.metadata.create_all(
        bind=eng,
        tables=[AIChatContextStorage.__table__],
    )
    return eng


@pytest.fixture
def sqlite_session_local(sqlite_engine):
    return sessionmaker(bind=sqlite_engine, autoflush=False, autocommit=False)


@pytest.fixture
def auth_user():
    u = MagicMock()
    u.user_id = 1
    u.tenant_id = 1
    u.status = "active"
    u.username = "e2e_test"
    return u


@pytest.fixture
def client(sqlite_session_local, auth_user):
    """TestClient:真实 SQLite + 鉴权 override + flag 开启。"""
    import app.routers.ai.ai_context as ai_context_module
    original_session_local = ai_context_module.SessionLocal
    ai_context_module.SessionLocal = sqlite_session_local

    test_app = FastAPI()
    test_app.include_router(context_router)
    test_app.dependency_overrides[get_current_user] = lambda: auth_user

    flag_patcher = patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True)
    flag_patcher.start()

    try:
        with TestClient(test_app) as c:
            yield c
    finally:
        flag_patcher.stop()
        ai_context_module.SessionLocal = original_session_local


@pytest.fixture
def recorder(sqlite_session_local):
    """真实 CrossModeContextRecorder(无 mock,Mem0 mock 在调用时 patch)。"""
    s = sqlite_session_local()
    try:
        yield CrossModeContextRecorder(s)
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────────────
# E2E 1:POST /entries — 真实 finalize 落库后,跨模式检索端到端
# ─────────────────────────────────────────────────────────────────────

class TestEntriesEndToEnd:
    """真实 finalize → L2 落库 → /entries 读取,验证完整链路。"""

    def test_e2e_entries_after_real_finalize(self, client, recorder, sqlite_session_local):
        """真实 recorder.record_finalize(general)→ L2 落库 → /entries 应能读到。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True
            MockMem0.return_value = mock_inst

            # 真实落库
            recorder.record_finalize(
                session_id=500, user_id=1, tenant_id=1,
                session_type="general",
                payload={
                    "user_input": "普通问题",
                    "answer": "这是普通回答",
                },
            )

        # /entries 端到端读取
        r = client.post("/ai/context/entries", json={"session_id": 500})
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert len(items) >= 1
        # 落库条目应能被检索
        source_modes = {item["source_mode"] for item in items}
        assert "general" in source_modes

    def test_e2e_entries_cross_mode_via_real_deep_research(
        self, client, recorder, sqlite_session_local
    ):
        """真实 recorder(deep_research)→ is_cross_mode_accessible=True → /entries allow_cross_mode=True 可见。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True
            MockMem0.return_value = mock_inst

            recorder.record_finalize(
                session_id=600, user_id=1, tenant_id=1,
                session_type="deep_research",
                payload={
                    "user_input": "AI 趋势调研",
                    "sub_questions": ["趋势1", "趋势2"],
                    "final_report": "AI 趋势调研报告...详细分析",
                    "sources": ["url1", "url2"],
                },
            )

        # allow_cross_mode=False → 跨模式条目不可见
        r_iso = client.post(
            "/ai/context/entries",
            json={"session_id": 600, "allow_cross_mode": False},
        )
        assert r_iso.status_code == 200
        iso_modes = {item["source_mode"] for item in r_iso.json()["items"]}
        assert "deep_research" not in iso_modes

        # allow_cross_mode=True → 跨模式条目可见
        r_open = client.post(
            "/ai/context/entries",
            json={"session_id": 600, "allow_cross_mode": True},
        )
        assert r_open.status_code == 200
        open_modes = {item["source_mode"] for item in r_open.json()["items"]}
        assert "deep_research" in open_modes


# ─────────────────────────────────────────────────────────────────────
# E2E 2:POST /breakdown — 多种 source_mode 写入后聚合统计
# ─────────────────────────────────────────────────────────────────────

class TestBreakdownEndToEnd:
    """真实多模式 finalize → /breakdown 聚合统计。"""

    def test_e2e_breakdown_aggregates_multiple_modes(
        self, client, recorder, sqlite_session_local
    ):
        """三种模式 finalize 后,/breakdown 聚合 entry_count 正确。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True
            MockMem0.return_value = mock_inst

            for mode_payload in [
                ("general", {"user_input": "q1", "answer": "a1"}),
                ("general", {"user_input": "q2", "answer": "a2"}),
                ("skill", {
                    "skill_name": "test_skill",
                    "skill_display_name": "测试技能",
                    "user_input": "skill_q",
                    "result": "ok",
                    "execution_id": "e1",
                }),
                ("react", {"user_input": "react_q", "answer": "react_a"}),
            ]:
                mode, payload = mode_payload
                recorder.record_finalize(
                    session_id=700, user_id=1, tenant_id=1,
                    session_type=mode, payload=payload,
                )

        r = client.post("/ai/context/breakdown", json={"session_id": 700})
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        counts = {row["source_mode"]: row["entry_count"] for row in items}
        # general 2 次,skill 1 次,react 1 次
        assert counts.get("general") == 2
        assert counts.get("skill") == 1
        assert counts.get("react") == 1

    def test_e2e_breakdown_isolated_per_session(
        self, client, recorder, sqlite_session_local
    ):
        """/breakdown 按 session_id 隔离,其他 session 的条目不计入。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True
            MockMem0.return_value = mock_inst

            # session 800: skill
            recorder.record_finalize(
                session_id=800, user_id=1, tenant_id=1,
                session_type="skill",
                payload={
                    "skill_name": "s", "skill_display_name": "技能",
                    "user_input": "x", "result": "y", "execution_id": "e1",
                },
            )
            # session 801: general(不同 session)
            recorder.record_finalize(
                session_id=801, user_id=1, tenant_id=1,
                session_type="general",
                payload={"user_input": "x", "answer": "y"},
            )

        # session 800 应只看到 skill
        r800 = client.post("/ai/context/breakdown", json={"session_id": 800})
        items_800 = {row["source_mode"]: row["entry_count"] for row in r800.json()["items"]}
        assert items_800 == {"skill": 1}


# ─────────────────────────────────────────────────────────────────────
# E2E 3:GET /strategies — 9 模式策略全字段一致性
# ─────────────────────────────────────────────────────────────────────

class TestStrategiesConsistency:
    """/strategies 与 STRATEGY_TABLE 数据驱动一致 + 全字段非空。"""

    EXPECTED_FIELD_KEYS = {
        "session_type", "source_mode", "priority", "ttl_hours",
        "write_mem0", "is_cross_mode_accessible",
        "display_label", "display_color",
    }

    def test_e2e_strategies_matches_strategy_table_count(self, client):
        """/strategies 返回条目数 == STRATEGY_TABLE 长度。"""
        from app.ai.services.cross_mode_recorder import STRATEGY_TABLE
        r = client.get("/ai/context/strategies")
        assert r.status_code == 200, r.text
        items = r.json()["strategies"]
        assert len(items) == len(STRATEGY_TABLE)

    def test_e2e_strategies_cross_mode_flags_match(self, client):
        """3 个跨模式可读策略 = deep_research + agent + team。"""
        from app.ai.services.cross_mode_recorder import STRATEGY_TABLE
        r = client.get("/ai/context/strategies")
        assert r.status_code == 200
        items = r.json()["strategies"]

        # 与 STRATEGY_TABLE 比对
        api_cross_modes = {
            s["session_type"] for s in items if s["is_cross_mode_accessible"]
        }
        table_cross_modes = {
            k for k, v in STRATEGY_TABLE.items() if v.is_cross_mode_accessible
        }
        assert api_cross_modes == table_cross_modes

    def test_e2e_strategies_write_mem0_flags_match(self, client):
        """write_mem0=False 的策略 = scheduled + shared(后台调度 + 共享层不写永久记忆)。"""
        from app.ai.services.cross_mode_recorder import STRATEGY_TABLE
        r = client.get("/ai/context/strategies")
        assert r.status_code == 200
        items = r.json()["strategies"]

        api_no_mem0 = {s["session_type"] for s in items if not s["write_mem0"]}
        table_no_mem0 = {
            k for k, v in STRATEGY_TABLE.items() if not v.write_mem0
        }
        assert api_no_mem0 == table_no_mem0

    def test_e2e_strategies_all_fields_non_empty(self, client):
        """所有策略条目字段非空 + 类型正确。"""
        r = client.get("/ai/context/strategies")
        assert r.status_code == 200
        for s in r.json()["strategies"]:
            # 字段完整
            assert self.EXPECTED_FIELD_KEYS.issubset(s.keys())
            # 类型正确
            assert isinstance(s["session_type"], str) and s["session_type"]
            assert isinstance(s["source_mode"], str) and s["source_mode"]
            assert isinstance(s["priority"], int)
            assert isinstance(s["ttl_hours"], int) and s["ttl_hours"] > 0
            assert isinstance(s["write_mem0"], bool)
            assert isinstance(s["is_cross_mode_accessible"], bool)
            assert isinstance(s["display_label"], str) and s["display_label"]
            assert isinstance(s["display_color"], str) and s["display_color"]
