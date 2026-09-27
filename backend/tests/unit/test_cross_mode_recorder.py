"""STRATEGY_TABLE 9 模式 + record_finalize 主入口测试。"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.ai.services.cross_mode_recorder import (
    STRATEGY_TABLE,
    CrossModeContextRecorder,
)


def test_all_nine_modes_have_strategy():
    expected = {
        "general", "react", "thinking", "deep_research",
        "skill", "agent", "team", "scheduled", "shared",
    }
    for m in expected:
        assert m in STRATEGY_TABLE, f"missing strategy for {m}"
        assert STRATEGY_TABLE[m].source_mode == m


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
    for m in ["general", "react", "thinking", "skill", "scheduled", "shared"]:
        assert STRATEGY_TABLE[m].is_cross_mode_accessible is False, (
            f"{m} should not be cross_mode_accessible"
        )


def test_has_strategy_returns_true_for_known_modes():
    for m in [
        "general", "react", "thinking", "deep_research",
        "skill", "agent", "team", "scheduled", "shared",
    ]:
        assert CrossModeContextRecorder.has_strategy(m) is True


def test_has_strategy_returns_false_for_unknown_mode():
    assert CrossModeContextRecorder.has_strategy("unknown_mode") is False


def test_record_finalize_writes_l2_and_mem0():
    """record_finalize 委托 ContextManager.persist_l2 + sync_to_long_term"""
    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(fake_db)
    with patch.object(recorder, "_ensure_manager") as mock_ensure:
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
    with patch.object(recorder, "_ensure_manager", side_effect=RuntimeError("boom")):
        rid = recorder.record_finalize(
            session_id=1, user_id=1, tenant_id=1,
            session_type="skill", payload={},
        )
    assert rid is None


def test_record_finalize_skips_mem0_for_scheduled():
    """scheduled 不调 sync_to_long_term"""
    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(fake_db)
    with patch.object(recorder, "_ensure_manager") as mock_ensure:
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