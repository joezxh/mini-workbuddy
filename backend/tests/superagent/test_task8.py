"""Task 8 单元测试 —— TR-8.1 瞬态重试 / TR-8.2 Assignment 状态机 / JobRegistry / handback 幂等。

不改动 policy.py / effects.py（归属另一 agent）；handback 测试参考
test_engine_transactions.py 的 MockRepository fixture 模式。
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.superagent.assessor import AssessorService
from app.ai.superagent.engine.core import SuperAgentEngine
from app.ai.superagent.executor.background import (
    COLLECT_WAIT_S, JobRegistry, collect_children,
)
from app.ai.superagent.executor.report import (
    ASSIGNMENT_TRANSITIONS, can_transition, next_assignment_status,
)
from app.ai.superagent.executor.transient import (
    TRANSIENT_ERRNOS, TRANSIENT_HTTP, retry_with_backoff,
)
from app.ai.superagent.policy import PolicyService


# ========= 测试辅助异常 =========

class ErrnoError(Exception):
    """携带 errno 的错误（模拟 ECONNRESET 等系统错误码）。"""

    def __init__(self, errno: str):
        super().__init__(errno)
        self.errno = errno


class HttpError(Exception):
    """携带 HTTP 状态码的错误。"""

    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


async def _run_retry(coro_factory, config=None) -> list[float]:
    """注入立即返回的 sleep，返回记录到的退避延迟序列。"""
    sleeps: list[float] = []

    async def _no_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    await retry_with_backoff(coro_factory, config=config, sleep=_no_sleep)
    return sleeps


# ========= TR-8.1：Transient 自动重试 =========

class TestTransientRetry:
    @pytest.mark.asyncio
    async def test_econnreset_retries_then_succeeds(self):
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ErrnoError("ECONNRESET")
            return "ok"

        sleeps = await _run_retry(flaky)
        assert calls["n"] == 3
        # 15s→30s 指数退避（含 0~5s 抖动）
        assert 15 <= sleeps[0] <= 20
        assert 30 <= sleeps[1] <= 35

    @pytest.mark.asyncio
    async def test_http_429_retries(self):
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise HttpError(429)
            return "done"

        sleeps = await _run_retry(flaky)
        assert calls["n"] == 2
        assert len(sleeps) == 1

    @pytest.mark.asyncio
    async def test_http_500_exhausts_after_3_attempts(self):
        calls = {"n": 0}

        async def always_500():
            calls["n"] += 1
            raise HttpError(500)

        with pytest.raises(HttpError):
            await _run_retry(always_500)
        assert calls["n"] == 3  # 重试 ×3 后耗尽

    @pytest.mark.asyncio
    async def test_non_transient_raises_immediately(self):
        calls = {"n": 0}

        async def bad():
            calls["n"] += 1
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await _run_retry(bad)
        assert calls["n"] == 1  # 非瞬态不重试

    def test_transient_code_table_covers_spec(self):
        assert {"ECONNRESET", "ECONNREFUSED", "ETIMEDOUT", "EAI_AGAIN"} <= TRANSIENT_ERRNOS
        assert {408, 429, 500, 502, 503, 504} <= TRANSIENT_HTTP


# ========= TR-8.2：Assignment 状态机 =========

class TestAssignmentStateMachine:
    def test_ready_to_ended(self):
        assert next_assignment_status("running", "ready") == "ended"
        assert can_transition("running", "ended")

    def test_failed_to_ended(self):
        assert next_assignment_status("running", "failed") == "ended"
        assert can_transition("running", "ended")

    def test_progress_to_running(self):
        assert next_assignment_status("pending", "progress") == "running"
        assert can_transition("pending", "running")

    def test_blocked_keeps_running(self):
        assert next_assignment_status("running", "blocked") == "running"

    def test_ended_is_terminal(self):
        for nxt in ("running", "pending", "ended"):
            assert not can_transition("ended", nxt)
        assert ASSIGNMENT_TRANSITIONS["ended"] == []

    def test_pending_cannot_jump_to_ended(self):
        assert not can_transition("pending", "ended")

    def test_running_to_pending_allowed(self):
        assert can_transition("running", "pending")

    def test_unknown_state_rejected(self):
        assert not can_transition("ghost", "running")
        assert can_transition("pending", "unknown_target") is False


# ========= TR-8.2 附属：JobRegistry + collect_children =========

class FakeProc:
    """假 asyncio subprocess —— terminate 后立即退出。"""

    def __init__(self) -> None:
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        while self.returncode is None:
            await asyncio.sleep(0.01)
        return self.returncode


class StubbornProc(FakeProc):
    """terminate 无效 —— 只有 kill 能终止。"""

    def terminate(self) -> None:
        self.terminated = True  # 不设置 returncode


class BrokenProc:
    """所有方法抛异常 —— kill_all 必须吞掉。"""

    returncode = None

    def terminate(self) -> None:
        raise RuntimeError("nope")

    def kill(self) -> None:
        raise RuntimeError("nope")

    async def wait(self) -> int:  # pragma: no cover - 不会被等到
        raise RuntimeError("nope")


class TestJobRegistry:
    def test_collect_wait_constant(self):
        assert COLLECT_WAIT_S == 1800  # 30min hard limit

    @pytest.mark.asyncio
    async def test_register_and_list_snapshot(self):
        registry = JobRegistry()
        registry.register(FakeProc(), "gh-poll")
        registry.register(FakeProc(), "lark-listen")
        jobs = registry.list()
        assert [j.name for j in jobs] == ["gh-poll", "lark-listen"]
        assert len(registry) == 2

    @pytest.mark.asyncio
    async def test_kill_all_terminates_processes(self):
        registry = JobRegistry()
        p1, p2 = FakeProc(), StubbornProc()
        registry.register(p1, "gentle")
        registry.register(p2, "stubborn")
        await registry.kill_all(wait_s=0.3)
        assert p1.terminated and p1.returncode is not None
        assert p2.killed
        assert len(registry) == 0  # kill_all 后清空

    @pytest.mark.asyncio
    async def test_kill_all_cancels_tasks(self):
        registry = JobRegistry()
        task = asyncio.create_task(asyncio.sleep(3600))
        registry.register(task, "loop")
        await registry.kill_all(wait_s=0.3)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_kill_all_never_raises(self):
        registry = JobRegistry()
        registry.register(BrokenProc(), "broken")
        await registry.kill_all(wait_s=0.05)  # 不抛异常即通过

    @pytest.mark.asyncio
    async def test_kill_all_skips_finished_process(self):
        registry = JobRegistry()
        p = FakeProc()
        p.terminate()  # returncode 已设置 → 已退出
        registry.register(p, "finished")
        await registry.kill_all(wait_s=0.05)
        assert p.killed is False

    @pytest.mark.asyncio
    async def test_collect_children_all_done_returns_true(self):
        registry = JobRegistry()
        finished = FakeProc()
        finished.terminate()
        registry.register(finished, "finished")
        registry.register(asyncio.create_task(asyncio.sleep(0)), "quick")
        assert await collect_children(registry, timeout_s=2) is True

    @pytest.mark.asyncio
    async def test_collect_children_timeout_kills_and_returns_false(self):
        registry = JobRegistry()
        stuck = StubbornProc()
        registry.register(stuck, "stuck-proc")
        task = asyncio.create_task(asyncio.sleep(3600))
        registry.register(task, "stuck-task")
        ok = await collect_children(registry, timeout_s=0.05, kill_wait_s=0.3)
        assert ok is False
        assert stuck.killed
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_collect_children_empty_registry(self):
        assert await collect_children(JobRegistry(), timeout_s=0.05) is True


# ========= TR-8.3：handback 幂等 =========

class _FakeQuery:
    """最小 SQLAlchemy query 链 mock —— filter 提取 (attr, value) 等值条件。"""

    def __init__(self, first_fn=None):
        self._first_fn = first_fn
        self._criteria: list = []

    def filter(self, *criteria):
        self._criteria.extend(criteria)
        return self

    def first(self):
        if self._first_fn is None:
            return None
        eqs: list[tuple[str, object]] = []
        for c in self._criteria:
            try:
                eqs.append((c.left.key, c.right.value))
            except AttributeError:
                continue
        return self._first_fn(eqs)

    def update(self, values=None, **kwargs):
        return 1


class HandbackDB:
    """支持 query 链的 db mock —— handback audit 记录由 repo.logs 推导。"""

    def __init__(self, repo: "HandbackRepository"):
        self._repo = repo

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def query(self, model):
        if model.__name__ == "SuperAgentAuditLog":
            def first_fn(eqs):
                rows = [l for l in self._repo.logs if l.get("action") == "handback"]
                for attr, val in eqs:
                    if attr in ("ticket_id", "trigger_id"):
                        rows = [r for r in rows if r.get(attr) == val]
                return rows[0] if rows else None
            return _FakeQuery(first_fn)
        return _FakeQuery()  # SuperAgentTrigger 等 → first()=None，update()=1


class HandbackRepository:
    """最小 Repository mock —— 参考 test_engine_transactions.MockRepository 模式。"""

    def __init__(self):
        self.db = HandbackDB(self)
        self.logs: list[dict] = []

    @contextmanager
    def atomic(self):
        yield self.db
        self.db.commit()

    def get_ticket(self, db, ticket_id):
        t = MagicMock()
        t.id = ticket_id
        t.workspace_id = 1
        return t

    def log_action(self, db, **kwargs):
        self.logs.append(kwargs)
        return MagicMock()


def _make_engine() -> tuple[SuperAgentEngine, HandbackRepository]:
    repo = HandbackRepository()
    policy = PolicyService()
    assessor = AssessorService(policy=policy)
    engine = SuperAgentEngine(
        repository=repo, policy=policy, assessor=assessor, effects=AsyncMock(),
    )
    return engine, repo


class TestHandbackIdempotent:
    @pytest.mark.asyncio
    async def test_second_handback_same_ticket_trigger_returns_false(self):
        engine, repo = _make_engine()
        first = engine.handback("ticket-1", "trigger-1", "policy changed")
        assert first is True
        assert any(l["action"] == "handback" for l in repo.logs)
        await asyncio.sleep(0)  # 让 create_task 的 enqueue 协程跑完

        second = engine.handback("ticket-1", "trigger-1", "again")
        assert second is False
        # 每 Ticket×Trigger 只记录一次 handback
        assert len([l for l in repo.logs if l["action"] == "handback"]) == 1

    @pytest.mark.asyncio
    async def test_handback_other_trigger_allowed(self):
        engine, _repo = _make_engine()
        assert engine.handback("ticket-1", "trigger-1", "r1") is True
        assert engine.handback("ticket-1", "trigger-2", "r2") is True

    @pytest.mark.asyncio
    async def test_handback_missing_ticket_returns_false(self):
        engine, repo = _make_engine()
        repo.get_ticket = lambda db, ticket_id: None
        assert engine.handback("ghost", "trigger-1", "r") is False
