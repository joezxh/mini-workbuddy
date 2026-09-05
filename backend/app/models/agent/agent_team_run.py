"""AgentTeam 多智能体团队协作 —— 运行时模型

包含三张表：
    - agent_team_run           运行实例（含配置快照，保证回放一致性）
    - agent_team_run_step      节点级执行快照
    - agent_team_intervention  人工介入记录

设计要点：
    1. ``agent_team_run.team_snapshot`` 冻结运行发起时的完整团队配置（成员 + 边 + run_config），
       后续团队被修改不影响历史运行的回放与分支重跑。
    2. 细粒度事件流复用 ``agent_execution_event`` 表（execution_id = run_id，source='team'），
       本模块的 ``run_step`` 只存节点级聚合结果，用于列表展示与断点续跑，两者职责不重叠。
    3. 人工介入采用「队列 + 消费」模型：介入请求先落库为 pending，执行引擎在节点边界检查并消费。

参见：docs/agent/agent-team-design.md §3 §4
"""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, Boolean,
    TIMESTAMP, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class RunStatus(str):
    """运行状态"""
    PENDING = "pending"       # 已创建，尚未开始
    RUNNING = "running"       # 执行中
    PAUSED = "paused"         # 被人工暂停，等待恢复
    SUCCESS = "success"       # 正常完成
    FAILED = "failed"         # 异常终止
    CANCELLED = "cancelled"   # 人工取消

    ALL = (PENDING, RUNNING, PAUSED, SUCCESS, FAILED, CANCELLED)

    #: 终态：不会再变化，可安全归档 / 回放
    TERMINAL = (SUCCESS, FAILED, CANCELLED)

    #: 活跃态：占用执行资源，需支持干预
    ACTIVE = (PENDING, RUNNING, PAUSED)


class StepStatus(str):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"       # 条件不满足 / 上游中止
    INTERVENED = "intervened"  # 被人工干预（改写输出、跳过等）

    ALL = (PENDING, RUNNING, SUCCESS, FAILED, SKIPPED, INTERVENED)
    TERMINAL = (SUCCESS, FAILED, SKIPPED, INTERVENED)


class TriggerType(str):
    """运行触发来源"""
    MANUAL = "manual"       # 用户在对话窗手动发起
    API = "api"             # 外部 API 调用
    SCHEDULE = "schedule"   # 定时任务
    REPLAY = "replay"       # 基于历史运行的分支重跑

    ALL = (MANUAL, API, SCHEDULE, REPLAY)


class InterventionType(str):
    """人工介入类型"""
    PAUSE = "pause"                 # 暂停运行
    RESUME = "resume"               # 恢复运行
    CANCEL = "cancel"               # 取消运行
    EDIT_OUTPUT = "edit_output"     # 改写某节点输出后继续
    RETRY_NODE = "retry_node"       # 重跑某节点
    SKIP_NODE = "skip_node"         # 跳过某节点
    INJECT_MESSAGE = "inject_message"  # 向后续节点注入补充指令
    ANSWER_ASK = "answer_ask"       # 回答节点的提问（HINT_BLOCK）

    ALL = (PAUSE, RESUME, CANCEL, EDIT_OUTPUT, RETRY_NODE,
           SKIP_NODE, INJECT_MESSAGE, ANSWER_ASK)

    #: 作用于整个运行（无需指定 node_key）
    RUN_LEVEL = (PAUSE, RESUME, CANCEL)

    #: 作用于具体节点（必须指定 node_key）
    NODE_LEVEL = (EDIT_OUTPUT, RETRY_NODE, SKIP_NODE, ANSWER_ASK)


class InterventionStatus(str):
    """介入请求的处理状态"""
    PENDING = "pending"     # 已入队，等待执行引擎消费
    APPLIED = "applied"     # 已生效
    EXPIRED = "expired"     # 过期未消费（如节点已执行完毕）
    REJECTED = "rejected"   # 被拒绝（如状态不允许）

    ALL = (PENDING, APPLIED, EXPIRED, REJECTED)


class AgentTeamRun(Base, TenantMixin):
    """团队运行实例"""
    __tablename__ = "agent_team_run"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True,
                    comment="运行唯一标识（UUID），同时作为 agent_execution_event.execution_id")

    team_id = Column(BigInteger, nullable=False, index=True, comment="所属团队 agent_team.id")
    conversation_id = Column(String(64), nullable=True, index=True, comment="关联会话ID")

    # ── 配置快照：冻结发起时的团队定义，保证回放一致性 ─────────────────────
    team_snapshot = Column(JSONB, nullable=False, comment=(
        "团队配置快照 {team:{...}, members:[...], edges:[...], run_config:{...}}"
    ))

    # ── 输入输出 ──────────────────────────────────────────────────────────
    input_text = Column(Text, nullable=True, comment="用户原始输入")
    input_context = Column(JSONB, nullable=True, comment="附加上下文（文件、变量等）")
    final_output = Column(Text, nullable=True, comment="团队最终输出")
    node_outputs = Column(JSONB, nullable=True, comment="各节点输出汇总 {node_key: output}")

    # ── 状态 ──────────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, server_default=RunStatus.PENDING,
                    comment="pending/running/paused/success/failed/cancelled")
    current_round = Column(Integer, nullable=False, server_default="0",
                           comment="当前轮次（msghub/supervisor 模式）")
    current_nodes = Column(JSONB, nullable=True, comment="当前正在执行的节点 node_key 列表")
    error_message = Column(Text, nullable=True, comment="失败原因")

    # ── 统计 ──────────────────────────────────────────────────────────────
    total_tokens = Column(Integer, nullable=False, server_default="0", comment="累计 token 消耗")
    total_steps = Column(Integer, nullable=False, server_default="0", comment="累计节点执行次数")
    duration_ms = Column(Integer, nullable=True, comment="总耗时（毫秒）")

    # ── 溯源 ──────────────────────────────────────────────────────────────
    trigger_type = Column(String(20), nullable=False, server_default=TriggerType.MANUAL,
                          comment="manual/api/schedule/replay")
    parent_run_id = Column(String(64), nullable=True, index=True,
                           comment="分支重跑时的父运行 run_id")
    branch_from_node = Column(String(64), nullable=True,
                              comment="分支重跑的起始节点 node_key")

    workspace_id = Column(BigInteger, nullable=True, index=True, comment="多租户隔离")
    created_by = Column(BigInteger, nullable=True, comment="发起人ID")

    started_at = Column(TIMESTAMP, nullable=True, comment="开始执行时间")
    finished_at = Column(TIMESTAMP, nullable=True, comment="结束时间")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_team_run_team_created", "team_id", "created_at"),
        Index("idx_team_run_status", "status"),
        Index("idx_team_run_conversation", "conversation_id"),
        Index("idx_team_run_workspace", "workspace_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentTeamRun {self.run_id} team={self.team_id} status={self.status}>"

    @property
    def is_terminal(self) -> bool:
        """是否已到终态"""
        return self.status in RunStatus.TERMINAL

    @property
    def is_active(self) -> bool:
        """是否仍占用执行资源"""
        return self.status in RunStatus.ACTIVE

    def get_snapshot_run_config(self) -> Dict[str, Any]:
        """从快照读取 run_config（回放/续跑时必须用快照而非团队当前配置）"""
        return (self.team_snapshot or {}).get("run_config") or {}


class AgentTeamRunStep(Base, TenantMixin):
    """节点级执行快照

    注意：细粒度事件（TEXT_CHUNK/TOOL_CALL 等）存于 agent_execution_event 表，
    本表只保存节点级聚合结果，用于步骤列表展示、断点续跑与分支重跑。
    """
    __tablename__ = "agent_team_run_step"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True, comment="所属运行 agent_team_run.run_id")

    node_key = Column(String(64), nullable=False, comment="节点标识")
    role_name = Column(String(100), nullable=True, comment="角色名（快照，防止团队改名后失真）")
    agent_config_id = Column(BigInteger, nullable=True, comment="实际执行的 agent_config.id")

    round_no = Column(Integer, nullable=False, server_default="0", comment="轮次（动态模式下同节点可多次执行）")
    layer_no = Column(Integer, nullable=True, comment="DAG 拓扑层号（同层并行）")
    seq = Column(Integer, nullable=False, server_default="0", comment="全局执行序号")

    # ── 输入输出 ──────────────────────────────────────────────────────────
    input_text = Column(Text, nullable=True, comment="合并后的实际输入")
    upstream_nodes = Column(JSONB, nullable=True, comment="上游节点 node_key 列表")
    output_text = Column(Text, nullable=True, comment="节点输出")

    # ── 状态 ──────────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, server_default=StepStatus.PENDING,
                    comment="pending/running/success/failed/skipped/intervened")
    error_message = Column(Text, nullable=True, comment="失败原因")
    retry_count = Column(Integer, nullable=False, server_default="0", comment="重试次数")

    # ── 统计 ──────────────────────────────────────────────────────────────
    tokens = Column(Integer, nullable=False, server_default="0", comment="token 消耗")
    duration_ms = Column(Integer, nullable=True, comment="耗时（毫秒）")

    extra_data = Column(JSONB, nullable=True, comment="扩展信息（工具调用摘要、引用来源等）")

    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_team_step_run_seq", "run_id", "seq"),
        Index("idx_team_step_run_node", "run_id", "node_key"),
    )

    def __repr__(self) -> str:
        return f"<AgentTeamRunStep run={self.run_id} node={self.node_key} status={self.status}>"


class AgentTeamIntervention(Base, TenantMixin):
    """人工介入记录（队列 + 消费模型）"""
    __tablename__ = "agent_team_intervention"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True, comment="所属运行 agent_team_run.run_id")

    intervention_type = Column(String(30), nullable=False, comment=(
        "pause/resume/cancel/edit_output/retry_node/skip_node/inject_message/answer_ask"
    ))
    node_key = Column(String(64), nullable=True, comment="目标节点（节点级介入必填）")
    round_no = Column(Integer, nullable=True, comment="目标轮次")

    payload = Column(JSONB, nullable=True, comment="介入内容 {content, reason, ...}")

    status = Column(String(20), nullable=False, server_default=InterventionStatus.PENDING,
                    comment="pending/applied/expired/rejected")
    applied_at = Column(TIMESTAMP, nullable=True, comment="被执行引擎消费的时间")
    reject_reason = Column(Text, nullable=True, comment="拒绝/过期原因")

    operator_id = Column(BigInteger, nullable=True, comment="操作人ID")
    operator_name = Column(String(100), nullable=True, comment="操作人名称（快照）")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_team_intervention_run", "run_id", "status"),
        Index("idx_team_intervention_created", "created_at"),
    )

    def __repr__(self) -> str:
        return (f"<AgentTeamIntervention run={self.run_id} "
                f"type={self.intervention_type} status={self.status}>")

    @property
    def is_pending(self) -> bool:
        return self.status == InterventionStatus.PENDING
