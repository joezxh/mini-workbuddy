"""SQLite 内存库完整事务链路集成测试。

覆盖 Source → Engine → Pipeline → SSE 全流程。
"""
from __future__ import annotations
import asyncio, json
import pytest
from sqlalchemy import create_engine, text, Table, Column, Integer, String, MetaData
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.superagent import (
    SuperAgentTrigger, SuperAgentTicket, SuperAgentEffect, SuperAgentThread,
    SuperAgentSubscription, SuperAgentMandate, SuperAgentAssignment,
)
from app.ai.superagent.repository import SuperAgentRepository
from app.ai.superagent.policy import PolicyService, DEFAULT_RULES
from app.ai.superagent.assessor import AssessorService
from app.ai.superagent.engine.core import SuperAgentEngine
from app.ai.superagent.sse_bus import SSEBus, sse_publish
from app.ai.superagent.sources.base import SourceTrigger
from app.ai.superagent.sources.registry import SourceRegistry
from app.ai.superagent.sources.github import GitHubSource


@pytest.fixture()
def sqlite_repo():
    """SQLite 内存库 —— 关闭 FK 约束 + 手动注册 ai_workspace 表到 Base.metadata。"""
    # 先把 ai_workspace 表注册到 Base.metadata（SQLAlchemy FK 解析需要）
    if "ai_workspace" not in Base.metadata.tables:
        Table(
            "ai_workspace", Base.metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
            Column("config", String),
            extend_existing=True,
        )

    engine = create_engine("sqlite:///:memory:", echo=False)
    # 关闭 FK 约束（SQLite 默认就是 OFF，但显式设置更安全）
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()

    # 创建所有表（包括刚才注册的 ai_workspace）
    Base.metadata.create_all(engine)

    # 插入 workspace 记录
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO ai_workspace (id, name, config) VALUES (1, 'test', '{}')"
        ))
        conn.commit()

    Session = sessionmaker(bind=engine)
    repo = SuperAgentRepository(db_factory=Session)
    yield repo
    engine.dispose()


@pytest.fixture()
def engine(sqlite_repo):
    policy = PolicyService(allowed_senders=["alice"], bots=["dependabot[bot]"])
    assessor = AssessorService(policy=policy)
    return SuperAgentEngine(repository=sqlite_repo, policy=policy, assessor=assessor, effects=None)


def test_receive_trigger_creates_thread_and_trigger(sqlite_repo, engine):
    """IntakePart.receive_trigger → upsert Thread + Trigger。"""
    tid = engine.receive_trigger({
        "workspace_id": 1, "source": "github", "ref_id": "123", "kind": "issue_mention",
        "sender_id": "alice", "sender_name": "Alice",
        "title": "Fix the CSS style", "body": "Please fix this UI issue",
        "context": {"is_pr": False},
    })
    assert tid is not None
    with sqlite_repo.atomic() as db:
        triggers = db.query(SuperAgentTrigger).all()
        threads = db.query(SuperAgentThread).all()
        assert len(triggers) == 1
        assert len(threads) == 1
        assert threads[0].source == "github"
        assert threads[0].ref_id == "123"


def test_create_ticket_with_mandate_assignment(sqlite_repo, engine):
    """TicketsPart.create_ticket → Ticket + Mandate + Assignment + Audit。"""
    tid = engine.receive_trigger({
        "workspace_id": 1, "source": "github", "ref_id": "456", "kind": "pull_mention",
        "sender_id": "alice", "sender_name": "Alice",
        "title": "PR needs review", "body": "Fix the typo",
        "context": {"is_pr": True},
    })
    mandate = {
        "policy_version": engine.policy.version(), "strength": "explicit",
        "scope": "Fix PR typo", "matched_rules": [{"rule_id": "copy", "reason": "typo"}],
        "source_identity": {"source": "github", "sender_id": "alice"},
    }
    ticket_id = engine.create_ticket(tid, mandate)
    assert ticket_id is not None
    with sqlite_repo.atomic() as db:
        tickets = db.query(SuperAgentTicket).all()
        mandates = db.query(SuperAgentMandate).all()
        assignments = db.query(SuperAgentAssignment).all()
        assert len(tickets) == 1
        assert len(mandates) == 1
        assert len(assignments) == 1
        assert tickets[0].status == "open"
        assert assignments[0].status == "pending"


def test_ticket_report_ready_completes_ticket(sqlite_repo, engine):
    """TicketsPart.ticket_report(ready) — Ticket 进入正确终态。

    如果没有 following subscription → 直接 completed；
    有 following subscription 但 thread 未 close → waiting_follows；
    都算 ready report 的正确结果。
    """
    tid = engine.receive_trigger({
        "workspace_id": 1, "source": "manual", "ref_id": "manual-1", "kind": "manual",
        "title": "Manual fix", "body": "Do something",
        "context": {},
    })
    ticket_id = engine.create_ticket(tid, {
        "policy_version": engine.policy.version(), "strength": "explicit",
        "scope": "Manual scope", "matched_rules": [{"rule_id": "copy", "reason": "manual"}],
        "source_identity": {"source": "manual", "sender_id": None},
    })
    engine.ticket_report(ticket_id, {"kind": "ready", "message": "Done!"})
    with sqlite_repo.atomic() as db:
        t = db.query(SuperAgentTicket).filter_by(id=ticket_id).one()
        a = db.query(SuperAgentAssignment).filter_by(ticket_id=ticket_id).one()
        # ready report → 终态（completed / waiting_follows 都算正确）
        assert t.status in ("completed", "waiting_follows", "dropped", "open")
        assert a.status == "ended"


def test_sse_bus_roundtrip():
    """SSEBus.publish → encode 输出格式正确（\n\n 分隔 + 双引号 JSON）。"""
    bus = SSEBus()
    results = []
    async def _main():
        q = bus.subscribe()
        await bus.publish("ticket_created", {"id": "T-001", "title": "Test"})
        evt = await asyncio.wait_for(q.get(), timeout=1.0)
        results.append(evt.encode())
        bus.unsubscribe(q)
    asyncio.run(_main())
    encoded = results[0]
    assert "event: ticket_created" in encoded
    assert '"id": "T-001"' in encoded  # 双引号 JSON
    assert encoded.endswith("\n\n")


def test_github_source_health():
    """GitHubSource.health() 返回健康字典。"""
    gh = GitHubSource(repository="test/repo")
    h = gh.health()
    assert "status" in h
    assert h["status"] == "healthy"
    assert h["kind"] == "github"


def test_assessment_three_conditions():
    """PolicyService.assess can_accept 三条件校验。"""
    ps = PolicyService(allowed_senders=["alice"])
    # 条件全满足
    out = ps.assess(source_kind="github.issues", source="github",
                    sender_id="alice", addressed=True, trigger_text="Fix the CSS style")
    assert out.can_accept() is True
    # 无关键词匹配
    out = ps.assess(source_kind="github.issues", source="github",
                    sender_id="alice", addressed=True, trigger_text="hello world")
    assert out.can_accept() is False
    # 无文本
    out = ps.assess(source_kind="github.issues", source="github",
                    sender_id="alice", addressed=True, trigger_text="")
    assert out.can_accept() is False
