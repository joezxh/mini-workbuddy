import uuid

from app.db.database import engine, Base
from app.db.init_models import *  # noqa: F401,F403
from app.models.duplex.duplex_voice_session import DuplexVoiceSession
from app.models.duplex.duplex_voice_turn import DuplexVoiceTurn
from app.duplex.voice.voice_session_service import create_voice_session
from app.duplex.voice.voice_turn_service import (
    append_turn, mark_interrupted, bump_generation,
)


def setup_module(module):
    # 确保两张新表存在（幂等）
    Base.metadata.create_all(engine, tables=[
        DuplexVoiceSession.__table__,
        DuplexVoiceTurn.__table__,
    ])


def test_create_and_append():
    vid = create_voice_session(
        1, "MED-1", "party_a", "dashscope", mode="single", agent_id="a1",
    )
    assert vid
    turn_id = f"t-{uuid.uuid4().hex[:8]}"
    tid = append_turn(vid, turn_id, "user", "voice", transcript="你好", latency_ms=850)
    assert tid > 0
    mark_interrupted(turn_id)
    gen = bump_generation(turn_id)
    assert gen == 1
