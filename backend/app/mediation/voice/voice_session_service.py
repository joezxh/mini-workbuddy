"""语音会话 / 轮次持久化服务（差距分析 §2.4 / §3.4）。"""
from datetime import datetime, timezone
from uuid import uuid4

from app.db.database import SessionLocal
from app.models.duplex.duplex_voice_session import DuplexVoiceSession


def create_voice_session(
    duplex_session_id: int,
    case_number: str,
    participant_id: str,
    provider: str,
    mode: str = "single",
    agent_id: str | None = None,
    voice_metadata: dict | None = None,
) -> str:
    """创建一条语音连接会话记录，返回 voice_session_id（uuid4 hex）。"""
    vid = uuid4().hex
    with SessionLocal() as db:
        rec = DuplexVoiceSession(
            id=vid,
            duplex_session_id=duplex_session_id,
            case_number=case_number,
            participant_id=participant_id,
            provider=provider,
            mode=mode,
            status="connecting",
            agent_id=agent_id,
            voice_metadata=voice_metadata or {},
            connected_at=datetime.now(timezone.utc),
        )
        db.add(rec)
        db.commit()
    return vid


def update_voice_session_status(
    voice_session_id: str,
    status: str,
    disconnect_reason: str | None = None,
) -> None:
    """更新语音会话状态（connected/disconnected）。"""
    with SessionLocal() as db:
        sess = db.get(DuplexVoiceSession, voice_session_id)
        if sess:
            sess.status = status
            if disconnect_reason:
                sess.disconnect_reason = disconnect_reason
            if status == "disconnected":
                sess.disconnected_at = datetime.now(timezone.utc)
            db.commit()


def get_voice_session(voice_session_id: str) -> DuplexVoiceSession | None:
    with SessionLocal() as db:
        return db.get(DuplexVoiceSession, voice_session_id)
