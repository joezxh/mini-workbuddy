"""RunCollector：团队运行事件收集器。

orchestrator 在每个 worker 的 spawn/start/done 阶段通过 event_svc 记录节点事件；
RunCollector 负责在运行开始/结束时补充团队级事件。
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.agent.agent import ExecutionEventType

logger = logging.getLogger(__name__)


class RunCollector:
    """团队运行事件收集器。"""

    def __init__(self, event_svc: Any) -> None:
        self.event_svc = event_svc

    def emit_team_start(self, team_code: str, run_id: str) -> None:
        try:
            self.event_svc.record(
                event_type=ExecutionEventType.TEAM_START,
                content={"team_code": team_code, "run_id": run_id, "status": "start"},
                source="team",
                source_id=team_code,
            )
        except Exception as exc:
            logger.debug("emit team start failed: %s", exc)

    def emit_team_done(self, team_code: str, final_text: str) -> None:
        try:
            self.event_svc.record(
                event_type=ExecutionEventType.TEAM_DONE,
                content={"team_code": team_code, "result": final_text, "status": "done"},
                source="team",
                source_id=team_code,
            )
        except Exception as exc:
            logger.debug("emit team done failed: %s", exc)

    def emit_team_error(self, team_code: str, error: str) -> None:
        try:
            self.event_svc.record(
                event_type=ExecutionEventType.TEAM_ERROR,
                content={"team_code": team_code, "error": error, "status": "error"},
                source="team",
                source_id=team_code,
            )
        except Exception as exc:
            logger.debug("emit team error failed: %s", exc)
