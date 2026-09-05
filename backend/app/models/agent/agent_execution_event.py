"""AgentExecutionEvent - Agent 执行事件日志表

记录 Agent 执行过程中的所有事件，用于审计和调试。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, BigInteger, String, Integer, JSON, DateTime, Index
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class ExecutionEventType(str, Enum):
    """执行事件类型"""
    # 基础事件类型
    TEXT = "text"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    HITL_PAUSE = "hitl_pause"
    HITL_RESUME = "hitl_resume"
    ERROR = "error"
    METRICS = "metrics"
    
    # 技能执行事件类型（前端 EventTimelineRenderer 期望）
    ENGINE_DECISION = "engine_decision"      # 引擎决策
    SKILL_START = "skill_start"              # 技能启动
    PROGRESS = "progress"                    # 进度更新
    TEXT_CHUNK = "text_chunk"                # 文本片段
    TEXT_DONE = "text_done"                  # 文本完成
    CHART_DATA = "chart_data"                # 图表数据
    FILE_GENERATED = "file_generated"        # 文件生成
    ARTIFACT = "artifact"                    # 技能产物文件（含 file_id / filename / size / mime）
    SKILL_RESULT = "skill_result"            # 技能结果
    COMPLETED = "completed"                  # 执行完成
    FAILED = "failed"                        # 执行失败

    # ── 团队协作事件（AgentTeam）────────────────────────────────────────
    # 复用本表存储：execution_id = agent_team_run.run_id，source = "team"，
    # source_id = node_key（团队级事件为 NULL）。详见 docs/agent/agent-team-design.md §4
    TEAM_START = "team_start"                # 团队运行开始
    TEAM_DONE = "team_done"                  # 团队运行结束
    TEAM_LAYER_START = "team_layer_start"    # DAG 某一拓扑层开始（层内节点并行）
    TEAM_LAYER_DONE = "team_layer_done"      # DAG 某一拓扑层结束
    TEAM_ROUND_START = "team_round_start"    # 轮次开始（msghub/supervisor）
    TEAM_ROUND_DONE = "team_round_done"      # 轮次结束
    NODE_START = "node_start"                # 节点开始执行
    NODE_DONE = "node_done"                  # 节点执行完成
    NODE_FAILED = "node_failed"              # 节点执行失败
    NODE_SKIPPED = "node_skipped"            # 节点被跳过（条件不满足/上游中止）
    NODE_INPUT = "node_input"                # 节点合并后的实际输入（便于回溯多上游拼接结果）
    HANDOFF = "handoff"                      # 节点间交接
    INTERVENTION = "intervention"            # 人工介入被消费
    HINT_BLOCK = "hint_block"                # 节点向用户提问，等待作答


class AgentExecutionEvent(Base, TenantMixin):
    """Agent 执行事件日志表"""
    __tablename__ = "agent_execution_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # ── 执行关联 ───────────────────────────────────────────────────────────
    execution_id = Column(String(64), nullable=False, index=True, comment="执行 ID")
    trace_id = Column(String(64), nullable=True, index=True, comment="链路追踪 ID")

    # ── 事件信息 ───────────────────────────────────────────────────────────
    event_type = Column(String(30), nullable=False, comment="事件类型")
    sequence = Column(Integer, nullable=False, comment="事件序号")
    content = Column(JSON, nullable=True, comment="事件内容（根据类型结构化存储）")

    # ── 事件来源 ───────────────────────────────────────────────────────────
    source = Column(String(50), nullable=True, comment="事件来源: agent/mcp/skill")
    source_id = Column(String(100), nullable=True, comment="来源标识")

    # ── 元数据 ─────────────────────────────────────────────────────────────
    event_metadata = Column("metadata", JSON, nullable=True, comment="附加元数据")

    # ── 时间戳 ────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_event_execution_seq", "execution_id", "sequence"),
        Index("idx_event_type", "event_type"),
        Index("idx_event_trace", "trace_id"),
    )
