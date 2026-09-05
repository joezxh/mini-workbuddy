"""Agent Team CRUD 服务。

TODO: AgentScope 原生 Team API 适配——
  TeamGraphBuilder / TeamGraph / MemberResolver 需基于 AgentScope 重新实现。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.agent.agent_config import AgentConfig
from app.models.agent.agent_team import AgentTeam, AgentTeamMember, AgentTeamEdge
from app.schemas.agent.agent_team import (
    AgentTeamCreate,
    AgentTeamUpdate,
    AgentTeamMemberCreate,
    AgentTeamEdgeCreate,
    TeamGraphSaveRequest,
    TeamGraphValidateResult,
)


# TODO: 以下 stub 类待 AgentScope 原生 Team API 实现后替换
class NodeSpec:
    def __init__(self, node_key: str, is_aggregator: bool = False,
                 agent_config_id=None, role_name: str = "", **kw):
        self.node_key = node_key
        self.is_aggregator = is_aggregator
        self.agent_config_id = agent_config_id
        self.role_name = role_name

class EdgeSpec:
    def __init__(self, from_node_key: str, to_node_key: str,
                 edge_config: dict = None, **kw):
        self.from_node_key = from_node_key
        self.to_node_key = to_node_key
        self.edge_config = edge_config or {}


class AgentTeamService:
    """Agent Team 持久化与校验服务。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 查询 ─────────────────────────────────────────────

    def list_teams(
        self,
        *,
        workspace_id: Optional[int] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentTeam]:
        q = self.db.query(AgentTeam).filter(AgentTeam.is_deleted.is_(False))
        if workspace_id is not None:
            q = q.filter(AgentTeam.workspace_id == workspace_id)
        if category is not None:
            q = q.filter(AgentTeam.category == category)
        if is_active is not None:
            q = q.filter(AgentTeam.is_active.is_(is_active))
        if keyword:
            like = f"%{keyword}%"
            q = q.filter((AgentTeam.name.ilike(like)) | (AgentTeam.team_code.ilike(like)))
        return (
            q.order_by(AgentTeam.sort_order.asc(), AgentTeam.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_team(self, team_id: int) -> AgentTeam:
        team = (
            self.db.query(AgentTeam)
            .filter(AgentTeam.id == team_id, AgentTeam.is_deleted.is_(False))
            .first()
        )
        if team is None:
            raise TeamNotFound(team_id)
        return team

    def get_members(self, team_id: int) -> List[AgentTeamMember]:
        self.get_team(team_id)  # 校验存在
        return (
            self.db.query(AgentTeamMember)
            .filter(AgentTeamMember.team_id == team_id)
            .order_by(AgentTeamMember.sort_order.asc(), AgentTeamMember.id.asc())
            .all()
        )

    def get_edges(self, team_id: int) -> List[AgentTeamEdge]:
        self.get_team(team_id)
        return (
            self.db.query(AgentTeamEdge)
            .filter(AgentTeamEdge.team_id == team_id)
            .order_by(AgentTeamEdge.sort_order.asc(), AgentTeamEdge.id.asc())
            .all()
        )

    # ── 创建 / 更新 / 删除 ────────────────────────────────

    def create_team(self, payload: AgentTeamCreate, *, created_by: Optional[int] = None) -> AgentTeam:
        team_code = payload.team_code or self._gen_code(payload.name)
        if self._code_exists(team_code):
            raise TeamCodeConflict(team_code)

        team = AgentTeam(
            team_code=team_code,
            name=payload.name,
            description=payload.description,
            category=payload.category,
            mode=payload.mode,
            graph=payload.graph,
            shared_knowledge_bases=payload.shared_knowledge_bases,
            shared_tools=payload.shared_tools,
            run_config=(payload.run_config.model_dump() if payload.run_config else None),
            sort_order=payload.sort_order or 0,
            workspace_id=payload.workspace_id,
            created_by=created_by,
        )
        self.db.add(team)
        self.db.flush()  # 拿到 team.id

        self._sync_members(team, payload.members)
        self._sync_edges(team, payload.edges)
        self.db.commit()
        self.db.refresh(team)
        logger.info(f"[Team] 创建团队 {team.team_code}(id={team.id}) mode={team.mode}")
        return team

    def update_team(self, team_id: int, payload: AgentTeamUpdate) -> AgentTeam:
        team = self.get_team(team_id)
        data = payload.model_dump(exclude_unset=True)

        for field in (
            "name",
            "description",
            "category",
            "mode",
            "graph",
            "shared_knowledge_bases",
            "shared_tools",
            "sort_order",
            "workspace_id",
            "is_active",
        ):
            if field in data:
                setattr(team, field, data[field])

        if "run_config" in data:
            team.run_config = (
                payload.run_config.model_dump() if payload.run_config else None
            )

        if "members" in data:
            self._sync_members(team, payload.members)
        if "edges" in data:
            self._sync_edges(team, payload.edges)

        self.db.commit()
        self.db.refresh(team)
        logger.info(f"[Team] 更新团队 {team.team_code}(id={team.id})")
        return team

    def save_team_graph(
        self, team_id: int, payload: "TeamGraphSaveRequest"
    ) -> AgentTeam:
        """保存团队拓扑（成员 + 边 + 画布布局），闭环 §6.2 拓扑保存流程。

        使用已有的 _sync_members / _sync_edges 做增量同步（全量替换，幂等），
        并将前端画布布局快照写入 graph 字段。
        """
        team = self.get_team(team_id)
        self._sync_members(team, payload.members)
        self._sync_edges(team, payload.edges)
        if payload.layout is not None:
            team.graph = payload.layout
        self.db.commit()
        self.db.refresh(team)
        logger.info(
            f"[Team] 保存拓扑 {team.team_code}(id={team.id}) "
            f"members={len(payload.members)} edges={len(payload.edges)}"
        )
        return team

    def delete_team(self, team_id: int) -> None:
        team = self.get_team(team_id)
        team.is_deleted = True
        # 级联软删除成员 / 边（保持引用完整）
        self.db.query(AgentTeamMember).filter(
            AgentTeamMember.team_id == team_id
        ).delete(synchronize_session=False)
        self.db.query(AgentTeamEdge).filter(
            AgentTeamEdge.team_id == team_id
        ).delete(synchronize_session=False)
        self.db.commit()
        logger.info(f"[Team] 软删除团队 id={team_id}")

    # ── 校验（整合 P2）─────────────────────────────────────

    def validate_team(self, team_id: int) -> TeamGraphValidateResult:
        """对持久化后的团队做拓扑 / 成员解析校验。"""
        team = self.get_team(team_id)
        members = self.get_members(team_id)
        edges = self.get_edges(team_id)

        member_creates = [self._member_to_create(m) for m in members]
        edge_creates = [self._edge_to_create(e) for e in edges]
        return self.validate_spec(team, member_creates, edge_creates)

    def validate_spec(
        self,
        team: AgentTeam,
        members: List[AgentTeamMemberCreate],
        edges: List[AgentTeamEdgeCreate],
    ) -> TeamGraphValidateResult:
        """对一份团队定义做校验，返回 ``TeamGraphValidateResult``。"""
        errors: List[str] = []
        warnings: List[str] = []

        # 1) 边推导（dag/sequential 模式用请求提供的边；其余由 builder 推导）
        try:
            edge_specs = self._resolve_edges(team, members, edges)
        except TeamValidationError as exc:
            return TeamGraphValidateResult(
                valid=False,
                errors=[e.message for e in exc.errors],
                warnings=[],
                layers=[],
                entry_nodes=[],
                terminal_nodes=[],
            )

        # 2) 拓扑校验
        # TODO: 待 AgentScope TeamGraph 实现后恢复完整校验
        agg_key = (team.run_config or {}).get("aggregator_node_key")
        member_node_specs = [
            NodeSpec(
                node_key=m.node_key,
                is_aggregator=(m.node_key == agg_key),
                agent_config_id=m.agent_config_id,
                role_name=m.role_name,
            )
            for m in members
        ]
        node_specs = member_node_specs

        return TeamGraphValidateResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            layers=[],
            entry_nodes=[n.node_key for n in node_specs],
            terminal_nodes=[],
        )

    # ── 内部工具 ──────────────────────────────────────────

    def _resolve_edges(
        self,
        team: AgentTeam,
        members: List[AgentTeamMemberCreate],
        edges: List[AgentTeamEdgeCreate],
    ) -> List[EdgeSpec]:
        """根据模式推导最终边集合。"""
        run_config: Dict[str, Any] = team.run_config or {}
        if team.mode in ("dag", "sequential"):
            # 用户显式提供的边即为权威
            if not edges:
                raise TeamValidationError(
                    [TeamValidateError(code="no_edges", message="该模式必须提供 edges")]
                )
            return [
                EdgeSpec(
                    from_node_key=e.from_node_key,
                    to_node_key=e.to_node_key,
                    edge_config=e.edge_config or {},
                )
                for e in edges
            ]

        # 其余模式由 builder 推导
        # TODO: 待 AgentScope TeamGraphBuilder 实现后恢复
        raise TeamValidationError(
            [TeamValidateError(code="not_implemented",
                               message=f"模式 '{team.mode}' 的边推导待 AgentScope 适配")]
        )

    def _sync_members(self, team: AgentTeam, members: List[AgentTeamMemberCreate]) -> None:
        # 全量替换（简单且幂等）
        self.db.query(AgentTeamMember).filter(
            AgentTeamMember.team_id == team.id
        ).delete(synchronize_session=False)

        seen_keys = set()
        for idx, m in enumerate(members):
            if m.node_key in seen_keys:
                raise TeamValidationError(
                    [TeamValidateError(code="dup_node_key", message=f"重复 node_key: {m.node_key}")]
                )
            seen_keys.add(m.node_key)
            nc = m.node_config.model_dump() if m.node_config else None
            self.db.add(
                AgentTeamMember(
                    team_id=team.id,
                    agent_config_id=m.agent_config_id,
                    node_key=m.node_key,
                    role_name=m.role_name,
                    role_desc=m.role_desc,
                    avatar=m.avatar,
                    sort_order=m.sort_order if m.sort_order is not None else idx,
                    override_system_prompt=m.override_system_prompt,
                    override_llm_config=m.override_llm_config,
                    override_knowledge_bases=m.override_knowledge_bases,
                    override_tools=m.override_tools,
                    override_skills=m.override_skills,
                    node_config=nc,
                )
            )

    def _sync_edges(self, team: AgentTeam, edges: List[AgentTeamEdgeCreate]) -> None:
        self.db.query(AgentTeamEdge).filter(
            AgentTeamEdge.team_id == team.id
        ).delete(synchronize_session=False)
        for idx, e in enumerate(edges):
            self.db.add(
                AgentTeamEdge(
                    team_id=team.id,
                    from_node_key=e.from_node_key,
                    to_node_key=e.to_node_key,
                    label=e.label,
                    condition=e.condition,
                    sort_order=e.sort_order if e.sort_order is not None else idx,
                    edge_config=e.edge_config,
                )
            )

    def _member_to_create(self, m: AgentTeamMember) -> AgentTeamMemberCreate:
        return AgentTeamMemberCreate(
            node_key=m.node_key,
            agent_config_id=m.agent_config_id,
            role_name=m.role_name,
            role_desc=m.role_desc,
            avatar=m.avatar,
            sort_order=m.sort_order,
            override_system_prompt=m.override_system_prompt,
            override_llm_config=m.override_llm_config,
            override_knowledge_bases=m.override_knowledge_bases,
            override_tools=m.override_tools,
            override_skills=m.override_skills,
            node_config=m.node_config,
            is_active=m.is_active,
        )

    def _edge_to_create(self, e: AgentTeamEdge) -> AgentTeamEdgeCreate:
        return AgentTeamEdgeCreate(
            from_node_key=e.from_node_key,
            to_node_key=e.to_node_key,
            label=e.label,
            condition=e.condition,
            sort_order=e.sort_order,
            edge_config=e.edge_config,
        )

    def _gen_code(self, name: str) -> str:
        from datetime import datetime

        base = "team_" + (name or "unnamed")
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{base}_{stamp}"

    def _code_exists(self, team_code: str) -> bool:
        return (
            self.db.query(AgentTeam.id)
            .filter(AgentTeam.team_code == team_code, AgentTeam.is_deleted.is_(False))
            .first()
            is not None
        )

    def _load_agent_config(self, agent_config_id: int) -> Optional[AgentConfig]:
        return (
            self.db.query(AgentConfig)
            .filter(AgentConfig.id == agent_config_id, AgentConfig.is_deleted.is_(False))
            .first()
        )


# ── 异常 ─────────────────────────────────────────────────


class TeamNotFound(Exception):
    def __init__(self, team_id: int):
        self.team_id = team_id
        super().__init__(f"团队不存在: id={team_id}")


class TeamCodeConflict(Exception):
    def __init__(self, team_code: str):
        self.team_code = team_code
        super().__init__(f"team_code 已存在: {team_code}")


class TeamValidateError:
    """校验错误项（code / message / detail）。"""

    def __init__(self, code: str, message: str, detail: Optional[Any] = None):
        self.code = code
        self.message = message
        self.detail = detail


class TeamValidationError(Exception):
    """聚合多个校验错误，供 Service / Router 映射为 422。"""

    def __init__(self, errors: List[TeamValidateError]):
        self.errors = errors
        super().__init__("; ".join(e.message for e in errors))


__all__ = [
    "AgentTeamService",
    "TeamNotFound",
    "TeamCodeConflict",
    "TeamValidationError",
    "TeamValidateError",
]
