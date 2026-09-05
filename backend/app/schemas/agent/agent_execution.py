"""AgentExecution 查询接口 Pydantic 响应模型。

仅做响应结构定义，不含任何业务逻辑（聚合/JOIN 下沉到 service）。
"""
from __future__ import annotations

import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from pydantic import BaseModel


# ── 单个执行记录项（列表用，输出截断） ──────────────────────────────────────

class AgentExecutionItem(BaseModel):
    """Agent 执行记录列表项。"""
    execution_id: str
    session_id: Optional[int] = None
    session_title: Optional[str] = None
    user_id: Optional[int] = None
    execution_mode: str
    target_id: Optional[str] = None
    status: str
    user_input: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 列表响应（分页） ────────────────────────────────────────────────────────

class AgentExecutionListResp(BaseModel):
    """执行记录分页列表响应。"""
    items: List[AgentExecutionItem]
    total: int
    page: int
    page_size: int


# ── 详情（含完整输出 + trace 概要） ──────────────────────────────────────────

class AgentTraceSummary(BaseModel):
    """关联链路概要。"""
    trace_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    status: Optional[str] = None
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}


# ── 调用链节点事件（详情/链路用） ──────────────────────────────────────────

class AgentExecutionEventItem(BaseModel):
    """执行链节点事件：用于绘制分层 DAG 拓扑与时间线。

    拓扑相关字段（node_key / agent_code / role_name / node_status / layer /
    parent_keys / channel / node_type 等）存放于 metadata_json，这里提取为
    便捷字段便于前端直接使用。
    """
    id: int
    execution_id: str
    event_type: Optional[str] = None
    sequence: Optional[int] = None
    content: Optional[Any] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    # 拓扑便捷字段（来自 metadata_json）
    node_key: Optional[str] = None
    agent_code: Optional[str] = None
    role_name: Optional[str] = None
    node_status: Optional[str] = None
    node_type: Optional[str] = None
    channel: Optional[str] = None
    layer: Optional[int] = None
    parent_keys: List[str] = []
    created_at: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_event(cls, event: Any) -> "AgentExecutionEventItem":
        meta = event.event_metadata or {}
        content = event.content
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False)
        return cls(
            id=event.id,
            execution_id=event.execution_id,
            event_type=event.event_type,
            sequence=event.sequence,
            content=content,
            source=event.source,
            source_id=event.source_id,
            node_key=meta.get("node_key") or meta.get("node_role"),
            agent_code=meta.get("agent_code"),
            role_name=meta.get("role_name"),
            node_status=meta.get("node_status"),
            node_type=meta.get("node_type"),
            channel=meta.get("channel"),
            layer=meta.get("layer"),
            parent_keys=meta.get("parent_keys") or [],
            created_at=event.created_at,
            metadata_json=meta,
        )


# ── 人工介入暂停（详情用） ─────────────────────────────────────────────────

class AgentHitlPauseItem(BaseModel):
    """人工介入暂停记录。"""
    id: int
    execution_id: str
    pause_type: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    user_id: Optional[int] = None
    approver_id: Optional[int] = None
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 事件列表响应 ───────────────────────────────────────────────────────────

class AgentExecutionEventListResp(BaseModel):
    """调用链事件列表响应。"""
    items: List[AgentExecutionEventItem]
    total: int


class AgentExecutionDetail(AgentExecutionItem):
    """执行记录详情：在 Item 基础上含完整 output/error/metadata 与 trace 概要。"""
    metadata_json: Optional[Dict[str, Any]] = None
    trace: Optional[AgentTraceSummary] = None
    events: List[AgentExecutionEventItem] = []
    hitl_pauses: List[AgentHitlPauseItem] = []


# ── 统计聚合 ────────────────────────────────────────────────────────────────

class AgentExecutionStats(BaseModel):
    """执行记录统计聚合。"""
    total: int
    by_execution_mode: Dict[str, int]
    by_status: Dict[str, int]
    total_latency_ms: int
    avg_latency_ms: float
