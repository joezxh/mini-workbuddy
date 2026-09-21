"""event_types 权威模块单测：别名归一化、路由表、信封校验。"""
from app.schemas.agent.event_types import (
    EventCategory, EventLevel, ExecutionEventType, EventEnvelope,
    LEGACY_ALIAS, DEFAULT_ROUTES, normalize_event_type, route_of,
)


# ── 别名归一化 ──────────────────────────────────────────────────────────

def test_legacy_alias_mapping():
    assert LEGACY_ALIAS["text"] == "text_chunk"
    assert LEGACY_ALIAS["thinking"] == "thinking_chunk"
    assert LEGACY_ALIAS["agent_complete"] == "agent_done"
    assert LEGACY_ALIAS["completed"] == "agent_done"
    assert LEGACY_ALIAS["skill_load"] == "skill_loaded"
    assert LEGACY_ALIAS["skill_complete"] == "skill_result"
    assert LEGACY_ALIAS["agent_error"] == "error"
    assert LEGACY_ALIAS["failed"] == "error"
    assert LEGACY_ALIAS["timeout"] == "interrupt_requested"


def test_normalize_known_alias_and_passthrough():
    assert normalize_event_type("text") == "text_chunk"
    assert normalize_event_type("team_start") == "team_start"      # 已是新值，原样
    assert normalize_event_type("whatever_unknown") == "whatever_unknown"  # 未知不炸


def test_enum_is_plain_str_subclass():
    """str 子类保证 ExecutionEventType.TEXT == 'text' 为 True（避免 Enum 陷阱）。"""
    assert ExecutionEventType.TEXT_CHUNK == "text_chunk"
    assert isinstance(ExecutionEventType.TEXT_CHUNK, str)


# ── 路由表 ──────────────────────────────────────────────────────────────

def test_delta_events_not_routed_to_db():
    for t in ("text_chunk", "thinking_chunk", "data_chunk"):
        assert EventLevel.DB not in DEFAULT_ROUTES[t].levels, t


def test_block_summary_routed_to_db():
    for t in ("text_done", "thinking_done"):
        assert EventLevel.DB in DEFAULT_ROUTES[t].levels, t


def test_tool_and_lifecycle_routed_to_db():
    for t in ("tool_call", "tool_result", "reply_start", "reply_end",
              "hitl_pause", "interrupted", "skill_result", "agent_done"):
        assert EventLevel.DB in DEFAULT_ROUTES[t].levels, t


def test_model_call_is_log_only():
    r = DEFAULT_ROUTES["model_call"]
    assert EventLevel.LOG in r.levels and EventLevel.DB not in r.levels


def test_route_of_fallback_for_unknown():
    r = route_of("totally_unknown_event")
    assert EventLevel.DB in r.levels  # 未知事件保守落库
    assert r.category == EventCategory.RUNTIME


def test_every_enum_member_has_route():
    members = [v for k, v in vars(ExecutionEventType).items() if not k.startswith("_")]
    missing = [m for m in members if m not in DEFAULT_ROUTES]
    assert missing == [], f"缺路由: {missing}"


# ── 信封 ────────────────────────────────────────────────────────────────

def test_envelope_defaults():
    env = EventEnvelope(
        execution_id="exec-1", event_type="tool_call",
        category=EventCategory.TOOL, levels=[EventLevel.DB, EventLevel.STREAM],
        content={"tool_name": "Bash"},
    )
    assert env.event_version == 1
    assert env.reply_id is None and env.ui_hint is None
    assert env.metadata == {}
