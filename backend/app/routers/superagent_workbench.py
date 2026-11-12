"""SuperAgent 工作台路由 —— Feed / Ideas / Goals / Chat（Task 4.6）。

端点清单（prefix=/super-agent，由 router_registry 叠加 /api/v1）：
  GET  /feed?workspace_id&kind            — Feed 列表（≤200）
  POST /feed                              — 手动发布 Feed
  POST /feed/{id}/read                    — 标记已读
  GET  /ideas                             — Idea 列表
  POST /ideas                             — 手动创建 Idea
  POST /ideas/{id}/pin                    — 置顶切换
  POST /ideas/refresh                     — AI 批量生成 Idea（回落 STARTER）
  GET  /goals                             — Goal 列表
  POST /goals                             — 创建 Goal
  GET  /goals/{id}                        — Goal 详情（drawer）
  PATCH /goals/{id}                       — 更新状态
  POST /goals/{id}/steps/{idx}/toggle     — 勾选/取消步骤
  POST /goals/{id}/steps/{idx}/skip       — 跳过步骤
  POST /goals/{id}/proposals              — Agent 提议（L4）
  POST /goals/{id}/proposals/{idx}/accept — 接受提议（+step, version+1）
  POST /goals/{id}/proposals/{idx}/dismiss— 忽略提议
  POST /goals/{id}/notes                  — 追加进展笔记
  GET  /chat/sessions                     — 会话列表
  POST /chat/sessions                     — 新建会话
  GET  /chat/sessions/{id}                — 会话消息
  POST /chat/send                         — 发送消息（SSE 流式）
  POST /chat/abort                        — 中断 run
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.ai.superagent.workbench import get_chat, get_workbench

router = APIRouter(prefix="/super-agent", tags=["SuperAgent 工作台"])


# ============ Pydantic Schema ============

class FeedPublishRequest(BaseModel):
    workspace_id: int
    kind: str = Field("system", description="system/ai_batch/reminder/approval/goal_updated")
    title: str = Field(..., min_length=1, max_length=300)
    body: str = ""
    prompt: Optional[str] = None
    goal_id: Optional[str] = None
    quiet: bool = True


class IdeaCreateRequest(BaseModel):
    workspace_id: int
    emo: str = "💡"
    pitch: str = Field(..., min_length=1, max_length=300)
    detail: str = ""
    kind: str = Field("chat", description="chat/goal/routine")
    prompt: Optional[str] = None


class IdeaRefreshRequest(BaseModel):
    workspace_id: int
    count: int = Field(3, ge=1, le=5)


class GoalCreateRequest(BaseModel):
    workspace_id: int
    title: str = Field(..., min_length=1, max_length=300)
    context: str = Field("", max_length=300)
    steps: list[str] = []
    source: str = "manual"
    cron: Optional[str] = None
    due: Optional[str] = None


class GoalPatchRequest(BaseModel):
    status: str = Field(..., description="active/paused/done/cancelled")


class NoteRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class SessionCreateRequest(BaseModel):
    workspace_id: int
    title: str = "新对话"


class ChatSendRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=5000)
    run_id: str


class ChatAbortRequest(BaseModel):
    run_id: str


# ============ Feed ============

@router.get("/feed")
async def list_feed(
    workspace_id: int = Query(...),
    kind: Optional[str] = Query(None),
) -> list[dict]:
    """Feed 列表（≤200 条，倒序）。"""
    return get_workbench().list_feed(workspace_id, kind=kind)


@router.post("/feed", status_code=201)
async def publish_feed(req: FeedPublishRequest) -> dict:
    return {"id": get_workbench().publish_feed(
        req.workspace_id, req.kind, req.title, body=req.body,
        prompt=req.prompt, goal_id=req.goal_id, quiet=req.quiet,
    )}


@router.post("/feed/{post_id}/read")
async def mark_feed_read(post_id: int, workspace_id: int = Query(...)) -> dict:
    if not get_workbench().mark_feed_read(post_id, workspace_id):
        raise HTTPException(status_code=404, detail=f"Feed post {post_id} not found")
    return {"ok": True}


@router.get("/feed/stream")
async def feed_stream(workspace_id: int = Query(...)):
    """Feed SSE 长连接 —— feed_post / proposal_created / goal_updated。

    EventSource 仅支持 GET；历史由 REST listFeed 补齐，这里只推实时。
    """
    import asyncio, time
    from app.ai.superagent.sse_bus import SSEBus

    bus = SSEBus.instance()
    q = bus.subscribe(maxsize=500)

    async def _stream():
        try:
            yield f"event: connected\ndata: {json.dumps({'workspace_id': workspace_id})}\n\n"
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=30)
                    if evt.event in {"feed_post", "proposal_created", "goal_updated"}:
                        yield evt.encode()
                except asyncio.TimeoutError:
                    yield f": heartbeat {int(time.time())}\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ============ Ideas ============

@router.get("/ideas")
async def list_ideas(workspace_id: int = Query(...)) -> list[dict]:
    return get_workbench().list_ideas(workspace_id)


@router.post("/ideas", status_code=201)
async def create_idea(req: IdeaCreateRequest) -> dict:
    idea = get_workbench().create_idea(
        req.workspace_id, req.emo, req.pitch, detail=req.detail,
        kind=req.kind, prompt=req.prompt, src="manual",
    )
    if idea is None:
        raise HTTPException(status_code=409, detail="重复的 Idea（fingerprint 去重）")
    return idea


@router.post("/ideas/{idea_id}/pin")
async def pin_idea(idea_id: int, workspace_id: int = Query(...)) -> dict:
    if not get_workbench().pin_idea(idea_id, workspace_id):
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return {"ok": True}


@router.post("/ideas/refresh")
async def refresh_ideas(req: IdeaRefreshRequest) -> dict:
    created = await get_workbench().refresh_ideas(req.workspace_id, req.count)
    return {"created": created, "count": len(created)}


# ============ Goals ============

@router.get("/goals")
async def list_goals(workspace_id: int = Query(...)) -> list[dict]:
    return get_workbench().list_goals(workspace_id)


@router.post("/goals", status_code=201)
async def create_goal(req: GoalCreateRequest) -> dict:
    return get_workbench().create_goal(
        req.workspace_id, req.title, context=req.context, steps=req.steps,
        source=req.source, cron=req.cron, due=req.due,
    )


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().get_goal(goal_id, workspace_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    return goal


@router.patch("/goals/{goal_id}")
async def patch_goal(goal_id: str, req: GoalPatchRequest, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().patch_goal(goal_id, workspace_id, req.status)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found 或状态非法")
    return goal


@router.post("/goals/{goal_id}/steps/{step_idx}/toggle")
async def toggle_step(goal_id: str, step_idx: int, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().toggle_step(goal_id, workspace_id, step_idx)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} / step {step_idx} not found")
    return goal


@router.post("/goals/{goal_id}/steps/{step_idx}/skip")
async def skip_step(goal_id: str, step_idx: int, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().skip_step(goal_id, workspace_id, step_idx)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} / step {step_idx} not found")
    return goal


@router.post("/goals/{goal_id}/proposals")
async def propose(goal_id: str, workspace_id: int = Query(...)) -> dict:
    goal = await get_workbench().propose(goal_id, workspace_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    return goal


@router.post("/goals/{goal_id}/proposals/{proposal_idx}/accept")
async def accept_proposal(goal_id: str, proposal_idx: int, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().accept_proposal(goal_id, workspace_id, proposal_idx)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_idx} 不可接受（不存在或已处理）")
    return goal


@router.post("/goals/{goal_id}/proposals/{proposal_idx}/dismiss")
async def dismiss_proposal(goal_id: str, proposal_idx: int, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().dismiss_proposal(goal_id, workspace_id, proposal_idx)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_idx} 不可忽略（不存在或已处理）")
    return goal


@router.post("/goals/{goal_id}/notes")
async def add_note(goal_id: str, req: NoteRequest, workspace_id: int = Query(...)) -> dict:
    goal = get_workbench().add_note(goal_id, workspace_id, req.text)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    return goal


# ============ Chat ============

@router.get("/chat/sessions")
async def list_chat_sessions(workspace_id: int = Query(...)) -> list[dict]:
    return get_chat().list_sessions(workspace_id)


@router.post("/chat/sessions", status_code=201)
async def create_chat_session(req: SessionCreateRequest) -> dict:
    return get_chat().create_session(req.workspace_id, req.title)


@router.get("/chat/sessions/{session_id}")
async def get_chat_session(session_id: str, workspace_id: int = Query(...)) -> dict:
    session = get_chat().get_session(session_id, workspace_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")
    return session


@router.post("/chat/send")
async def chat_send(req: ChatSendRequest) -> StreamingResponse:
    """发送消息 —— SSE 流（text_delta / done / interrupted / error）。"""
    chat = get_chat()
    if chat.get_session(req.session_id) is None:
        raise HTTPException(status_code=404, detail=f"Chat session {req.session_id} not found")
    logger.info(f"chat_send · session={req.session_id} · run={req.run_id}")

    async def _stream():
        async for chunk in chat.stream_reply(req.session_id, req.message, req.run_id):
            yield chunk

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/chat/abort")
async def chat_abort(req: ChatAbortRequest) -> dict:
    ok = get_chat().abort(req.run_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")
    return {"ok": True}
