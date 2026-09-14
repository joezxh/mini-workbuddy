"""T13: ProtocolAdapter 能力协商 + build_ready_payload 测试。"""
import pytest

from app.duplex.voice.capabilities import ProviderCapabilities
from app.duplex.voice.protocol_adapter import (
    NegotiatedSession,
    ProtocolAdapter,
)


def test_capabilities_defaults_include_negotiation_dims():
    caps = ProviderCapabilities()
    assert caps.server_vad
    assert not caps.manual_vad_only
    assert caps.barge_in_mode == "server"
    # M1 字段保持兼容
    assert caps.supports_interrupt is True
    assert caps.input_sample_rate == 16000


def test_negotiate_prefers_server_vad():
    caps = ProviderCapabilities(server_vad=True, semantic_vad=False)
    ns = ProtocolAdapter.negotiate({"vad_mode": "server"}, caps)
    assert isinstance(ns, NegotiatedSession)
    assert ns.vad_mode == "server"


def test_negotiate_falls_back_to_manual():
    caps = ProviderCapabilities(server_vad=False, manual_vad_only=True)
    ns = ProtocolAdapter.negotiate({"vad_mode": "server"}, caps)
    assert ns.vad_mode == "manual"


def test_negotiate_prefers_semantic_when_supported():
    caps = ProviderCapabilities(server_vad=True, semantic_vad=True)
    ns = ProtocolAdapter.negotiate({"vad_mode": "semantic"}, caps)
    assert ns.vad_mode == "semantic"


def test_negotiate_propagates_sample_rates():
    caps = ProviderCapabilities(input_sample_rate=8000, output_sample_rate=16000)
    ns = ProtocolAdapter.negotiate({}, caps)
    assert ns.input_sample_rate == 8000
    assert ns.output_sample_rate == 16000
    assert ns.transcription is True


def test_build_ready_payload_contains_session_info():
    caps = ProviderCapabilities()
    payload = ProtocolAdapter.build_ready_payload(caps, "sess-1", "loopback")
    assert payload["session_id"] == "sess-1"
    assert payload["provider"] == "loopback"
    assert payload["input_sample_rate"] == 16000
    assert payload["output_sample_rate"] == 24000
    assert payload["server_vad"] is True
    assert payload["supports_interrupt"] is True
    assert payload["vad_mode"] == "server"
