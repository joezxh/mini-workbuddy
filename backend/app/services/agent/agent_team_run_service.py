"""AI Team 运行实例服务（AgentTeamRunService）。

职责：
- 创建 ``AgentTeamRun`` 运行实例（冻结团队配置快照，保证回放一致性）
- 写入节点级执行快照 ``AgentTeamRunStep``（支持断点续跑 / 分支重跑）
- 更新运行状态、累计统计与最终输出

设计：docs/agent/agent-team-design.md §3 §4
- ``team_snapshot`` 冻结运行发起时的完整团队定义（成员 + 边 + run_config）
- ``run_step`` 只存节点级聚合结果，细粒度事件流复用 ``agent_execution_event`` 表
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.agent.agent_team import AgentTeam, AgentTeamMember, AgentTeamEdge
from app.models.agent.agent_team_run import (
    AgentTeamRun,
    AgentTeamRunStep,
    RunStatus,
    StepStatus,
    TriggerType,
)


class AgentTeamRunService:
    """团队运行实例服务。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 创建运行实例 ──────────────────────────────────────────────────────────

    def create_run(
        self,
        team: AgentTeam,
        members: List[AgentTeamMember],
        edges: List[AgentTeamEdge],
        *,
        input_text: Optional[str] = None,
        input_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        trigger_type: str = TriggerType.MANUAL,
        parent_run_id: Optional[str] = None,
        branch_from_node: Optional[str] = None,
        workspace_id: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> AgentTeamRun:
        """基于团队配置创建运行实例并冻结快照。"""
        run_id = str(uuid.uuid4())
        snapshot = self._build_snapshot(team, members, edges)
        run = AgentTeamRun(
            run_id=run_id,
            team_id=team.id,
            conversation_id=conversation_id,
            team_snapshot=snapshot,
            input_text=input_text,
            input_context=input_context,
            status=RunStatus.PENDING,
            trigger_type=trigger_type,
            parent_run_id=parent_run_id,
            branch_from_node=branch_from_node,
            workspace_id=workspace_id,
            created_by=created_by,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def _build_snapshot(
        self,
        team: AgentTeam,
        members: List[AgentTeamMember],
        edges: List[AgentTeamEdge],
    ) -> Dict[str, Any]:
        run_config = team.run_config or {}
        aggregator_key = run_config.get("aggregator_node_key")
        return {
            "team": {
                "id": team.id,
                "name": team.name,
                "mode": team.mode,
                "run_config": run_config,
            },
            "members": [
                {
                    "node_key": m.node_key,
                    "role_name": m.role_name,
                    "agent_config_id": m.agent_config_id,
                    "is_aggregator": bool(aggregator_key and m.node_key == aggregator_key),
                }
                for m in members
            ],
            "edges": [
                {
                    "from_node_key": e.from_node_key,
                    "to_node_key": e.to_node_key,
                    "edge_config": e.edge_config or {},
                }
                for e in edges
            ],
            "run_config": team.run_config or {},
        }

    # ── 节点级步骤快照 ─────────────────────────────────────────────────────────

    def begin_step(
        self,
        run: AgentTeamRun,
        *,
        node_key: str,
        role_name: Optional[str] = None,
        agent_config_id: Optional[int] = None,
        round_no: int = 0,
        layer_no: Optional[int] = None,
        seq: int,
        input_text: Optional[str] = None,
        upstream_nodes: Optional[List[str]] = None,
    ) -> AgentTeamRunStep:
        """创建并持久化一个「运行中」的步骤快照。"""
        step = AgentTeamRunStep(
            run_id=run.run_id,
            node_key=node_key,
            role_name=role_name,
            agent_config_id=agent_config_id,
            round_no=round_no,
            layer_no=layer_no,
            seq=seq,
            input_text=input_text,
            upstream_nodes=upstream_nodes,
            status=StepStatus.RUNNING,
            started_at=__import__("datetime").datetime.utcnow(),
        )
        self.db.add(step)
        self.db.flush()
        return step

    def finish_step(
        self,
        step: AgentTeamRunStep,
        *,
        status: str,
        output_text: Optional[str] = None,
        error_message: Optional[str] = None,
        tokens: int = 0,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """完成步骤快照写入（成功 / 失败 / 跳过）。"""
        step.status = status
        step.output_text = output_text
        step.error_message = error_message
        step.tokens = tokens
        step.extra_data = extra_data
        step.finished_at = __import__("datetime").datetime.utcnow()
        if step.started_at is not None:
            delta = (step.finished_at - step.started_at).total_seconds() * 1000
            step.duration_ms = int(delta)
        self.db.flush()

    # ── 运行实例状态更新 ───────────────────────────────────────────────────────

    def mark_running(self, run: AgentTeamRun) -> None:
        run.status = RunStatus.RUNNING
        run.started_at = __import__("datetime").datetime.utcnow()
        self.db.flush()

    def mark_success(self, run: AgentTeamRun, final_output: str, total_tokens: int, total_steps: int) -> None:
        run.status = RunStatus.SUCCESS
        run.final_output = final_output
        run.total_tokens = total_tokens
        run.total_steps = total_steps
        run.finished_at = __import__("datetime").datetime.utcnow()
        if run.started_at is not None:
            delta = (run.finished_at - run.started_at).total_seconds() * 1000
            run.duration_ms = int(delta)
        self.db.flush()

    def mark_failed(self, run: AgentTeamRun, error_message: str) -> None:
        run.status = RunStatus.FAILED
        run.error_message = error_message
        run.finished_at = __import__("datetime").datetime.utcnow()
        if run.started_at is not None:
            delta = (run.finished_at - run.started_at).total_seconds() * 1000
            run.duration_ms = int(delta)
        self.db.flush()

    def get(self, run_id: str) -> Optional[AgentTeamRun]:
        return self.db.query(AgentTeamRun).filter(AgentTeamRun.run_id == run_id).first()

    def list_steps(self, run_id: str) -> List[AgentTeamRunStep]:
        return (
            self.db.query(AgentTeamRunStep)
            .filter(AgentTeamRunStep.run_id == run_id)
            .order_by(AgentTeamRunStep.seq)
            .all()
        )

    # ── 提交 ────────────────────────────────────────────────────────────────

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
