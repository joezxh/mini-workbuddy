"""Agent 执行事件类型 —— 全系统唯一权威来源。

spec: docs/superpowers/specs/2026-09-21-agent-event-architecture-design.md §4.2/§4.3

设计要点：
- 枚举用普通 str 子类（非 Enum），保持 ``ExecutionEventType.TEXT_CHUNK == "text_chunk"``
  为 True，与旧 schemas 版行为一致，避免 ``str, Enum`` 相等性陷阱。
- 历史值经 LEGACY_ALIAS 在写入侧归一化；DB 存量行不迁移，读取侧按别名双读。
- levels 是分发目标集合（可多选）：delta 类仅 [STREAM] 不落库，
  text_done/thinking_done 携带块级汇总以 [DB] 落库。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional

from pydantic import BaseModel, Field


# ── 类别与级别 ────────────────────────────────────────────────────────────

class EventCategory(str):
    """事件分类。"""
    LIFECYCLE = "lifecycle"
    TEXT = "text"
    THINKING = "thinking"
    DATA = "data"
    TOOL = "tool"
    MODEL = "model"
    RUNTIME = "runtime"
    CONFIG = "config"
    HITL = "hitl"
    INTERRUPT = "interrupt"
    SKILL = "skill"
    AGENT = "agent"
    TEAM = "team"
    ARTIFACT = "artifact"
    ERROR = "error"
    METRICS = "metrics"


class EventLevel(int):
    """分发层级（多选集合的元素）。"""
    LOG = 0      # 仅日志
    DB = 1       # 持久化
    STREAM = 2   # SSE 推送
    UI = 3       # 前端渲染路由


# ── 统一事件类型（单一权威来源）─────────────────────────────────────────

class ExecutionEventType(str):
    """统一执行事件类型（对齐 AgentScope 2.0.8 事件目录，归并历史冗余）。"""

    # 生命周期（对齐 ReplyStart/ReplyEnd）
    REPLY_START = "reply_start"
    REPLY_END = "reply_end"                      # content.finished_reason

    # 文本/思考/数据流（对齐 Block* 三段式）
    TEXT_CHUNK = "text_chunk"                    # [STREAM] delta 不落库
    TEXT_DONE = "text_done"                      # [DB] 块级汇总
    THINKING_CHUNK = "thinking_chunk"            # [STREAM]
    THINKING_DONE = "thinking_done"              # [DB]
    DATA_CHUNK = "data_chunk"                    # [STREAM]

    # 工具（对齐 ToolCall*/ToolResult*）
    TOOL_CALL = "tool_call"                      # state: asking|allowed|submitted
    TOOL_RESULT = "tool_result"                  # state: running|success|error|interrupted|denied

    # 模型计量（对齐 ModelCallStart/End）
    MODEL_CALL = "model_call"                    # metadata: input/output_tokens

    # 运行时（对齐 ExceedMaxIters 等）
    ITERATION_LIMIT = "iteration_limit"
    PROGRESS = "progress"
    CONTEXT_COMPRESSED = "context_compressed"

    # 配置智能体
    CONFIG_LOADED = "config_loaded"
    CONFIG_VALIDATED = "config_validated"
    SCHEMA_APPLIED = "schema_applied"

    # 中断智能体
    INTERRUPT_REQUESTED = "interrupt_requested"  # reason: timeout|user_cancel|system
    INTERRUPTED = "interrupted"

    # HITL
    HITL_PAUSE = "hitl_pause"
    HITL_RESUME = "hitl_resume"

    # Skill / Agent
    SKILL_LOADED = "skill_loaded"
    SKILL_START = "skill_start"
    SKILL_RESULT = "skill_result"
    AGENT_START = "agent_start"
    AGENT_DONE = "agent_done"
    AGENT_RETRY = "agent_retry"
    ENGINE_DECISION = "engine_decision"
    ARTIFACT = "artifact"
    CHART_DATA = "chart_data"
    FILE_GENERATED = "file_generated"

    # 团队（存量保留）
    TEAM_START = "team_start"
    TEAM_DONE = "team_done"
    TEAM_ERROR = "team_error"
    TEAM_LAYER_START = "team_layer_start"
    TEAM_LAYER_DONE = "team_layer_done"
    TEAM_ROUND_START = "team_round_start"
    TEAM_ROUND_DONE = "team_round_done"
    NODE_START = "node_start"
    NODE_DONE = "node_done"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    NODE_INPUT = "node_input"
    HANDOFF = "handoff"
    INTERVENTION = "intervention"
    HINT_BLOCK = "hint_block"
    DISPATCH_PLAN = "dispatch_plan"
    PLAN_REVISED = "plan_revised"

    # 通用
    ERROR = "error"
    METRICS = "metrics"
    CUSTOM = "custom"                            # 对齐 AgentScope CustomEvent


# ── 历史别名（写入侧归一化）─────────────────────────────────────────────

LEGACY_ALIAS: Dict[str, str] = {
    "text": "text_chunk",
    "thinking": "thinking_chunk",
    "agent_complete": "agent_done",
    "completed": "agent_done",
    "skill_load": "skill_loaded",
    "skill_complete": "skill_result",
    "agent_error": "error",
    "failed": "error",
    "timeout": "interrupt_requested",
}


def normalize_event_type(value: str) -> str:
    """历史事件值归一化；未知值原样返回（不阻断写入方）。"""
    return LEGACY_ALIAS.get(value, value)


# ── 路由表 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EventRoute:
    category: str
    levels: FrozenSet[int]
    ui_hint: Optional[str] = None


def _r(category: str, *levels: int, ui: Optional[str] = None) -> EventRoute:
    return EventRoute(category=category, levels=frozenset(levels), ui_hint=ui)


_L = EventLevel.LOG
_D = EventLevel.DB
_S = EventLevel.STREAM
_U = EventLevel.UI

DEFAULT_ROUTES: Dict[str, EventRoute] = {
    # 生命周期
    "reply_start": _r(EventCategory.LIFECYCLE, _D),
    "reply_end": _r(EventCategory.LIFECYCLE, _D),
    # 流式 delta —— 不落库（spec 验收：DB 行数下降 ≥80%）
    "text_chunk": _r(EventCategory.TEXT, _S, ui="markdown"),
    "text_done": _r(EventCategory.TEXT, _D),
    "thinking_chunk": _r(EventCategory.THINKING, _S),
    "thinking_done": _r(EventCategory.THINKING, _D),
    "data_chunk": _r(EventCategory.DATA, _S, ui="markdown"),
    # 工具
    "tool_call": _r(EventCategory.TOOL, _D, _S, _U, ui="timeline"),
    "tool_result": _r(EventCategory.TOOL, _D, _S, _U, ui="timeline"),
    # 模型计量 —— 仅日志
    "model_call": _r(EventCategory.MODEL, _L),
    # 运行时
    "iteration_limit": _r(EventCategory.RUNTIME, _D, _S, _U, ui="timeline"),
    "progress": _r(EventCategory.RUNTIME, _S, _U, ui="timeline"),
    "context_compressed": _r(EventCategory.RUNTIME, _L),
    # 配置
    "config_loaded": _r(EventCategory.CONFIG, _D),
    "config_validated": _r(EventCategory.CONFIG, _D),
    "schema_applied": _r(EventCategory.CONFIG, _D),
    # 中断
    "interrupt_requested": _r(EventCategory.INTERRUPT, _D, _S, _U, ui="timeline"),
    "interrupted": _r(EventCategory.INTERRUPT, _D, _S, _U, ui="timeline"),
    # HITL
    "hitl_pause": _r(EventCategory.HITL, _D, _S, _U, ui="confirm"),
    "hitl_resume": _r(EventCategory.HITL, _D, _S),
    # Skill / Agent
    "skill_loaded": _r(EventCategory.SKILL, _D, _S, _U, ui="timeline"),
    "skill_start": _r(EventCategory.SKILL, _D, _S, _U, ui="timeline"),
    "skill_result": _r(EventCategory.SKILL, _D, _S, _U),
    "agent_start": _r(EventCategory.AGENT, _D, _S, _U, ui="timeline"),
    "agent_done": _r(EventCategory.AGENT, _D, _S, _U),
    "agent_retry": _r(EventCategory.AGENT, _D, _S, _U, ui="timeline"),
    "engine_decision": _r(EventCategory.AGENT, _D, _S, _U, ui="timeline"),
    "artifact": _r(EventCategory.ARTIFACT, _D, _S, _U, ui="artifact"),
    "chart_data": _r(EventCategory.ARTIFACT, _D, _S, _U, ui="chart"),
    "file_generated": _r(EventCategory.ARTIFACT, _D, _S, _U, ui="artifact"),
    # 团队（存量保留 DB 行为）
    "team_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_done": _r(EventCategory.TEAM, _D, _S, _U),
    "team_error": _r(EventCategory.TEAM, _D, _S, _U),
    "team_layer_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_layer_done": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_round_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "team_round_done": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_start": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_done": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_failed": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_skipped": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "node_input": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "handoff": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "intervention": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "hint_block": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "dispatch_plan": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    "plan_revised": _r(EventCategory.TEAM, _D, _S, _U, ui="timeline"),
    # 通用
    "error": _r(EventCategory.ERROR, _D, _S, _U, ui="timeline"),
    "metrics": _r(EventCategory.METRICS, _L, _D),
    "custom": _r(EventCategory.RUNTIME, _D),
}

# 未知事件的兜底路由：保守落库
_FALLBACK_ROUTE = EventRoute(
    category=EventCategory.RUNTIME, levels=frozenset({EventLevel.DB}),
)


def route_of(event_type: str) -> EventRoute:
    """查询事件路由；未知事件返回保守兜底（DB）。"""
    return DEFAULT_ROUTES.get(event_type, _FALLBACK_ROUTE)


# ── 事件信封 ──────────────────────────────────────────────────────────────

class EventEnvelope(BaseModel):
    """统一事件信封：EventBus 分发与持久化的标准载荷。

    sequence 由 ExecutionEventService 在落库时分配，调用方不填。
    """
    execution_id: str
    trace_id: Optional[str] = None
    event_type: str
    category: str
    levels: List[int] = Field(default_factory=list)
    content: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    source_id: Optional[str] = None
    reply_id: Optional[str] = None
    block_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    interrupt_reason: Optional[str] = None
    ui_hint: Optional[str] = None
    event_version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
