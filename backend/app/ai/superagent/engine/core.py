"""SuperAgentEngine — 领域内核（纯逻辑 + SQLAlchemy 事务）。

对齐 dsh-superagent engine.ts 的 Ports 模式：Engine 接受
Policy / Assessor / Executor / Outbox / Effects 作为端口依赖，
所有方法在 repository.atomic() 内运行。

Engine 5 部件（Part）：
  Intake    — Trigger 入库 + 扇入 Thread
  Evals     — Thread 串行 Eval + 过期重排
  Tickets   — Ticket 生命周期 + Subscription fan-out
  Assignments — Executor 绑定 + WorkerReport 状态机
  Replies   — Outbox Channel 写入 + SSE 推送
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Any

from loguru import logger


def _safe_create_task(coro) -> None:
    """安全的 asyncio.create_task —— 无 running loop 时静默跳过（单元测试场景）。"""
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(coro)
    except RuntimeError:
        logger.debug(f"_safe_create_task skipped — no running loop")


async def _try_sse_publish(event: str, data: dict | None = None) -> None:
    """延迟 import sse_bus，避免循环依赖。SSEBus 未安装时静默跳过。"""
    try:
        from ..sse_bus import sse_publish
        await sse_publish(event, data)
    except Exception as e:
        logger.debug(f"_try_sse_publish skipped: {e}")


# ============ Repository 接口（Ports 模式）============

class Repository(Protocol):
    """Engine 唯一持久化端口。所有事务在 atomic() 内完成。"""

    def atomic(self):
        """上下文管理器 —— 一个 Engine 方法调用 = 一个事务。"""
        ...


# ============ 5 个 Part 实现 ============

@dataclass
class _BasePart:
    """Engine 部件基类。持有 engine 引用以便访问其他部件。"""

    engine: "SuperAgentEngine" = field(init=False, repr=False)

    def __post_init__(self) -> None:
        pass


@dataclass
class IntakePart(_BasePart):
    """Intake — Trigger 入库 + 扇入 Thread。

    接收来自 Source 的 Trigger → 写入 sa_trigger → 关联/创建 sa_thread →
    通知 Evals 新 Thread 有待评估。
    """

    def receive_trigger(self, trigger: dict) -> str:
        """接收 Trigger → 入库 → 扇入 Thread → enqueue EFFECT_ASSESS。"""
        import shortuuid

        repo = self.engine.repository
        db = trigger.pop("_db", None)
        trigger_id = shortuuid.uuid()[:12]

        workspace_id = trigger["workspace_id"]
        source = trigger.get("source", "manual")
        ref_id = trigger.get("ref_id", trigger_id)

        # upsert thread
        thread = repo.upsert_thread(
            db,
            workspace_id=workspace_id,
            source=source,
            ref_id=ref_id,
            title=trigger.get("title"),
            url=trigger.get("url"),
            context=trigger.get("context"),
        )

        # create trigger
        repo.create_trigger(
            db,
            id=trigger_id,
            workspace_id=workspace_id,
            source=source,
            ref_id=ref_id,
            thread_id=thread.id,
            sender_id=trigger.get("sender_id"),
            sender_name=trigger.get("sender_name"),
            kind=trigger.get("kind", "manual"),
            title=trigger.get("title"),
            body=trigger.get("body"),
            url=trigger.get("url"),
            context=trigger.get("context", {}),
            status="pending",
        )

        # audit
        repo.log_action(
            db,
            workspace_id=workspace_id,
            action="receive_trigger",
            trigger_id=trigger_id,
            detail={"source": source, "thread_id": thread.id},
        )

        logger.info(
            f"IntakePart.receive_trigger · trigger={trigger_id} · thread={thread.id}"
        )

        # enqueue EFFECT_ASSESS（异步：事务外）
        try:
            db.commit()
        except Exception:
            pass

        # SSE 广播
        _safe_create_task(
            _try_sse_publish("trigger_received", {
                "trigger_id": trigger_id,
                "thread_id": thread.id,
                "source": source,
                "kind": trigger.get("kind"),
            })
        )

        if self.engine.effects is not None:
            asyncio.create_task(
                self.engine.effects.enqueue(
                    workspace_id=workspace_id,
                    kind="assessment",
                    payload={"thread_id": thread.id},
                )
            )
        return trigger_id


@dataclass
class EvalsPart(_BasePart):
    """Evals — Thread 串行 Eval 调度。"""

    def decide(self, thread_id: str) -> dict:
        """对 Thread 进行 Eval → 返回 Candidate / Decision。"""
        repo = self.engine.repository
        assessor = self.engine.assessor
        policy = self.engine.policy

        # 获取 thread
        with repo.atomic() as db:
            thread = db.query(
                __import__("app.models.superagent", fromlist=["SuperAgentThread"]).SuperAgentThread
            ).get(thread_id)
            if thread is None:
                logger.warning(f"EvalsPart.decide · thread={thread_id} not found")
                return {"accepted": False, "reason": "thread not found"}

            # 获取该 thread 的所有 pending triggers
            from app.models.superagent import SuperAgentTrigger
            triggers = list(
                db.query(SuperAgentTrigger)
                .filter(SuperAgentTrigger.thread_id == thread_id)
                .filter(SuperAgentTrigger.status == "pending")
                .all()
            )

            # 事务内快照 —— atomic 结束 Session close + expire，ORM 对象 detach 不可跨事务访问
            thread_source = thread.source
            thread_workspace_id = thread.workspace_id
            trigger_dicts = [
                {
                    "id": t.id, "title": t.title, "body": t.body,
                    "sender_id": t.sender_id, "sender_name": t.sender_name,
                    "addressed": t.kind in ("issue_mention", "pull_mention", "comment_mention"),
                }
                for t in triggers
            ]

        if not triggers:
            return {"accepted": False, "reason": "no pending triggers"}

        # 评估
        candidates = assessor.evaluate_thread(
            thread_id=thread_id,
            triggers=trigger_dicts,
            source_kind=f"github.{thread_source}" if thread_source.startswith("github") else thread_source,
            source=thread_source,
        )

        accepted = [c for c in candidates if c.should_accept]

        # 更新 trigger 状态
        with repo.atomic() as db:
            accepted_ids = {c.trigger_id for c in accepted}
            ignored_ids = {c.trigger_id for c in candidates if not c.should_accept}
            from app.models.superagent import SuperAgentTrigger
            if accepted_ids:
                db.query(SuperAgentTrigger).filter(
                    SuperAgentTrigger.id.in_(accepted_ids)
                ).update({"status": "accepted"}, synchronize_session="fetch")
            if ignored_ids:
                db.query(SuperAgentTrigger).filter(
                    SuperAgentTrigger.id.in_(ignored_ids)
                ).update({"status": "ignored"}, synchronize_session="fetch")

            repo.log_action(
                db,
                workspace_id=thread_workspace_id,
                action="decide",
                detail={
                    "thread_id": thread_id,
                    "total": len(candidates),
                    "accepted": len(accepted),
                },
            )

        logger.info(
            f"EvalsPart.decide · thread={thread_id} · "
            f"{len(accepted)}/{len(candidates)} accepted"
        )

        # enqueue EFFECT_LAUNCH for each accepted trigger
        for c in accepted:
            asyncio.create_task(
                self.engine.effects.enqueue(
                    workspace_id=thread_workspace_id,
                    kind="launch",
                    payload={
                        "trigger_id": c.trigger_id,
                        "thread_id": thread_id,
                    },
                )
            )

        # SSE 广播
        _safe_create_task(
            _try_sse_publish("eval_decided", {
                "thread_id": thread_id,
                "accepted": len(accepted),
                "total": len(candidates),
                "accepted_triggers": [c.trigger_id for c in accepted],
            })
        )

        return {
            "accepted": len(accepted) > 0,
            "accepted_triggers": [c.trigger_id for c in accepted],
            "total": len(candidates),
        }


@dataclass
class TicketsPart(_BasePart):
    """Tickets — Ticket 生命周期。"""

    def create_ticket(self, trigger_id: str, mandate: dict) -> str:
        """accept 决策 → 创建 Ticket + Mandate + Assignment(pending) + log Audit。"""
        import shortuuid

        repo = self.engine.repository
        policy = self.engine.policy

        ticket_id = shortuuid.uuid()[:12]
        mandate_id = shortuuid.uuid()[:12]
        assignment_id = shortuuid.uuid()[:12]

        # 在 atomic 内先查出 trigger 属性缓存（atomic 结束后 Session close 对象会 detach）
        trigger_title: str | None = None
        trigger_workspace_id: int = 0

        with repo.atomic() as db:
            from app.models.superagent import SuperAgentTrigger

            trigger = repo.get_trigger(db, trigger_id)
            if trigger is None:
                logger.error(f"TicketsPart.create_ticket · trigger={trigger_id} not found")
                raise ValueError(f"Trigger {trigger_id} not found")

            # 缓存属性 —— atomic 结束后 Session close 对象 detach
            trigger_title = trigger.title
            trigger_workspace_id = trigger.workspace_id

            # Ticket
            repo.create_ticket(
                db,
                id=ticket_id,
                workspace_id=trigger_workspace_id,
                trigger_id=trigger_id,
                status="open",
                title=mandate.get("title") or trigger_title or "Untitled Ticket",
                intent_evidence=mandate.get("intent_evidence", ""),
                acknowledgement=mandate.get("acknowledgement", ""),
            )

            # Mandate
            repo.create_mandate(
                db,
                id=mandate_id,
                ticket_id=ticket_id,
                workspace_id=trigger_workspace_id,
                policy_version=policy.version() if policy else "legacy",
                strength=mandate.get("strength", "explicit"),
                scope=mandate.get("scope"),
                matched_rules=mandate.get("matched_rules", []),
                source_identity={
                    "source": trigger.source,
                    "sender_id": trigger.sender_id,
                },
                trigger_id=trigger_id,
                acknowledgement=mandate.get("acknowledgement"),
                intent_evidence=mandate.get("intent_evidence"),
                worktree_name=mandate.get("worktree_name"),
            )

            # Assignment (pending)
            repo.create_assignment(
                db,
                id=assignment_id,
                ticket_id=ticket_id,
                workspace_id=trigger_workspace_id,
                status="pending",
            )

            # Subscription —— ticket 订阅触发 thread
            repo.upsert_subscription(
                db,
                ticket_id=ticket_id,
                thread_id=trigger.thread_id or f"{trigger.source}:{trigger.ref_id}",
                workspace_id=trigger_workspace_id,
                kind="following",
            )

            # Audit
            repo.log_action(
                db,
                workspace_id=trigger_workspace_id,
                action="create_ticket",
                ticket_id=ticket_id,
                trigger_id=trigger_id,
                detail={"mandate_id": mandate_id},
            )

        logger.info(f"TicketsPart.create_ticket · ticket={ticket_id} · trigger={trigger_id}")

        # SSE 广播 —— 用缓存的属性（atomic 已结束，trigger 对象已 detach）
        _safe_create_task(
            _try_sse_publish("ticket_created", {
                "ticket_id": ticket_id,
                "trigger_id": trigger_id,
                "title": trigger_title,
                "status": "open",
            })
        )

        return ticket_id

    def ticket_report(self, ticket_id: str, report: dict) -> None:
        """WorkerReport 回写 + followsDone 检查。"""
        repo = self.engine.repository
        from app.ai.superagent.executor.report import next_assignment_status

        report_kind = report.get("kind", "progress")
        new_assignment_status = next_assignment_status("running", report_kind)

        with repo.atomic() as db:
            repo.update_assignment(
                db, ticket_id=ticket_id,
                status=new_assignment_status,
                final_report=report,
                ended_at=datetime.utcnow() if new_assignment_status == "ended" else None,
            )

            # Ticket 状态转换
            ticket = repo.get_ticket(db, ticket_id)
            if ticket is None:
                logger.error(f"TicketsPart.ticket_report · ticket={ticket_id} not found")
                return

            if report_kind == "ready":
                # followsDone: 检查所有 following Subscription Thread closed
                from app.models.superagent import SuperAgentThread
                subscriptions = repo.list_subscriptions(db, ticket_id=ticket_id)
                following = [s for s in subscriptions if s.kind == "following"]

                if not following:
                    # 没有外部订阅依赖 → 直接完成
                    repo.update_ticket(
                        db, ticket_id=ticket_id,
                        status="completed", completed_at=datetime.utcnow(),
                    )
                else:
                    # 有订阅依赖 → 检查是否全部 Thread 已 closed
                    all_closed = True
                    for sub in following:
                        thread_obj = (
                            db.query(SuperAgentThread)
                            .filter(SuperAgentThread.id == sub.thread_id)
                            .first()
                        )
                        if thread_obj is None or thread_obj.status != "closed":
                            all_closed = False
                            break
                    if all_closed:
                        repo.update_ticket(
                            db, ticket_id=ticket_id,
                            status="completed", completed_at=datetime.utcnow(),
                        )
                        repo.log_action(
                            db,
                            workspace_id=ticket.workspace_id,
                            action="follows_done",
                            ticket_id=ticket_id,
                            detail={"following_count": len(following)},
                        )
                    else:
                        # 仍有订阅 Thread 未关闭 → Ticket 进入 waiting_follows
                        repo.update_ticket(db, ticket_id=ticket_id, status="waiting_follows")
            elif report_kind == "blocked":
                awaiting = report.get("awaiting_human", True)
                new_status = "waiting_hitl" if awaiting else "waiting_person"
                repo.update_ticket(db, ticket_id=ticket_id, status=new_status)
            elif report_kind == "failed":
                repo.update_ticket(db, ticket_id=ticket_id, status="failed")
            elif report_kind == "dropped":
                repo.update_ticket(db, ticket_id=ticket_id, status="dropped")
            elif report_kind == "progress":
                repo.update_ticket(db, ticket_id=ticket_id, status="working")

            repo.log_action(
                db,
                workspace_id=ticket.workspace_id,
                action="ticket_report",
                ticket_id=ticket_id,
                detail={"report": report},
            )

        logger.info(
            f"TicketsPart.ticket_report · ticket={ticket_id} · kind={report_kind} → "
            f"assignment={new_assignment_status}"
        )

        # SSE 广播 —— 事件类型依赖 report_kind
        _safe_create_task(
            _try_sse_publish("ticket_updated", {
                "ticket_id": ticket_id,
                "report_kind": report_kind,
                "assignment_status": new_assignment_status,
            })
        )
        if report_kind == "ready":
            _safe_create_task(
                _try_sse_publish("ticket_completed", {"ticket_id": ticket_id})
            )

    def handback(self, ticket_id: str, trigger_id: str, reason: str) -> bool:
        """Worker 交还 Trigger → 重新排队 Eval（每 Ticket×Trigger 只交还一次）。"""
        repo = self.engine.repository

        # 用 context 追踪 handback
        handback_key = f"handback:{ticket_id}:{trigger_id}"
        # 检查是否已交还过（用 Audit log 作为去重标记）
        with repo.atomic() as db:
            from app.models.superagent import SuperAgentAuditLog
            existing = db.query(SuperAgentAuditLog).filter(
                SuperAgentAuditLog.ticket_id == ticket_id,
                SuperAgentAuditLog.trigger_id == trigger_id,
                SuperAgentAuditLog.action == "handback",
            ).first()
            if existing:
                logger.info(
                    f"TicketsPart.handback · ticket={ticket_id} trigger={trigger_id} "
                    f"already handed back — skip"
                )
                return False

            ticket = repo.get_ticket(db, ticket_id)
            if ticket is None:
                logger.error(f"TicketsPart.handback · ticket={ticket_id} not found")
                return False

            # 交还 trigger → status=pending 重新进入 eval queue
            from app.models.superagent import SuperAgentTrigger
            db.query(SuperAgentTrigger).filter(
                SuperAgentTrigger.id == trigger_id
            ).update({"status": "pending"}, synchronize_session="fetch")

            repo.log_action(
                db,
                workspace_id=ticket.workspace_id,
                action="handback",
                ticket_id=ticket_id,
                trigger_id=trigger_id,
                detail={"reason": reason},
            )

        logger.info(
            f"TicketsPart.handback · ticket={ticket_id} · trigger={trigger_id} · reason={reason}"
        )

        # 重新 enqueue assessment
        asyncio.create_task(
            self.engine.effects.enqueue(
                workspace_id=ticket.workspace_id,
                kind="assessment",
                payload={"trigger_id": trigger_id},
            )
        )
        return True


@dataclass
class AssignmentsPart(_BasePart):
    """Assignments — Ticket ↔ Executor 绑定。"""

    def launch(self, ticket_id: str) -> str:
        """Assignment pending → running。返回 executor_session 名。"""
        import shortuuid

        repo = self.engine.repository
        session_name = f"worker-{shortuuid.uuid()[:8]}"

        with repo.atomic() as db:
            from app.models.superagent import SuperAgentAssignment
            assignment = repo.get_assignment(db, ticket_id=ticket_id)
            if assignment is None:
                logger.error(f"AssignmentsPart.launch · ticket={ticket_id} assignment not found")
                raise ValueError(f"Assignment for ticket {ticket_id} not found")
            if assignment.status != "pending":
                logger.warning(
                    f"AssignmentsPart.launch · ticket={ticket_id} "
                    f"assignment already {assignment.status}"
                )
                return assignment.executor_session or session_name

            repo.update_assignment(
                db, ticket_id=ticket_id,
                status="running",
                executor_session=session_name,
                started_at=datetime.utcnow(),
            )

            ticket = repo.get_ticket(db, ticket_id)
            if ticket:
                repo.update_ticket(db, ticket_id, status="working")
                repo.log_action(
                    db,
                    workspace_id=ticket.workspace_id,
                    action="launch",
                    ticket_id=ticket_id,
                    detail={"executor_session": session_name},
                )

        logger.info(
            f"AssignmentsPart.launch · ticket={ticket_id} · session={session_name}"
        )

        # SSE 广播
        _safe_create_task(
            _try_sse_publish("assignment_launched", {
                "ticket_id": ticket_id,
                "session_name": session_name,
            })
        )
        return session_name


@dataclass
class RepliesPart(_BasePart):
    """Replies — Outbox Channel 写入。"""

    def send_reply(self, ticket_id: str, message: str, channel: Any = None) -> None:
        """Worker 回复 → OutboxService.send_reply()。"""
        repo = self.engine.repository

        with repo.atomic() as db:
            ticket = repo.get_ticket(db, ticket_id)
            if ticket is None:
                logger.error(f"RepliesPart.send_reply · ticket={ticket_id} not found")
                return

            repo.log_action(
                db,
                workspace_id=ticket.workspace_id,
                action="send_reply",
                ticket_id=ticket_id,
                detail={"message_preview": message[:200]},
            )

        # 异步 enqueue delivery effect
        asyncio.create_task(
            self.engine.effects.enqueue(
                workspace_id=ticket.workspace_id,
                kind="delivery",
                payload={"ticket_id": ticket_id, "message": message},
            )
        )
        logger.info(f"RepliesPart.send_reply · ticket={ticket_id} · msg_len={len(message)}")


# ============ Engine 组装 ============

@dataclass
class SuperAgentEngine:
    """SuperAgent 引擎 —— 领域内核。

    构造时注入所有 Port 依赖（Ports 模式），所有方法在
    repository.atomic() 内运行。
    """

    # --- 端口依赖 ---
    repository: Repository
    policy: Any | None = None
    assessor: Any | None = None
    executor: Any | None = None
    outbox: Any | None = None
    effects: Any | None = None

    # --- 5 个 Part ---
    intake: IntakePart = field(default_factory=IntakePart)
    evals: EvalsPart = field(default_factory=EvalsPart)
    tickets: TicketsPart = field(default_factory=TicketsPart)
    assignments: AssignmentsPart = field(default_factory=AssignmentsPart)
    replies: RepliesPart = field(default_factory=RepliesPart)

    def __post_init__(self) -> None:
        # 反向注入 engine 引用
        self.intake.engine = self  # type: ignore[attr-defined]
        self.evals.engine = self  # type: ignore[attr-defined]
        self.tickets.engine = self  # type: ignore[attr-defined]
        self.assignments.engine = self  # type: ignore[attr-defined]
        self.replies.engine = self  # type: ignore[attr-defined]
        logger.info("SuperAgentEngine 初始化完成 · 5 Parts 就绪")

    # ============ 核心事务 ============

    def receive_trigger(self, trigger: dict) -> str:
        """端口：Intake.receive_trigger。"""
        with self.repository.atomic() as db:
            trigger_copy = dict(trigger)
            trigger_copy["_db"] = db
            return self.intake.receive_trigger(trigger_copy)

    def decide(self, thread_id: str) -> dict:
        """端口：Evals.decide。Thread 串行 Eval。"""
        return self.evals.decide(thread_id)

    def create_ticket(self, trigger_id: str, mandate: dict) -> str:
        """端口：Tickets.create_ticket。accept → Ticket + Mandate + Assignment。"""
        return self.tickets.create_ticket(trigger_id, mandate)

    def ticket_report(self, ticket_id: str, report: dict) -> None:
        """端口：Tickets.ticket_report。WorkerReport 回写 + followsDone。"""
        self.tickets.ticket_report(ticket_id, report)

    def launch(self, ticket_id: str) -> str:
        """端口：Assignments.launch。Assignment pending→running。"""
        return self.assignments.launch(ticket_id)

    def ticket_interrupted(self, ticket_id: str) -> None:
        """Worker 被中断 → Assignment ended → Ticket open。"""
        self.tickets.ticket_report(ticket_id, {"kind": "failed", "message": "interrupted"})

    def retry_ticket(self, ticket_id: str) -> None:
        """Transient retry 耗尽后手动重试 → re-enqueue EFFECT_LAUNCH。"""
        repo = self.repository
        with repo.atomic():
            from app.models.superagent import SuperAgentTicket
            ticket = repo.get_ticket(repo._db_factory.__wrapped__() if hasattr(repo._db_factory, '__wrapped__') else repo._db_factory(), ticket_id)
            if ticket is None:
                logger.error(f"retry_ticket · ticket={ticket_id} not found")
                return
            repo.update_ticket(repo._db_factory.__wrapped__() if hasattr(repo._db_factory, '__wrapped__') else repo._db_factory(),
                               ticket_id, status="open")

    def handback(self, ticket_id: str, trigger_id: str, reason: str) -> bool:
        """Worker 交还 Trigger → 重新排队 Eval。"""
        return self.tickets.handback(ticket_id, trigger_id, reason)
