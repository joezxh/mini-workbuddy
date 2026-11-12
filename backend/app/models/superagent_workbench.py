"""SuperAgent 工作台模型 —— Feed / Ideas / Goals（Task 4.6）。

对齐 demo.html（docs/super-agent-demo）语义：
  SaFeedPost — Feed 时间线（5 kind：system/ai_batch/reminder/approval/goal_updated）
  SaIdea     — Idea 卡（emo/pitch/detail/kind chat|goal|routine，fingerprint 去重）
  SaGoal     — Goal（steps 五态 + proposals + version）
"""
from sqlalchemy import (
    String, JSON, Integer, BigInteger, Boolean, TIMESTAMP, Text, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class SaFeedPost(Base):
    """Feed 时间线 — 工作台首页信息流。"""
    __tablename__ = "sa_feed_post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True,
        comment="system/ai_batch/reminder/approval/goal_updated")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str | None] = mapped_column(String(1000), nullable=True,
        comment="可直接发起对话的预填 prompt（'带 prompt 发起对话'）")
    goal_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="关联对象类型 ticket/goal/...")
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quiet: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False,
        comment="quiet 事件：无 SSE 推送、展示去抖（demo.html 契约）")
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)


class SaIdea(Base):
    """Idea 卡 — AI 批量生成的灵感（emo + pitch + detail），可转为对话/Goal/Routine。"""
    __tablename__ = "sa_idea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    emo: Mapped[str] = mapped_column(String(10), default="💡", nullable=False)
    pitch: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="chat", nullable=False,
        comment="chat/goal/routine")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="转对话时预填")
    src: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="来源描述（demo.html 的 src 字段）")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False,
        comment="sha1(workspace_id + kind + pitch) 去重")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("workspace_id", "fingerprint", name="uq_sa_idea_ws_fingerprint"),)


class SaGoal(Base):
    """Goal — 目标卡片（steps 五态 + proposals L4 + version）。"""
    __tablename__ = "sa_goal"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="短 UUID")
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    context: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True,
        comment="active/paused/done/cancelled")
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="0-100")
    cron: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="check-in 计划")
    next_checkin: Mapped[str | None] = mapped_column(String(40), nullable=True)
    due: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="创建来源（idea/manual/demo）")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="每次 proposal accept +1")
    steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False,
        comment="[{idx, text, status: done/pending/in_progress/blocked/skipped}]")
    proposals: Mapped[list] = mapped_column(JSON, default=list, nullable=False,
        comment="[{idx, kind, message, payload, status: pending/accepted/dismissed}]")
    notes: Mapped[list] = mapped_column(JSON, default=list, nullable=False,
        comment="[{ts, text}] 进展时间线")
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)


Index("ix_sa_feed_ws_kind", SaFeedPost.workspace_id, SaFeedPost.kind)
Index("ix_sa_idea_ws_pinned", SaIdea.workspace_id, SaIdea.pinned)
Index("ix_sa_goal_ws_status", SaGoal.workspace_id, SaGoal.status)
