"""PipelineExecutor + Effect handler 接线测试。

- Task 1.5 / TR-1.4：PipelineExecutor 骨架（实例化 / start-stop / resume 幂等 / enqueue 落库）
- Task 3.6 / TR-3.2 / TR-3.3：崩溃恢复 + 6 kind handler 真实管道接线
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text, Table, Column, Integer, String
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.superagent import (
    SuperAgentAssignment, SuperAgentEffect, SuperAgentThread, SuperAgentTicket,
)
from app.ai.superagent.repository import SuperAgentRepository
from app.ai.superagent.policy import PolicyService
from app.ai.superagent.assessor import AssessorService
from app.ai.superagent.engine.core import SuperAgentEngine
from app.ai.superagent.effects import EffectQueue
from app.ai.superagent.executor.session import WorkerSession
from app.ai.superagent.pipeline import PipelineExecutor, RESUMABLE_TICKET_STATUSES
from app.ai.superagent.reflector import ReflectorService


# ========= Task 1.5: Repository mock =========

class FakeTicket:
    def __init__(self, id: str, status: str = "open"):
        self.id = id
        self.status = status


class FakeAssignment:
    def __init__(self, status: str = "pending"):
        self.status = status


class MockRepository:
    """模拟 SuperAgentRepository —— 可配置 open Ticket / Assignment。"""

    def __init__(self):
        self.tickets: list[FakeTicket] = []
        self.assignments: dict[str, FakeAssignment] = {}

    @contextmanager
    def atomic(self):
        yield MagicMock()
        # no-op commit

    def list_tickets(self, db, *, workspace_id, status=None, limit=50):
        return [t for t in self.tickets if t.status == status][:limit]

    def get_assignment(self, db, ticket_id):
        return self.assignments.get(ticket_id)


@pytest.fixture
def mock_repo():
    return MockRepository()


@pytest.fixture
def queue(mock_repo):
    q = EffectQueue(repo=mock_repo)
    with patch.object(q, "enqueue", new=MagicMock()) as mocked:
        # enqueue 是 async —— 换成可 await 的 stub
        async def _fake_enqueue(**kwargs):
            mocked(**kwargs)
            return "e1"
        q.enqueue = _fake_enqueue  # type: ignore[method-assign]
        yield q


# ========= Task 3: SQLite 内存库 fixtures =========

@pytest.fixture()
def sqlite_repo():
    """SQLite 内存库 —— 关闭 FK 约束 + 注册 ai_workspace 表（同 test_engine_full_flow）。"""
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


@pytest.fixture()
def engine(sqlite_repo):
    policy = PolicyService(allowed_senders=["alice"], bots=["dependabot[bot]"])
    assessor = AssessorService(policy=policy)
    return SuperAgentEngine(repository=sqlite_repo, policy=policy, assessor=assessor, effects=None)


@pytest.fixture()
def fresh_sse_bus():
    """每个用到 SSEBus 的测试独立单例（避免 asyncio.Lock 跨 loop 绑定）。"""
    from app.ai.superagent.sse_bus import SSEBus
    SSEBus._instance = None
    yield SSEBus.instance()
    SSEBus._instance = None


def _make_trigger(sa_engine: SuperAgentEngine, ref_id: str) -> str:
    """创建一个 trigger（effects=None 不入队），返回 trigger_id。"""
    return sa_engine.receive_trigger({
        "workspace_id": 1, "source": "github", "ref_id": ref_id, "kind": "issue_mention",
        "sender_id": "alice", "sender_name": "Alice",
        "title": "Fix nav bar", "body": "The nav bar overlaps the hero section",
        "context": {},
    })


# ========= TR-1.4: PipelineExecutor 实例化无异常 =========

def test_pipeline_executor_instantiation(mock_repo):
    executor = PipelineExecutor(
        repo=mock_repo, engine=MagicMock(), queue=MagicMock(),
        registry=MagicMock(), workspace_id=1,
    )
    assert executor.repo is mock_repo
    assert executor.workspace_id == 1
    assert executor._started is False


def test_resume_without_queue_is_noop(mock_repo):
    executor = PipelineExecutor(repo=mock_repo, queue=None)
    assert executor._resumed == set()


# ========= resume(): 未终态 Ticket → 重新入队 launch effect =========

@pytest.mark.asyncio
async def test_resume_reenqueues_launch_for_open_ticket(mock_repo, queue):
    mock_repo.tickets = [FakeTicket("t_open", status="open")]
    mock_repo.assignments["t_open"] = FakeAssignment(status="pending")

    executor = PipelineExecutor(repo=mock_repo, queue=queue, workspace_id=1)
    resumed = await executor.resume()

    assert resumed == 1
    assert executor._resumed == {"t_open"}


@pytest.mark.asyncio
async def test_resume_recovers_running_assignment(mock_repo, queue):
    """TR-3.3：崩溃时 Worker 已 launch（assignment running）→ 重启后同样恢复。"""
    mock_repo.tickets = [FakeTicket("t_mid", status="working")]
    mock_repo.assignments["t_mid"] = FakeAssignment(status="running")

    executor = PipelineExecutor(repo=mock_repo, queue=queue, workspace_id=1)
    resumed = await executor.resume()

    assert resumed == 1
    assert executor._resumed == {"t_mid"}


@pytest.mark.asyncio
async def test_resume_is_idempotent(mock_repo, queue):
    """同一 Ticket 二次 resume 不重复入队（main.py start() 后再 resume() 的场景）。"""
    mock_repo.tickets = [FakeTicket("t1", status="working")]
    mock_repo.assignments["t1"] = FakeAssignment(status="pending")

    executor = PipelineExecutor(repo=mock_repo, queue=queue, workspace_id=1)
    first = await executor.resume()
    second = await executor.resume()

    assert (first, second) == (1, 0)


@pytest.mark.asyncio
async def test_start_and_stop_lifecycle(mock_repo):
    """start() 启动 queue/registry，stop() 幂等停止。"""
    queue = EffectQueue(repo=mock_repo)
    registry = MagicMock()
    registry.start_all_polling = MagicMock()
    registry.stop_all_polling = MagicMock()
    import asyncio

    async def _noop_polling(ws, engine=None):
        return None

    async def _noop_stop():
        return None

    registry.start_all_polling = _noop_polling
    registry.stop_all_polling = _noop_stop

    executor = PipelineExecutor(repo=mock_repo, queue=queue, registry=registry)
    await executor.start()
    assert executor._started is True
    assert queue._task is not None

    await executor.stop()
    assert executor._started is False
    assert queue._task is None

    await executor.stop()  # 幂等


# ========= TR-1.4: EffectQueue.enqueue() 写 SQLite 成功 =========

def test_enqueue_writes_sqlite(tmp_path):
    """真实 SQLite 落库验证 —— enqueue 后 sa_effect 有记录。"""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.db.database import Base
    from app.models.superagent import SuperAgentEffect

    engine = create_engine(f"sqlite:///{tmp_path/'effect.db'}")
    SuperAgentEffect.__table__.create(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    repo = SuperAgentRepository(db_factory=Session)
    queue = EffectQueue(repo=repo)

    import asyncio
    eid = asyncio.run(queue.enqueue(
        workspace_id=1, kind="launch", ticket_id="t1", payload={"k": "v"},
    ))

    with Session() as db:
        rows = list(db.execute(select(SuperAgentEffect)).scalars())
    assert len(rows) == 1
    assert rows[0].id == eid
    assert rows[0].kind == "launch"
    assert rows[0].status == "pending"
    assert rows[0].seq == 1
    assert rows[0].payload == {"k": "v"}
    engine.dispose()


def test_resumable_statuses():
    for status in ("open", "working", "waiting_hitl", "waiting_person"):
        assert status in RESUMABLE_TICKET_STATUSES


# ========= TR-3.3 崩溃恢复（真实 SQLite）=========

@pytest.mark.asyncio
async def test_resume_reenqueues_launch_for_open_tickets(sqlite_repo, engine):
    """resume()：open Ticket 重新入队 launch effect；已终态（failed）不恢复。"""
    tid = _make_trigger(engine, "resume-1")
    ticket_id = engine.create_ticket(tid, {"title": "Fix nav", "strength": "explicit"})

    tid2 = _make_trigger(engine, "resume-2")
    failed_id = engine.create_ticket(tid2, {"title": "Already failed", "strength": "explicit"})
    with sqlite_repo.atomic() as db:
        sqlite_repo.update_ticket(db, failed_id, status="failed")

    queue = EffectQueue(repo=sqlite_repo, engine=engine)
    pipeline = PipelineExecutor(
        repo=sqlite_repo, engine=engine, queue=queue, registry=MagicMock(),
    )
    recovered = await pipeline.resume()
    assert recovered == 1

    with sqlite_repo.atomic() as db:
        effects = db.query(SuperAgentEffect).filter(
            SuperAgentEffect.kind == "launch",
            SuperAgentEffect.ticket_id == ticket_id,
        ).all()
        assert len(effects) == 1
        assert effects[0].status == "pending"
        assert effects[0].payload.get("resumed") is True
        assert effects[0].payload.get("ticket_id") == ticket_id

    # 幂等：再次 resume 不重复入队
    assert await pipeline.resume() == 0


# ========= handler 接线 =========

@pytest.mark.asyncio
async def test_handle_assessment_calls_engine_decide(sqlite_repo, engine, monkeypatch, fresh_sse_bus):
    """assessment effect → engine.decide(thread_id) 被调用。"""
    _make_trigger(engine, "assess-1")
    thread_id = "github:assess-1"

    called: dict = {}

    def fake_decide(tid: str) -> dict:
        called["thread_id"] = tid
        return {"accepted": True}

    monkeypatch.setattr(engine.evals, "decide", fake_decide)

    q = EffectQueue(repo=sqlite_repo, engine=engine)
    result = await q._handle_assessment({"thread_id": thread_id}, MagicMock(seq=1, ticket_id=None))

    assert called["thread_id"] == thread_id
    assert result["ok"] is True
    assert result["decide"] == {"accepted": True}


@pytest.mark.asyncio
async def test_handle_launch_creates_ticket_and_reports_ready(sqlite_repo, engine, monkeypatch, fresh_sse_bus):
    """launch effect → create_ticket + launch + Worker → reflector pass → ready report。"""
    tid = _make_trigger(engine, "launch-1")
    thread_id = "github:launch-1"
    # 关闭订阅 Thread → ready report 后 Ticket 直接 completed
    with sqlite_repo.atomic() as db:
        db.query(SuperAgentThread).filter(
            SuperAgentThread.id == thread_id
        ).update({"status": "closed"})

    async def fake_run(self, task, tools=None):
        return "done: nav bar fixed and verified"

    monkeypatch.setattr(WorkerSession, "run", fake_run)

    q = EffectQueue(repo=sqlite_repo, engine=engine)
    result = await q._handle_launch(
        {"trigger_id": tid, "thread_id": thread_id}, MagicMock(seq=1, ticket_id=None),
    )
    assert result["ok"] is True
    ticket_id = result["ticket_id"]

    # 等待后台 worker 任务完成
    await asyncio.gather(*list(q._worker_tasks))
    await asyncio.sleep(0.05)  # flush SSE 任务

    with sqlite_repo.atomic() as db:
        ticket = sqlite_repo.get_ticket(db, ticket_id)
        assignment = sqlite_repo.get_assignment(db, ticket_id=ticket_id)
        assert ticket.status == "completed"
        assert assignment.status == "ended"
        assert assignment.final_report.get("kind") == "ready"
        assert assignment.final_report["reflect"]["completed"] is True


@pytest.mark.asyncio
async def test_handle_launch_skips_duplicate_ticket(sqlite_repo, engine, monkeypatch, fresh_sse_bus):
    """同一 trigger 已有 ticket → 跳过 create，复用现有 ticket。"""
    tid = _make_trigger(engine, "dup-1")
    existing_id = engine.create_ticket(tid, {"title": "Existing", "strength": "explicit"})

    async def fake_run(self, task, tools=None):
        return "done: work completed fully"

    monkeypatch.setattr(WorkerSession, "run", fake_run)

    q = EffectQueue(repo=sqlite_repo, engine=engine)
    result = await q._handle_launch({"trigger_id": tid}, MagicMock(seq=2, ticket_id=None))
    await asyncio.gather(*list(q._worker_tasks))
    await asyncio.sleep(0.05)

    assert result["ticket_id"] == existing_id
    with sqlite_repo.atomic() as db:
        assert db.query(SuperAgentTicket).count() == 1


@pytest.mark.asyncio
async def test_outbox_handlers_dispatch(sqlite_repo, fresh_sse_bus):
    """delivery/notice/reply handler → OutboxService 对应方法 → SSE 事件。"""
    from app.ai.superagent.outbox import OutboxService

    outbox = OutboxService()
    q = EffectQueue(repo=sqlite_repo, outbox=outbox)

    r1 = await q._handle_delivery(
        {"ticket_id": "t1", "message": "result msg"}, MagicMock(seq=1, ticket_id=None),
    )
    r2 = await q._handle_notice(
        {"ticket_id": "t1", "message": "need attention"}, MagicMock(seq=1, ticket_id=None),
    )
    r3 = await q._handle_reply(
        {"ticket_id": "t1", "message": "reply msg"}, MagicMock(seq=1, ticket_id=None),
    )
    assert all(r["ok"] for r in (r1, r2, r3))

    history = {e.event: e.data for e in fresh_sse_bus.replay_history(limit=50)}
    assert history["outbox_result"]["message"] == "result msg"
    assert history["outbox_attention"]["message"] == "need attention"
    assert history["outbox_reply"]["message"] == "reply msg"


@pytest.mark.asyncio
async def test_outbox_feishu_channel(monkeypatch):
    """Outbox Feishu 通道：chat 解析失败 → False；lark-cli 成功 → True；失败退出码 → False。"""
    from app.ai.superagent.outbox import OutboxService

    # 1) 无目标群解析 → 不发起进程，直接 False
    ob_none = OutboxService()
    monkeypatch.setattr(ob_none, "_resolve_feishu_chat", lambda: None)
    assert await ob_none._send_feishu("t1", "hello", "outbox_result") is False

    # 2) 显式 default_chat_id + mock lark-cli 子进程成功 → True
    class _Proc:
        returncode = 0
        async def communicate(self):
            return (b'{"code":0}', b"")

    captured: dict = {}

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        return _Proc()

    ob = OutboxService(default_chat_id="oc_test_chat")
    monkeypatch.setattr("app.ai.superagent.outbox.asyncio.create_subprocess_exec", _fake_exec)
    assert await ob._send_feishu("t1", "hello", "outbox_result") is True
    args = list(captured["args"])
    assert "POST" in args and "/open-apis/im/v1/messages" in args
    body = args[args.index("--body") + 1]
    assert "oc_test_chat" in body and "hello" in body

    # 3) lark-cli 非零退出 → False
    class _FailProc:
        returncode = 1
        stderr = b"boom"
        async def communicate(self):
            return (b"", b"boom")

    async def _fail_exec(*args, **kwargs):
        return _FailProc()

    monkeypatch.setattr("app.ai.superagent.outbox.asyncio.create_subprocess_exec", _fail_exec)
    assert await ob._send_feishu("t1", "hello", "outbox_result") is False


# ========= Reflector 重试闭环（TR-3.2）=========

def test_reflector_heuristic_verify():
    """无 LLM 启发式：非空且无 stub 标记 → pass；空 / stub 标记 → fail。"""
    reflector = ReflectorService(repo=MagicMock(), engine=None)

    ok = reflector.verify("t1", "所有修改已完成并通过验证")
    assert ok.completed is True

    empty = reflector.verify("t1", "")
    assert empty.completed is False

    stub = reflector.verify("t1", "[stub-worker] ticket=t1 task=fix")
    assert stub.completed is False

    err = reflector.verify("t1", "[AgentScope error] boom")
    assert err.completed is False


@pytest.mark.asyncio
async def test_reflector_retries_then_failed(sqlite_repo, engine, fresh_sse_bus):
    """verify fail → re-enqueue launch ×max_retries → 超限 → ticket failed。"""
    tid = _make_trigger(engine, "retry-1")
    ticket_id = engine.create_ticket(tid, {"title": "Retry me", "strength": "explicit"})

    q = EffectQueue(repo=sqlite_repo, engine=engine)
    reflector = ReflectorService(repo=sqlite_repo, engine=engine, queue=q, max_retries=2)
    bad_output = "[stub-worker] ticket=x task=y"

    await reflector.finalize(ticket_id, bad_output, trigger_id=tid)  # retry 1
    await reflector.finalize(ticket_id, bad_output, trigger_id=tid)  # retry 2
    await reflector.finalize(ticket_id, bad_output, trigger_id=tid)  # 超限 → failed

    with sqlite_repo.atomic() as db:
        ticket = sqlite_repo.get_ticket(db, ticket_id)
        assert ticket.status == "failed"
        retries = db.query(SuperAgentEffect).filter(
            SuperAgentEffect.kind == "launch",
            SuperAgentEffect.ticket_id == ticket_id,
        ).count()
        assert retries == 2  # max_retries=2 次 re-enqueue


# ========= Sources（Task 3.7）=========

@pytest.mark.asyncio
async def test_http_and_manual_sources():
    """HTTPSource / ManualSource：submit → poll 取出 → 队列清空。"""
    from app.ai.superagent.sources.base import SourceTrigger
    from app.ai.superagent.sources.http_source import HTTPSource
    from app.ai.superagent.sources.manual_source import ManualSource

    http = HTTPSource()
    assert http.is_enabled() is True
    assert http.health()["status"] == "healthy"
    http.submit(SourceTrigger(source="http", ref_id="r1", kind="http", workspace_id=1))
    triggers, cursor = await http.poll_once(1, None)
    assert len(triggers) == 1 and triggers[0].ref_id == "r1"
    assert cursor is not None
    again, _ = await http.poll_once(1, cursor)
    assert again == []

    manual = ManualSource()
    assert manual.is_enabled() is True
    manual.submit(SourceTrigger(source="manual", ref_id="m1", kind="manual"))
    mtriggers, _ = await manual.poll_once(1, None)
    assert len(mtriggers) == 1 and mtriggers[0].ref_id == "m1"
