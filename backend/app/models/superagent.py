"""SuperAgent 运行时模型 —— Engine 核心事务载体。

所有表带 workspace_id FK，与 MinWorkBuddy 既有 ai_workspace 表绑定。
配置字段（github_source_cfg / feishu_source_cfg / policy_rules 等）
不新建表，统一存入 ai_workspace.config JSON 字段或后续扩展 JSON 列。
"""
from sqlalchemy import (
    String, JSON, Integer, BigInteger, Boolean, TIMESTAMP, ForeignKey, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


# ============ 1. Engine 核心运行时表 ============

class SuperAgentTrigger(Base):
    """Trigger — Source 产生的原始触发信号。

    来自 GitHub Source（4 种 Trigger）/ Feishu Source / HTTP Source / 手动创建。
    Engine.intake 接收 → 入库 → 扇入 Thread → 进入 Eval 队列。
    """
    __tablename__ = "sa_trigger"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="短 UUID")
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="github/feishu/http/manual")
    ref_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="Source 内部 ID（Issue/PR 号 / Feishu thread_id / 手动 None）")
    thread_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("sa_thread.id"), nullable=True, index=True)
    sender_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="sender 标识（GitHub username / Feishu ou_xxx）")
    sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, comment="issue_mention/pull_mention/comment_mention/ci_failure/manual/...")
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, comment="PR head / CI facts / 截图 等元数据")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="pending → evaling → accepted/ignored/blocked")
    eval_attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


class SuperAgentTicket(Base):
    """Ticket — Engine 核心生命周期单位。

    由 accept 决策时创建。一个 Ticket 绑定一个 Executor（Worker Session）。
    """
    __tablename__ = "sa_ticket"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="短 UUID")
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    trigger_id: Mapped[str] = mapped_column(String(32), ForeignKey("sa_trigger.id"), nullable=False)
    mandate_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("sa_mandate.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True,
        comment="open → working → waiting_person → waiting_hitl → completed/failed/dropped")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    intent_evidence: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Eval 时 AgentScope Agent 的意图证据")
    acknowledgement: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Eval accept 确认语")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP, nullable=True)


class SuperAgentEffect(Base):
    """Durable Effect Queue — 对齐 dsh-superagent effect 表。

    6 种 kind：assessment / launch / delivery / relay / notice / reply。
    SQLite + asyncio.Queue 双层：asyncio.Queue 做活跃调度，SQLite 做 durable 持久化。
    """
    __tablename__ = "sa_effect"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True,
        comment="assessment/launch/delivery/relay/notice/reply")
    seq: Mapped[int] = mapped_column(Integer, nullable=False, comment="per-kind 队列序号")
    generation: Mapped[int] = mapped_column(Integer, default=0, comment="Policy version 触发的重新生成标记")
    ticket_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("sa_ticket.id"), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True,
        comment="pending → running → done/failed/cancelled")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    due: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP, nullable=True, comment="下次可执行时间（指数退避）")
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)


# ============ 2. Source 运行时表（Thread/Subscription/Mandate/Assignment） ============

class SuperAgentThread(Base):
    """Thread — Trigger 的时间序列容器，Eval 串行运行的单位。"""
    __tablename__ = "sa_thread"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="f'{source}:{ref_id}'")
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ref_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", comment="open/closed/merged")
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, comment="is_pr/ci_facts 等元数据")
    cursor: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Source 读取游标（ISO timestamp / ETag）")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("workspace_id", "source", "ref_id", name="uq_sa_thread_ws_src_ref"),)


class SuperAgentSubscription(Base):
    """Subscription — Ticket ↔ Thread 多对多。

    kind=following：借出授权（Worker 为这个 Thread 工作）。
    kind=context_only：仅上下文（Worker 主动关注，不借出授权、不恢复 Ticket）。
    Subscription fan-out 不经过 Eval。
    """
    __tablename__ = "sa_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(32), ForeignKey("sa_ticket.id"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(32), ForeignKey("sa_thread.id"), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="following", comment="following/context_only")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("ticket_id", "thread_id", name="uq_sa_sub_ticket_thread"),)


class SuperAgentMandate(Base):
    """Mandate — 不可变授权，accept 时创建。

    包含 Policy version + strength + scope + matched rules。
    Policy 变更不撤销 Mandate，只送达 Assignment 通知。
    """
    __tablename__ = "sa_mandate"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(32), ForeignKey("sa_ticket.id"), nullable=False, unique=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, comment="Policy settings 的 hash")
    strength: Mapped[str] = mapped_column(String(20), nullable=False, comment="explicit/inferred")
    scope: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="允许的工作范围描述")
    matched_rules: Mapped[list] = mapped_column(JSON, default=list, nullable=False, comment="[{rule_id, reason}]")
    source_identity: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, comment="{source, sender_id}")
    trigger_id: Mapped[str] = mapped_column(String(32), ForeignKey("sa_trigger.id"), nullable=False)
    acknowledgement: Mapped[str | None] = mapped_column(String(500), nullable=True)
    intent_evidence: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    worktree_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="GitHub PR 关联时 kebab-case Git 分支名")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


class SuperAgentAssignment(Base):
    """Assignment — Ticket ↔ Executor 绑定。

    status=pending/running/ended。WorkerReport 5 种状态回写到 final_report。
    """
    __tablename__ = "sa_assignment"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(32), ForeignKey("sa_ticket.id"), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, comment="pending/running/ended")
    executor_session: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Worker AgentScope Agent 实例名")
    started_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP, nullable=True)
    ended_at: Mapped[TIMESTAMP | None] = mapped_column(TIMESTAMP, nullable=True)
    final_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, comment="WorkerReport {kind, message, ...}")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)


class SuperAgentAuditLog(Base):
    """审计日志 — Engine 所有事务写此表。"""
    __tablename__ = "sa_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    trigger_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="receive_trigger/decide/accept/reject/...")
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)


# 复合索引
Index("ix_sa_ticket_ws_status", SuperAgentTicket.workspace_id, SuperAgentTicket.status)
Index("ix_sa_trigger_ws_source", SuperAgentTrigger.workspace_id, SuperAgentTrigger.source)
Index("ix_sa_effect_kind_status", SuperAgentEffect.kind, SuperAgentEffect.status)
Index("ix_sa_assignment_ticket", SuperAgentAssignment.ticket_id, SuperAgentAssignment.status)
