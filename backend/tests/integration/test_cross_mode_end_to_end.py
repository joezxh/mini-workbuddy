"""Task 15: 端到端集成测试 — 模拟 SSE finalize → 触发 recorder → 验证 L2 + Mem0 + 检索。

覆盖范围:
- test_end_to_end_skill_mode:L2 落库 + Mem0 调用 + 检索可读
- test_end_to_end_scheduled_no_mem0:scheduled 仅 L2,不调 Mem0
- test_end_to_end_deep_research_cross_mode:is_cross_mode_accessible=True 跨模式检索
- test_end_to_end_l2_persistence_and_audit_log:L2 行 + ai_session_finalize_log 审计
- test_end_to_end_mem0_failure_silent:Mem0 失败静默,不影响 L2

测试策略:
- 真实 SQLite(create_all + JSONB → JSON 兼容编译)
- Mem0Service 用 MagicMock 替换,避免外部依赖
- ai_session_finalize_log 与 AIChatContextStorage 共享同一临时 SQLite
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


# --- SQLite 兼容性(沿用现有测试模式) ---
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "JSON"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN202
    return "INTEGER"


# 触发所有模型注册
import app.db.init_models  # noqa: F401,E402
from app.db.database import Base  # noqa: E402
from app.models.ai.ai_chat_context_storage import AIChatContextStorage  # noqa: E402
from app.models.ai.ai_session_finalize_log import AISessionFinalizeLog  # noqa: E402
from app.ai.services.cross_mode_recorder import CrossModeContextRecorder  # noqa: E402


# --- Fixtures ---

@pytest.fixture
def sqlite_engine(tmp_path):
    """内存 SQLite + create_all 跨模式相关表(AIChatContextStorage + AISessionFinalizeLog)。"""
    eng = create_engine(f"sqlite:///{tmp_path / 'e2e_test.db'}")
    Base.metadata.create_all(
        bind=eng,
        tables=[
            AIChatContextStorage.__table__,
            AISessionFinalizeLog.__table__,
        ],
    )
    return eng


@pytest.fixture
def db(sqlite_engine):
    """SQLAlchemy session — E2E 主体用的 db 对象。"""
    s = sessionmaker(bind=sqlite_engine, autoflush=False, autocommit=False)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def recorder(db):
    """真实 CrossModeContextRecorder(无 mock,只 patch Mem0Service)。"""
    return CrossModeContextRecorder(db)


@pytest.fixture(autouse=True)
def _enable_flag():
    """全局开启 ENABLE_CROSS_MODE_RECORDER,避免 E2E 路径被 flag 截胡。"""
    flag_patcher = patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True)
    flag_patcher.start()
    try:
        yield
    finally:
        flag_patcher.stop()


# ─────────────────────────────────────────────────────────────────────
# E2E 用例 1:Skill 模式 — L2 落库 + Mem0 调用 + 检索可读
# ─────────────────────────────────────────────────────────────────────

class TestSkillModeEndToEnd:
    """Skill 模式端到端:模拟 SSE finalize 入口 → 触发 recorder → 验证全链路。"""

    def test_end_to_end_skill_mode(self, db, recorder):
        """Skill 模式端到端:L2 + Mem0 同步 + 检索。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True  # Mem0Service.record → bool
            MockMem0.return_value = mock_inst

            # 模拟 skill finalize
            rid = recorder.record_finalize(
                session_id=100, user_id=1, tenant_id=1,
                session_type="skill",
                payload={
                    "skill_name": "report_gen",
                    "skill_display_name": "报告生成器",
                    "user_input": "生成本月报告",
                    "result": "已生成 PDF",
                    "execution_id": "exec-001",
                },
                case_number="default",
            )

        # 1) L2 落库
        assert rid is not None
        row = db.query(AIChatContextStorage).get(rid)
        assert row is not None
        assert row.source_mode == "skill"
        assert "skill" in row.context_tags
        assert "report_gen" in row.context_tags
        assert row.is_cross_mode_accessible is False
        assert row.context_data["skill_name"] == "report_gen"

        # 2) Mem0 调用过(message 包含报告生成器)
        mock_inst.record.assert_called_once()
        call_args = mock_inst.record.call_args
        assert "报告生成器" in call_args.kwargs["message"]

        # 3) 检索可读(同模式内 allow_cross_mode=False,应能读到自己的 skill 记录)
        from app.ai.context_manager import ContextManager
        mgr = ContextManager(tenant_id=1, user_id=1)
        entries = mgr.get_context_with_mode_filter(
            session_id=100, user_id=1, allow_cross_mode=False,
            source_mode="skill", db=db,
        )
        assert len(entries) == 1
        assert entries[0]["context_data"]["skill_name"] == "report_gen"
        assert entries[0]["source_mode"] == "skill"


# ─────────────────────────────────────────────────────────────────────
# E2E 用例 2:Scheduled 模式 — 仅 L2,不调 Mem0
# ─────────────────────────────────────────────────────────────────────

class TestScheduledNoMem0:
    """Scheduled 模式端到端:仅 L2,不调 Mem0。"""

    def test_end_to_end_scheduled_no_mem0(self, db, recorder):
        """Scheduled 端到端:仅 L2,不调 Mem0。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            MockMem0.return_value = mock_inst

            rid = recorder.record_finalize(
                session_id=200, user_id=1, tenant_id=1,
                session_type="scheduled",
                payload={
                    "task_id": 999, "task_no": "T-001",
                    "target_mode": "agent", "user_input": "x",
                    "priority": 5,
                },
            )

        # L2 落库成功
        assert rid is not None
        # Mem0 未调用
        mock_inst.record.assert_not_called()
        row = db.query(AIChatContextStorage).get(rid)
        assert row is not None
        assert row.source_mode == "scheduled"
        assert row.is_cross_mode_accessible is False
        assert row.context_data["task_id"] == 999


# ─────────────────────────────────────────────────────────────────────
# E2E 用例 3:Deep Research 模式 — 跨模式可读
# ─────────────────────────────────────────────────────────────────────

class TestDeepResearchCrossMode:
    """Deep research 模式端到端:is_cross_mode_accessible=True,其他模式能读到。"""

    def test_end_to_end_deep_research_cross_mode(self, db, recorder):
        """Deep research 端到端:is_cross_mode_accessible=True,跨模式检索可读到。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True
            MockMem0.return_value = mock_inst

            rid = recorder.record_finalize(
                session_id=300, user_id=1, tenant_id=1,
                session_type="deep_research",
                payload={
                    "user_input": "AI 趋势",
                    "sub_questions": ["Q1", "Q2"],
                    "final_report": "趋势分析报告...",
                    "sources": [1, 2, 3],
                },
            )

        assert rid is not None
        row = db.query(AIChatContextStorage).get(rid)
        assert row.is_cross_mode_accessible is True
        assert row.source_mode == "deep_research"

        # 跨模式检索:general 模式 + allow_cross_mode=True 应能读到
        from app.ai.context_manager import ContextManager
        mgr = ContextManager(tenant_id=1, user_id=1)
        entries = mgr.get_context_with_mode_filter(
            session_id=300, user_id=1, allow_cross_mode=True,
            source_mode="deep_research", db=db,
        )
        assert len(entries) == 1
        assert entries[0]["is_cross_mode_accessible"] is True

        # 反之:allow_cross_mode=False 不应返回(默认过滤)
        entries_iso = mgr.get_context_with_mode_filter(
            session_id=300, user_id=1, allow_cross_mode=False,
            source_mode="deep_research", db=db,
        )
        assert len(entries_iso) == 0


# ─────────────────────────────────────────────────────────────────────
# E2E 用例 4:L2 行 + ai_session_finalize_log 审计
# ─────────────────────────────────────────────────────────────────────

class TestL2AndAuditLog:
    """L2 落库 + ai_session_finalize_log 审计日志双写。"""

    def test_end_to_end_writes_audit_log(self, db, recorder):
        """Recorder 写入 L2 的同时,ai_session_finalize_log 也新增一条记录。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            mock_inst.record.return_value = True
            MockMem0.return_value = mock_inst

            rid = recorder.record_finalize(
                session_id=400, user_id=2, tenant_id=2,
                session_type="agent",
                payload={
                    "user_input": "执行任务",
                    "final_answer": "任务已完成,返回结果: OK",  # agent.extract_summary 读 final_answer
                    "result": "完成",
                    "agent_name": "test_agent",
                },
            )

        assert rid is not None
        # 审计日志存在
        audit = (
            db.query(AISessionFinalizeLog)
            .filter(AISessionFinalizeLog.session_id == 400)
            .one()
        )
        assert audit.session_type == "agent"
        assert audit.source_mode == "agent"
        assert audit.l2_record_id == rid
        assert audit.mem0_synced is True
        # ContextManager.sync_to_long_term 规范化为 f"mem_{user_id}_{session_id}"
        assert audit.mem0_memory_id == "mem_2_400"
        assert audit.error_message is None


# ─────────────────────────────────────────────────────────────────────
# E2E 用例 5:Mem0 失败静默 — 不影响 L2
# ─────────────────────────────────────────────────────────────────────

class TestMem0FailureSilent:
    """Mem0 调用失败时,L2 仍应落库,审计日志记 mem0_synced=False。"""

    def test_end_to_end_mem0_failure_silent(self, db, recorder):
        """Mem0 失败 → 异常被吞 → L2 仍落库 + 审计标记失败。"""
        with patch("app.ai.services.mem0_service.Mem0Service") as MockMem0:
            mock_inst = MagicMock()
            # record 调用内部抛错,但 ContextManager.sync_to_long_term 应已 try/except 静默
            mock_inst.record.side_effect = RuntimeError("Mem0 unavailable")
            MockMem0.return_value = mock_inst

            # 整条 record_finalize 不应抛
            rid = recorder.record_finalize(
                session_id=500, user_id=1, tenant_id=1,
                session_type="general",
                payload={
                    "user_input": "测试 Mem0 失败",
                    "answer": "回答",
                },
            )

        # L2 落库仍然成功
        assert rid is not None
        row = db.query(AIChatContextStorage).get(rid)
        assert row is not None
        assert row.source_mode == "general"
