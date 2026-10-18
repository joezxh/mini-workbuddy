"""向量维度对齐工具测试（fit_vector_dimension / resolve_engine / get_segment_vector_dimension）。"""
from __future__ import annotations

from app.services.kb.vector_utils import (
    fit_vector_dimension,
    get_segment_vector_dimension,
    resolve_engine,
)


def test_fit_pads_short_vector():
    assert fit_vector_dimension([1.0, 2.0], 4) == [1.0, 2.0, 0.0, 0.0]


def test_fit_truncates_long_vector():
    assert fit_vector_dimension([1.0, 2.0, 3.0, 4.0, 5.0], 3) == [1.0, 2.0, 3.0]


def test_fit_keeps_equal_length():
    assert fit_vector_dimension([1.0, 2.0, 3.0], 3) == [1.0, 2.0, 3.0]


def test_fit_none_with_target_dim_pads_to_zeros():
    # None 视为空向量；给定目标维度时补齐为全零向量（保持既有语义）
    assert fit_vector_dimension(None, 3) == [0.0, 0.0, 0.0]


def test_fit_none_without_target_dim_is_empty():
    assert fit_vector_dimension(None, None) == []
    assert fit_vector_dimension(None, 0) == []


def test_fit_zero_or_none_dim_is_noop():
    assert fit_vector_dimension([1.0, 2.0], 0) == [1.0, 2.0]
    assert fit_vector_dimension([1.0, 2.0], None) == [1.0, 2.0]


class _FakeSession:
    bind = "ENGINE"


class _FakeEngine:
    def connect(self):  # pragma: no cover - 仅用于 resolve_engine 识别
        raise AssertionError("connect 不应被调用")


class _BoomEngine:
    def connect(self):
        raise RuntimeError("no database")


def test_resolve_engine_from_session():
    assert resolve_engine(_FakeSession()) == "ENGINE"


def test_resolve_engine_from_engine():
    eng = _FakeEngine()
    assert resolve_engine(eng) is eng


def test_resolve_engine_none():
    assert resolve_engine(None) is None


def test_get_segment_vector_dimension_none_engine():
    assert get_segment_vector_dimension(None) is None


def test_get_segment_vector_dimension_handles_error():
    # 读不到物理维度时返回 None（调用方回落 settings.EMBEDDING_DIMENSION），不抛异常
    assert get_segment_vector_dimension(_BoomEngine()) is None
