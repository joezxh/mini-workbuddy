import app.db.init_models  # noqa: F401  注册全部模型
from app.db.database import SessionLocal
from app.models.agent.agent_hitl_pause import AgentHitlPause

db = SessionLocal()
try:
    pause = AgentHitlPause(
        execution_id="tmp-schema-check",
        pause_type="ask_user",
        pause_payload={"q": "ok"},
    )
    db.add(pause)
    db.flush()
    print("agent_hitl_pause insert ok | round_no:", pause.round_no, "| payload:", pause.pause_payload)
finally:
    db.rollback()
    db.close()