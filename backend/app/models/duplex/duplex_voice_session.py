"""语音连接会话表。"""
from sqlalchemy import Column, String, Integer, BigInteger, TIMESTAMP, JSON, func
from app.db.database import Base


class DuplexVoiceSession(Base):
    __tablename__ = "duplex_voice_session"

    id = Column(String(36), primary_key=True)  # uuid4 hex
    duplex_session_id = Column(
        BigInteger, nullable=False, index=True,
        comment="关联 duplex_session.id（BigInteger，与存量 ORM 一致）",
    )
    case_number = Column(String(64), index=True, comment="案件编号检索键")
    participant_id = Column(String(64), comment="说话人/参与者标识")
    provider = Column(String(32), nullable=False, comment="dashscope|local")
    mode = Column(String(16), nullable=False, server_default="single")
    status = Column(String(16), nullable=False, server_default="connecting")
    input_sample_rate = Column(Integer, server_default="16000")
    output_sample_rate = Column(Integer, server_default="24000")
    agent_id = Column(String(64), comment="绑定的 AI Agent 标识")
    connected_at = Column(TIMESTAMP)
    disconnected_at = Column(TIMESTAMP)
    disconnect_reason = Column(String(64))
    reconnect_count = Column(Integer, server_default="0")
    voice_metadata = Column(JSON, comment="voiceIdentity/language/greeting 快照")
    created_at = Column(TIMESTAMP, server_default=func.now())
