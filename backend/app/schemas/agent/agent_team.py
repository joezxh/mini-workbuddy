"""AgentTeam 多智能体团队协作 —— Pydantic Schema

覆盖：团队 CRUD、成员、图边、整图保存、运行发起、运行详情、步骤、人工介入、模板。

参见：docs/agent/agent-team-design.md
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.agent.agent_team import (
    END_NODE,
    RESERVED_NODE_KEYS,
    START_NODE,
    NodeErrorPolicy,
    NodeInputMode,
    TeamMode,
)
from app.models.agent.agent_team_run import (
    InterventionType,
    TriggerType,
)

#: node_key 命名规范：字母开头，允许字母数字下划线，长度 1-64
NODE_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


def validate_node_key(value: str, *, allow_reserved: bool = False) -> str:
    """校验 node_key 合法性"""
    if allow_reserved and value in RESERVED_NODE_KEYS:
        return value
    if value in RESERVED_NODE_KEYS:
        raise ValueError(f"node_key 不能使用保留字: {value}")
    if not NODE_KEY_PATTERN.match(value or ""):
        raise ValueError(
            f"node_key 非法: {value!r}，需字母开头且仅含字母/数字/下划线，长度 ≤64"
        )
    return value


# ── 运行配置 / 节点配置 ────────────────────────────────────────────────────────

class AgentTeamRunConfig(BaseModel):
    """团队运行策略配置（对应 agent_team.run_config）"""
    max_rounds: int = Field(10, ge=1, le=100, description="最大轮次（msghub/supervisor）")
    max_parallel: int = Field(5, ge=1, le=50, description="同层最大并发节点数")
    node_timeout_seconds: int = Field(120, ge=1, le=3600, description="单节点超时（秒）")
    total_timeout_seconds: int = Field(600, ge=1, le=86400, description="整体超时（秒）")
    on_node_error: str = Field(NodeErrorPolicy.CONTINUE, description="节点失败策略: continue/abort")
    supervisor_node_key: Optional[str] = Field(None, description="主管节点（supervisor 模式必填）")
    aggregator_node_key: Optional[str] = Field(None, description="汇总节点（parallel 模式）")
    allow_intervention: bool = Field(True, description="是否允许人工介入")
    persist_events: bool = Field(True, description="是否持久化事件流")
    persist_chunks: bool = Field(False, description="是否持久化 TEXT_CHUNK（默认否，仅落 TEXT_DONE）")

    @field_validator("on_node_error")
    @classmethod
    def _check_policy(cls, v: str) -> str:
        if v not in (NodeErrorPolicy.CONTINUE, NodeErrorPolicy.ABORT):
            raise ValueError(f"on_node_error 非法: {v}")
        return v


class AgentTeamNodeConfig(BaseModel):
    """成员节点行为配置（对应 agent_team_member.node_config）"""
    input_mode: str = Field(NodeInputMode.CONCAT, description="多上游合并方式: concat/json")
    input_template: Optional[str] = Field(None, description="输入模板，支持 {upstream}/{user_input} 占位")
    output_key: Optional[str] = Field(None, description="输出在上下文中的键名，默认用 node_key")
    condition: Optional[str] = Field(None, description="执行条件表达式（预留）")
    retry: int = Field(0, ge=0, le=5, description="失败重试次数")
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600, description="节点级超时覆盖")
    is_entry: bool = Field(False, description="是否入口节点")
    is_terminal: bool = Field(False, description="是否终止节点（其输出作为团队最终输出）")

    @field_validator("input_mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in (NodeInputMode.CONCAT, NodeInputMode.JSON):
            raise ValueError(f"input_mode 非法: {v}")
        return v


# ── 成员 Schema ───────────────────────────────────────────────────────────────

class AgentTeamMemberBase(BaseModel):
    """成员基础字段"""
    node_key: str = Field(..., max_length=64, description="团队内唯一节点标识")
    agent_config_id: int = Field(..., description="引用的 agent_config.id")
    role_name: str = Field(..., max_length=100, description="团队内角色名")
    role_desc: Optional[str] = Field(None, description="角色职责说明")
    avatar: Optional[str] = Field(None, max_length=200, description="头像")
    sort_order: int = Field(0, description="顺序")

    # 覆盖配置：None = 沿用 agent_config 原值
    override_system_prompt: Optional[str] = Field(None, description="覆盖系统提示词")
    override_llm_config: Optional[Dict[str, Any]] = Field(None, description="覆盖模型配置（深合并）")
    override_knowledge_bases: Optional[List[int]] = Field(None, description="覆盖知识库 ID 列表")
    override_tools: Optional[List[str]] = Field(None, description="覆盖工具列表")
    override_skills: Optional[List[str]] = Field(None, description="覆盖技能列表")

    # TeamSay 工具预设（§12.4）：单点追问时可被 @提及 调起的成员 node_key 列表
    tool_preset: Optional[List[str]] = Field(None, description="TeamSay 工具预设：可 @提及 的成员 node_key 列表")

    node_config: Optional[AgentTeamNodeConfig] = Field(None, description="节点行为配置")
    is_active: bool = Field(True, description="是否启用")

    @field_validator("node_key")
    @classmethod
    def _check_node_key(cls, v: str) -> str:
        return validate_node_key(v)


class AgentTeamMemberCreate(AgentTeamMemberBase):
    """新增成员"""


class AgentTeamMemberUpdate(BaseModel):
    """更新成员（全部可选）"""
    agent_config_id: Optional[int] = None
    role_name: Optional[str] = Field(None, max_length=100)
    role_desc: Optional[str] = None
    avatar: Optional[str] = Field(None, max_length=200)
    sort_order: Optional[int] = None
    override_system_prompt: Optional[str] = None
    override_llm_config: Optional[Dict[str, Any]] = None
    override_knowledge_bases: Optional[List[int]] = None
    override_tools: Optional[List[str]] = None
    override_skills: Optional[List[str]] = None
    tool_preset: Optional[List[str]] = None
    node_config: Optional[AgentTeamNodeConfig] = None
    is_active: Optional[bool] = None


class AgentTeamMemberOut(AgentTeamMemberBase):
    """成员输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 关联展示（由 Service 装配，非数据库字段）
    agent_name: Optional[str] = Field(None, description="引用 Agent 的名称")
    agent_code: Optional[str] = Field(None, description="引用 Agent 的编码")
    agent_available: bool = Field(True, description="引用的 Agent 是否仍存在且启用")


# ── 图边 Schema ───────────────────────────────────────────────────────────────

class AgentTeamEdgeBase(BaseModel):
    """边基础字段"""
    from_node_key: str = Field(..., max_length=64, description="上游节点，'__START__' 表示虚拟入口")
    to_node_key: str = Field(..., max_length=64, description="下游节点，'__END__' 表示虚拟出口")
    label: Optional[str] = Field(None, max_length=100, description="边标签")
    condition: Optional[str] = Field(None, description="条件表达式（预留）")
    sort_order: int = Field(0, description="同一下游的多上游拼接顺序")
    edge_config: Optional[Dict[str, Any]] = Field(None, description="前端样式等")

    @field_validator("from_node_key", "to_node_key")
    @classmethod
    def _check_keys(cls, v: str) -> str:
        return validate_node_key(v, allow_reserved=True)

    @model_validator(mode="after")
    def _check_edge(self) -> "AgentTeamEdgeBase":
        if self.from_node_key == self.to_node_key:
            raise ValueError(f"边的起止节点不能相同: {self.from_node_key}")
        if self.from_node_key == END_NODE:
            raise ValueError(f"{END_NODE} 不能作为边的起点")
        if self.to_node_key == START_NODE:
            raise ValueError(f"{START_NODE} 不能作为边的终点")
        return self


class AgentTeamEdgeCreate(AgentTeamEdgeBase):
    """新增边"""


class AgentTeamEdgeOut(AgentTeamEdgeBase):
    """边输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    created_at: Optional[datetime] = None


# ── 画布布局 ──────────────────────────────────────────────────────────────────

class AgentTeamGraphNodePosition(BaseModel):
    """画布节点坐标"""
    node_key: str = Field(..., max_length=64)
    x: float = 0
    y: float = 0


class AgentTeamGraphViewport(BaseModel):
    """画布视口"""
    x: float = 0
    y: float = 0
    zoom: float = Field(1.0, gt=0, le=4)


class AgentTeamGraphLayout(BaseModel):
    """画布布局快照（对应 agent_team.graph，仅前端展示用，非执行数据源）"""
    nodes: List[AgentTeamGraphNodePosition] = Field(default_factory=list)
    viewport: Optional[AgentTeamGraphViewport] = None


# ── 团队 Schema ───────────────────────────────────────────────────────────────

class AgentTeamBase(BaseModel):
    """团队基础字段"""
    name: str = Field(..., max_length=200, description="团队名称")
    description: Optional[str] = Field(None, description="描述")
    category: Optional[str] = Field(None, max_length=50, description="用途分类")
    mode: str = Field(TeamMode.SEQUENTIAL, description="协作模式（来源模板）: sequential/parallel/msghub/supervisor/dag")
    execution_mode: Optional[str] = Field(
        None,
        description="执行引擎分流（§13.4）: llm_orchestrated(生效) / static_dag(废弃回放)。"
        "建表迁移前 DB 可能为 NULL，故响应层容忍空值。",
    )
    shared_knowledge_bases: Optional[List[int]] = Field(None, description="团队共享知识库 ID 列表")
    shared_tools: Optional[List[str]] = Field(None, description="团队共享工具")
    run_config: Optional[AgentTeamRunConfig] = Field(None, description="运行策略配置")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序权重")

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in TeamMode.ALL:
            raise ValueError(f"mode 非法: {v}，可选 {TeamMode.ALL}")
        return v


class AgentTeamCreate(AgentTeamBase):
    """创建团队"""
    team_code: Optional[str] = Field(None, max_length=100, description="唯一标识码，留空则自动生成")
    members: List[AgentTeamMemberCreate] = Field(default_factory=list, description="初始成员")
    edges: List[AgentTeamEdgeCreate] = Field(default_factory=list, description="初始边")
    graph: Optional[Dict[str, Any]] = Field(None, description="画布布局快照（节点坐标 / 视口）")
    workspace_id: Optional[int] = Field(None, description="所属工作空间 ID")


class AgentTeamUpdate(BaseModel):
    """更新团队（全部可选）"""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    mode: Optional[str] = None
    execution_mode: Optional[str] = Field(
        None, description="执行引擎分流（§13.4）: llm_orchestrated / static_dag"
    )
    shared_knowledge_bases: Optional[List[int]] = None
    shared_tools: Optional[List[str]] = None
    run_config: Optional[AgentTeamRunConfig] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TeamMode.ALL:
            raise ValueError(f"mode 非法: {v}，可选 {TeamMode.ALL}")
        return v


class TeamOut(AgentTeamBase):
    """团队输出（列表用，不含成员与边）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_code: str
    graph: Optional[Dict[str, Any]] = None
    workspace_id: Optional[int] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    member_count: int = Field(0, description="成员数量")


class TeamDetailOut(TeamOut):
    """团队详情（含成员与边）"""
    members: List[AgentTeamMemberOut] = Field(default_factory=list)
    edges: List[AgentTeamEdgeOut] = Field(default_factory=list)


class TeamGraphSaveRequest(BaseModel):
    """整图保存：一次性覆盖成员 + 边 + 布局

    Service 侧按 node_key 做增删改比对，而非全删重建，以保留成员 id。
    """
    mode: Optional[str] = Field(None, description="同时切换协作模式")
    members: List[AgentTeamMemberCreate] = Field(..., description="全量成员")
    edges: List[AgentTeamEdgeCreate] = Field(default_factory=list, description="全量边")
    layout: Optional[AgentTeamGraphLayout] = Field(None, description="画布布局")

    @model_validator(mode="after")
    def _check_graph(self) -> "TeamGraphSaveRequest":
        keys = [m.node_key for m in self.members]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            raise ValueError(f"node_key 重复: {sorted(dup)}")

        known = set(keys) | RESERVED_NODE_KEYS
        for e in self.edges:
            if e.from_node_key not in known:
                raise ValueError(f"边的上游节点不存在: {e.from_node_key}")
            if e.to_node_key not in known:
                raise ValueError(f"边的下游节点不存在: {e.to_node_key}")

        pairs = [(e.from_node_key, e.to_node_key) for e in self.edges]
        dup_edges = {p for p in pairs if pairs.count(p) > 1}
        if dup_edges:
            raise ValueError(f"重复的边: {sorted(dup_edges)}")
        return self


class TeamGraphValidateResult(BaseModel):
    """图校验结果"""
    valid: bool
    errors: List[str] = Field(default_factory=list, description="阻断性错误")
    warnings: List[str] = Field(default_factory=list, description="非阻断提示")
    layers: List[List[str]] = Field(default_factory=list, description="拓扑分层结果（同层可并行）")
    entry_nodes: List[str] = Field(default_factory=list)
    terminal_nodes: List[str] = Field(default_factory=list)


# ── 运行 Schema ───────────────────────────────────────────────────────────────

class TeamRunCreate(BaseModel):
    """发起运行"""
    input_text: str = Field(..., min_length=1, description="用户输入")
    input_context: Optional[Dict[str, Any]] = Field(None, description="附加上下文")
    conversation_id: Optional[str] = Field(None, max_length=64, description="关联会话")
    trigger_type: str = Field(TriggerType.MANUAL, description="触发来源")
    run_config_override: Optional[AgentTeamRunConfig] = Field(None, description="本次运行的配置覆盖")
    model_id: Optional[int] = Field(None, description="前端所选大模型 id（ai_chat_model.id），用于指定编排 Leader/Worker 模型")

    @field_validator("trigger_type")
    @classmethod
    def _check_trigger(cls, v: str) -> str:
        if v not in TriggerType.ALL:
            raise ValueError(f"trigger_type 非法: {v}")
        return v


class TeamChatCreate(BaseModel):
    """团队对话（SSE 流式）请求体。

    与 TeamRunCreate 对齐，但面向 chat 场景，触发来源默认 chat。
    """

    message: str = Field(..., min_length=1, description="用户对话内容")
    input_context: Optional[Dict[str, Any]] = Field(None, description="附加上下文")
    conversation_id: Optional[str] = Field(None, max_length=64, description="关联会话")
    session_id: Optional[str] = Field(None, description="网关会话 ID（SSE 关联）")
    trigger_type: str = Field(TriggerType.API, description="触发来源（chat 视作外部 API 调用）")
    model_id: Optional[int] = Field(None, description="前端所选大模型 id（ai_chat_model.id），用于指定编排 Leader/Worker 模型")

    @field_validator("trigger_type")
    @classmethod
    def _check_trigger_chat(cls, v: str) -> str:
        if v not in TriggerType.ALL:
            raise ValueError(f"trigger_type 非法: {v}")
        return v


class TeamRunBranchRequest(BaseModel):
    """基于历史运行分支重跑"""
    from_node_key: str = Field(..., max_length=64, description="从该节点起重新执行，其上游沿用历史输出")
    input_overrides: Optional[Dict[str, str]] = Field(
        None, description="覆盖指定节点的历史输出 {node_key: output}"
    )

    @field_validator("from_node_key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        return validate_node_key(v)


class TeamRunStepOut(BaseModel):
    """节点执行快照输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    node_key: str
    role_name: Optional[str] = None
    agent_config_id: Optional[int] = None
    round_no: int = 0
    layer_no: Optional[int] = None
    seq: int = 0
    input_text: Optional[str] = None
    upstream_nodes: Optional[List[str]] = None
    output_text: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    retry_count: int = 0
    tokens: int = 0
    duration_ms: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TeamRunOut(BaseModel):
    """运行输出（列表用）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    team_id: int
    conversation_id: Optional[str] = None
    input_text: Optional[str] = None
    final_output: Optional[str] = None
    status: str
    current_round: int = 0
    current_nodes: Optional[List[str]] = None
    error_message: Optional[str] = None
    total_tokens: int = 0
    total_steps: int = 0
    duration_ms: Optional[int] = None
    trigger_type: str = TriggerType.MANUAL
    parent_run_id: Optional[str] = None
    branch_from_node: Optional[str] = None
    created_by: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    team_name: Optional[str] = Field(None, description="团队名称（装配字段）")


class TeamRunDetailOut(TeamRunOut):
    """运行详情（含步骤与快照）"""
    team_snapshot: Optional[Dict[str, Any]] = None
    node_outputs: Optional[Dict[str, Any]] = None
    input_context: Optional[Dict[str, Any]] = None
    steps: List[TeamRunStepOut] = Field(default_factory=list)


# ── 人工介入 Schema ───────────────────────────────────────────────────────────

class InterventionCreate(BaseModel):
    """提交人工介入请求"""
    intervention_type: str = Field(..., description=f"介入类型，可选 {InterventionType.ALL}")
    node_key: Optional[str] = Field(None, max_length=64, description="目标节点（节点级介入必填）")
    round_no: Optional[int] = Field(None, ge=0, description="目标轮次")
    payload: Optional[Dict[str, Any]] = Field(None, description="介入内容 {content, reason}")

    @field_validator("intervention_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in InterventionType.ALL:
            raise ValueError(f"intervention_type 非法: {v}，可选 {InterventionType.ALL}")
        return v

    @model_validator(mode="after")
    def _check_node_required(self) -> "InterventionCreate":
        if self.intervention_type in InterventionType.NODE_LEVEL and not self.node_key:
            raise ValueError(f"{self.intervention_type} 为节点级介入，必须指定 node_key")
        if self.node_key:
            validate_node_key(self.node_key)
        if self.intervention_type == InterventionType.EDIT_OUTPUT:
            if not (self.payload or {}).get("content"):
                raise ValueError("edit_output 必须在 payload.content 提供改写后的内容")
        if self.intervention_type == InterventionType.INJECT_MESSAGE:
            if not (self.payload or {}).get("content"):
                raise ValueError("inject_message 必须在 payload.content 提供注入内容")
        return self


class InterventionOut(BaseModel):
    """介入记录输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    intervention_type: str
    node_key: Optional[str] = None
    round_no: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    status: str
    applied_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    created_at: Optional[datetime] = None


# ── 事件回放 Schema ───────────────────────────────────────────────────────────

class TeamRunEventOut(BaseModel):
    """回放事件（由 agent_execution_event 转换）"""
    sequence: int
    event_type: str
    node_key: Optional[str] = Field(None, description="事件归属节点，团队级事件为 None")
    content: Optional[Dict[str, Any]] = None
    event_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class TeamRunReplayOut(BaseModel):
    """回放数据包"""
    run: TeamRunDetailOut
    events: List[TeamRunEventOut] = Field(default_factory=list)


class TeamTimelineItem(BaseModel):
    """时间线条目（已做轻量聚合，便于前端播放器逐帧回放）"""
    sequence: int
    event_type: str
    node_key: Optional[str] = None
    title: str
    detail: Optional[str] = None
    created_at: Optional[datetime] = None


class TeamTimelineOut(BaseModel):
    """回放时间线（run + 聚合事件序列）"""
    run: TeamRunDetailOut
    timeline: List[TeamTimelineItem] = Field(default_factory=list)


class TeamRerunCreate(BaseModel):
    """分支重跑（P8 回放衍生操作）。

    基于已完成的运行 ``run_id`` 派生一次新运行：
    - ``branch_from_node`` 指定从哪个节点开始重跑（断点续跑 / 局部重放）；
    - 新运行记录 ``parent_run_id = run_id``，形成可追溯分支链。
    """
    branch_from_node: Optional[str] = Field(None, max_length=64, description="重跑起点节点")
    input_text: Optional[str] = Field(None, description="覆盖输入（不填则复用原运行输入）")
    input_context: Optional[Dict[str, Any]] = Field(None, description="覆盖附加上下文")
    trigger_type: str = Field(TriggerType.MANUAL, description="触发来源")


# ── v2 实时干预（运行态介入）Schema ─────────────────────────────────────────────
# 与设计文档 §12.6 的 InterventionType（pause/resume/cancel/inject_message/skip_node/branch）对齐。
class TeamInterventionV2Create(BaseModel):
    """提交一次运行态实时干预（v2）。"""
    intervention_type: str = Field(
        ...,
        description=f"介入类型，可选 {InterventionType.ALL}",
    )
    node_key: Optional[str] = Field(None, max_length=64, description="目标节点（skip_node 必填）")
    round_no: Optional[int] = Field(None, ge=0, description="目标轮次（不填=立即生效）")
    payload: Optional[Dict[str, Any]] = Field(None, description="介入内容，按类型不同")
    operator_name: Optional[str] = Field(None, max_length=64, description="操作人名称")

    @field_validator("intervention_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in InterventionType.ALL:
            raise ValueError(f"intervention_type 非法: {v}（可选 {InterventionType.ALL}）")
        return v

    @model_validator(mode="after")
    def _check_payload(self) -> "TeamInterventionV2Create":
        if self.intervention_type == InterventionType.SKIP_NODE and not self.node_key:
            raise ValueError("skip_node 必须指定 node_key")
        if self.intervention_type == InterventionType.INJECT_MESSAGE and not (
            (self.payload or {}).get("message") or (self.payload or {}).get("text")
        ):
            raise ValueError("inject_message 必须在 payload.message 提供注入内容")
        return self


class TeamInterventionV2Out(BaseModel):
    """v2 实时干预记录输出。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    intervention_type: str
    node_key: Optional[str] = None
    round_no: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    status: str
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    result_note: Optional[str] = None
    created_at: Optional[datetime] = None


# ── 模板 Schema ───────────────────────────────────────────────────────────────

class TeamTemplateOut(BaseModel):
    """内置团队模板（代码内声明，不入库）"""
    key: str = Field(..., description="模板唯一标识")
    name: str
    description: Optional[str] = None
    mode: str
    member_count: int = 0
    available: bool = Field(True, description="当前工作空间是否具备全部所需 Agent")
    missing_agent_keys: List[str] = Field(default_factory=list, description="缺失的 agent_code 列表")


class TeamFromTemplateRequest(BaseModel):
    """按模板实例化团队"""
    template_key: str = Field(..., description="模板标识")
    name: Optional[str] = Field(None, max_length=200, description="团队名称，留空用模板名")
    team_code: Optional[str] = Field(None, max_length=100, description="留空自动生成")
