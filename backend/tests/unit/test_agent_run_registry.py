"""AgentRunRegistry 与执行取消路径单测（Fake 全家桶，无 DB）。"""
import asyncio
import time
import types

import pytest

import app.ai.skills.execution as exec_mod
from app.ai.skills.execution import SkillExecutionService, SkillEvent
from app.ai.events.registry import AgentRunRegistry, get_run_registry


class FakeBus:
    """替身 EventBus：仅记录发布的信封，避免真实 DB 落库。"""

    def __init__(self, event_service=None):
        self.published = []
        self.execution_id = None
        self.trace_id = None

    def publish(self, env):
        self.published.append(env)


class SlowAgent:
    def __init__(self, delay=0.2):
        self._delay = delay

    async def reply_stream(self, inputs):
        for _ in range(5):
            await asyncio.sleep(self._delay)
            yield types.SimpleNamespace()


@pytest.fixture(autouse=True)
def _clean_registry():
    """避免真实单例跨用例泄漏（execute 的 finally 正常会自清理）。"""
    yield
    get_run_registry().unregister("exec-cancel")
    get_run_registry().unregister("e1")
    get_run_registry().unregister("e2")


def test_registry_lifecycle_and_cancel():
    async def main():
        reg = AgentRunRegistry()
        async def forever():
            await asyncio.sleep(30)
        t = asyncio.create_task(forever())
        reg.register("e1", t)
        assert reg.get("e1").task is t
        assert reg.cancel("e1", reason="user_cancel") is True
        await asyncio.sleep(0)
        assert t.cancelled()
        reg.unregister("e1")
        assert reg.get("e1") is None
        assert reg.cancel("e1") is False      # 已反注册 → False
    asyncio.run(main())


def test_waiting_hitl_status_transition():
    async def main():
        reg = AgentRunRegistry()
        async def noop():
            await asyncio.sleep(30)
        t = asyncio.create_task(noop())
        h = reg.register("e2", t)
        reg.mark_waiting_hitl("e2", reply_id="r1")
        assert h.status == "waiting_hitl" and h.reply_id == "r1"
        reg.mark_running("e2")
        assert h.status == "running"
        t.cancel()
    asyncio.run(main())


def _patch(monkeypatch, svc, records):
    """全量 Fake 补丁；返回本用例内的 FakeBus 列表（供信封断言）。"""
    buses = []

    def _fake_bus(event_service=None):
        bus = FakeBus()
        buses.append(bus)
        return bus

    monkeypatch.setattr(svc, "_load_skill", lambda name: asyncio.sleep(0, result={
        "name": name, "description": "d", "markdown": "# m", "dir": None,
        "allowed_tools": None, "source": "test",
    }))
    monkeypatch.setattr(svc, "_build_toolkit", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **kw: "sys")
    monkeypatch.setattr(svc, "_build_model", lambda *a, **kw: object())
    monkeypatch.setattr(svc, "_create_agent", lambda *a, **kw: SlowAgent())
    monkeypatch.setattr(exec_mod, "record_execution_start", lambda db, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_done", lambda db, *a, **kw: None)
    monkeypatch.setattr(exec_mod, "record_execution_failed",
                        lambda db, eid, *a, **kw: records.append(kw))
    # Task 8 起执行主记录的 SessionLocal 在模块顶部导入，patch exec_mod 命名空间
    monkeypatch.setattr(exec_mod, "SessionLocal", lambda: None)
    monkeypatch.setattr(exec_mod, "EventBus", _fake_bus)
    monkeypatch.setattr(svc, "_record_metrics", lambda *a, **kw: None)
    return buses


def test_execute_cancel_emits_interrupt_events(monkeypatch):
    """运行中取消：SSE 输出中断提示，主记录 interrupt_reason=user_cancel。"""
    svc = SkillExecutionService(timeout=30)
    records = []
    _patch(monkeypatch, svc, records)

    async def run():
        async def canceller():
            for _ in range(200):
                h = get_run_registry().get("exec-cancel")
                if h is not None:
                    get_run_registry().cancel("exec-cancel", reason="user_cancel")
                    return
                await asyncio.sleep(0.02)
        asyncio.create_task(canceller())
        t0 = time.monotonic()
        evts = [e async for e in svc.execute("demo", "hi", execution_id="exec-cancel")]
        elapsed = time.monotonic() - t0
        return evts, elapsed

    evts, elapsed = asyncio.run(run())
    # 回归守卫（I-01）：cancel 后主循环应被哨兵即时唤醒，
    # 而非阻塞到 svc.timeout（30s）才响应
    assert elapsed < 10, (
        f"cancel 后 generator 耗时 {elapsed:.2f}s，应远小于 svc.timeout=30s"
    )
    assert any(e.type == "error" and "中断" in e.data["message"] for e in evts)
    failed = [r for r in records if r.get("interrupt_reason") == "user_cancel"]
    assert failed, "取消路径应落 interrupt_reason=user_cancel"
    # 取消后注册表应已清理
    assert get_run_registry().get("exec-cancel") is None
