"""SuperAgentEngine 事务单元测试 —— 使用 mock Repository。"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager

from app.ai.superagent.engine.core import SuperAgentEngine
from app.ai.superagent.policy import PolicyService
from app.ai.superagent.assessor import AssessorService
from app.ai.superagent.executor.report import (
    WorkerReport, ReportKind, next_assignment_status,
    ASSIGNMENT_TRANSITIONS, TICKET_TRANSITIONS,
)
from app.ai.superagent.executor.transient import (
    is_transient_error, RetryConfig,
)


# ========= Repository mock =========

class MockDB:
    """模拟 SQLAlchemy Session。"""

    def __init__(self):
        self._committed = False
        self._rolled_back = False

    def commit(self):
        self._committed = True

    def rollback(self):
        self._rolled_back = True

    def close(self):
        pass


class MockRepository:
    """模拟 SuperAgentRepository，实现 atomic 上下文管理器。"""

    def __init__(self):
        self.db = MockDB()
        self.triggers_created = []
        self.tickets_created = []
        self.mandates_created = []
        self.assignments_created = []
        self.subscriptions_upserted = []
        self.logs = []

    @contextmanager
    def atomic(self):
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def upsert_thread(self, db, **kwargs):
        mock_thread = MagicMock()
        mock_thread.id = kwargs.get("id", f"{kwargs.get('source', 'test')}:{kwargs.get('ref_id', 'ref')}")
        return mock_thread

    def create_trigger(self, db, **kwargs):
        obj = MagicMock()
        obj.id = kwargs.get("id", "trigger_id")
        obj.workspace_id = kwargs.get("workspace_id", 1)
        self.triggers_created.append(kwargs)
        return obj

    def get_trigger(self, db, trigger_id):
        t = MagicMock()
        t.id = trigger_id
        t.workspace_id = 1
        t.source = "manual"
        t.sender_id = None
        t.thread_id = f"manual:{trigger_id}"
        t.title = "Test trigger"
        t.body = ""
        return t

    def create_ticket(self, db, **kwargs):
        obj = MagicMock()
        obj.id = kwargs.get("id", "ticket_id")
        obj.workspace_id = kwargs.get("workspace_id", 1)
        self.tickets_created.append(kwargs)
        return obj

    def get_ticket(self, db, ticket_id):
        t = MagicMock()
        t.id = ticket_id
        t.workspace_id = 1
        return t

    def update_ticket(self, db, ticket_id, **updates):
        pass

    def create_mandate(self, db, **kwargs):
        obj = MagicMock()
        obj.id = kwargs.get("id", "mandate_id")
        self.mandates_created.append(kwargs)
        return obj

    def get_mandate(self, db, ticket_id):
        m = MagicMock()
        m.ticket_id = ticket_id
        return m

    def create_assignment(self, db, **kwargs):
        obj = MagicMock()
        obj.id = kwargs.get("id", "assignment_id")
        obj.ticket_id = kwargs.get("ticket_id")
        obj.status = kwargs.get("status", "pending")
        self.assignments_created.append(kwargs)
        return obj

    def get_assignment(self, db, ticket_id):
        a = MagicMock()
        a.ticket_id = ticket_id
        a.status = "pending"
        return a

    def update_assignment(self, db, ticket_id, **updates):
        pass

    def upsert_subscription(self, db, **kwargs):
        self.subscriptions_upserted.append(kwargs)
        return MagicMock()

    def list_subscriptions(self, db, *, ticket_id=None, thread_id=None):
        return []

    def log_action(self, db, **kwargs):
        self.logs.append(kwargs)
        return MagicMock()


@pytest.fixture
def engine():
    repo = MockRepository()
    policy = PolicyService()
    assessor = AssessorService(policy=policy)
    return SuperAgentEngine(
        repository=repo, policy=policy, assessor=assessor, effects=None,
    )


# ========= Engine 事务测试 =========

class TestEngineReceiveTrigger:
    def test_receive_trigger_creates_trigger_and_thread(self, engine):
        trigger = {
            "workspace_id": 1,
            "source": "github",
            "ref_id": "issue#42",
            "kind": "issue_mention",
            "title": "Fix a typo",
            "body": "There's a typo in the login button",
            "sender_id": "alice",
        }
        trigger_id = engine.receive_trigger(trigger)
        assert trigger_id is not None
        assert len(engine.repository.triggers_created) == 1
        assert len(engine.repository.logs) >= 1

    def test_receive_trigger_audit_log_written(self, engine):
        trigger = {
            "workspace_id": 1,
            "source": "feishu",
            "ref_id": "chat:msg_123",
            "kind": "dm",
            "title": "请修复样式",
            "body": "按钮样式不对",
            "sender_id": "ou_abc",
        }
        engine.receive_trigger(trigger)
        logs = [l for l in engine.repository.logs if l["action"] == "receive_trigger"]
        assert len(logs) == 1


class TestEngineCreateTicket:
    def test_create_ticket_creates_all_entities(self, engine):
        ticket_id = engine.create_ticket(
            trigger_id="trigger_123",
            mandate={
                "title": "修复文案 typo",
                "strength": "explicit",
                "matched_rules": [{"rule_id": "copy", "reason": "typo 命中"}],
                "intent_evidence": "sender 明确要求修复",
            },
        )
        assert ticket_id is not None
        # 应创建 Ticket + Mandate + Assignment
        assert len(engine.repository.tickets_created) >= 1
        assert len(engine.repository.mandates_created) >= 1
        assert len(engine.repository.assignments_created) >= 1
        # Subscription 应 upsert
        assert len(engine.repository.subscriptions_upserted) >= 1

    def test_create_ticket_assignment_status_pending(self, engine):
        engine.create_ticket(
            trigger_id="trigger_123",
            mandate={"matched_rules": [{"rule_id": "x"}], "intent_evidence": "e"},
        )
        assert len(engine.repository.assignments_created) >= 1
        assert engine.repository.assignments_created[0]["status"] == "pending"


class TestEngineLaunch:
    def test_launch_returns_session_name(self, engine):
        session_name = engine.launch("ticket_123")
        assert session_name.startswith("worker-")
        assert len(session_name) > len("worker-")


class TestEngineTicketReport:
    def test_ticket_report_progress(self, engine):
        engine.ticket_report("ticket_123", {
            "kind": "progress", "message": "正在执行",
        })
        logs = [l for l in engine.repository.logs if l["action"] == "ticket_report"]
        assert len(logs) >= 1

    def test_ticket_report_ready(self, engine):
        engine.ticket_report("ticket_123", {
            "kind": "ready", "message": "完成修复",
        })
        logs = [l for l in engine.repository.logs if l["action"] == "ticket_report"]
        assert len(logs) >= 1

    def test_ticket_report_blocked(self, engine):
        engine.ticket_report("ticket_123", {
            "kind": "blocked", "message": "需要确认设计方案",
            "awaiting_human": True,
        })
        logs = [l for l in engine.repository.logs if l["action"] == "ticket_report"]
        assert len(logs) >= 1


# ========= WorkerReport 状态机测试 =========

class TestWorkerReportTransitions:
    def test_assignment_transition_progress_to_running(self):
        new_status = next_assignment_status("pending", "progress")
        assert new_status == "running"

    def test_assignment_transition_ready_to_ended(self):
        new_status = next_assignment_status("running", "ready")
        assert new_status == "ended"

    def test_assignment_transition_failed_to_ended(self):
        new_status = next_assignment_status("running", "failed")
        assert new_status == "ended"

    def test_assignment_transition_blocked_keeps_running(self):
        new_status = next_assignment_status("running", "blocked")
        assert new_status == "running"

    def test_assignment_valid_transitions_defined(self):
        for status in ("pending", "running", "ended"):
            assert status in ASSIGNMENT_TRANSITIONS

    def test_ticket_transitions_defined(self):
        for status in ("open", "working", "completed", "failed", "dropped"):
            assert status in TICKET_TRANSITIONS


class TestWorkerReportDataclass:
    def test_terminal_ready(self):
        r = WorkerReport(kind="ready", message="done")
        assert r.terminal
        assert not r.is_blocked

    def test_terminal_dropped(self):
        r = WorkerReport(kind="dropped", message="skip")
        assert r.terminal

    def test_blocked_is_blocked(self):
        r = WorkerReport(kind="blocked", message="need HITL", awaiting_human=True)
        assert r.is_blocked
        assert not r.terminal

    def test_failed_not_terminal_for_retry(self):
        r = WorkerReport(kind="failed", message="network error", transient=True)
        assert not r.terminal


# ========= Transient Retry 测试 =========

class TestTransientRetry:
    def test_transient_timeout(self):
        from asyncio import TimeoutError as AsyncTimeout
        assert is_transient_error(AsyncTimeout())

    def test_transient_connection_reset(self):
        from socket import error as SocketError
        err = ConnectionResetError()
        assert is_transient_error(err)

    def test_http_500_is_transient(self):
        class MockHTTPError(Exception):
            def __init__(self):
                self.status_code = 500
        assert is_transient_error(MockHTTPError())

    def test_http_429_is_transient(self):
        class MockHTTPError(Exception):
            def __init__(self):
                self.status_code = 429
        assert is_transient_error(MockHTTPError())

    def test_http_400_not_transient(self):
        class MockHTTPError(Exception):
            def __init__(self):
                self.status_code = 400
        assert not is_transient_error(MockHTTPError())

    def test_value_error_not_transient(self):
        assert not is_transient_error(ValueError("bad input"))

    def test_retry_config_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.base_delay == 15.0
        assert cfg.max_delay == 120.0
