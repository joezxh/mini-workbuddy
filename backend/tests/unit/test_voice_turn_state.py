"""T12: TurnState 代际仲裁单元测试。"""
import pytest

from app.duplex.voice.constants import VoiceState
from app.duplex.voice.turn_state import TurnState


def test_initial_state_is_idle():
    t = TurnState()
    assert t.voice_state == VoiceState.IDLE.value
    assert t.generation == 0
    assert t.is_playing() is False


def test_mark_speaking_bumps_generation_and_plays():
    t = TurnState()
    t.mark_speaking()
    assert t.generation == 1
    assert t.voice_state == VoiceState.SPEAKING.value
    assert t.is_playing() is True


def test_speech_started_bumps_generation_and_listens():
    t = TurnState()
    t.on_speech_started()
    assert t.generation == 1
    assert t.voice_state == VoiceState.LISTENING.value


def test_speech_stopped_and_audio_done_return_idle():
    t = TurnState()
    t.mark_speaking()
    t.on_speech_stopped()
    assert t.voice_state == VoiceState.IDLE.value
    t.mark_speaking()
    t.on_audio_done()
    assert t.voice_state == VoiceState.IDLE.value


def test_generation_increments_across_turns():
    t = TurnState()
    t.on_speech_started()  # gen 1
    t.mark_speaking()      # gen 2
    t.on_speech_started()  # gen 3
    assert t.generation == 3


def test_is_stale_detects_stale_frames():
    t = TurnState()
    t.mark_speaking()  # gen 1
    assert t.is_stale(0) is True   # 旧代际
    assert t.is_stale(1) is False  # 当前代际
    t.on_speech_started()  # gen 2
    assert t.is_stale(1) is True
    assert t.is_stale(2) is False


def test_interrupt_returns_to_idle():
    t = TurnState()
    t.mark_speaking()
    t.on_interrupt()
    assert t.voice_state == VoiceState.IDLE.value
    assert t.is_playing() is False
