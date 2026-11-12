"""SuperAgent FastAPI 路由 —— Engine + Source API（Task 1.4 + Task 6.6）。

端点清单：
  GET  /health       — 引擎健康检查
  POST /tickets      — 手动创建 Ticket（skip eval，直接 ACCEPTED）
  GET  /tickets      — 列表（按 workspace 过滤）
  GET  /tickets/{id} — 详情
  GET  /events       — SSE 事件流（前端 Feed/Ideas/Goals 订阅）
  GET  /sources                   — Source 列表 + health（Task 6.6）
  GET  /sources/{kind}/config     — Source 配置 Schema + 当前值（Task 6.6）
  PUT  /sources/{kind}/config     — 更新 Source 配置（Task 6.6）
  GET  /threads                   — 按 Source 列出 Thread（Task 6.6）
  GET  /tickets/{id}/subscriptions — Ticket 的 Subscription 列表（Task 6.6）
  POST /tickets/{id}/subscriptions — 添加 Subscription（context_only）（Task 6.6）
"""
from __future__ import annotations

from typing import Optional, Literal, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.superagent.repository import SuperAgentRepository
from app.ai.superagent.policy import PolicyService
from app.ai.superagent.assessor import AssessorService
from app.ai.superagent.engine.core import SuperAgentEngine

router = APIRouter(prefix="/super-agent", tags=["SuperAgent 引擎"])


# ============ 单例 Engine 工厂 ============

_engine_instance: SuperAgentEngine | None = None


def get_engine() -> SuperAgentEngine:
    """延迟初始化 SuperAgentEngine 单例。"""
    global _engine_instance
    if _engine_instance is None:
        repo = SuperAgentRepository()
        policy = PolicyService()
        assessor = AssessorService(policy=policy)
        _engine_instance = SuperAgentEngine(
            repository=repo, policy=policy, assessor=assessor, effects=None,
        )
        logger.info("SuperAgentEngine 单例已初始化")
    return _engine_instance


# ============ Pydantic Schema ============

class TicketCreateRequest(BaseModel):
    """手动创建 Ticket —— skip eval，直接 accept。"""
    title: str = Field(..., min_length=1, max_length=500)
    prompt: Optional[str] = Field(None, max_length=10000)
    workspace_id: int
    source: str = Field("manual", description="触发来源")


class TicketBrief(BaseModel):
    """列表视图 — 只返回关键字段。"""
    id: str
    status: str
    title: str
    source: str = "manual"
    created_at: str


class TicketDetail(TicketBrief):
    """详情视图 — 包含 Subscription / Mandate / Assignment 摘要。"""
    intent_evidence: Optional[str] = None
    mandate: Optional[dict] = None
    assignment: Optional[dict] = None


# ============ 端点 ============

@router.get("/health")
async def health(request: Request) -> dict:
    """引擎健康检查 —— 模块状态取自 app.state（缺省 unknown，不造假值）。"""
    state = getattr(request.app, "state", None)

    def _get(attr: str) -> Any:
        return getattr(state, attr, None) if state is not None else None

    # engine —— app.state 优先，回退模块单例（不强制创建，避免无 DB 环境拉起连接）
    engine = _get("superagent_engine") or _engine_instance

    def _running(obj: Any, attr: str) -> str:
        """运行态判定：bool 标志 / asyncio.Task / 任务集合，缺省 unknown。"""
        if obj is None or not hasattr(obj, attr):
            return "unknown"
        flag = getattr(obj, attr)
        if isinstance(flag, bool):
            return "running" if flag else "stopped"
        try:
            return "running" if not flag.done() else "stopped"
        except AttributeError:
            return "running" if bool(flag) else "stopped"

    module_status = {
        "engine": "ok" if engine is not None else "unknown",
        "outbox": "ok" if getattr(engine, "outbox", None) is not None else "unknown",
        "effect_queue": _running(_get("superagent_effect_queue"), "_task"),
        "registry": _running(_get("superagent_registry"), "_poll_tasks"),
        "pipeline": _running(_get("superagent_pipeline"), "_started"),
    }

    return {
        "status": "ok",
        "component": "super-agent-engine",
        "version": "0.2.0",
        "parts": ["intake", "evals", "tickets", "assignments", "replies"],
        "modules": ["repository", "policy", "assessor", "effects", "executor", "tools"],
        "module_status": module_status,
    }


@router.post("/tickets", response_model=TicketBrief, status_code=201)
async def create_ticket(req: TicketCreateRequest) -> TicketBrief:
    """手动创建 Ticket — skip eval，直接 accept。"""
    import shortuuid
    from datetime import datetime

    engine = get_engine()
    repo: SuperAgentRepository = engine.repository

    # 手动创建 trigger → 直接 create_ticket
    trigger_id = shortuuid.uuid()[:12]
    now_iso = datetime.utcnow().isoformat() + "Z"

    with repo.atomic() as db:
        # 创建 trigger（手动来源）
        repo.create_trigger(
            db,
            id=trigger_id,
            workspace_id=req.workspace_id,
            source=req.source,
            ref_id=trigger_id,
            thread_id=req.source,
            kind="manual",
            title=req.title,
            body=req.prompt or "",
            status="accepted",
        )

        # create ticket + mandate + assignment
        ticket_id = engine.tickets.create_ticket(
            trigger_id=trigger_id,
            mandate={
                "title": req.title,
                "strength": "explicit",
                "matched_rules": [{"rule_id": "manual", "reason": "手动创建"}],
                "intent_evidence": f"manual creation · prompt={req.prompt[:100] if req.prompt else ''}",
            },
        )

    with repo.atomic() as db:
        ticket = repo.get_ticket(db, ticket_id)
        if ticket is None:
            raise HTTPException(status_code=500, detail="Ticket creation failed")
        created_at = (
            ticket.created_at.isoformat() + "Z"
            if ticket.created_at else now_iso
        )

    logger.info(
        f"手动创建 Ticket {ticket_id} · workspace={req.workspace_id} · "
        f"title={req.title[:60]}"
    )

    return TicketBrief(
        id=ticket_id,
        status="open",
        title=req.title,
        source=req.source,
        created_at=created_at,
    )


@router.get("/tickets", response_model=list[TicketBrief])
async def list_tickets(
    workspace_id: int = Query(..., description="Workspace ID"),
    status: Optional[str] = Query(None, description="过滤状态"),
    limit: int = Query(20, ge=1, le=100),
) -> list[TicketBrief]:
    """Ticket 列表 —— 按 workspace 过滤。"""
    engine = get_engine()
    repo: SuperAgentRepository = engine.repository

    logger.debug(f"list_tickets ws={workspace_id} status={status} limit={limit}")

    with repo.atomic() as db:
        tickets = repo.list_tickets(
            db, workspace_id=workspace_id, status=status, limit=limit,
        )

    return [
        TicketBrief(
            id=t.id,
            status=t.status,
            title=t.title,
            source="github",  # 实际从 trigger 获取
            created_at=(
                t.created_at.isoformat() + "Z"
                if t.created_at else "1970-01-01T00:00:00Z"
            ),
        )
        for t in tickets
    ]


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: str) -> TicketDetail:
    """Ticket 详情 —— 包含 Subscription / Mandate / Assignment 摘要。"""
    engine = get_engine()
    repo: SuperAgentRepository = engine.repository

    with repo.atomic() as db:
        ticket = repo.get_ticket(db, ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        mandate = repo.get_mandate(db, ticket_id=ticket_id)
        assignment = repo.get_assignment(db, ticket_id=ticket_id)

    return TicketDetail(
        id=ticket.id,
        status=ticket.status,
        title=ticket.title,
        source="github",
        created_at=(
            ticket.created_at.isoformat() + "Z"
            if ticket.created_at else "1970-01-01T00:00:00Z"
        ),
        intent_evidence=ticket.intent_evidence,
        mandate={
            "strength": mandate.strength,
            "policy_version": mandate.policy_version,
            "matched_rules": mandate.matched_rules,
        } if mandate else None,
        assignment={
            "status": assignment.status,
            "executor_session": assignment.executor_session,
            "started_at": (
                assignment.started_at.isoformat() + "Z"
                if assignment.started_at else None
            ),
        } if assignment else None,
    )


@router.get("/events")
async def events(workspace_id: int = Query(...)):
    """SSE 事件流 —— 前端 Feed/Ideas/Goals 订阅。

    契约：event: <name> + data: <json>（双引号）+ \n\n 分隔。
    新连接先收到最近 50 条历史，再收实时推送。
    """
    import asyncio, json, time
    from fastapi.responses import StreamingResponse
    from app.ai.superagent.sse_bus import SSEBus

    bus = SSEBus.instance()
    q = bus.subscribe(maxsize=500)

    async def _stream():
        try:
            # 1. 先推历史
            for evt in bus.replay_history(limit=50):
                yield evt.encode()
            yield f"event: connected\ndata: {json.dumps({'workspace_id': workspace_id})}\n\n"
            # 2. 再推实时（60s 心跳 + 自动重连提示）
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=30)
                    yield evt.encode()
                except asyncio.TimeoutError:
                    yield f": heartbeat {int(time.time())}\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ============ Task 6.6: Source API 路由 ============

# --- Source 配置 Schema（对齐 tasks.md 6.4/6.5 pydantic 定义） ---

class GitHubSourceConfig(BaseModel):
    """GitHub Source 配置 —— 存入 ai_workspace.config.github_source_cfg。"""
    repository: str = Field("", description='"owner/name"')
    gh_cli: str = Field("gh", description="gh 命令路径")
    poll_seconds: int = Field(60, ge=60, le=3600)
    failures_before_error: int = Field(3, ge=1, le=20)
    observe_issues: bool = False
    observe_pulls: bool = False
    observe_comments: bool = False
    observe_ci: bool = False
    ci_branch: str = "main"


class FeishuChatItem(BaseModel):
    chat_id: str = Field(..., pattern=r"^oc_[a-zA-Z0-9]+$")
    name: Optional[str] = None
    listen: Literal["mentions", "all"] = "mentions"


class FeishuSourceConfig(BaseModel):
    """Feishu Source 配置 —— 存入 ai_workspace.config.feishu_source_cfg。"""
    lark_cli: str = Field("lark-cli", description="lark-cli 命令路径")
    chats: list[FeishuChatItem] = []
    direct_messages: bool = True
    other_chats: Literal["none", "mentions"] = "none"
    read_page_size: int = Field(20, ge=1, le=100)
    link_timeout_ms: int = Field(5000, ge=1000, le=30000)

_SOURCE_CONFIG_MODELS = {
    "github": (GitHubSourceConfig, "github_source_cfg"),
    "feishu": (FeishuSourceConfig, "feishu_source_cfg"),
}

# --- SourceRegistry 单例（poll 用，Task 6.6 / b3 共享） ---

_registry_instance = None


def get_registry():
    """延迟初始化 SourceRegistry 单例 —— 按当前 workspace config 构建已配置的 Source。"""
    global _registry_instance
    if _registry_instance is None:
        from app.ai.superagent.sources.registry import SourceRegistry
        from app.ai.superagent.sources.github import GitHubSource
        from app.ai.superagent.sources.feishu import FeishuSource, FeishuChat as FeishuChatCfg
        from app.ai.superagent.sources.http_source import HTTPSource
        from app.ai.superagent.sources.manual_source import ManualSource
        _registry_instance = SourceRegistry()
        cfg = _read_workspace_source_cfgs()
        if cfg.get("github_source_cfg", {}).get("repository"):
            g = GitHubSource(**{**GitHubSourceConfig(**cfg["github_source_cfg"]).model_dump()})
            _registry_instance.register("github", g)
        feishu_cfg = cfg.get("feishu_source_cfg", {})
        if feishu_cfg.get("chats"):
            fc = FeishuSourceConfig(**feishu_cfg)
            chats = [FeishuChatCfg(chat_id=c.chat_id, name=c.name, listen=c.listen) for c in fc.chats]
            _registry_instance.register("feishu", FeishuSource(
                lark_cli_path=fc.lark_cli, direct_messages=fc.direct_messages,
                other_chats=fc.other_chats, read_page_size=fc.read_page_size,
                link_timeout_ms=fc.link_timeout_ms, chats=chats,
            ))
        # http / manual —— 极简内置 Source（内存队列，始终注册）
        _registry_instance.register("http", HTTPSource())
        _registry_instance.register("manual", ManualSource())
        logger.info(f"SourceRegistry 单例已初始化 · sources={list(_registry_instance.all().keys())}")
    return _registry_instance


def _read_workspace_source_cfgs() -> dict:
    """读 ai_workspace.config 中的 source 配置片段（默认 workspace_id=1）。"""
    from app.db.database import SessionLocal
    from app.models.ai.ai_workspace import AiWorkspace
    try:
        db = SessionLocal()
        try:
            ws = db.get(AiWorkspace, 1)
            cfg = (ws.config or {}) if ws else {}
        finally:
            db.close()
        return {
            "github_source_cfg": cfg.get("github_source_cfg", {}) or {},
            "feishu_source_cfg": cfg.get("feishu_source_cfg", {}) or {},
        }
    except Exception as e:
        logger.warning(f"读取 workspace source 配置失败（用默认值）: {e}")
        return {"github_source_cfg": {}, "feishu_source_cfg": {}}


def _write_workspace_source_cfg(key: str, value: dict) -> None:
    """写 ai_workspace.config 中的 source 配置片段。"""
    from app.db.database import SessionLocal
    from app.models.ai.ai_workspace import AiWorkspace
    db = SessionLocal()
    try:
        ws = db.get(AiWorkspace, 1)
        if ws is None:
            raise HTTPException(status_code=404, detail="workspace 1 不存在")
        cfg = dict(ws.config or {})
        cfg[key] = value
        ws.config = cfg
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"写入配置失败: {e}")
    finally:
        db.close()


class SourceBrief(BaseModel):
    kind: str
    status: str
    failures: int = 0
    last_error: Optional[str] = None
    next_poll: Optional[str] = None
    registered: bool = True


@router.get("/sources", response_model=list[SourceBrief])
async def list_sources() -> list[SourceBrief]:
    """Source 列表 —— registry 内已注册 Source 的 health board + 未注册 kind 的占位。"""
    registry = get_registry()
    items: list[SourceBrief] = []
    for h in registry.health_board():
        items.append(SourceBrief(
            kind=h.get("kind", "?"), status=h.get("status", "unknown"),
            failures=h.get("failures", 0), last_error=h.get("last_error"),
            next_poll=h.get("next_poll"),
        ))
    registered = set(registry.all().keys())
    for kind in ("github", "feishu", "http", "manual"):
        if kind not in registered:
            items.append(SourceBrief(kind=kind, status="unregistered", registered=False))
    return items


@router.get("/sources/{kind}/config")
async def get_source_config(kind: str) -> dict:
    """Source 配置 —— 返回 JSON Schema + 当前生效值。"""
    if kind not in _SOURCE_CONFIG_MODELS:
        raise HTTPException(status_code=404, detail=f"未知 Source kind: {kind}")
    model, cfg_key = _SOURCE_CONFIG_MODELS[kind]
    cfgs = _read_workspace_source_cfgs()
    return {
        "kind": kind,
        "schema": model.model_json_schema(),
        "config": cfgs.get(cfg_key, {}),
        "config_key": cfg_key,
    }


@router.put("/sources/{kind}/config")
async def put_source_config(kind: str, payload: dict) -> dict:
    """更新 Source 配置 —— 校验后写入 ai_workspace.config；registry 内实例热替换。"""
    if kind not in _SOURCE_CONFIG_MODELS:
        raise HTTPException(status_code=404, detail=f"未知 Source kind: {kind}")
    model, cfg_key = _SOURCE_CONFIG_MODELS[kind]
    try:
        validated = model(**(payload or {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"配置校验失败: {e}")
    _write_workspace_source_cfg(cfg_key, validated.model_dump())
    # 热替换 registry 内实例（下次 poll 生效）
    global _registry_instance
    _registry_instance = None  # 简单起见：直接重建（poll loop 由 startup 层重启）
    logger.info(f"Source 配置已更新 · kind={kind}")
    return {"kind": kind, "config": validated.model_dump(), "updated": True}


@router.get("/threads")
async def list_threads(
    workspace_id: int = Query(...),
    source: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Thread 列表 —— 按 workspace（可选 source）过滤。"""
    from app.models.superagent import SuperAgentThread
    engine = get_engine()
    repo: SuperAgentRepository = engine.repository
    with repo.atomic() as db:
        stmt = select(SuperAgentThread).where(SuperAgentThread.workspace_id == workspace_id)
        if source:
            stmt = stmt.where(SuperAgentThread.source == source)
        stmt = stmt.order_by(SuperAgentThread.updated_at.desc()).limit(limit)
        threads = list(db.execute(stmt).scalars())
    return [
        {
            "id": t.id, "source": t.source, "ref_id": t.ref_id,
            "title": t.title, "url": t.url, "status": t.status,
            "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else None,
        }
        for t in threads
    ]


class SubscriptionCreateRequest(BaseModel):
    thread_id: str = Field(..., min_length=1)
    kind: Literal["following", "context_only"] = "context_only"


@router.get("/tickets/{ticket_id}/subscriptions")
async def list_ticket_subscriptions(ticket_id: str) -> list[dict]:
    """Ticket 的 Subscription 列表 —— 含 Thread 摘要。"""
    engine = get_engine()
    repo: SuperAgentRepository = engine.repository
    from app.models.superagent import SuperAgentThread
    with repo.atomic() as db:
        ticket = repo.get_ticket(db, ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        subs = repo.list_subscriptions(db, ticket_id=ticket_id)
        thread_ids = [s.thread_id for s in subs]
        threads = {}
        if thread_ids:
            for t in db.execute(
                select(SuperAgentThread).where(SuperAgentThread.id.in_(thread_ids))
            ).scalars():
                threads[t.id] = t
    return [
        {
            "id": s.id, "ticket_id": s.ticket_id, "thread_id": s.thread_id,
            "kind": s.kind,
            "thread": {
                "id": threads[s.thread_id].id,
                "source": threads[s.thread_id].source,
                "title": threads[s.thread_id].title,
                "url": threads[s.thread_id].url,
                "status": threads[s.thread_id].status,
            } if s.thread_id in threads else None,
            "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
        }
        for s in subs
    ]


@router.post("/tickets/{ticket_id}/subscriptions", status_code=201)
async def add_ticket_subscription(ticket_id: str, req: SubscriptionCreateRequest) -> dict:
    """添加 Subscription —— Task 6.6 规定此处 kind=context_only（仅上下文）。"""
    engine = get_engine()
    repo: SuperAgentRepository = engine.repository
    from app.models.superagent import SuperAgentThread
    with repo.atomic() as db:
        ticket = repo.get_ticket(db, ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        thread = db.get(SuperAgentThread, req.thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail=f"Thread {req.thread_id} not found")
        sub = repo.upsert_subscription(
            db, ticket_id=ticket_id, thread_id=req.thread_id,
            workspace_id=ticket.workspace_id, kind=req.kind,
        )
        if sub is None:
            raise HTTPException(status_code=409, detail="Subscription 已存在")
    logger.info(f"Subscription 添加 · ticket={ticket_id} · thread={req.thread_id} · kind={req.kind}")
    return {
        "ticket_id": ticket_id, "thread_id": req.thread_id,
        "kind": req.kind, "created": True,
    }
