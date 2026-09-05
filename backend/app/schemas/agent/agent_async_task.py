"""AgentAsyncTask 相关 schema（Pydantic v2）"""
from __future__ import annotations

from typing import Optional, Any
from pydantic import BaseModel, Field


class AgentAsyncTaskCreate(BaseModel):
    task_name: str = Field(..., max_length=255)
    target_mode: str = Field(..., description="agent/team/skill")
    payload: dict = Field(default_factory=dict)
    session_id: Optional[str] = None
    priority: int = Field(5, ge=0, le=9)
    timeout_seconds: int = Field(1800, gt=0)
    max_retries: int = Field(2, ge=0, le=10)


class AgentAsyncTaskOut(BaseModel):
    id: int
    taskNo: Optional[str] = None
    sessionId: Optional[str] = None
    userId: int
    taskName: str
    targetMode: str
    payload: Optional[Any] = None
    status: str
    priority: int
    progress: float
    timeoutSeconds: int
    maxRetries: int
    retryCount: int
    executionId: Optional[str] = None
    resultData: Optional[Any] = None
    errorMessage: Optional[str] = None
    submittedAt: Optional[str] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None


class AgentAsyncTaskListResp(BaseModel):
    total: int
    items: list[AgentAsyncTaskOut]


class AgentAsyncTaskCancelResp(BaseModel):
    id: int
    status: str
    message: str
