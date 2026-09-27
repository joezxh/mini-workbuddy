"""STRATEGY_TABLE 9 会话模式 + record_finalize 主入口测试。

v2.0:会话模式清单加入 data(SQLBot);shared 为存储层兜底(非会话模式)。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.ai.services.cross_mode_recorder import (
    STRATEGY_TABLE,
    CrossModeContextRecorder,
    StreamAnswerCollector,
    finalize_chat_stream,
)


# 9 种会话模式(权威清单)+ shared 存储兜底
SESSION_MODES = {
    "general", "react", "thinking", "deep_research",
    "skill", "agent", "team", "data", "scheduled",
}
ALL_TABLE_MODES = SESSION_MODES | {"shared"}


def test_all_nine_modes_have_strategy():
    expected = ALL_TABLE_MODES
    for m in expected:
        assert m in STRATEGY_TABLE, f"missing strategy for {m}"
        assert STRATEGY_TABLE[m].source_mode == m


def test_data_strategy():
    """data(SQLBot) 策略:48h TTL、写 Mem0、跨模式隔离"""
    s = STRATEGY_TABLE["data"]
    assert s.ttl_hours == 48
    assert s.write_mem0 is True
    assert s.is_cross_mode_accessible is False
    payload = {
        "user_input": "近 7 天风险事件数量",
        "sql": "SELECT COUNT(*) FROM risk_event",
        "record_count": 156,
        "datasource_id": 42,
        "chart_type": "column",
    }
    assert "datasource_42" in s.context_tags(payload)
    summary = s.extract_summary(payload)
    assert "SQL" in summary and "156" in summary


def test_scheduled_does_not_write_mem0():
    """scheduled 模式 write_mem0=False(永久记忆不写后台调度)"""
    assert STRATEGY_TABLE["scheduled"].write_mem0 is False
    assert STRATEGY_TABLE["scheduled"].extract_summary({"user_input": "x"}) == ""


def test_deep_research_agent_team_cross_mode_accessible():
    """deep_research / agent / team 三种模式 is_cross_mode_accessible=True"""
    for m in ["deep_research", "agent", "team"]:
        assert STRATEGY_TABLE[m].is_cross_mode_accessible is True, (
            f"{m} should be cross_mode_accessible"
        )


def test_other_modes_default_not_cross_mode():
    """其余模式 is_cross_mode_accessible 默认 False"""
    for m in ["general", "react", "thinking", "skill", "data", "scheduled", "shared"]:
        assert STRATEGY_TABLE[m].is_cross_mode_accessible is False, (
            f"{m} should not be cross_mode_accessible"
        )


def test_has_strategy_returns_true_for_known_modes():
    for m in ALL_TABLE_MODES:
        assert CrossModeContextRecorder.has_strategy(m) is True


def test_has_strategy_returns_false_for_unknown_mode():
    assert CrossModeContextRecorder.has_strategy("unknown_mode") is False


def test_record_finalize_writes_l2_and_mem0():
    """record_finalize 委托 ContextManager.persist_l2 + sync_to_long_term"""
    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(fake_db)
    with patch.object(recorder, "_ensure_manager") as mock_ensure, \
         patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True):
        mgr = MagicMock()
        mgr.persist_l2_context.return_value = 42
        mgr.sync_to_long_term.return_value = "mem_xyz"
        mock_ensure.return_value = mgr
        with patch.object(recorder, "_write_audit"):
            rid = recorder.record_finalize(
                session_id=1, user_id=1, tenant_id=1,
                session_type="skill",
                payload={
                    "skill_name": "report_gen",
                    "skill_display_name": "报告生成器",
                    "result": "ok",
                    "user_input": "x",
                    "execution_id": "exec-1",
                },
                case_number="default",
            )
        assert rid == 42
        mgr.persist_l2_context.assert_called_once()
        mgr.sync_to_long_term.assert_called_once()


def test_record_finalize_silent_on_failure():
    """整体异常被吞,不抛"""
    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(fake_db)
    with patch.object(recorder, "_ensure_manager", side_effect=RuntimeError("boom")), \
         patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True):
        rid = recorder.record_finalize(
            session_id=1, user_id=1, tenant_id=1,
            session_type="skill", payload={},
        )
    assert rid is None


def test_record_finalize_skips_mem0_for_scheduled():
    """scheduled 不调 sync_to_long_term"""
    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(fake_db)
    with patch.object(recorder, "_ensure_manager") as mock_ensure, \
         patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True):
        mgr = MagicMock()
        mgr.persist_l2_context.return_value = 1
        mgr.sync_to_long_term.return_value = None
        mock_ensure.return_value = mgr
        with patch.object(recorder, "_write_audit"):
            recorder.record_finalize(
                session_id=1, user_id=1, tenant_id=1,
                session_type="scheduled",
                payload={
                    "task_id": 1,
                    "task_no": "T-001",
                    "target_mode": "agent",
                    "user_input": "x",
                    "priority": 5,
                },
            )
        mgr.sync_to_long_term.assert_not_called()


# ── v2.0:StreamAnswerCollector + finalize_chat_stream ──────────────────


class TestStreamAnswerCollector:
    def test_collects_text_deltas(self):
        c = StreamAnswerCollector()
        c.feed('event: text_delta\ndata: {"delta": "你"}\n\n')
        c.feed('event: text_delta\ndata: {"delta": "好"}\n\n')
        assert c.answer == "你好"

    def test_final_answer_overrides_deltas(self):
        c = StreamAnswerCollector()
        c.feed('event: text_delta\ndata: {"delta": "部分"}\n\n')
        c.feed('event: done\ndata: {"answer": "完整回答"}\n\n')
        assert c.answer == "完整回答"

    def test_counts_tool_calls(self):
        c = StreamAnswerCollector()
        c.feed('event: tool_call_start\ndata: {"tool_name": "sql"}\n\n')
        c.feed('event: tool_call_start\ndata: {"tool_name": "web"}\n\n')
        assert c.tool_calls_count == 2

    def test_malformed_event_is_silent(self):
        c = StreamAnswerCollector()
        c.feed("not a sse event")
        c.feed("")
        c.feed(None)  # type: ignore[arg-type]
        assert c.answer == ""

    def test_corrupt_json_is_silent(self):
        c = StreamAnswerCollector()
        c.feed('event: text_delta\ndata: {broken json\n\n')
        assert c.answer == ""


class TestFinalizeChatStream:
    def test_calls_recorder_with_collected_answer(self):
        c = StreamAnswerCollector()
        c.feed('event: text_delta\ndata: {"delta": "结果"}\n\n')
        fake_db = MagicMock()
        with patch(
            "app.ai.services.cross_mode_recorder.CrossModeContextRecorder"
        ) as MockRec, patch(
            "app.config.settings.ENABLE_CROSS_MODE_RECORDER", True
        ):
            rec = MockRec.return_value
            rec.record_finalize.return_value = 7
            rid = finalize_chat_stream(
                fake_db, session_id=1, user_id=1, tenant_id=1,
                session_type="general", user_input="问", collector=c,
            )
        assert rid == 7
        kwargs = rec.record_finalize.call_args.kwargs
        assert kwargs["payload"]["answer"] == "结果"
        assert kwargs["session_type"] == "general"

    def test_unknown_mode_returns_none_without_recorder(self):
        c = StreamAnswerCollector()
        fake_db = MagicMock()
        with patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True):
            rid = finalize_chat_stream(
                fake_db, session_id=1, user_id=1, tenant_id=1,
                session_type="no_such_mode", user_input="x", collector=c,
            )
        assert rid is None

    def test_silent_on_internal_error(self):
        c = StreamAnswerCollector()
        fake_db = MagicMock()
        with patch(
            "app.ai.services.cross_mode_recorder.CrossModeContextRecorder",
            side_effect=RuntimeError("boom"),
        ), patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True):
            rid = finalize_chat_stream(
                fake_db, session_id=1, user_id=1, tenant_id=1,
                session_type="general", user_input="x", collector=c,
            )
        assert rid is None