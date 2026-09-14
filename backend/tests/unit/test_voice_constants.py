from app.duplex.voice.constants import VoiceState, EventType, ProviderKey, ErrorCode

def test_voice_state_values():
    assert VoiceState.LISTENING == "listening"
    assert VoiceState.PROCESSING == "processing"
    assert VoiceState.SPEAKING == "speaking"

def test_event_type_members_present():
    for e in ["connect", "voice_ready", "voice_state", "turn_started",
              "audio_delta", "audio_done", "transcript_delta", "transcript_final",
              "interrupt", "playback_clear", "error", "pong"]:
        assert hasattr(EventType, e.upper())

def test_provider_key_and_error_code():
    assert ProviderKey.DASHSCOPE == "dashscope"
    assert ErrorCode.PROVIDER_UNAVAILABLE == "provider_unavailable"
    assert ErrorCode.FATAL == "fatal"
