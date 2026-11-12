"""Repository —— SuperAgentEngine 唯一持久化端口的 SQLAlchemy 实现。

所有 Engine 事务在 atomic() 上下文管理器内运行，事务粒度 = 一个 Engine 方法调用。
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from loguru import logger
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.superagent import (
    SuperAgentAuditLog, SuperAgentAssignment, SuperAgentEffect, SuperAgentMandate,
    SuperAgentSubscription, SuperAgentThread, SuperAgentTicket, SuperAgentTrigger,
)
from app.models.superagent_workspace_config import SuperAgentWorkspaceConfig


class SuperAgentRepository:
    """Engine 唯一持久化端口 —— 所有 SQL 事务在此完成。"""

    def __init__(self, db_factory: callable = SessionLocal):
        self._db_factory = db_factory

    @contextmanager
    def atomic(self) -> Iterator[Session]:
        """一个 Engine 方法调用 = 一个事务。"""
        db: Session = self._db_factory()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Repository.atomic rolled back: {e}")
            raise
        finally:
            db.close()

    # -------- Trigger --------
    def create_trigger(self, db: Session, **fields) -> SuperAgentTrigger:
        obj = SuperAgentTrigger(**fields)
        db.add(obj)
        db.flush()
        return obj

    def get_trigger(self, db: Session, trigger_id: str) -> SuperAgentTrigger | None:
        return db.get(SuperAgentTrigger, trigger_id)

    # -------- Thread --------
    def upsert_thread(self, db: Session, *, workspace_id: int, source: str,
                      ref_id: str, title: str | None = None,
                      url: str | None = None,
                      context: dict | None = None) -> SuperAgentThread:
        stmt = select(SuperAgentThread).where(
            SuperAgentThread.workspace_id == workspace_id,
            SuperAgentThread.source == source,
            SuperAgentThread.ref_id == ref_id,
        )
        thread = db.execute(stmt).scalar_one_or_none()
        if thread is None:
            thread = SuperAgentThread(
                id=f"{source}:{ref_id}", workspace_id=workspace_id, source=source,
                ref_id=ref_id, title=title, url=url, context=context or {},
            )
            db.add(thread)
        elif title:
            thread.title = title
        return thread

    def open_threads(self, db: Session, workspace_id: int) -> list[SuperAgentThread]:
        stmt = select(SuperAgentThread).where(
            SuperAgentThread.workspace_id == workspace_id,
            SuperAgentThread.status == "open",
        ).order_by(SuperAgentThread.updated_at.desc())
        return list(db.execute(stmt).scalars())

    # -------- Ticket --------
    def create_ticket(self, db: Session, **fields) -> SuperAgentTicket:
        obj = SuperAgentTicket(**fields)
        db.add(obj)
        db.flush()
        return obj

    def get_ticket(self, db: Session, ticket_id: str) -> SuperAgentTicket | None:
        return db.get(SuperAgentTicket, ticket_id)

    def list_tickets(self, db: Session, *, workspace_id: int,
                     status: str | None = None,
                     limit: int = 50) -> list[SuperAgentTicket]:
        stmt = select(SuperAgentTicket).where(
            SuperAgentTicket.workspace_id == workspace_id
        )
        if status:
            stmt = stmt.where(SuperAgentTicket.status == status)
        stmt = stmt.order_by(SuperAgentTicket.created_at.desc()).limit(limit)
        return list(db.execute(stmt).scalars())

    def update_ticket(self, db: Session, ticket_id: str, **updates) -> None:
        db.execute(
            update(SuperAgentTicket).where(SuperAgentTicket.id == ticket_id).values(**updates)
        )

    # -------- Subscription --------
    def upsert_subscription(self, db: Session, *, ticket_id: str, thread_id: str,
                            workspace_id: int,
                            kind: str = "following") -> SuperAgentSubscription | None:
        stmt = select(SuperAgentSubscription).where(
            SuperAgentSubscription.ticket_id == ticket_id,
            SuperAgentSubscription.thread_id == thread_id,
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            return None  # already exists
        obj = SuperAgentSubscription(
            ticket_id=ticket_id, thread_id=thread_id,
            workspace_id=workspace_id, kind=kind,
        )
        db.add(obj)
        db.flush()
        return obj

    def list_subscriptions(self, db: Session, *,
                           ticket_id: str | None = None,
                           thread_id: str | None = None) -> list[SuperAgentSubscription]:
        stmt = select(SuperAgentSubscription)
        if ticket_id:
            stmt = stmt.where(SuperAgentSubscription.ticket_id == ticket_id)
        if thread_id:
            stmt = stmt.where(SuperAgentSubscription.thread_id == thread_id)
        return list(db.execute(stmt).scalars())

    def threads_for_ticket(self, db: Session, ticket_id: str) -> list[SuperAgentThread]:
        """Subscription fan-out：Ticket 订阅的所有 Thread。"""
        subscriptions = self.list_subscriptions(db, ticket_id=ticket_id)
        thread_ids = [s.thread_id for s in subscriptions]
        if not thread_ids:
            return []
        stmt = select(SuperAgentThread).where(SuperAgentThread.id.in_(thread_ids))
        return list(db.execute(stmt).scalars())

    # -------- Mandate --------
    def create_mandate(self, db: Session, **fields) -> SuperAgentMandate:
        obj = SuperAgentMandate(**fields)
        db.add(obj)
        db.flush()
        return obj

    def get_mandate(self, db: Session, ticket_id: str) -> SuperAgentMandate | None:
        stmt = select(SuperAgentMandate).where(SuperAgentMandate.ticket_id == ticket_id)
        return db.execute(stmt).scalar_one_or_none()

    # -------- Assignment --------
    def create_assignment(self, db: Session, **fields) -> SuperAgentAssignment:
        obj = SuperAgentAssignment(**fields)
        db.add(obj)
        db.flush()
        return obj

    def get_assignment(self, db: Session, ticket_id: str) -> SuperAgentAssignment | None:
        stmt = select(SuperAgentAssignment).where(SuperAgentAssignment.ticket_id == ticket_id)
        return db.execute(stmt).scalar_one_or_none()

    def update_assignment(self, db: Session, ticket_id: str, **updates) -> None:
        db.execute(
            update(SuperAgentAssignment).where(
                SuperAgentAssignment.ticket_id == ticket_id,
            ).values(**updates)
        )

    # -------- Effect --------
    def next_seq(self, db: Session, kind: str, workspace_id: int) -> int:
        stmt = select(func.coalesce(func.max(SuperAgentEffect.seq), 0)).where(
            SuperAgentEffect.kind == kind,
            SuperAgentEffect.workspace_id == workspace_id,
        )
        result = db.execute(stmt).scalar_one() or 0
        return result + 1

    def enqueue_effect(self, db: Session, **fields) -> SuperAgentEffect:
        obj = SuperAgentEffect(**fields)
        db.add(obj)
        db.flush()
        return obj

    def effects_by_status(self, db: Session, *, kind: str | None = None,
                          status: str = "pending",
                          limit: int = 20) -> list[SuperAgentEffect]:
        stmt = select(SuperAgentEffect).where(SuperAgentEffect.status == status)
        if kind:
            stmt = stmt.where(SuperAgentEffect.kind == kind)
        stmt = stmt.order_by(SuperAgentEffect.created_at.asc()).limit(limit)
        return list(db.execute(stmt).scalars())

    def update_effect_status(self, db: Session, effect_id: str, status: str,
                             **extra) -> None:
        values: dict[str, object] = {"status": status}
        values.update(extra)
        db.execute(
            update(SuperAgentEffect).where(SuperAgentEffect.id == effect_id).values(**values)
        )

    # -------- Workspace Config --------
    def get_workspace_config(self, db: Session,
                             workspace_id: int) -> SuperAgentWorkspaceConfig | None:
        stmt = select(SuperAgentWorkspaceConfig).where(
            SuperAgentWorkspaceConfig.workspace_id == workspace_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def upsert_workspace_config(self, db: Session, workspace_id: int,
                                **updates) -> SuperAgentWorkspaceConfig:
        cfg = self.get_workspace_config(db, workspace_id)
        if cfg is None:
            cfg = SuperAgentWorkspaceConfig(workspace_id=workspace_id)
            db.add(cfg)
        for k, v in updates.items():
            setattr(cfg, k, v)
        db.flush()
        return cfg

    # -------- Audit --------
    def log_action(self, db: Session, *, workspace_id: int, action: str,
                   ticket_id: str | None = None,
                   trigger_id: str | None = None,
                   detail: dict | None = None) -> SuperAgentAuditLog:
        obj = SuperAgentAuditLog(
            workspace_id=workspace_id, ticket_id=ticket_id, trigger_id=trigger_id,
            action=action, detail=detail or {},
        )
        db.add(obj)
        return obj
