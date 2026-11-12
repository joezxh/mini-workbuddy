"""WorkerReport —— Worker 运行时报告。5 种状态。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


ReportKind = Literal["progress", "blocked", "failed", "ready", "dropped"]


@dataclass
class WorkerReport:
    """Worker → Executor 的状态回写。"""
    kind: ReportKind
    message: str = ""
    tool_calls: list[dict] | None = None
    # blocked 时的补充
    awaiting_human: bool = False
    # failed 时的补充
    error: str | None = None
    transient: bool = False

    @property
    def terminal(self) -> bool:
        return self.kind in ("ready", "dropped")

    @property
    def is_blocked(self) -> bool:
        return self.kind == "blocked"


# Assignment 状态机（Task 8.1 —— 显式化）
ASSIGNMENT_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["running"],
    "running": ["ended", "pending"],
    "ended": [],
}

TICKET_TRANSITIONS: dict[str, list[str]] = {
    "open": ["working", "waiting_person", "waiting_hitl", "completed", "failed", "dropped"],
    "working": ["open", "waiting_person", "waiting_hitl", "completed", "failed", "dropped"],
    "waiting_person": ["working", "completed", "dropped"],
    "waiting_hitl": ["working", "completed", "dropped"],
    "completed": [],
    "failed": [],
    "dropped": [],
}


def next_assignment_status(current: str,
                           report_kind: ReportKind | str) -> str:
    """WorkerReport → Assignment 状态机。"""
    mapping: dict[str, str] = {
        "progress": "running",
        "blocked": "running",
        "failed": "ended",
        "ready": "ended",
        "dropped": "ended",
    }
    return mapping.get(str(report_kind), current)


def can_transition(current: str, nxt: str) -> bool:
    """Assignment 状态机 —— 判断 current → nxt 是否为合法迁移。"""
    return nxt in ASSIGNMENT_TRANSITIONS.get(current, [])
