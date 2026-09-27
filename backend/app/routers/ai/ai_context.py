"""
AI Context Router - Multi-layer context management endpoints

Provides RESTful API for:
- Context statistics retrieval (T1.4 Endpoint A)
- Isolated context retrieval (T1.4 Endpoint B)
- Context compaction triggering (T1.4 Endpoint C)
- Cross-mode context retrieval (PR-2 Task 8):
    POST /entries, POST /breakdown, GET /strategies

Dependencies:
- Consumes: ContextManager (from T1.3), Mem0Service (from T1.2),
            STRATEGY_TABLE (PR-1 cross_mode_recorder)
- Produces: Pydantic-validated JSON responses
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.db.database import SessionLocal
from app.deps import get_current_user
from app.ai.context_manager import ContextManager
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

# --- Request/Response Schemas ---

class ContextStatsRequest(BaseModel):
    """Query parameters for stats endpoint"""
    mode: str | None = Field(
        None,
        description="Filter by specific mode (e.g., 'dify', 'sqlbot', 'agentscope')"
    )
    include_mem0_stats: bool = Field(True, description="Include Mem0 statistics")


class BatchContextStatsRequest(BaseModel):
    """Batch stats query parameters"""
    session_ids: list[str | int] = Field(..., description="List of session IDs")


class ContextStatsResponse(BaseModel):
    """Statistics response per session"""
    session_id: int = Field(..., description="Session ID")
    total_tokens: int = Field(0, description="Total token usage")
    message_counts: dict = Field(default_factory=dict, description="Message counts by layer")
    vector_store_messages: int = Field(0, description="Mem0 vector store messages")
    shared_context_count: int = Field(0, description="Shared context entries")
    last_compaction_time: str | None = Field(None, description="Last compaction timestamp")
    computed_at: str = Field(..., description="ISO timestamp")


class ContextRetrievalRequest(BaseModel):
    """Retrieval configuration"""
    limit: int = Field(10, ge=1, le=100, description="Max entries to retrieve")
    enable_mem0_retrieval: bool = Field(False, description="Enable Mem0 retrieval")
    mem0_limit: int = Field(5, ge=1, le=20, description="Mem0 memories to retrieve")
    token_budget: int = Field(16000, ge=1000, le=32000, description="Target token budget")


class ContextRetrievalResponse(BaseModel):
    """Retrieved context"""
    shared: dict = Field(..., description="Shared context data")
    isolated: dict[str, dict] = Field(..., description="Mode-specific contexts")
    mem0_summary: str = Field("", description="Long-term memory summary")
    total_tokens: int = Field(..., description="Estimated token usage")
    budget_remaining: int = Field(..., description="Remaining tokens in budget")


class CompactionRequest(BaseModel):
    """Compaction trigger request"""
    mode: str = Field(..., description="Target mode")
    key: str = Field(..., description="Context key to compact")
    strategy: str = Field(
        "summary_and_keep_latest",
        description="Strategy: 'sliding_window', 'priority_eviction', 'access_based', or 'summary_and_keep_latest'"
    )
    target_tokens: int = Field(8000, ge=1000, le=32000, description="Target tokens after compaction")


class CompactionResponse(BaseModel):
    """Compaction result"""
    success: bool = Field(..., description="Whether compaction succeeded")
    mode: str = Field(..., description="Affected mode")
    key: str = Field(..., description="Affected context key")
    strategy: str = Field(..., description="Used strategy")
    entries_before: int = Field(..., description="Entries before compaction")
    entries_after: int = Field(..., description="Entries after compaction")
    tokens_before: int = Field(..., description="Token count before")
    tokens_after: int = Field(..., description="Token count after")
    compaction_ratio: float = Field(..., description="Compression ratio (after/before)")
    compacted_at: str = Field(..., description="ISO timestamp")
    error: str | None = Field(None, description="Error message if failed")


# --- Main router ---

router = APIRouter(prefix="/ai/context", tags=["ai_context"])


@router.post("/stats/batch", response_model=dict, summary="Batch get context statistics")
async def get_batch_context_stats(
    request: BatchContextStatsRequest,
    user = Depends(get_current_user),  # Use real authentication instead of dummy
) -> dict:
    """
    Retrieve context statistics for multiple sessions.
    
    Returns a map of session_id -> ContextStatsResponse
    """
    try:
        from app.services.mem0_service import Mem0Service
        from app.services.ai_session_service import AISessionService
        
        mem0_service = Mem0Service()
        session_service = AISessionService()
        
        stats_map = {}
        for session_id in request.session_ids:
            # Get basic session info
            session = await session_service.get_session(int(session_id))
            if not session or session.user_id != user.user_id:
                continue
            
            # Count local messages
            local_msg_count = await session_service.get_message_count(int(session_id))
            
            # Count shared context entries (tenant-wide, not per-session)
            from sqlalchemy import select
            from app.models.ai.ai_chat_context_storage import AIChatContextStorage
            
            async with SessionLocal() as session:
                stmt = select(AIChatContextStorage).where(
                    AIChatContextStorage.tenant_id == user.tenant_id,
                    AIChatContextStorage.mode == "shared"  # Only count shared layer
                )
                results = await session.execute(stmt)
                shared_context_entries = results.scalars().all()
                shared_context_count = len(shared_context_entries)
            
            # Get Mem0 stats if enabled
            vector_msg_count = 0
            if mem0_service.enabled:
                try:
                    mem0_memories = await mem0_service.search_memories(
                        user_id=str(user.user_id),
                        session_id=int(session_id)
                    )
                    vector_msg_count = len(mem0_memories) if mem0_memories else 0
                except Exception:
                    pass
            
            # Estimate tokens (simplified calculation)
            total_tokens = local_msg_count * 50 + vector_msg_count * 100 + shared_context_count * 30  # Rough estimate
            
            stats_map[int(session_id)] = ContextStatsResponse(
                session_id=int(session_id),
                total_tokens=total_tokens,
                message_counts={
                    "local": local_msg_count,
                    "vector_store": vector_msg_count,
                    "shared_context": shared_context_count
                },
                vector_store_messages=vector_msg_count,
                shared_context_count=shared_context_count,  # Now implemented!
                last_compaction_time=None,  # Will be implemented in Phase 2
                computed_at=datetime.now().isoformat()
            )
        
        return {"items": stats_map}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batch stats: {str(e)}"
        )


@router.post("/stats", response_model=list[ContextStatsResponse], summary="Get context statistics")
async def get_context_stats(
    request: ContextStatsRequest,
    user = Depends(get_current_user),  # Real authentication
) -> list[ContextStatsResponse]:
    """Retrieve context statistics from database"""
    
    try:
        # For now, delegate to batch endpoint with all sessions
        from app.services.ai_session_service import AISessionService
        session_service = AISessionService()
        
        # Get all sessions for this user
        all_sessions = await session_service.get_user_sessions(user.user_id)
        session_ids = [s.session_id for s in all_sessions]
        
        # Reuse batch logic
        batch_request = BatchContextStatsRequest(session_ids=session_ids)
        batch_result = await get_batch_context_stats(batch_request, user)
        
        return list(batch_result["items"].values())
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )


@router.post("/retrieve/{mode}/{key}", response_model=ContextRetrievalResponse, summary="Retrieve isolated context")
async def retrieve_context(
    mode: str,
    key: str,
    request: ContextRetrievalRequest,
    user = Depends(get_current_user)  # Real auth
) -> ContextRetrievalResponse:
    """
    Build full context using ContextManager.
    
    Note: This is a demonstration endpoint. In production, you would:
    1. Load existing context from database
    2. Pass it to ContextManager.build_full_context()
    3. Return the assembled context
    """
    
    try:
        # Create a minimal context manager instance
        # In production, load existing state from database first
        manager = ContextManager(tenant_id=user.tenant_id)
        
        # Set some example shared context (load from DB in production)
        manager.set_shared_context("preferences", {
            "theme": "dark",
            "language": "en"
        })
        
        # Build full context
        context = manager.build_full_context(
            max_tokens=request.token_budget,
            enable_mem0_retrieval=request.enable_mem0_retrieval,
            mem0_limit=request.mem0_limit
        )
        
        return ContextRetrievalResponse(
            shared=context["shared"],
            isolated=context["isolated"],
            mem0_summary=context["mem0_summary"],
            total_tokens=context["total_tokens"],
            budget_remaining=context["budget_remaining"]
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve context: {str(e)}"
        )


@router.post("/compaction", response_model=CompactionResponse, summary="Trigger context compaction")
async def trigger_compaction(
    request: CompactionRequest,
    user = Depends(get_current_user)  # Real auth
) -> CompactionResponse:
    """
    Compact a context entry using specified strategy.
    
    Supports strategies:
    - 'summary_and_keep_latest': Summarize old entries, keep recent N
    - 'sliding_window': Keep last N entries in window
    - 'priority_eviction': Remove lowest priority first
    - 'access_based': Keep most frequently accessed
    
    Returns detailed metrics on what was removed/kept.
    """
    
    try:
        manager = ContextManager(tenant_id=user.tenant_id)
        
        # Call the compact_context method (implemented in Phase 2)
        result = manager.compact_context(
            mode=request.mode,
            key=request.key,
            strategy=request.strategy,
            target_tokens=request.target_tokens,
        )
        
        if not result["success"]:
            return CompactionResponse(
                success=False,
                mode=result.get("mode", request.mode),
                key=result.get("key", request.key),
                strategy=result.get("strategy", request.strategy),
                entries_before=result.get("entries_before", 0),
                entries_after=result.get("entries_after", 0),
                tokens_before=result.get("tokens_before", 0),
                tokens_after=result.get("tokens_after", 0),
                compaction_ratio=1.0,
                compacted_at=datetime.now().isoformat(),
                error=result.get("reason") or result.get("error", "Unknown error"),
            )
        
        ratio = result.get("tokens_before", 0) / max(result.get("tokens_after", 1), 1)
        
        return CompactionResponse(
            success=True,
            mode=result["mode"],
            key=result["key"],
            strategy=result["strategy"],
            entries_before=result["entries_before"],
            entries_after=result["entries_after"],
            tokens_before=result["tokens_before"],
            tokens_after=result["tokens_after"],
            compaction_ratio=ratio,
            compacted_at=result["compacted_at"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compaction failed: {str(e)}"
        )


# ────────────────────────────────────────────────────────────────────
# PR-2 Task 8: 跨模式上下文 3 个前端路由
# (POST /entries, POST /breakdown, GET /strategies)
# ────────────────────────────────────────────────────────────────────


class ContextEntriesRequest(BaseModel):
    """跨模式上下文条目检索请求体。"""
    session_id: int = Field(..., description="主会话 ID")
    allow_cross_mode: bool = Field(False, description="是否允许读取跨模式可读记录")
    include_tags: Optional[list[str]] = Field(None, description="上下文标签过滤(命中其一即返回)")
    source_mode: Optional[str] = Field(None, description="限定单一来源模式")
    limit: int = Field(50, ge=1, le=200, description="返回数量上限")


class BreakdownRequest(BaseModel):
    """模式分布统计请求体。"""
    session_id: int = Field(..., description="主会话 ID")


def _require_cross_mode_enabled() -> None:
    """读取 cross-mode recorder 功能开关,关闭时抛 503。

    strategies 端点不调用此函数(总是 200,前端可 fallback)。
    """
    try:
        from app.config import settings
        if not settings.ENABLE_CROSS_MODE_RECORDER:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="cross-mode recorder disabled",
            )
    except HTTPException:
        raise
    except Exception:
        # 配置层异常按"启用"对待(与 recorder 内部策略一致:降级为开启)
        return


@router.post("/entries", response_model=dict, summary="跨模式上下文条目检索")
async def list_context_entries(
    request: ContextEntriesRequest,
    user=Depends(get_current_user),
) -> dict:
    """跨模式上下文条目检索(前端驱动 9 模式卡片)。

    支持 source_mode + include_tags + allow_cross_mode 三个过滤维度。
    """
    _require_cross_mode_enabled()

    from app.ai.context_manager import ContextManager

    s = SessionLocal()
    try:
        mgr = ContextManager(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
        )
        items = mgr.get_context_with_mode_filter(
            session_id=request.session_id,
            user_id=user.user_id,
            allow_cross_mode=request.allow_cross_mode,
            include_tags=request.include_tags,
            source_mode=request.source_mode,
            limit=request.limit,
            db=s,
        )
        return {"items": items, "total": len(items)}
    finally:
        s.close()


@router.post("/breakdown", response_model=dict, summary="跨模式条目分布统计")
async def get_cross_mode_breakdown(
    request: BreakdownRequest,
    user=Depends(get_current_user),
) -> dict:
    """按 source_mode 聚合的统计 breakdown。

    返回 [{source_mode, entry_count}, ...] 列表(包含全部出现的 source_mode,
    即使 entry_count 为 0 也会被剔除;空 session 返回空列表)。
    """
    _require_cross_mode_enabled()

    from app.models.ai.ai_chat_context_storage import AIChatContextStorage

    s = SessionLocal()
    try:
        rows = (
            s.query(
                AIChatContextStorage.source_mode,
                func.count(AIChatContextStorage.id).label("entry_count"),
            )
            .where(
                AIChatContextStorage.tenant_id == user.tenant_id,
                AIChatContextStorage.session_id == request.session_id,
            )
            .group_by(AIChatContextStorage.source_mode)
            .all()
        )
        return {
            "items": [
                {"source_mode": r.source_mode, "entry_count": r.entry_count}
                for r in rows
            ]
        }
    finally:
        s.close()


MODE_LABELS = {
    "general":       "通用对话",
    "react":         "ReAct 计划",
    "thinking":      "深度思考",
    "deep_research": "深度研究",
    "skill":         "技能执行",
    "agent":         "智能体",
    "team":          "智能体团队",
    "scheduled":     "云端调度",
    "shared":        "共享层",
}

MODE_COLORS = {
    "general":       "blue",
    "react":         "cyan",
    "thinking":      "purple",
    "deep_research": "magenta",
    "skill":         "green",
    "agent":         "gold",
    "team":          "orange",
    "scheduled":     "default",
    "shared":        "default",
}


@router.get("/strategies", response_model=dict, summary="列出 9 模式 finalize 策略")
async def list_strategies() -> dict:
    """返回 STRATEGY_TABLE 给前端渲染模式卡片清单。

    此端点不受 ENABLE_CROSS_MODE_RECORDER 关闭影响,前端可始终 fallback 使用。
    """
    from app.ai.services.cross_mode_recorder import STRATEGY_TABLE
    items = []
    for s in STRATEGY_TABLE.values():
        items.append({
            "session_type": s.session_type,
            "source_mode":  s.source_mode,
            "priority":     s.priority,
            "ttl_hours":    s.ttl_hours,
            "write_mem0":   s.write_mem0,
            "is_cross_mode_accessible": s.is_cross_mode_accessible,
            "display_label": MODE_LABELS.get(s.session_type, s.session_type),
            "display_color": MODE_COLORS.get(s.session_type, "default"),
        })
    return {"strategies": items}
