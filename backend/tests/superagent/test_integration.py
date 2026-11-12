"""Task 5.2 / 5.3 集成测试 —— 端到端 Pipeline 全链 + SSE 推送 + 审计 + 健康检查。

- TR-5.2：receive_trigger → assessment(decide accept) → launch → Worker(stub) →
  Reflector(pass) → ticket_report ready → Ticket COMPLETED；
  SSE：monkeypatch sse_bus.sse_publish 收集事件，断言 ticket_created / ticket_completed。
- TR-5.3：每次 Engine 事务后 sa_audit_log 有新记录；/health module_status 覆盖全模块。
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text, Table, Column, Integer, String
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.superagent import (
    SuperAgentAssignment, SuperAgentAuditLog, SuperAgentEffect,
    SuperAgentTicket, SuperAgentThread,
)
from app.ai.superagent.repository import SuperAgentRepository
from app.ai.superagent.policy import PolicyService, AdmissionRule
from app.ai.superagent.assessor import AssessorService
from app.ai.superagent.engine.core import SuperAgentEngine
from app.ai.superagent.effects import EffectQueue
from app.ai.superagent.executor.session import WorkerSession


# ========= fixtures（与 test_pipeline / test_engine_full_flow 同款 SQLite 内存库）=========

@pytest.fixture()
def sqlite_repo():
    """SQLite 内存库 —— 关闭 FK 约束 + 注册 ai_workspace 表。"""
    if "ai_workspace" not in Base.metadata.tables:
        Table(
            "ai_workspace", Base.metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
            Column("config", String),
            extend_existing=True,
        )

    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO ai_workspace (id, name, config) VALUES (1, 'test', '{}')"
        ))
        conn.commit()

    Session = sessionmaker(bind=engine)
    repo = SuperAgentRepository(db_factory=Session)
    yield repo
    engine.dispose()


def _make_policy() -> PolicyService:
    """默认 AdmissionTable + github.github 显式放行。

    EvalsPart.decide 用 f"github.{thread.source}" 拼 source_kind ——
    source="github" 时即 "github.github"（默认表无此 kind，需显式放行）。
    """
    rows = PolicyService._default_admission() + [
        AdmissionRule("github.github", "listed_unaddressed", "explicit"),
        AdmissionRule("github.github", "unlisted_addressed", "explicit"),
    ]
    return PolicyService(
        allowed_senders=["alice"], bots=["dependabot[bot]"], admission_rows=rows,
    )


@pytest.fixture()
def engine(sqlite_repo):
    """默认 Policy —— decide 对 github.github 全 ignore（审计测试不触发 launch enqueue）。"""
    policy = PolicyService(allowed_senders=["alice"], bots=["dependabot[bot]"])
    assessor = AssessorService(policy=policy)
    return SuperAgentEngine(
        repository=sqlite_repo, policy=policy, assessor=assessor, effects=None,
    )


_TRIGGER = {
    "workspace_id": 1, "source": "github", "ref_id": "int-001", "kind": "issue_mention",
    "sender_id": "alice", "sender_name": "Alice",
    "title": "Fix the typo in login button", "body": "typo: 'Logn' should be 'Login'",
    "context": {},
}


def _ticket_row(repo, trigger_id: str) -> tuple[str, str] | None:
    """事务内快照 Ticket（atomic 结束后 ORM 对象 detach，不可再访问属性）。"""
    with repo.atomic() as db:
        t = (
            db.query(SuperAgentTicket)
            .filter(SuperAgentTicket.trigger_id == trigger_id)
            .first()
        )
        return (t.id, t.status) if t else None


async def _wait_until(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return predicate()


def _close_thread(repo: SuperAgentRepository, thread_id: str) -> None:
    with repo.atomic() as db:
        db.query(SuperAgentThread).filter(
            SuperAgentThread.id == thread_id
        ).update({"status": "closed"})


# ========= TR-5.2：端到端全链 =========

@pytest.mark.asyncio
async def test_e2e_trigger_assess_launch_worker_reflect_completed(
    sqlite_repo, monkeypatch,
):
    """全链：Trigger → decide(accept) → launch → Worker stub → Reflect pass → COMPLETED。"""
    # SSE 收集（core/effects 均为调用时 from ..sse_bus import sse_publish → 补丁生效）
    events: list[tuple[str, dict]] = []

    async def _collect(event, data=None):
        events.append((event, data or {}))

    monkeypatch.setattr("app.ai.superagent.sse_bus.sse_publish", _collect)

    # Worker stub —— 正常文本（非空且无 stub 标记 → Reflector 启发式 pass）
    async def fake_run(self, task, tools=None):
        return "done: typo fixed, login button text verified"

    monkeypatch.setattr(WorkerSession, "run", fake_run)

    policy = _make_policy()
    sa_engine = SuperAgentEngine(
        repository=sqlite_repo, policy=policy,
        assessor=AssessorService(policy=policy), effects=None,
    )
    queue = EffectQueue(repo=sqlite_repo, engine=sa_engine)
    sa_engine.effects = queue  # 与 main.py lifespan 同款接线

    # 入库 Trigger 并关闭订阅 Thread（ready report → followsDone 直接 completed）
    trigger_id = sa_engine.receive_trigger(dict(_TRIGGER))
    _close_thread(sqlite_repo, "github:int-001")

    await queue.start()
    try:
        def _completed() -> bool:
            row = _ticket_row(sqlite_repo, trigger_id)
            return row is not None and row[1] == "completed"

        done = await _wait_until(_completed)
        assert done, "Ticket 未在超时内 COMPLETED"
    finally:
        await queue.stop()

    ticket_id = _ticket_row(sqlite_repo, trigger_id)[0]
    with sqlite_repo.atomic() as db:
        ticket = sqlite_repo.get_ticket(db, ticket_id)
        assignment = sqlite_repo.get_assignment(db, ticket_id=ticket_id)
        assert ticket.status == "completed"
        assert ticket.completed_at is not None
        assert assignment.status == "ended"
        assert assignment.executor_session  # engine.launch 已绑定 session
        assert assignment.final_report.get("kind") == "ready"
        assert assignment.final_report["reflect"]["completed"] is True

        # sa_effect：assessment / launch 各有 done 记录（launch 无重试）
        by_kind: dict[str, list] = {}
        for e in db.query(SuperAgentEffect).all():
            by_kind.setdefault(e.kind, []).append(e)
        assert [e.status for e in by_kind["assessment"]] == ["done"]
        assert by_kind["assessment"][0].result["decide"]["accepted"] is True
        assert [e.status for e in by_kind["launch"]] == ["done"]
        assert by_kind["launch"][0].payload.get("trigger_id") == trigger_id

    # SSE：全链关键事件均发布（含 ticket_created / ticket_completed）
    names = [n for n, _ in events]
    for expected in (
        "trigger_received", "eval_decided", "ticket_created",
        "assignment_launched", "ticket_completed",
    ):
        assert expected in names, f"缺少 SSE 事件: {expected}"
    created = next(d for n, d in events if n == "ticket_created")
    completed = next(d for n, d in events if n == "ticket_completed")
    assert created["ticket_id"] == ticket_id
    assert completed["ticket_id"] == ticket_id


# ========= TR-5.3：审计日志 =========

def _audit_actions(repo: SuperAgentRepository) -> list[str]:
    with repo.atomic() as db:
        return [r.action for r in db.query(SuperAgentAuditLog).all()]


def test_audit_log_written_per_transaction(sqlite_repo, engine):
    """receive_trigger / decide / create_ticket / ticket_report 各事务写 sa_audit_log。"""
    counts: list[int] = []

    trigger_id = engine.receive_trigger(dict(_TRIGGER))
    actions = _audit_actions(sqlite_repo)
    counts.append(len(actions))
    assert actions.count("receive_trigger") == 1

    # 默认 Policy：github.github 无 admission 行 → ignore（不触发 launch enqueue）
    decision = engine.decide("github:int-001")
    assert decision["accepted"] is False
    actions = _audit_actions(sqlite_repo)
    counts.append(len(actions))
    assert actions.count("decide") == 1

    ticket_id = engine.create_ticket(trigger_id, {
        "title": "Fix the typo", "strength": "explicit",
        "scope": "Fix login button typo",
        "matched_rules": [{"rule_id": "copy", "reason": "typo"}],
        "intent_evidence": "alice explicitly requested",
    })
    actions = _audit_actions(sqlite_repo)
    counts.append(len(actions))
    assert actions.count("create_ticket") == 1

    _close_thread(sqlite_repo, "github:int-001")
    engine.ticket_report(ticket_id, {"kind": "ready", "message": "done"})
    actions = _audit_actions(sqlite_repo)
    counts.append(len(actions))
    assert actions.count("ticket_report") == 1
    assert actions.count("follows_done") == 1  # following Thread 已 closed

    # 每次事务后审计记录严格单调新增
    assert counts == sorted(counts) and len(set(counts)) == len(counts)

    with sqlite_repo.atomic() as db:
        assert sqlite_repo.get_ticket(db, ticket_id).status == "completed"


# ========= TR-5.3：健康检查 module_status =========

async def _call_health(state) -> dict:
    from app.routers.superagent import health
    import app.routers.superagent as sa_router

    saved = sa_router._engine_instance
    sa_router._engine_instance = None  # 隔离模块单例，避免跨测试污染
    try:
        request = SimpleNamespace(app=SimpleNamespace(state=state))
        return await health(request)
    finally:
        sa_router._engine_instance = saved


@pytest.mark.asyncio
async def test_health_defaults_to_unknown():
    """无 app.state 注入 → module_status 全 unknown（不造假值）。"""
    result = await _call_health(SimpleNamespace())
    assert result["status"] == "ok"
    assert result["component"] == "super-agent-engine"
    assert set(result["parts"]) == {"intake", "evals", "tickets", "assignments", "replies"}
    assert result["module_status"] == {
        "engine": "unknown",
        "outbox": "unknown",
        "effect_queue": "unknown",
        "registry": "unknown",
        "pipeline": "unknown",
    }


@pytest.mark.asyncio
async def test_health_module_status_reflects_runtime():
    """注入运行/停止态对象 → module_status 与真实运行一致。"""
    async def _hang():
        await asyncio.Event().wait()

    hanging = asyncio.create_task(_hang())
    try:
        running = await _call_health(SimpleNamespace(
            superagent_engine=SimpleNamespace(outbox=object()),
            superagent_effect_queue=SimpleNamespace(_task=hanging),
            superagent_pipeline=SimpleNamespace(_started=True),
            superagent_registry=SimpleNamespace(_poll_tasks={"http": hanging}),
        ))
        assert running["module_status"] == {
            "engine": "ok", "outbox": "ok",
            "effect_queue": "running", "registry": "running", "pipeline": "running",
        }

        stopped = await _call_health(SimpleNamespace(
            superagent_engine=SimpleNamespace(outbox=None),
            superagent_effect_queue=SimpleNamespace(_task=None),
            superagent_pipeline=SimpleNamespace(_started=False),
            superagent_registry=SimpleNamespace(_poll_tasks={}),
        ))
        assert stopped["module_status"] == {
            "engine": "ok", "outbox": "unknown",
            "effect_queue": "stopped", "registry": "stopped", "pipeline": "stopped",
        }
    finally:
        hanging.cancel()
        try:
            await hanging
        except asyncio.CancelledError:
            pass
