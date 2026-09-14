from app.db.database import Base
from app.db.init_models import *  # triggers registration
from app.models.duplex.duplex_voice_session import DuplexVoiceSession
from app.models.duplex.duplex_voice_turn import DuplexVoiceTurn

def test_tables_registered():
    assert "duplex_voice_session" in Base.metadata.tables
    assert "duplex_voice_turn" in Base.metadata.tables
