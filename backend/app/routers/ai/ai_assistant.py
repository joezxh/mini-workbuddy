"""AI 助手相关接口（示例提问推荐等）。

路由前缀：/api/v1/ai-assistant

示例提问推荐流程：
1. 前端从「当前已打开会话」中提取关键词（实体 / 领域词 / 金额 / 日期等）；
2. 自动请求本接口，携带这些关键词；
3. 服务端在示例提问题库上做「关键词匹配检索」，按重合度打分排序返回最相关的示例提问；
4. 若无关键词或未命中，则回退到默认题库（与原静态示例保持一致）。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user
from app.middleware.sqlbot_client import sqlbot_client
from app.models.ai.ai_chat import AiChatMessage, AiChatSession
from app.models.sys.sys_user import SysUser
from app.services.ai.ai_chat_service import AiChatService
from app.schemas.ai.ai_assistant import (
    ExampleQuestionRecommendRequest,
    ExampleQuestionRecommendResponse,
)

router = APIRouter(prefix="/api/v1/ai-assistant", tags=["AI助手"])


# ── 默认示例提问题库（原静态示例，作为回退与匹配数据源）─────────────────────────
# 每条含：question 示例提问文本；keywords 匹配标签；session_types 适用场景（空=通用）。
_EXAMPLE_QUESTION_BANK: List[dict] = [
    {
        "question": "请帮我总结这段会议记录的核心要点，并列出待办事项。",
        "keywords": ["总结", "会议", "要点", "待办"],
        "session_types": ["general"],
    },
    {
        "question": "帮我把这份销售数据按地区做汇总，并用图表展示趋势。",
        "keywords": ["销售", "数据", "汇总", "图表", "趋势"],
        "session_types": ["general", "data"],
    },
    {
        "question": "我想了解最近行业政策的变化，帮我检索并整理要点。",
        "keywords": ["政策", "行业", "检索", "整理"],
        "session_types": ["general"],
    },
    {
        "question": "请为这份产品文档生成一段简明的使用说明。",
        "keywords": ["产品", "文档", "说明", "生成"],
        "session_types": ["general"],
    },
    {
        "question": "帮我起草一封委婉拒绝合作邀约的邮件。",
        "keywords": ["邮件", "起草", "拒绝", "合作"],
        "session_types": ["general"],
    },
    # ── 金融证券类（首次进入以「金融证券」为关键词检索时命中）────────────────────
    {
        "question": "我想咨询股票配资纠纷：对方平台在行情波动时强制平仓后拒不退还保证金，我该如何维权追回损失？",
        "keywords": ["金融证券", "股票", "配资", "期货", "强制平仓", "维权", "纠纷"],
        "session_types": ["finance", "general"],
    },
    {
        "question": "在银行购买了某理财产品，销售人员口头承诺保本保收益，结果到期大幅亏损，能否要求银行赔偿？",
        "keywords": ["金融证券", "理财", "银行", "基金", "适当性", "虚假陈述", "赔偿"],
        "session_types": ["finance", "general"],
    },
    {
        "question": "上市公司因虚假陈述被处罚，我在此期间买入其股票产生亏损，可以索赔吗？诉讼时效与索赔路径怎么算？",
        "keywords": ["金融证券", "股票", "证券", "虚假陈述", "内幕交易", "索赔"],
        "session_types": ["finance", "general"],
    },
    {
        "question": "朋友推荐我加杠杆做期货交易，亏损后交易平台跑路，投入的资金能否追回？如何收集证据？",
        "keywords": ["金融证券", "期货", "杠杆", "基金", "维权", "证据"],
        "session_types": ["finance", "general"],
    },
    {
        "question": "基金定投持续亏损，销售机构未做风险测评与适当性匹配，我能否向机构主张赔偿？",
        "keywords": ["金融证券", "基金", "理财", "适当性", "赔偿", "风险测评"],
        "session_types": ["finance", "general"],
    },
]


def _score_item(item: dict, keywords: List[str], session_type: Optional[str]) -> int:
    """计算题库条目与输入关键词的重合度得分。"""
    tags = item.get("keywords") or []
    text = item.get("question") or ""
    score = 0
    for kw in keywords:
        if not kw:
            continue
        if kw in tags:
            score += 3  # 标签精确命中权重更高
        elif kw in text:
            score += 1  # 文本包含命中
    # 场景匹配加权
    types = item.get("session_types") or []
    if session_type and types and session_type in types:
        score += 2
    return score


@router.post("/example-questions/recommend", response_model=ExampleQuestionRecommendResponse)
def recommend_example_questions(req: ExampleQuestionRecommendRequest):
    """根据会话关键词进行匹配检索，返回最相关的示例提问。"""
    keywords = [k.strip() for k in (req.keywords or []) if k and k.strip()]
    limit = max(1, min(int(req.limit or 3), 10))

    if not keywords:
        # 无关键词：回退默认题库（取前 limit 条）
        return ExampleQuestionRecommendResponse(
            questions=[q["question"] for q in _EXAMPLE_QUESTION_BANK[:limit]],
            matched=False,
            source_keywords=[],
        )

    scored = [
        (item, _score_item(item, keywords, req.session_type))
        for item in _EXAMPLE_QUESTION_BANK
    ]
    # 仅保留有命中的条目，按得分降序
    matched = [(item, s) for item, s in scored if s > 0]
    matched.sort(key=lambda x: x[1], reverse=True)

    if not matched:
        # 未命中任何关键词：回退默认题库，保持原示例提问不变
        return ExampleQuestionRecommendResponse(
            questions=[q["question"] for q in _EXAMPLE_QUESTION_BANK[:limit]],
            matched=False,
            source_keywords=keywords,
        )

    questions = [item["question"] for item, _ in matched[:limit]]
    return ExampleQuestionRecommendResponse(
        questions=questions,
        matched=True,
        source_keywords=keywords,
    )


# ── 请求体 Schema（用户端）──────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    session_title: Optional[str] = None
    session_type: str = "general"


class UpdateSessionRequest(BaseModel):
    session_title: Optional[str] = None
    session_type: Optional[str] = None  # 会话内切换模式(∈ context_policies.SESSION_MODES)


class PinSessionRequest(BaseModel):
    is_pinned: bool


class BatchDeleteRequest(BaseModel):
    ids: List[int]


# ── 序列化辅助（与 ai_chat.py 管理端保持一致）───────────────────────────────────

def _session_to_dict(s: AiChatSession) -> dict:
    return {
        "session_id": s.session_id,
        "user_id": s.user_id,
        "session_title": s.session_title,
        "session_type": s.session_type,
        "status": s.status,
        "message_count": s.message_count,
        "is_pinned": s.is_pinned,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _message_to_dict(m: AiChatMessage) -> dict:
    return {
        "message_id": m.message_id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "message_type": m.message_type,
        "extra_data": m.extra_data,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _get_owned_session(svc: AiChatService, session_id: int, user_id: int) -> AiChatSession:
    """获取属于当前用户的会话；缺失或越权均按 404 处理。"""
    session = svc.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


# ── 用户端会话接口（仅能操作自己的会话）────────────────────────────────────────

@router.get("/sessions")
def list_my_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """当前用户的会话列表（置顶优先、按更新时间倒序）"""
    svc = AiChatService(db)
    total, items = svc.get_user_sessions(
        user_id=current_user.user_id, page=page, page_size=page_size, status=status
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_session_to_dict(s) for s in items],
    }


@router.post("/sessions", status_code=200)
def create_my_session(
    body: CreateSessionRequest = CreateSessionRequest(),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """新建会话"""
    svc = AiChatService(db)
    session = svc.create_session(
        user_id=current_user.user_id,
        session_title=body.session_title,
        session_type=body.session_type,
    )
    return _session_to_dict(session)


@router.get("/sessions/{session_id}")
def get_my_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiChatService(db)
    session = _get_owned_session(svc, session_id, current_user.user_id)
    return _session_to_dict(session)


@router.put("/sessions/{session_id}")
def update_my_session(
    session_id: int,
    body: UpdateSessionRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新会话标题或切换模式。

    会话内切换模式(session_type)时,消息与 L2 上下文天然延续——
    L2 条目按 source_mode 标记来源模式,跨模式可读性由
    is_cross_mode_accessible 控制。
    """
    svc = AiChatService(db)
    session = _get_owned_session(svc, session_id, current_user.user_id)
    changed = False
    if body.session_type:
        from app.core.context_policies import SESSION_MODES
        if body.session_type not in SESSION_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"非法会话模式: {body.session_type},可选值: {', '.join(SESSION_MODES)}",
            )
        session.session_type = body.session_type
        changed = True
    if body.session_title:
        session.session_title = body.session_title
        changed = True
    if changed:
        db.commit()
        db.refresh(session)
    return _session_to_dict(session)


@router.delete("/sessions/{session_id}")
def delete_my_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiChatService(db)
    _get_owned_session(svc, session_id, current_user.user_id)
    svc.delete_session(session_id)
    return {"message": "删除成功"}


@router.post("/sessions/{session_id}/pin")
def pin_my_session(
    session_id: int,
    body: PinSessionRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiChatService(db)
    _get_owned_session(svc, session_id, current_user.user_id)
    session = svc.pin_session(session_id, body.is_pinned)
    return _session_to_dict(session)


@router.post("/sessions/batch-delete")
def batch_delete_my_sessions(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """批量删除（仅限当前用户拥有的会话）"""
    svc = AiChatService(db)
    owned_ids = [
        s.session_id
        for s in db.query(AiChatSession).filter(
            AiChatSession.session_id.in_(body.ids or []),
            AiChatSession.user_id == current_user.user_id,
        ).all()
    ]
    count = svc.batch_delete_sessions(owned_ids)
    return {"deleted": count, "message": f"已删除 {count} 个会话"}


@router.get("/sessions/{session_id}/messages")
def list_my_session_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiChatService(db)
    _get_owned_session(svc, session_id, current_user.user_id)
    total, items = svc.get_session_messages(session_id=session_id, page=page, page_size=page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_message_to_dict(m) for m in items],
    }


@router.delete("/sessions/{session_id}/messages")
def clear_my_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AiChatService(db)
    _get_owned_session(svc, session_id, current_user.user_id)
    count = svc.delete_session_messages(session_id)
    return {"deleted": count, "message": f"已清空 {count} 条消息"}


# ── SQLBot 数据源（代理到独立部署的 SQLBot 服务，可配置，不校验连通性）───────────

@router.get("/chat/sqlbot/datasources")
async def list_sqlbot_datasources(
    refresh: bool = Query(False, description="是否强制刷新缓存"),
    _: SysUser = Depends(get_current_user),
):
    """获取 SQLBot 可用数据源列表（代理到远程 SQLBot 服务，带 10 分钟缓存）。"""
    try:
        raw = await sqlbot_client.list_datasources(use_cache=not refresh)
    except Exception as exc:
        # SQLBot 服务可能未配置/未连通：降级返回空列表，不阻断页面
        from loguru import logger
        logger.warning(f"获取 SQLBot 数据源列表失败: {exc}")
        return {"datasources": []}

    datasources = [
        {
            "id": ds.get("id"),
            "name": ds.get("name") or ds.get("title"),
            "db_type": ds.get("db_type") or ds.get("type"),
        }
        for ds in (raw if isinstance(raw, list) else [])
    ]
    return {"datasources": datasources}



