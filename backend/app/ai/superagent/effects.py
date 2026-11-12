"""EffectQueue —— Durable 6 kind 持久化队列 + 指数退避 + per-kind 并发限制。

对齐 dsh-superagent effect 表 + Later 信号。Task 7 完整队列实现。
"""
from __future__ import annotations
import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

from loguru import logger

from .repository import SuperAgentRepository


EFFECT_KINDS = ["assessment", "launch", "delivery", "relay", "notice", "reply"]
# per-kind 并发限制（对齐 dsh-superagent 规格）：
#   assessment=4、launch=workspace max_workers（sa_workspace_config 缺省回落 3）、
#   delivery=2、relay=4、notice=8、reply=4
EFFECT_CONCURRENCY = {
    "assessment": 4, "launch": 3, "delivery": 2,
    "relay": 4, "notice": 8, "reply": 4,
}


class EffectQueue:
    """Durable Effect Queue —— SQLAlchemy 持久化 + asyncio 活跃调度。

    engine/outbox/reflector 为可选依赖（默认 None 保持向后兼容）：
      - engine    — handler 内驱动 decide/create_ticket/launch/ticket_report
      - outbox    — delivery/notice/reply 消息投递（缺省懒创建 OutboxService）
      - reflector — Worker 产出校验（缺省懒创建 ReflectorService）
    """

    def __init__(self, repo: SuperAgentRepository, engine: Any | None = None,
                 outbox: Any | None = None, reflector: Any | None = None):
        self.repo = repo
        self._engine = engine
        self._outbox = outbox
        self._reflector = reflector
        self._worker_tasks: set[asyncio.Task] = set()
        self._stop = asyncio.Event()
        self._later_signals: dict[str, asyncio.Event] = {
            k: asyncio.Event() for k in EFFECT_KINDS
        }
        self._task: asyncio.Task | None = None
        self._running: dict[str, int] = {k: 0 for k in EFFECT_KINDS}

    async def enqueue(self, *, workspace_id: int, kind: str,
                      ticket_id: str | None = None,
                      payload: dict | None = None) -> str:
        """入队 Effect —— 写 sa_effect + signal 激活 worker。"""
        assert kind in EFFECT_KINDS, f"Unknown effect kind: {kind}"
        import shortuuid
        eid = shortuuid.uuid()[:12]
        with self.repo.atomic() as db:
            seq = self.repo.next_seq(db, kind, workspace_id)
            self.repo.enqueue_effect(
                db, id=eid, workspace_id=workspace_id, kind=kind, seq=seq,
                ticket_id=ticket_id, payload=payload or {}, status="pending",
            )
        self._later_signals[kind].set()
        logger.info(f"EffectQueue.enqueue · {kind}#{seq} · ticket={ticket_id}")
        return eid

    async def start(self) -> None:
        """启动所有 6 kind worker。"""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_all_kinds())
        logger.info(f"EffectQueue started · {len(EFFECT_KINDS)} kinds")

    async def stop(self) -> None:
        self._stop.set()
        for sig in self._later_signals.values():
            sig.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_all_kinds(self) -> None:
        """每个 kind 一个 worker loop。"""
        tasks = [asyncio.create_task(self._kind_worker(k)) for k in EFFECT_KINDS]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    async def _kind_worker(self, kind: str) -> None:
        """per-kind worker —— 从 DB 取 pending Effect → 执行 → 回写状态。"""
        while not self._stop.is_set():
            # 取 pending 且 due<=now 的 Effect；事务内快照后执行
            #（atomic 结束 Session close + expire，ORM 对象 detach 不可跨事务访问）
            claimed: list[Any] = []
            with self.repo.atomic() as db:
                effects = self.repo.effects_by_status(
                    db, kind=kind, status="pending",
                    limit=EFFECT_CONCURRENCY[kind] * 3,
                )
                ready = [
                    e for e in effects
                    if e.due is None or e.due <= datetime.utcnow()
                ]
                slots = EFFECT_CONCURRENCY[kind] - self._running.get(kind, 0)
                claimed = self._claim_effects(
                    db, kind, ready, max(0, slots),
                )

            for e in claimed:
                try:
                    await self._execute(kind, e)
                except Exception as exc:
                    await self._handle_failure(kind, e, exc)
                finally:
                    self._running[kind] = max(0, self._running.get(kind, 0) - 1)

            # 等待 signal 或下一个 cycle
            sig = self._later_signals[kind]
            sig.clear()
            try:
                await asyncio.wait_for(sig.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

    def _claim_effects(self, db: Any, kind: str, ready: list[Any],
                       slots: int) -> list[Any]:
        """事务内领取 Effect —— 标记 running 并返回执行快照。

        launch kind 按 workspace max_workers 额外限流（sa_workspace_config
        缺配置时回落 EFFECT_CONCURRENCY 默认值 3）；其余 kind 直接取前 slots 个。
        """
        picked: list[Any] = []
        if kind == "launch":
            ws_caps: dict[int, int] = {}
            ws_claimed: dict[int, int] = {}
            for e in ready:
                if len(picked) >= slots:
                    break
                ws = e.workspace_id
                if ws not in ws_caps:
                    ws_caps[ws] = self._workspace_max_workers(db, ws)
                if ws_claimed.get(ws, 0) >= ws_caps[ws]:
                    continue
                ws_claimed[ws] = ws_claimed.get(ws, 0) + 1
                picked.append(e)
        else:
            picked = ready[:slots]

        claimed: list[Any] = []
        for e in picked:
            self.repo.update_effect_status(db, e.id, "running")
            self._running[kind] = self._running.get(kind, 0) + 1
            claimed.append(SimpleNamespace(
                id=e.id, kind=kind, seq=e.seq, workspace_id=e.workspace_id,
                ticket_id=e.ticket_id,
                payload=dict(e.payload or {}), attempts=e.attempts or 0,
            ))
        return claimed

    def _workspace_max_workers(self, db: Any, workspace_id: int) -> int:
        """解析 workspace 的 launch 并发上限 —— sa_workspace_config.max_workers，
        缺配置/非法值回落默认 3。"""
        fallback = EFFECT_CONCURRENCY["launch"]
        try:
            cfg = self.repo.get_workspace_config(db, workspace_id)
        except Exception as exc:
            logger.warning(f"EffectQueue · workspace config lookup failed "
                           f"(ws={workspace_id}): {exc}")
            return fallback
        if cfg is None:
            return fallback
        try:
            mw = int(cfg.max_workers)
        except (TypeError, ValueError):
            return fallback
        return mw if mw > 0 else fallback

    async def _execute(self, kind: str, effect: Any) -> None:
        """执行 Effect —— 分发到 handler。"""
        handler_name = f"_handle_{kind}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            logger.warning(f"EffectQueue · no handler for kind={kind}")
            self._mark_done(effect.id, {"handler": "missing"})
            return
        result = await handler(effect.payload, effect)
        self._mark_done(effect.id, result)

    async def _handle_failure(self, kind: str, effect: Any, exc: Exception) -> None:
        """失败 → 指数退避（15s → 30s → 60s → fail）。"""
        attempts = effect.attempts + 1
        if attempts >= 4:
            self._mark_failed(effect.id, attempts, str(exc))
            return
        delay = 15 * (2 ** (attempts - 1)) + random.uniform(0, 5)
        logger.warning(
            f"EffectQueue · {kind}#{effect.seq} failure (attempt {attempts}/4) · "
            f"retry in {delay:.1f}s"
        )
        with self.repo.atomic() as db:
            self.repo.update_effect_status(
                db, effect.id, "pending",
                attempts=attempts,
                due=datetime.utcnow() + timedelta(seconds=delay),
            )

    def _mark_done(self, eid: str, result: dict) -> None:
        with self.repo.atomic() as db:
            self.repo.update_effect_status(db, eid, "done", result=result)

    def _mark_failed(self, eid: str, attempts: int, error: str) -> None:
        with self.repo.atomic() as db:
            self.repo.update_effect_status(
                db, eid, "failed",
                attempts=attempts,
                result={"error": error},
            )

    # ---- 依赖懒创建（局部 import 防循环依赖）----

    def _get_outbox(self) -> Any:
        if self._outbox is None:
            from .outbox import OutboxService
            self._outbox = OutboxService()
        return self._outbox

    def _get_reflector(self) -> Any:
        if self._reflector is None:
            from .reflector import ReflectorService
            self._reflector = ReflectorService(repo=self.repo, engine=self._engine, queue=self)
        return self._reflector

    # ---- 6 kind handler（真实管道）----

    async def _handle_assessment(self, payload: dict, effect: Any) -> dict:
        """EffectQueue._handle_assessment —— Thread Eval → engine.decide()。

        Engine 在 accept 后自行 enqueue launch effect。
        """
        from .sse_bus import sse_publish
        logger.info(f"EffectQueue · assessment#{effect.seq} · payload={payload}")
        await sse_publish("effect_assessment", {"kind": "assessment", "seq": effect.seq, "ticket_id": effect.ticket_id})
        thread_id = payload.get("thread_id")
        if self._engine is None or not thread_id:
            return {"ok": True, "message": "Assessment skipped (no engine/thread_id)"}
        decision = self._engine.decide(thread_id)
        return {"ok": True, "decide": decision}

    async def _handle_launch(self, payload: dict, effect: Any) -> dict:
        """EffectQueue._handle_launch —— 创建 Ticket（防重复）→ launch → 后台 Worker。"""
        from .sse_bus import sse_publish
        logger.info(f"EffectQueue · launch#{effect.seq} · payload={payload}")
        await sse_publish("effect_launch", {"kind": "launch", "seq": effect.seq, "ticket_id": effect.ticket_id})
        engine = self._engine
        if engine is None:
            return {"ok": True, "message": "Launch skipped (no engine)"}

        trigger_id = payload.get("trigger_id")
        ticket_id = payload.get("ticket_id") or effect.ticket_id
        if ticket_id is None and trigger_id:
            # 防重复创建：同一 trigger 已有 ticket 则跳过 create
            ticket_id = self._ticket_for_trigger(trigger_id)
            if ticket_id is None:
                ticket_id = self._create_ticket_for_trigger(trigger_id)
        if ticket_id is None:
            return {"ok": False, "error": f"no ticket resolvable (trigger={trigger_id})"}

        engine.launch(ticket_id)
        task = asyncio.create_task(self._run_worker(ticket_id, trigger_id))
        self._worker_tasks.add(task)
        task.add_done_callback(self._worker_tasks.discard)
        return {"ok": True, "ticket_id": ticket_id, "worker": "dispatched"}

    async def _handle_delivery(self, payload: dict, effect: Any) -> dict:
        """EffectQueue._handle_delivery —— Outbox 结果投递。"""
        from .sse_bus import sse_publish
        logger.info(f"EffectQueue · delivery#{effect.seq} · payload={payload}")
        await sse_publish("effect_delivery", {"kind": "delivery", "seq": effect.seq, "ticket_id": effect.ticket_id})
        ticket_id = payload.get("ticket_id") or effect.ticket_id
        if ticket_id:
            await self._get_outbox().send_result(ticket_id, payload.get("message", ""))
        return {"ok": True, "message": "Delivery dispatched"}

    async def _handle_relay(self, payload: dict, effect: Any) -> dict:
        """EffectQueue._handle_relay —— 跨 Source 消息转发。

        SSE 转发（前端 Feed 实时消费）+ 真实外发通道：payload 带
        relay_to（如 "feishu"）时经 Outbox.send_relay 投递，可选
        chat_id 显式指定目标群（缺省用 workspace feishu_source_cfg 首群）。
        """
        from .sse_bus import sse_publish
        logger.info(f"EffectQueue · relay#{effect.seq} · payload={payload}")
        await sse_publish("effect_relay", {
            **payload,
            "kind": "relay", "seq": effect.seq, "ticket_id": effect.ticket_id,
        })
        relay_to = payload.get("relay_to")
        if relay_to:
            await self._get_outbox().send_relay(
                effect.ticket_id or "",
                payload.get("message", ""),
                channel=relay_to,
                chat_id=payload.get("chat_id"),
            )
            return {"ok": True, "message": f"Relay forwarded via SSE + {relay_to}"}
        return {"ok": True, "message": "Relay forwarded via SSE"}

    async def _handle_notice(self, payload: dict, effect: Any) -> dict:
        """EffectQueue._handle_notice —— Outbox 注意力通知。"""
        from .sse_bus import sse_publish
        logger.info(f"EffectQueue · notice#{effect.seq} · payload={payload}")
        await sse_publish("effect_notice", {"kind": "notice", "seq": effect.seq, "ticket_id": effect.ticket_id})
        ticket_id = payload.get("ticket_id") or effect.ticket_id
        await self._get_outbox().send_attention(ticket_id or "", payload.get("message", ""))
        return {"ok": True, "message": "Notice dispatched"}

    async def _handle_reply(self, payload: dict, effect: Any) -> dict:
        """EffectQueue._handle_reply —— Worker 回复到 Outbox。"""
        from .sse_bus import sse_publish
        logger.info(f"EffectQueue · reply#{effect.seq} · payload={payload}")
        await sse_publish("effect_reply", {"kind": "reply", "seq": effect.seq, "ticket_id": effect.ticket_id})
        ticket_id = payload.get("ticket_id") or effect.ticket_id
        if ticket_id:
            await self._get_outbox().send_reply(ticket_id, payload.get("message", ""))
        return {"ok": True, "message": "Reply dispatched"}

    # ---- launch 辅助 ----

    def _ticket_for_trigger(self, trigger_id: str) -> str | None:
        """同一 trigger 已有 Ticket → 返回 id（防重复创建）。"""
        with self.repo.atomic() as db:
            from app.models.superagent import SuperAgentTicket
            row = db.query(SuperAgentTicket).filter(
                SuperAgentTicket.trigger_id == trigger_id
            ).first()
            return row.id if row else None

    def _create_ticket_for_trigger(self, trigger_id: str) -> str | None:
        """accepted Trigger → engine.create_ticket()（Mandate 由 Trigger 字段构建）。"""
        engine = self._engine
        if engine is None:
            return None
        with self.repo.atomic() as db:
            trigger = self.repo.get_trigger(db, trigger_id)
            if trigger is None:
                logger.error(f"EffectQueue · launch · trigger={trigger_id} not found")
                return None
            mandate = {
                "title": trigger.title,
                "strength": "explicit",
                "scope": (trigger.body or "")[:1000] or None,
                "matched_rules": [{"rule_id": "effect_launch", "reason": "accepted trigger"}],
                "source_identity": {"source": trigger.source, "sender_id": trigger.sender_id},
                "intent_evidence": f"accepted trigger · kind={trigger.kind}",
            }
        return engine.create_ticket(trigger_id, mandate)

    def _mandate_scope(self, ticket_id: str) -> str | None:
        """Worker task 文本 —— Mandate.scope。"""
        with self.repo.atomic() as db:
            mandate = self.repo.get_mandate(db, ticket_id=ticket_id)
            return (mandate.scope or None) if mandate else None

    async def _run_worker(self, ticket_id: str, trigger_id: str | None) -> None:
        """后台 Worker 执行 + Reflector 校验闭环。

        WorkerSession.run() → reflector.finalize()：
          pass → engine.ticket_report(kind="ready")
          fail → re-enqueue launch（重试计数见 ReflectorService.max_retries）
          超限 / 异常 → engine.ticket_report(kind="failed")
        """
        engine = self._engine
        if engine is None:
            return
        from .executor.session import WorkerSession

        try:
            task_text = self._mandate_scope(ticket_id) or "Complete the ticket task and report the result."
            session = WorkerSession(ticket_id=ticket_id)
            output = await session.run(task_text)
            await session.stop()
        except Exception as e:
            logger.error(f"EffectQueue · worker crashed · ticket={ticket_id}: {e}")
            engine.ticket_report(ticket_id, {"kind": "failed", "error": str(e)})
            return

        try:
            await self._get_reflector().finalize(ticket_id, output, trigger_id=trigger_id)
        except Exception as e:
            logger.error(f"EffectQueue · reflector failed · ticket={ticket_id}: {e}")
            engine.ticket_report(ticket_id, {"kind": "failed", "error": str(e)})
