"""T14: ReconnectBackoff + classify_error 测试。"""
import pytest

from app.duplex.voice.constants import ErrorCode
from app.duplex.voice.reconnect_backoff import (
    ReconnectBackoff,
    classify_error,
)


def test_exponential_backoff_sequence():
    b = ReconnectBackoff(base=0.5, factor=2.0, cap=8.0, max_attempts=5)
    assert b.next_delay() == 0.5
    assert b.next_delay() == 1.0
    assert b.next_delay() == 2.0
    assert b.attempt == 3


def test_backoff_caps_at_max():
    b = ReconnectBackoff(base=1.0, factor=4.0, cap=4.0, max_attempts=10)
    assert b.next_delay() == 1.0
    assert b.next_delay() == 4.0
    assert b.next_delay() == 4.0


def test_reset_restarts_sequence():
    b = ReconnectBackoff(base=0.5, factor=2.0, cap=8.0, max_attempts=5)
    b.next_delay()
    b.next_delay()
    b.reset()
    assert b.attempt == 0
    assert b.next_delay() == 0.5


def test_should_retry_honors_max():
    b = ReconnectBackoff(base=0.5, factor=2.0, cap=8.0, max_attempts=2)
    assert b.should_retry() is True
    b.next_delay()
    b.next_delay()
    assert b.should_retry() is False


def test_classify_timeout_is_fatal():
    assert classify_error(TimeoutError()) == ErrorCode.FATAL


def test_classify_connection_error_is_provider_unavailable():
    assert classify_error(ConnectionError()) == ErrorCode.PROVIDER_UNAVAILABLE


def test_classify_value_error_is_other():
    assert classify_error(ValueError("bad")) == ErrorCode.OTHER
