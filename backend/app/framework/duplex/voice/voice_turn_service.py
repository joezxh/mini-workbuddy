"""语音轮次审计服务（打断 / 代际号 / SLO）。"""
from app.db.database import SessionLocal
from app.models.duplex.duplex_voice_turn import DuplexVoiceTurn


def append_turn(
    voice_session_id: str,
    turn_id: str,
    role: str,
    input_type: str,
    transcript: str | None = None,
    response_text: str | None = None,
    interrupted: bool = False,
    latency_ms: int | None = None,
) -> int:
    """追加一条轮次明细，返回 turn 主键 id。"""
    from datetime import datetime, timezone

    with SessionLocal() as db:
        turn = DuplexVoiceTurn(
            voice_session_id=voice_session_id,
            turn_id=turn_id,
            role=role,
            input_type=input_type,
            transcript=transcript,
            response_text=response_text,
            interrupted=interrupted,
            latency_ms=latency_ms,
            started_at=datetime.now(timezone.utc),
        )
        db.add(turn)
        db.commit()
        return turn.id


def mark_interrupted(turn_id: str) -> None:
    with SessionLocal() as db:
        turn = db.query(DuplexVoiceTurn).filter_by(turn_id=turn_id).first()
        if turn:
            turn.interrupted = True
            db.commit()


def bump_generation(turn_id: str) -> int:
    """打断后代际号 +1（打断审计）。返回最新代际号。"""
    with SessionLocal() as db:
        turn = db.query(DuplexVoiceTurn).filter_by(turn_id=turn_id).first()
        if not turn:
            return 0
        turn.turn_generation = (turn.turn_generation or 0) + 1
        db.commit()
        return turn.turn_generation


def record_latency(turn_id: str, latency_ms: int) -> None:
    with SessionLocal() as db:
        turn = db.query(DuplexVoiceTurn).filter_by(turn_id=turn_id).first()
        if turn:
            turn.latency_ms = latency_ms
            db.commit()
