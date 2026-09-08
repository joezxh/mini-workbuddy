"""AI Agent 统一路由 — AgentScope 原生实现

提供统一执行入口、会话管理、执行状态查询。
使用 AgentFactory + SSEBridge 替代原 Gateway/Engine 架构。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.deps import get_current_user_or_api_key, get_current_user
from app.models.sys.sys_user import SysUser
from app.services.ai.ai_chat_service import AiChatService
from app.ai.agent_factory import AgentFactory
from app.ai.sse_bridge import SSEBridge, create_done_event, create_error_event

router = APIRouter(prefix="/ai-agent", tags=["AI Agent"])


# ── 依赖注入 ──────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 请求/响应 Schema ──────────────────────────────────

class ChatRequest(BaseModel):
    """统一聊天请求"""
    message: str
    session_id: Optional[int] = None
    session_type: str = "general"
    file_ids: List[str] = []
    file_db_ids: List[int] = []
    model_id: Optional[int] = None
    workspace_id: Optional[int] = None
    # 智能体模式
    agent_id: Optional[int] = None
    agent_code: Optional[str] = None
    # 团队模式
    team_id: Optional[int] = None
    team_code: Optional[str] = None
    # 技能模式
    skill: Optional[dict] = None


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    session_type: str = "agent"


class SessionResponse(BaseModel):
    session_id: int
    title: Optional[str] = None
    session_type: str


# ── 辅助函数 ──────────────────────────────────────────

def _ensure_system_user(db: Session) -> int:
    """确保 sys_user 表中存在 API 系统用户"""
    from app.models.sys.sys_user import SysUser as _User
    system_user = db.query(_User).filter(_User.username == "__api_system__").first()
    if system_user:
        return system_user.user_id
    new_user = _User(
        username="__api_system__",
        password_hash="!api-system-no-login",
        real_name="[系统] API对接用户",
        status="active",
        is_admin=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user.user_id


def _get_user_id(user: Optional[SysUser], db: Session) -> int:
    if user:
        return user.user_id
    return _ensure_system_user(db)


# ── 统一聊天端点 ──────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[SysUser] = Depends(get_current_user_or_api_key),
):
    """AI 对话统一入口（SSE 流式）

    根据 session_type 创建对应 AgentScope Agent，流式返回回复。
    支持的模式：general / thinking / deep_research / skill / agent / team
    """
    message_text = req.message.strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="消息不能为空")

    session_type = req.session_type or "general"
    uid = _get_user_id(current_user, db)
    svc = AiChatService(db)

    # 获取或创建会话
    if req.session_id:
        session = svc.get_session(req.session_id)
        if not session or (current_user and session.user_id != uid):
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        session = svc.create_session(user_id=uid, session_type=session_type)

    session_id = session.session_id

    # 处理文件关联
    db_file_ids: list[int] = list(req.file_db_ids) if req.file_db_ids else []
    if not db_file_ids and req.file_ids:
        from app.models.sys.sys_infra_file import SysInfraFile
        for fid in req.file_ids:
            fid_str = str(fid)
            record = db.query(SysInfraFile).filter(
                SysInfraFile.path.ilike(f"%/{fid_str}.%"),
                SysInfraFile.deleted == '0',
            ).first()
            if record:
                db_file_ids.append(record.id)

    # 保存用户消息
    user_extra_data: dict = {}
    if req.file_ids:
        user_extra_data["file_ids"] = req.file_ids
    if db_file_ids:
        user_extra_data["file_db_ids"] = db_file_ids
    svc.add_message(
        session_id=session_id,
        role="user",
        content=message_text,
        extra_data=user_extra_data or None,
        file_id=db_file_ids[0] if db_file_ids else None,
    )
    svc.auto_title_session(session_id, message_text)

    # 构建 Agent 配置
    agent_config = _build_agent_config(req, session_type, db)

    # 双入口：execution_mode="plan" 自动映射为 react session_type
    if req.agent_id and agent_config.get("execution_mode") == "plan":
        session_type = "react"

    async def event_generator():
        """SSE 事件生成器"""
        try:
            # 创建 Agent
            factory = AgentFactory(db)
            agent = factory.create_agent(session_type, agent_config)

            # 创建用户消息
            from agentscope.message import UserMsg
            user_msg = UserMsg(content=message_text)

            # 通过 SSEBridge 流式输出
            bridge = SSEBridge()
            async for sse_event in bridge.stream_agent_reply(agent, user_msg):
                yield sse_event

            # 保存助手回复（简化：实际应从事件流中收集完整内容）
            yield create_done_event()

        except Exception as e:
            logger.error(f"Agent 执行失败: {e}")
            yield create_error_event(str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_agent_config(req: ChatRequest, session_type: str, db: Session) -> dict:
    """根据请求构建 Agent 配置"""
    config = {
        "name": "助手",
        "model_id": "default",
        "sys_prompt": "",
        "tools": [],
    }

    # 如果指定了模型 ID，从数据库获取
    if req.model_id:
        from app.models.ai.ai_api_key import AiChatModel
        model = db.query(AiChatModel).filter(AiChatModel.id == req.model_id).first()
        if model:
            config["model_id"] = model.model_name
            config["model_id_db"] = req.model_id  # 数字 ID 供 Research/Skill/Team Agent 使用

    # 如果指定了 Agent，从 agent_config 表读取人设和配置
    if req.agent_id:
        from app.models.agent.agent_config import AgentConfig
        agent_cfg = db.query(AgentConfig).filter(
            AgentConfig.id == req.agent_id
        ).first()
        if agent_cfg:
            config["name"] = agent_cfg.name or "助手"
            config["sys_prompt"] = agent_cfg.system_prompt or ""
            config["tools"] = agent_cfg.tools or []
            config["execution_mode"] = agent_cfg.execution_mode or "llm"
            config["react_config"] = agent_cfg.react_config or {}
            config["skills"] = agent_cfg.skills or []

    # 团队模式：传递 team_id
    if req.team_id and session_type == "team":
        config["team_id"] = req.team_id

    # 技能模式：传递 skill 配置
    if req.skill and session_type == "skill":
        config["skill"] = req.skill

    return config


# ── 会话管理 ──────────────────────────────────────────

@router.post("/session", response_model=SessionResponse)
async def create_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建新会话"""
    svc = AiChatService(db)
    session = svc.create_session(
        user_id=current_user.user_id,
        session_type=req.session_type,
        title=req.title,
    )
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        session_type=session.session_type,
    )


@router.get("/sessions")
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取用户会话列表"""
    svc = AiChatService(db)
    sessions = svc.list_sessions(
        user_id=current_user.user_id,
        skip=skip,
        limit=limit,
        session_type=session_type,
    )
    return [
        {
            "session_id": s.session_id,
            "title": s.title,
            "session_type": s.session_type,
            "created_at": str(s.created_at) if s.created_at else None,
            "updated_at": str(s.updated_at) if s.updated_at else None,
        }
        for s in sessions
    ]


@router.get("/session/{session_id}/messages")
async def get_messages(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取会话消息列表"""
    svc = AiChatService(db)
    session = svc.get_session(session_id)
    if not session or session.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = svc.list_messages(session_id=session_id, skip=skip, limit=limit)
    return [
        {
            "message_id": m.message_id,
            "role": m.role,
            "content": m.content,
            "tool_calls": m.tool_calls,
            "tool_results": m.tool_results,
            "created_at": str(m.created_at) if m.created_at else None,
        }
        for m in messages
    ]


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除会话"""
    svc = AiChatService(db)
    session = svc.get_session(session_id)
    if not session or session.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    svc.delete_session(session_id)
    return {"message": "会话已删除"}
