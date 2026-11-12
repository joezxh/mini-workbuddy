"""EffectQueue 单元测试。"""
import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ai.superagent.effects import (
    EffectQueue, EFFECT_KINDS, EFFECT_CONCURRENCY,
)
from app.ai.superagent.repository import SuperAgentRepository


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=SuperAgentRepository)
    # Setup atomic context manager
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    repo.atomic.return_value = ctx
    repo.next_seq.return_value = 1
    repo.enqueue_effect.return_value = MagicMock(id="e1")
    repo.effects_by_status.return_value = []
    repo.update_effect_status.return_value = None
    return repo


@pytest.mark.asyncio
async def test_enqueue_effect_kind_validation(mock_repo):
    queue = EffectQueue(repo=mock_repo)

    # 所有 kind 都应该有效
    for kind in EFFECT_KINDS:
        eid = await queue.enqueue(
            workspace_id=1, kind=kind, payload={"test": True},
        )
        assert eid is not None
        mock_repo.next_seq.assert_called()
        mock_repo.enqueue_effect.assert_called()


@pytest.mark.asyncio
async def test_enqueue_invalid_kind_raises(mock_repo):
    queue = EffectQueue(repo=mock_repo)
    with pytest.raises(AssertionError):
        await queue.enqueue(workspace_id=1, kind="invalid_kind")


@pytest.mark.asyncio
async def test_enqueue_uses_correct_seq(mock_repo):
    from unittest.mock import call

    seq_values = [1, 2, 3]
    mock_repo.next_seq.side_effect = seq_values

    queue = EffectQueue(repo=mock_repo)
    eids = []
    for i in range(3):
        eid = await queue.enqueue(
            workspace_id=1, kind="assessment", payload={},
        )
        eids.append(eid)

    assert len(eids) == 3
    assert mock_repo.next_seq.call_count == 3


@pytest.mark.asyncio
async def test_start_and_stop(mock_repo):
    queue = EffectQueue(repo=mock_repo)
    await queue.start()
    assert queue._task is not None
    await queue.stop()
    assert queue._task is None


@pytest.mark.asyncio
async def test_idempotent_start(mock_repo):
    queue = EffectQueue(repo=mock_repo)
    await queue.start()
    task1 = queue._task
    await queue.start()  # 第二次调用不应创建新 task
    task2 = queue._task
    assert task1 is task2
    await queue.stop()


def test_effect_kinds_completeness():
    assert "assessment" in EFFECT_KINDS
    assert "launch" in EFFECT_KINDS
    assert "delivery" in EFFECT_KINDS
    assert "relay" in EFFECT_KINDS
    assert "notice" in EFFECT_KINDS
    assert "reply" in EFFECT_KINDS
    assert len(EFFECT_KINDS) == 6


def test_effect_concurrency_limits():
    for kind in EFFECT_KINDS:
        assert kind in EFFECT_CONCURRENCY
        assert EFFECT_CONCURRENCY[kind] > 0


# ============ launch 并发接 sa_workspace_config.max_workers（遗留④）============

def _launch_effect(ws: int, i: int):
    return SimpleNamespace(
        id=f"e{ws}_{i}", workspace_id=ws, seq=i, ticket_id=None,
        payload={}, attempts=0, due=None,
    )


def test_launch_claim_caps_per_workspace(mock_repo):
    """max_workers=1 的 ws 只领 1 个；无配置 ws 回落默认 3。"""
    queue = EffectQueue(repo=mock_repo)
    db = MagicMock()
    ready = ([_launch_effect(1, i) for i in range(4)]
             + [_launch_effect(2, i) for i in range(2)])
    mock_repo.get_workspace_config.side_effect = lambda db, ws: (
        SimpleNamespace(max_workers=1) if ws == 1 else None
    )

    claimed = queue._claim_effects(db, "launch", ready, slots=10)

    ws1 = [c for c in claimed if c.workspace_id == 1]
    ws2 = [c for c in claimed if c.workspace_id == 2]
    assert len(ws1) == 1                     # ws1 max_workers=1
    assert len(ws2) == 2                     # ws2 无配置 → 默认 3
    assert all(c.kind == "launch" for c in claimed)
    assert mock_repo.update_effect_status.call_count == len(claimed)


def test_launch_claim_default_cap_without_config(mock_repo):
    """两个 ws 都无配置 → 每 ws 最多默认 3 个。"""
    queue = EffectQueue(repo=mock_repo)
    db = MagicMock()
    ready = [_launch_effect(7, i) for i in range(5)]
    mock_repo.get_workspace_config.return_value = None

    claimed = queue._claim_effects(db, "launch", ready, slots=10)
    assert len(claimed) == 3                 # EFFECT_CONCURRENCY["launch"]

    # max_workers 非法值（0 / 负数 / None）也回落默认
    mock_repo.get_workspace_config.return_value = SimpleNamespace(max_workers=0)
    assert len(queue._claim_effects(db, "launch", ready, slots=10)) == 3


def test_non_launch_claim_ignores_workspace_config(mock_repo):
    """非 launch kind 不查询 workspace 配置，直接取前 slots 个。"""
    queue = EffectQueue(repo=mock_repo)
    db = MagicMock()
    ready = [_launch_effect(1, i) for i in range(5)]
    mock_repo.get_workspace_config.return_value = SimpleNamespace(max_workers=1)

    claimed = queue._claim_effects(db, "assessment", ready, slots=2)
    assert len(claimed) == 2
    mock_repo.get_workspace_config.assert_not_called()


def test_workspace_max_workers_fallback_on_repo_error(mock_repo):
    """配置查询异常 → 回落默认 3（不抛）。"""
    queue = EffectQueue(repo=mock_repo)
    mock_repo.get_workspace_config.side_effect = RuntimeError("db down")
    assert queue._workspace_max_workers(MagicMock(), 1) == 3


@pytest.mark.asyncio
async def test_handle_relay_without_relay_to_only_sse(mock_repo, monkeypatch):
    """relay 无 relay_to → 仅 SSE 转发，不触发 Outbox 外发。"""
    from types import SimpleNamespace
    queue = EffectQueue(repo=mock_repo)
    effect = SimpleNamespace(seq=1, ticket_id="t1", payload={})
    called = []

    async def _fake_send_relay(*args, **kwargs):
        called.append(kwargs)
        return None

    from app.ai.superagent.outbox import OutboxService
    monkeypatch.setattr(OutboxService, "send_relay", _fake_send_relay)
    result = await queue._handle_relay({"message": "hi"}, effect)
    assert result["ok"] is True
    assert "Relay forwarded via SSE" in result["message"]
    assert called == []  # 未外发


@pytest.mark.asyncio
async def test_handle_relay_feishu_forwards_via_outbox(mock_repo, monkeypatch):
    """relay 带 relay_to=feishu → SSE + Outbox.send_relay 真实转发（含 chat_id）。"""
    from types import SimpleNamespace
    queue = EffectQueue(repo=mock_repo)
    effect = SimpleNamespace(seq=2, ticket_id="t2", payload={})
    captured: dict = {}

    async def _fake_send_relay(self, ticket_id, message, channel=None, chat_id=None):
        captured.update(ticket_id=ticket_id, message=message,
                        channel=channel, chat_id=chat_id)

    from app.ai.superagent.outbox import OutboxService
    monkeypatch.setattr(OutboxService, "send_relay", _fake_send_relay)
    result = await queue._handle_relay(
        {"message": "from github", "relay_to": "feishu", "chat_id": "oc_relay"}, effect,
    )
    assert result["ok"] is True
    assert "feishu" in result["message"]
    assert captured["ticket_id"] == "t2"
    assert captured["message"] == "from github"
    assert captured["channel"] == "feishu"
    assert captured["chat_id"] == "oc_relay"
