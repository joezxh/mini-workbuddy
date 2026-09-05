"""实时干预队列 — 运行态介入（暂停/恢复/取消/注入消息/跳过节点）。

编排器在每一轮的 checkpoint 调用 poll 轮询待处理干预，
apply 返回本轮要执行的动作。暂停语义通过 run 状态机实现。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models.agent.agent_team_run import (
    AgentTeamIntervention,
    InterventionStatus,
    InterventionType,
    RunStatus,
)

logger = logging.getLogger(__name__)


class V2InterventionQueue:
    """运行态干预队列。"""

    def __init__(self, db: Any):
        self.db = db

    def enqueue(
        self,
        *,
        run_id: str,
        intervention_type: str,
        payload: Optional[Dict[str, Any]] = None,
        node_key: Optional[str] = None,
        round_no: Optional[int] = None,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
    ) -> AgentTeamIntervention:
        """创建一条待处理干预。"""
        iv = AgentTeamIntervention(
            run_id=run_id,
            intervention_type=intervention_type,
            payload=payload or {},
            node_key=node_key,
            round_no=round_no,
            operator_id=operator_id,
            operator_name=operator_name,
            status=InterventionStatus.PENDING,
        )
        self.db.add(iv)
        self.db.flush()
        return iv

    def poll(self, run_id: str) -> List[AgentTeamIntervention]:
        """取回该 run 下所有 PENDING 干预（编排器在 checkpoint 调用）。"""
        return (
            self.db.query(AgentTeamIntervention)
            .filter(
                AgentTeamIntervention.run_id == run_id,
                AgentTeamIntervention.status == InterventionStatus.PENDING,
            )
            .order_by(AgentTeamIntervention.created_at)
            .all()
        )

    def list_pending(self, run_id: str) -> List[AgentTeamIntervention]:
        return self.poll(run_id)

    def list_all(self, run_id: str) -> List[AgentTeamIntervention]:
        return (
            self.db.query(AgentTeamIntervention)
            .filter(AgentTeamIntervention.run_id == run_id)
            .order_by(AgentTeamIntervention.created_at)
            .all()
        )

    def resolve(
        self, iv: AgentTeamIntervention, *, applied: bool = True,
        note: Optional[str] = None,
    ) -> None:
        iv.status = InterventionStatus.APPLIED if applied else InterventionStatus.REJECTED
        if note is not None:
            iv.result_note = note
        self.db.flush()

    def apply(self, interventions: List[AgentTeamIntervention]) -> Dict[str, Any]:
        """将一批干预合并为可执行的检查点动作。"""
        result: Dict[str, Any] = {
            "paused": False,
            "cancelled": False,
            "inject_messages": [],
            "skip_nodes": [],
            "resolved_ids": [],
        }
        for iv in interventions:
            t = iv.intervention_type
            if t == InterventionType.PAUSE:
                result["paused"] = True
                self.resolve(iv, applied=True, note="checkpoint paused")
                result["resolved_ids"].append(iv.id)
            elif t == InterventionType.CANCEL:
                result["cancelled"] = True
                self.resolve(iv, applied=True, note="run cancelled")
                result["resolved_ids"].append(iv.id)
            elif t == InterventionType.INJECT_MESSAGE:
                msg = (iv.payload or {}).get("message") or (iv.payload or {}).get("text")
                if msg:
                    result["inject_messages"].append(msg)
                self.resolve(iv, applied=True, note="message injected")
                result["resolved_ids"].append(iv.id)
            elif t == InterventionType.SKIP_NODE:
                node = (iv.payload or {}).get("node_key") or iv.node_key
                if node:
                    result["skip_nodes"].append(node)
                self.resolve(iv, applied=True, note="node skipped")
                result["resolved_ids"].append(iv.id)
            elif t == InterventionType.RESUME:
                self.resolve(iv, applied=True, note="resumed")
                result["resolved_ids"].append(iv.id)
            else:
                logger.warning("intervention type %s not handled, kept pending", t)
        return result


def is_run_paused(run: Any) -> bool:
    return getattr(run, "status", None) == RunStatus.PAUSED
