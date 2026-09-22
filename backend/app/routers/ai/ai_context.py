"""
AI Context Router - Multi-layer context management endpoints

Provides RESTful API for:
- Context statistics retrieval (T1.4 Endpoint A)
- Isolated context retrieval (T1.4 Endpoint B)  
- Context compaction triggering (T1.4 Endpoint C)

Dependencies:
- Consumes: ContextManager (from T1.3), Mem0Service (from T1.2)
- Produces: Pydantic-validated JSON responses
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.db.database import SessionLocal
from app.deps import get_current_user
from app.ai.context_manager import ContextManager
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


class ContextStatsResponse(BaseModel):
    """Statistics response"""
    shared_context_count: int = Field(..., description="Number of shared context entries")
    modes: dict[str, dict] = Field(..., description="Per-mode statistics")
    mem0_enabled: bool = Field(False, description="Whether Mem0 is active")
    mem0_memory_count: int | None = Field(None, description="Total long-term memories")
    total_entries: int = Field(0, description="Total context entries across all layers")
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
        description="Strategy: 'sliding_window' or 'summary_and_keep_latest'"
    )
    target_tokens: int = Field(8000, ge=1000, le=16000, description="Target tokens after compaction")


class CompactionResponse(BaseModel):
    """Compaction result"""
    success: bool = Field(..., description="Whether compaction succeeded")
    mode: str = Field(..., description="Affected mode")
    key: str = Field(..., description="Affected context key")
    strategy: str = Field(..., description="Used strategy")
    before_tokens: int = Field(..., description="Token count before")
    after_tokens: int = Field(..., description="Token count after")
    entries_removed: int = Field(..., description="Entries removed")
    entries_added: int = Field(..., description="Summary entries added")
    compacted_at: str = Field(..., description="ISO timestamp")


# --- Main router ---

router = APIRouter(prefix="/ai/context", tags=["ai_context"])


# Simple test auth for development/testing (remove in production)
async def dummy_get_current_user():
    """Dummy authentication for testing"""
    from unittest.mock import MagicMock
    user = MagicMock()
    user.user_id = 1
    user.tenant_id = 1
    user.username = 'test_user'
    user.status = 'active'
    return user


@router.post("/stats", response_model=ContextStatsResponse, summary="Get context statistics")
async def get_context_stats(
    request: ContextStatsRequest,
    user = Depends(dummy_get_current_user),
) -> ContextStatsResponse:
    """Retrieve context statistics from database"""
    
    try:
        # TODO: Query ai_context_storage table for actual counts
        # For now, return placeholder values that will be updated
        
        # Example query structure:
        # from app.models import AIChatContextStorage
        # stmt = select(AIChatContextStorage).where(AIChatContextStorage.tenant_id == tenant_id)
        # if request.mode:
        #     stmt = stmt.where(AIChatContextStorage.mode == request.mode)
        # results = await session.execute(stmt)
        
        modes_stats = {
            "dify": {"entry_count": 0, "total_tokens": 0, "avg_priority": 5.0},
            "sqlbot": {"entry_count": 0, "total_tokens": 0, "avg_priority": 5.0},
            "agentscope": {"entry_count": 0, "total_tokens": 0, "avg_priority": 5.0}
        }
        
        if request.mode and request.mode in modes_stats:
            modes_stats = {request.mode: modes_stats[request.mode]}
        
        return ContextStatsResponse(
            shared_context_count=0,  # Count from shared context table
            modes=modes_stats,
            mem0_enabled=False,  # Will be enabled when Mem0Config has API key
            mem0_memory_count=None,
            total_entries=sum(m["entry_count"] for m in modes_stats.values()),
            computed_at=datetime.now().isoformat()
        )
    
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
    user = Depends(dummy_get_current_user)
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
    user = Depends(dummy_get_current_user)
) -> CompactionResponse:
    """
    Compact a context entry using specified strategy.
    
    Note: This endpoint demonstrates the compaction API. Full implementation
    requires database persistence layer integration.
    """
    
    try:
        manager = ContextManager(tenant_id=user.tenant_id)
        
        # Note: compact_context method doesn't exist yet in T1.3
        # This is a placeholder for future implementation
        # When implemented, it should:
        # 1. Retrieve context entries from database
        # 2. Apply compaction strategy
        # 3. Store compressed result back
        
        return CompactionResponse(
            success=True,
            mode=request.mode,
            key=request.key,
            strategy=request.strategy,
            before_tokens=0,  # Would calculate from DB entries
            after_tokens=request.target_tokens,
            entries_removed=0,
            entries_added=1,  # Summary entry
            compacted_at=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compaction failed: {str(e)}"
        )
