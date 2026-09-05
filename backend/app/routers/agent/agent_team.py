"""Agent Team 路由（P3）。

提供团队 CRUD + 拓扑校验端点。
校验失败时返回 422，错误明细来自 P2（TeamGraph / MemberResolver）。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.schemas.agent.agent_team import (
    AgentTeamCreate,
    AgentTeamUpdate,
    TeamOut,
    TeamDetailOut,
    AgentTeamMemberOut,
    AgentTeamEdgeOut,
    TeamGraphValidateResult,
    TeamRunCreate,
    TeamRunOut,
    TeamChatCreate,
    TeamGraphSaveRequest,
)
from app.ai.services.execution_event_service import ExecutionEventService
from app.models.agent.agent_team_run import InterventionType, AgentTeamRun
from app.schemas.agent.agent_team import (
    TeamInterventionV2Create,
    TeamInterventionV2Out,
)

# 团队服务层
from app.services.agent.agent_team_service import (
    AgentTeamService,
    TeamNotFound,
    TeamCodeConflict,
    TeamValidationError,
)
from app.services.agent.agent_team_run_service import AgentTeamRunService

# 团队编排器
from app.ai.team.orchestrator import AgentScopeOrchestrator, ORCHESTRATOR_REGISTRY
from app.ai.team.models import ExecutionProfile
from app.ai.team.run_collector import RunCollector
from app.ai.team.intervention_queue import V2InterventionQueue
from app.ai.team.errors import render_team_error

router = APIRouter(prefix="/ai-team", tags=["AI Team"])


# ── 依赖注入 ──────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _svc(db: Session = Depends(get_db)) -> AgentTeamService:
    return AgentTeamService(db)


# ── 列表 / 详情 ────────────────────────────────────────

@router.get("", response_model=List[TeamOut])
def list_teams(
    workspace_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: AgentTeamService = Depends(_svc),
):
    teams = svc.list_teams(
        workspace_id=workspace_id,
        category=category,
        is_active=is_active,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return [_to_out(t, svc) for t in teams]


@router.post("", response_model=TeamDetailOut, status_code=201)
def create_team(
    payload: AgentTeamCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AgentTeamService(db)
    try:
        team = svc.create_team(payload, created_by=current_user.user_id)
    except TeamCodeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except TeamValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_detail(exc))
    return _to_detail(team, svc)


@router.get("/{team_id}", response_model=TeamDetailOut)
def get_team(team_id: int, svc: AgentTeamService = Depends(_svc)):
    team = svc.get_team(team_id)
    return _to_detail(team, svc)


@router.put("/{team_id}", response_model=TeamDetailOut)
def update_team(
    team_id: int,
    payload: AgentTeamUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AgentTeamService(db)
    try:
        team = svc.update_team(team_id, payload)
    except TeamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TeamValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_detail(exc))
    return _to_detail(team, svc)


@router.put("/{team_id}/graph", response_model=TeamDetailOut)
def save_team_graph(
    team_id: int,
    payload: TeamGraphSaveRequest,
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(get_current_user),
):
    """保存团队拓扑（成员 + 边 + 布局），闭环 §6.2 的拓扑保存流程。

    使用已有的 _sync_members / _sync_edges 做增量同步（保留未变化的行，
    删除前端已移除的节点 / 边），并持久化前端画布布局（layout）。
    """
    svc = AgentTeamService(db)
    try:
        team = svc.save_team_graph(team_id, payload)
    except TeamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TeamValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_detail(exc))
    return _to_detail(team, svc)


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, svc: AgentTeamService = Depends(_svc)):
    try:
        svc.delete_team(team_id)
    except TeamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None


# ── 成员 / 边查询 ──────────────────────────────────────

@router.get("/{team_id}/members", response_model=List[AgentTeamMemberOut])
def list_members(team_id: int, svc: AgentTeamService = Depends(_svc)):
    members = svc.get_members(team_id)
    return [_member_out(m, svc) for m in members]


@router.get("/{team_id}/edges", response_model=List[AgentTeamEdgeOut])
def list_edges(team_id: int, svc: AgentTeamService = Depends(_svc)):
    edges = svc.get_edges(team_id)
    return [AgentTeamEdgeOut.model_validate(e) for e in edges]


# ── 校验 ───────────────────────────────────────────────

@router.post("/{team_id}/validate", response_model=TeamGraphValidateResult)
def validate_team(team_id: int, svc: AgentTeamService = Depends(_svc)):
    try:
        return svc.validate_team(team_id)
    except TeamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── 运行（P4 执行引擎） ────────────────────────────────

@router.post("/{team_id}/run", response_model=TeamRunOut, status_code=201)
async def run_team(
    team_id: int,
    payload: TeamRunCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """基于 v2 AgentScope Leader 动态编排引擎运行团队并落库运行记录。

    流程：加载团队/成员 → 创建运行记录 → 构造事件服务与编排器 →
    由 Leader 在运行时动态派生 worker（完全走 AgentScope 运行时）→ 返回运行结果。
    注意：静态 agent_team_edge 拓扑已废弃，v2 不再读取。
    """
    svc = AgentTeamService(db)
    try:
        team = svc.get_team(team_id)
    except TeamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    members = svc.get_members(team_id)
    if not members:
        raise HTTPException(status_code=422, detail="团队没有成员，无法运行")

    run_svc = AgentTeamRunService(db)
    run = run_svc.create_run(
        team,
        members,
        [],  # v2 不再使用静态边
        input_text=payload.input_text,
        input_context=payload.input_context,
        conversation_id=payload.conversation_id,
        trigger_type=payload.trigger_type,
        created_by=current_user.user_id,
    )
    run_svc.mark_running(run)

    event_service = ExecutionEventService(
        execution_id=run.run_id,
        agent_config_id=None,
        agent_code=team.team_code,
        session_id=None,
        user_id=current_user.user_id,
    )
    collector = RunCollector(event_service)
    collector.emit_team_start(team.team_code, run.run_id)

    # v2 编排器不负责落库，由端点层负责 mark_success/mark_failed + commit
    try:
        orch = AgentScopeOrchestrator(
            db,
            team,
            run,
            event_svc=event_service,
            user_id=current_user.user_id,
            profile=ExecutionProfile.from_run_config(
                (run.team_snapshot or {}).get("run_config")
            ),
            model_id=payload.model_id,
        )
        final_text = await orch.submit(
            input_text=payload.input_text,
            input_context=payload.input_context,
            created_by=current_user.user_id,
        )
        collector.emit_team_done(team.team_code, final_text)
        run_svc.mark_success(run, final_text, total_tokens=0, total_steps=0)
        run_svc.commit()
    except Exception as exc:  # noqa: BLE001
        err_msg = render_team_error(exc)
        collector.emit_team_error(team.team_code, err_msg)
        run_svc.mark_failed(run, err_msg)
        run_svc.commit()
        raise HTTPException(status_code=500, detail=f"团队运行失败: {err_msg}")

    # run 对象仍在本会话中，可直接序列化返回
    return TeamRunOut.model_validate(run)


@router.post("/{team_id}/chat")
async def chat_team(
    team_id: int,
    payload: TeamChatCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """团队对话（SSE 流式）。

    通过 AgentFactory 创建 TeamAgent，以 SSE 实时推送团队运行状态与最终结论。
    """
    import json
    from app.ai.agent_factory import TeamAgent
    from app.ai.sse_bridge import create_done_event, create_error_event

    # 团队存在性快速校验
    svc = AgentTeamService(db)
    team = svc.get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"团队 {team_id} 不存在")

    async def event_generator():
        try:
            agent = TeamAgent(
                db=db,
                team_id=team_id,
                model_id=payload.model_id,
                name=getattr(team, "name", "团队"),
            )
            from agentscope.message import UserMsg
            user_msg = UserMsg(content=payload.message)

            async for event in agent.reply_stream(user_msg):
                if isinstance(event, dict):
                    event_type = event.get("type", "message")
                    event_data = event.get("data", event)
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                else:
                    # AgentScope 原生 Event（由 SSEBridge 处理）
                    from app.ai.sse_bridge import SSEBridge
                    bridge = SSEBridge()
                    sse = bridge._convert_event(event)
                    if sse:
                        yield f"event: {sse['type']}\ndata: {json.dumps(sse['data'], ensure_ascii=False)}\n\n"

            yield create_done_event()
        except Exception as e:
            yield create_error_event(str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── 装配辅助 ──────────────────────────────────────────

def _to_out(team: "Team", svc: AgentTeamService) -> TeamOut:
    out = TeamOut.model_validate(team)
    out.member_count = len(svc.get_members(team.id))
    return out


def _to_detail(team: "Team", svc: AgentTeamService) -> TeamDetailOut:
    out = TeamDetailOut.model_validate(team)
    out.member_count = len(svc.get_members(team.id))
    out.members = [_member_out(m, svc) for m in svc.get_members(team.id)]
    out.edges = [AgentTeamEdgeOut.model_validate(e) for e in svc.get_edges(team.id)]
    return out


def _member_out(m: "Member", svc: AgentTeamService) -> AgentTeamMemberOut:
    out = AgentTeamMemberOut.model_validate(m)
    ac = svc._load_agent_config(m.agent_config_id)
    if ac is not None:
        out.agent_name = ac.name
        out.agent_code = getattr(ac, "agent_code", None)
        out.agent_available = bool(getattr(ac, "is_active", True))
    else:
        out.agent_available = False
    return out


def _validation_detail(exc: TeamValidationError) -> dict:
    return {
        "type": "team_validation_error",
        "errors": [
            {"code": e.code, "message": e.message, "detail": e.detail}
            for e in exc.errors
        ],
    }



def _get_run_or_404(run_svc: AgentTeamRunService, team_id: int, run_id: str) -> AgentTeamRun:
    run = run_svc.get(run_id)
    if run is None or run.team_id != team_id:
        raise HTTPException(status_code=404, detail=f"运行 {run_id} 不存在或不属于团队 {team_id}")
    return run


# ── 实时人工干预（运行态介入，设计文档 §12.6）──────────────────────────────────────

@router.post(
    "/{team_id}/runs/{run_id}/interventions",
    response_model=TeamInterventionV2Out,
    summary="提交实时干预",
)
def create_intervention(
    team_id: int,
    run_id: str,
    body: TeamInterventionV2Create,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """提交一次运行态实时干预（pause / resume / cancel / inject_message / skip_node）。

    干预写入 AgentTeamIntervention 表；正在执行的编排器会在下一 checkpoint 轮询消费。
    resume / pause / cancel 会同步触达当前进程内的编排器实例（ORCHESTRATOR_REGISTRY）。
    """
    run_svc = AgentTeamRunService(db)
    _get_run_or_404(run_svc, team_id, run_id)

    queue = V2InterventionQueue(db)
    rec = queue.enqueue(
        run_id=run_id,
        intervention_type=body.intervention_type,
        payload=body.payload,
        node_key=body.node_key,
        round_no=body.round_no,
        operator_id=current_user.user_id,
        operator_name=body.operator_name or current_user.username,
    )

    # 同步触达当前进程内编排器（运行态立即生效）
    orch = ORCHESTRATOR_REGISTRY.get(run_id)
    if orch is not None:
        if body.intervention_type == InterventionType.RESUME:
            orch.resume()
        elif body.intervention_type == InterventionType.PAUSE:
            orch.request_pause()

    db.commit()
    return TeamInterventionV2Out.model_validate(rec)


@router.get(
    "/{team_id}/runs/{run_id}/interventions",
    response_model=List[TeamInterventionV2Out],
    summary="列出实时干预",
)
def list_interventions(
    team_id: int,
    run_id: str,
    status: Optional[str] = Query(None, description="按状态过滤：pending/applied/expired/rejected"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出某次运行的实时干预队列（默认全部，可按状态过滤）。"""
    run_svc = AgentTeamRunService(db)
    _get_run_or_404(run_svc, team_id, run_id)

    queue = V2InterventionQueue(db)
    recs = queue.list_all(run_id)
    if status:
        recs = [r for r in recs if r.status == status]
    return [TeamInterventionV2Out.model_validate(r) for r in recs]


# ── 对话消息重建（P 历史恢复）─────────────────────────────

class TeamRunMessageOut(BaseModel):
    """对话气泡：用于前端进入历史 run 时重建消息列表。"""
    role: str                      # user / team / worker / system
    author: str                   # 展示名（用户 / 团队长 / 政策解读 ...）
    node_key: Optional[str] = None
    content: str


@router.get(
    "/{team_id}/runs/{run_id}/messages",
    response_model=List[TeamRunMessageOut],
    summary="获取某次运行的对话消息（用于刷新/重进恢复）",
)
def get_run_messages(
    team_id: int,
    run_id: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """从 run + run_step 重建对话气泡。

    顺序：用户输入 → 各 worker 输出（按执行顺序 seq）→ 团队最终结论。
    这样前端刷新或重新进入带 runId 的对话页时无需重跑即可恢复历史。
    """
    run_svc = AgentTeamRunService(db)
    run = _get_run_or_404(run_svc, team_id, run_id)

    messages: List[TeamRunMessageOut] = []

    # 1) 用户输入
    if run.input_text:
        messages.append(TeamRunMessageOut(
            role="user", author="用户", node_key=None, content=run.input_text
        ))

    # 2) 各节点（worker / leader）输出，按执行顺序
    steps = run_svc.list_steps(run_id)
    for step in steps:
        if step.output_text:
            node_key = step.node_key or "worker"
            role = "team" if step.is_leader else "worker"
            messages.append(TeamRunMessageOut(
                role=role,
                author=step.role_name or node_key,
                node_key=node_key,
                content=step.output_text,
            ))

    # 3) 团队最终结论（避免与 leader 节点重复时仍兜底展示）
    if run.final_output:
        # 若已有 leader 的 team 气泡且内容相同，则不重复
        already = any(
            m.role == "team" and m.content.strip() == run.final_output.strip()
            for m in messages
        )
        if not already:
            messages.append(TeamRunMessageOut(
                role="team", author="团队", node_key="team", content=run.final_output
            ))

    return messages
