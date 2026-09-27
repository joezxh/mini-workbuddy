"""验证 9 模式策略常量的完整性与一致性。"""
from __future__ import annotations

from app.core.context_policies import (
    PRIORITY_MAP,
    DEFAULT_TTL_HOURS,
    DEFAULT_PROTECTED_MODES,
    MEM0_ENABLED_MODES,
)


EXPECTED_MODES = {
    "general", "react", "thinking", "deep_research",
    "skill", "agent", "team", "scheduled", "shared",
}


def test_priority_map_covers_all_nine_modes():
    assert EXPECTED_MODES.issubset(PRIORITY_MAP.keys())
    for mode, prio in PRIORITY_MAP.items():
        assert 1 <= prio <= 10, f"{mode} priority {prio} out of range"


def test_default_ttl_hours_covers_all_nine_modes():
    assert EXPECTED_MODES.issubset(DEFAULT_TTL_HOURS.keys())
    for mode, ttl in DEFAULT_TTL_HOURS.items():
        assert ttl > 0, f"{mode} ttl {ttl} <= 0"


def test_scheduled_not_in_mem0_enabled_modes():
    """scheduled 模式不写 Mem0(永久记忆)"""
    assert "scheduled" not in MEM0_ENABLED_MODES
    assert "shared" not in MEM0_ENABLED_MODES


def test_mem0_enabled_modes_count():
    """7 种交互模式写 Mem0(general/react/thinking/deep_research/skill/agent/team),
    scheduled + shared 不写"""
    assert len(MEM0_ENABLED_MODES) == 7


def test_protected_modes_subset():
    """受保护模式必须是已知模式"""
    for m in DEFAULT_PROTECTED_MODES:
        assert m in EXPECTED_MODES