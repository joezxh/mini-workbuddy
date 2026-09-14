"""T16: ReplayBuffer 测试。"""
import pytest

from app.duplex.voice.replay_buffer import (
    ReplayBuffer,
    SESSION_REPLAY_BUFFERS,
)


def test_push_and_len():
    b = ReplayBuffer()
    assert len(b) == 0
    b.push({"type": "transcript", "data": {"text": "a"}})
    assert len(b) == 1


def test_drain_returns_and_clears():
    b = ReplayBuffer()
    b.push({"t": 1})
    b.push({"t": 2})
    drained = b.drain()
    assert drained == [{"t": 1}, {"t": 2}]
    assert len(b) == 0


def test_maxlen_bounded():
    b = ReplayBuffer(maxlen=2)
    b.push({"t": 1})
    b.push({"t": 2})
    b.push({"t": 3})
    assert len(b) == 2
    assert b.drain() == [{"t": 2}, {"t": 3}]


def test_session_buffers_is_dict():
    assert isinstance(SESSION_REPLAY_BUFFERS, dict)
