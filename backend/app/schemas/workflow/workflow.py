"""工作流管理 Pydantic Schema"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PlatformTypeEnum:
    DIFY = "dify"
    COZE = "coze"
    CUSTOM_HTTP = "custom_http"
    ALL = ["dify", "coze", "custom_http"]


class FlowTypeEnum:
    WORKFLOW = "Workflow"
    CHATFLOW = "Chatflow"
    CHATBOT = "Chatbot"
    AGENT = "Agent"
    COMPLETION = "Completion"
    ALL = ["Workflow", "Chatflow", "Chatbot", "Agent", "Completion"]


# ── WorkflowFlow Schema ──────────────────────────────────────

class WorkflowFlowBase(BaseModel):
    flow_code: str = Field(..., max_length=100, description="业务唯一标识码")
    flow_name: str = Field(..., max_length=200, description="工作流名称")
    platform_type: str = Field("dify", description="平台类型")
    flow_type: str = Field(..., description="流程类型")
    base_url: str = Field(..., max_length=500, description="平台 API 基地址")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="入参 JSON Schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="出参 JSON Schema")
    config: Optional[Dict[str, Any]] = Field(None, description="平台扩展配置")
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class WorkflowFlowCreate(WorkflowFlowBase):
    api_key: str = Field(..., description="API Key（明文，后端加密存储）")


class WorkflowFlowUpdate(BaseModel):
    flow_name: Optional[str] = None
    platform_type: Optional[str] = None
    flow_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="新 API Key（明文）")
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class WorkflowFlowOut(BaseModel):
    id: int
    flow_code: str
    flow_name: str
    platform_type: str
    flow_type: str
    base_url: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]]
    config: Optional[Dict[str, Any]]
    description: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowFlowListOut(BaseModel):
    total: int
    items: List[WorkflowFlowOut]


# ── WorkflowExecutionLog Schema ──────────────────────────────

class WorkflowExecutionLogOut(BaseModel):
    id: int
    flow_id: int
    execution_id: Optional[str]
    status: str
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    latency_ms: Optional[int]
    retry_count: int
    platform_trace: Optional[Dict[str, Any]]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── WorkflowChain Schema ─────────────────────────────────────

class WorkflowChainBase(BaseModel):
    chain_code: str = Field(..., max_length=100)
    chain_name: str = Field(..., max_length=200)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    description: Optional[str] = None
    is_active: bool = True


class WorkflowChainCreate(WorkflowChainBase):
    pass


class WorkflowChainUpdate(BaseModel):
    chain_name: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WorkflowChainOut(WorkflowChainBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 测试执行 ─────────────────────────────────────────────────

class WorkflowTestReq(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "test-user"
    timeout: float = 600.0


class WorkflowTestResp(BaseModel):
    success: bool
    output: Dict[str, Any]
    error: Optional[str] = None
    latency_ms: int = 0
