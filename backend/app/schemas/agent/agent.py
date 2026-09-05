"""
Agent 配置相关 Schema (重构版)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(str):
    """执行模式枚举"""
    LLM = "llm"
    WORKFLOW = "workflow"
    SKILL = "skill"
    KNOWLEDGE = "knowledge"
    HARNESS = "harness"
    PLAN = "plan"
    TEAM = "team"


class ExecutionStatus(str):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionEventType(str):
    """执行事件类型"""
    # 基础事件
    TEXT = "text"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    METRICS = "metrics"

    # HITL 事件
    HITL_PAUSE = "hitl_pause"
    HITL_RESUME = "hitl_resume"

    # Skill 执行事件
    SKILL_START = "skill_start"
    SKILL_LOAD = "skill_load"
    SKILL_LOADED = "skill_loaded"
    SKILL_RESULT = "skill_result"
    SKILL_COMPLETE = "skill_complete"

    # Agent 执行事件
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_DONE = "agent_done"
    AGENT_RETRY = "agent_retry"
    AGENT_ERROR = "agent_error"

    # 团队（v2 动态编排）事件
    TEAM_START = "team_start"
    TEAM_DONE = "team_done"
    TEAM_ERROR = "team_error"
    # 团队 v2.1 Plan & Execute 事件（spec §7）
    DISPATCH_PLAN = "dispatch_plan"
    PLAN_REVISED = "plan_revised"
    TEAM_LAYER_START = "team_layer_start"
    TEAM_LAYER_DONE = "team_layer_done"

    # 特殊事件
    PROGRESS = "progress"
    TIMEOUT = "timeout"


# ── AgentConfig Schema ────────────────────────────────────────────────────────

class AgentConfigBase(BaseModel):
    """Agent 配置基础模型"""
    agent_code: str = Field(..., max_length=100, description="唯一标识码")
    name: str = Field(..., max_length=200, description="Agent名称")
    agent_type: str = Field(..., description="实现类型: CHAT/WORKFLOW/SKILL（字典 agent_type）")
    category: Optional[str] = Field(None, max_length=50, description="用途分类（数据字典: agent_category）")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序权重")


class AgentConfigStrategy(BaseModel):
    """Agent 策略配置（合并原 AgentStrategy）"""
    strategy_code: Optional[str] = Field(None, description="策略代码（数据字典: agent_strategy）")
    execution_mode: str = Field("llm", description="执行模式: llm/workflow/skill/knowledge/harness/plan/team")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class AgentConfigTools(BaseModel):
    """Agent 工具配置"""
    tools: List[str] = Field(default_factory=list, description="可用工具列表")
    skills: List[str] = Field(default_factory=list, description="可用 Skill 列表")
    mcp_servers: Optional[List[Dict[str, Any]]] = Field(None, description="MCP 服务器配置")
    knowledge_bases: List[int] = Field(default_factory=list, description="关联知识库 ID 列表")


class AgentConfigModel(BaseModel):
    """Agent 模型配置"""
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    base_url: Optional[str] = Field(None, description="API 端点")
    temperature: float = Field(0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(4096, description="最大 token 数")
    api_key_ref: Optional[str] = Field(None, description="API Key 引用（环境变量名）")
    model_code: Optional[str] = Field(None, description="关联的已注册 ChatModel 代码，后端据此解析已存储的 API Key 自动鉴权")


class AgentConfigExecution(BaseModel):
    """Agent 执行配置"""
    hitl_config: Optional[Dict[str, Any]] = Field(None, description="HITL 配置")
    react_config: Optional[Dict[str, Any]] = Field(None, description="ReAct 配置")
    context_config: Optional[Dict[str, Any]] = Field(None, description="上下文配置")


class AgentConfigCreate(AgentConfigBase):
    """创建 Agent 配置"""
    strategy: Optional[AgentConfigStrategy] = Field(None, description="策略配置")
    tools: Optional[AgentConfigTools] = Field(None, description="工具配置")
    llm_config: Optional[AgentConfigModel] = Field(None, alias="model_config", description="模型配置")
    execution: Optional[AgentConfigExecution] = Field(None, description="执行配置")
    config: Optional[Dict[str, Any]] = Field(None, description="类型特定配置")
    workspace_id: Optional[int] = Field(None, description="工作空间 ID")
    created_by: Optional[int] = Field(None, description="创建人ID")

    model_config = ConfigDict(populate_by_name=True)


class AgentConfigUpdate(BaseModel):
    """更新 Agent 配置"""
    name: Optional[str] = Field(None, max_length=200)
    agent_type: Optional[str] = Field(None)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    sort_order: Optional[int] = Field(None)
    strategy: Optional[AgentConfigStrategy] = Field(None)
    tools: Optional[AgentConfigTools] = Field(None)
    llm_config: Optional[AgentConfigModel] = Field(None, alias="model_config")
    execution: Optional[AgentConfigExecution] = Field(None)
    config: Optional[Dict[str, Any]] = Field(None)

    model_config = ConfigDict(populate_by_name=True)


class AgentConfigResponse(AgentConfigBase):
    """Agent 配置响应"""
    id: int
    strategy_code: Optional[str] = None
    execution_mode: str = "llm"
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    mcp_servers: Optional[List[Dict[str, Any]]] = None
    knowledge_bases: Optional[List[int]] = None
    llm_config: Optional[Dict[str, Any]] = Field(None, alias="model_config")
    hitl_config: Optional[Dict[str, Any]] = None
    react_config: Optional[Dict[str, Any]] = None
    context_config: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    workspace_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AgentConfigListResponse(BaseModel):
    """Agent 配置列表响应"""
    total: int
    items: List[AgentConfigResponse]


class AgentTeamStatus(BaseModel):
    """AgentTeam 能力状态（后端暂未实现）"""
    available: bool = False
    message: str = "AgentTeam 后端暂未实现"


class AgentRegistryResponse(BaseModel):
    """Agent 注册表响应（参考技能获取接口，按 category 分组展示）"""
    total: int
    agents: List[AgentConfigResponse]
    # 按 category 分组的 agents，便于前端以分类形式展示
    grouped: Dict[str, List[AgentConfigResponse]] = Field(default_factory=dict)
    categories: List[str] = Field(default_factory=list)
    # AgentTeam 多智能体协作能力（后端暂未实现）
    agent_team: AgentTeamStatus = Field(default_factory=AgentTeamStatus)


# ── AgentExecution Schema ──────────────────────────────────────────────────────

class AgentExecutionBase(BaseModel):
    """Agent 执行基础模型"""
    execution_id: str
    agent_config_id: Optional[int] = None
    agent_code: Optional[str] = None
    strategy_code: Optional[str] = None
    session_id: Optional[int] = None
    user_id: Optional[int] = None
    execution_mode: str = "llm"
    status: str = "pending"
    user_input: Optional[str] = None


class AgentExecutionCreate(AgentExecutionBase):
    """创建执行记录"""
    trace_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    schedule_id: Optional[int] = None
    max_retries: int = 3


class AgentExecutionUpdate(BaseModel):
    """更新执行记录"""
    status: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None


class AgentExecutionResponse(AgentExecutionBase):
    """执行记录响应"""
    id: int
    trace_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    schedule_id: Optional[int] = None
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── AgentExecutionEvent Schema ─────────────────────────────────────────────────

class AgentExecutionEventCreate(BaseModel):
    """创建执行事件"""
    execution_id: str
    event_type: str
    sequence: int
    content: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentExecutionEventResponse(AgentExecutionEventCreate):
    """执行事件响应"""
    id: int
    trace_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── ChatConfig / WorkflowConfig / SkillConfig (保留兼容) ───────────────────────

class ChatConfig(BaseModel):
    """CHAT 类型配置"""
    system_prompt: str = Field(..., description="系统提示词")
    model: str = Field("gpt-4", description="模型名称")
    temperature: float = Field(0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(4096, description="最大token数")
    tools: List[str] = Field(default_factory=list, description="可用工具列表")
    skills: List[str] = Field(default_factory=list, description="可用技能列表")


class WorkflowConfig(BaseModel):
    """WORKFLOW 类型配置"""
    dify_flow_code: str = Field(..., description="Dify流程编码")
    async_enabled: bool = Field(False, description="是否异步执行")
    timeout_seconds: int = Field(300, description="超时秒数")
    callback_url: Optional[str] = Field(None, description="回调URL")
    input_mapping: Dict[str, str] = Field(default_factory=dict, description="输入映射")
    output_mapping: Dict[str, str] = Field(default_factory=dict, description="输出映射")


class SkillConfig(BaseModel):
    """SKILL 类型配置"""
    skill_packages: List[str] = Field(default_factory=list, description="Skill包列表")
    rule_engine_enabled: bool = Field(True, description="是否启用规则引擎")
    max_concurrent: int = Field(3, ge=1, description="最大并发数")
    default_timeout: int = Field(60, description="默认超时秒数")
