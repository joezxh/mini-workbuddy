"""验证策略常量的完整性与一致性(v2.0:含 data 模式与 SESSION_MODES 权威清单)。"""
from __future__ import annotations

from app.core.context_policies import (
    PRIORITY_MAP,
    DEFAULT_TTL_HOURS,
    DEFAULT_PROTECTED_MODES,
    MEM0_ENABLED_MODES,
    SESSION_MODES,
    STORAGE_FALLBACK_MODE,
)

# 9 种会话模式(与前端 AssistantPanel fallback 映射对齐)
EXPECTED_SESSION_MODES = {
    "general", "react", "thinking", "deep_research",
    "skill", "agent", "team", "data", "scheduled",
}
# 全部存储模式(会话模式 + shared 兜底)
EXPECTED_MODES = EXPECTED_SESSION_MODES | {"shared"}


def test_session_modes_is_authoritative_nine():
    """SESSION_MODES 为 9 种会话模式的权威清单"""
    assert set(SESSION_MODES) == EXPECTED_SESSION_MODES
    assert len(SESSION_MODES) == 9


def test_storage_fallback_mode():
    assert STORAGE_FALLBACK_MODE == "shared"
    assert STORAGE_FALLBACK_MODE in EXPECTED_MODES


def test_priority_map_covers_all_modes():
    assert EXPECTED_MODES.issubset(PRIORITY_MAP.keys())
    for mode, prio in PRIORITY_MAP.items():
        assert 1 <= prio <= 10, f"{mode} priority {prio} out of range"


def test_default_ttl_hours_covers_all_modes():
    assert EXPECTED_MODES.issubset(DEFAULT_TTL_HOURS.keys())
    for mode, ttl in DEFAULT_TTL_HOURS.items():
        assert ttl > 0, f"{mode} ttl {ttl} <= 0"


def test_data_mode_policy():
    """data(SQLBot):短 TTL、写 Mem0"""
    assert DEFAULT_TTL_HOURS["data"] == 48
    assert "data" in MEM0_ENABLED_MODES
    assert PRIORITY_MAP["data"] == 2


def test_scheduled_not_in_mem0_enabled_modes():
    """scheduled 模式不写 Mem0(永久记忆)"""
    assert "scheduled" not in MEM0_ENABLED_MODES
    assert "shared" not in MEM0_ENABLED_MODES


def test_mem0_enabled_modes_count():
    """8 种交互模式写 Mem0,scheduled + shared 不写"""
    assert MEM0_ENABLED_MODES == EXPECTED_SESSION_MODES - {"scheduled"}


def test_protected_modes_subset():
    """受保护模式必须是已知模式"""
    for m in DEFAULT_PROTECTED_MODES:
        assert m in EXPECTED_MODES
