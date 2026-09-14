"""语音轮次明细表。"""
from sqlalchemy import Column, BigInteger, String, Text, Boolean, Integer, TIMESTAMP, func
from app.db.database import Base


class DuplexVoiceTurn(Base):
    __tablename__ = "duplex_voice_turn"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    voice_session_id = Column(
        String(36), nullable=False, index=True,
        comment="关联 duplex_voice_session.id",
    )
    turn_id = Column(String(64), nullable=False)
    turn_generation = Column(Integer, server_default="0", comment="代际号（打断审计）")
    role = Column(String(16), nullable=False, comment="user|assistant|system")
    input_type = Column(String(16), nullable=False, comment="voice|text")
    transcript = Column(Text)
    response_text = Column(Text)
    interrupted = Column(Boolean, server_default="false")
    audio_duration_ms = Column(Integer)
    response_duration_ms = Column(Integer)
    latency_ms = Column(Integer, comment="SLO：用户说完→AI 首音频")
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    cancelled = Column(Boolean, server_default="false")
