"""AgentTeam 多智能体团队协作 —— 团队定义模型

包含三张表：
    - agent_team          团队主表
    - agent_team_member   团队成员（引用 agent_config + 团队内覆盖配置）
    - agent_team_edge     图边（DAG 依赖关系，执行引擎的权威数据源）

设计要点：
    1. 五种协作模式（sequential/parallel/msghub/supervisor/dag）统一以 DAG 为底层存储，
       ``mode`` 字段仅记录来源模板并驱动运行时策略选择。
    2. 成员采用「引用 + 覆盖」：引用 ``agent_config.id``，``override_*`` 字段为 NULL 时沿用原值。
    3. ``agent_team.graph`` 只存前端画布布局（坐标/视口），``agent_team_edge`` 才是执行引擎读取的
       权威数据源，避免执行逻辑耦合前端 JSON 结构。

参见：docs/agent/agent-team-design.md §2
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, Integer,
    TIMESTAMP, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


# ── 保留节点标识 ──────────────────────────────────────────────────────────────

START_NODE = "__START__"
"""虚拟入口节点：``agent_team_edge.from_node_key`` 为此值表示该边的下游是入口节点"""

END_NODE = "__END__"
"""虚拟出口节点：``agent_team_edge.to_node_key`` 为此值表示该边的上游是终止节点"""

RESERVED_NODE_KEYS = frozenset({START_NODE, END_NODE})


class TeamMode(str):
    """协作模式（均落到 DAG 底层，此字段记录来源模板 + 驱动团队定义期的拓扑推导）

    注意（设计文档 §12 / §13.4）：v2 运行时实际执行不再依赖 ``mode``，统一由
    ``execution_mode`` 强制分流；``mode`` 仍用于团队定义期由 TeamGraphBuilder
    推导节点/边（parallel/supervisor/msghub 等），并用于前端展示与历史运行回放兼容。
    """
    SEQUENTIAL = "sequential"   # 链式：A→B→C
    PARALLEL = "parallel"       # 扇出 + 汇聚
    MSGHUB = "msghub"           # 群聊：成员互见，轮流发言
    SUPERVISOR = "supervisor"   # 主管动态调度
    DAG = "dag"                 # 自定义图

    ALL = (SEQUENTIAL, PARALLEL, MSGHUB, SUPERVISOR, DAG)

    #: 需要静态边的模式（由 TeamGraphBuilder 生成或用户手绘）
    STATIC_GRAPH_MODES = (SEQUENTIAL, PARALLEL, DAG)

    #: 动态轮次调度模式（不生成静态边）
    DYNAMIC_MODES = (MSGHUB, SUPERVISOR)


class ExecutionMode(str):
    """执行引擎分流（设计文档 §12.4 / §13.4）。

    v2 唯一生效值为 ``llm_orchestrated``（AgentScope Leader 动态编排）；
    ``static_dag`` 标记为 deprecated，旧路由不再分派，仅用于历史运行回放兼容。
    """

    LLM_ORCHESTRATED = "llm_orchestrated"   # v2：AgentScope Leader 纯动态 LLM 编排
    STATIC_DAG = "static_dag"               # 已废弃：v1 静态 DAG 调度器

    ALL = (LLM_ORCHESTRATED, STATIC_DAG)

    #: v2 实际生效的执行模式（路由分派依据）
    ACTIVE = (LLM_ORCHESTRATED,)

    @classmethod
    def is_active(cls, value: str) -> bool:
        """该执行模式是否为当前生效路径（非废弃回放）。"""
        return value in cls.ACTIVE


class NodeInputMode(str):
    """节点输入合并方式"""
    CONCAT = "concat"   # 默认：全部拼接 + 标注来源
    JSON = "json"       # 结构化：{node_key: output}


class NodeErrorPolicy(str):
    """单节点失败后的处理策略"""
    CONTINUE = "continue"   # 失败节点输出占位符，继续执行下游
    ABORT = "abort"         # 中止整个运行


class AgentTeam(Base, TenantMixin):
    """团队主表"""
    __tablename__ = "agent_team"

    # ── 基础信息 ───────────────────────────────────────────────────────────
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_code = Column(String(100), nullable=False, unique=True, index=True, comment="唯一标识码")
    name = Column(String(200), nullable=False, comment="团队名称")
    description = Column(Text, nullable=True, comment="描述")
    category = Column(String(50), nullable=True, comment="用途分类（数据字典: agent_team_category）")

    mode = Column(String(20), nullable=False, server_default=TeamMode.SEQUENTIAL,
                  comment="协作模式（来源模板）: sequential/parallel/msghub/supervisor/dag")

    #: 执行引擎分流（设计文档 §12.4 / §13.4）。v2 实际生效值 llm_orchestrated；
    #: static_dag 已废弃仅用于历史回放。路由层以此字段决定分派路径。
    execution_mode = Column(String(32), nullable=False, server_default=ExecutionMode.LLM_ORCHESTRATED,
                            comment="执行模式: llm_orchestrated(生效) / static_dag(废弃回放)")

    # ── 图定义（前端画布布局快照，非执行引擎数据源）────────────────────────
    graph = Column(JSONB, nullable=True,
                   comment="画布快照 {nodes:[{node_key,x,y}], viewport:{x,y,zoom}}")

    # ── 团队级共享资源 ────────────────────────────────────────────────────
    shared_knowledge_bases = Column(JSONB, nullable=True, comment="团队共享知识库 ID 列表（全员可访问）")
    shared_tools = Column(JSONB, nullable=True, comment="团队共享工具列表")

    # ── 运行策略 ──────────────────────────────────────────────────────────
    run_config = Column(JSONB, nullable=True, comment=(
        "运行配置 {max_rounds, max_parallel, node_timeout_seconds, node_timeout_per_batch, "
        "node_timeout_max, total_timeout_seconds, on_node_error, supervisor_node_key, "
        "aggregator_node_key, allow_intervention, persist_events}"
    ))

    # ── 元数据 ────────────────────────────────────────────────────────────
    is_active = Column(Boolean, nullable=False, server_default="true", comment="是否启用")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="排序权重")
    workspace_id = Column(BigInteger, nullable=True, comment="多租户隔离")

    # ── 审计字段（仅用于展示，不参与鉴权）──────────────────────────────────
    created_by = Column(BigInteger, nullable=True, comment="创建人ID")
    updated_by = Column(BigInteger, nullable=True, comment="最后修改人ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false", comment="软删除")

    __table_args__ = (
        Index("idx_agent_team_category", "category"),
        Index("idx_agent_team_active", "is_active"),
        Index("idx_agent_team_workspace", "workspace_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentTeam {self.team_code}:{self.name} mode={self.mode}>"

    # ── 运行配置读取（带默认值）────────────────────────────────────────────

    #: run_config 各项默认值，Service / Executor 统一走 get_run_option 读取
    RUN_CONFIG_DEFAULTS: Dict[str, Any] = {
        "max_rounds": 10,
        "max_parallel": 5,
        "node_timeout_seconds": 120,
        "node_timeout_per_batch": 60,
        "node_timeout_max": 900,
        "total_timeout_seconds": 1800,
        "on_node_error": NodeErrorPolicy.CONTINUE,
        "supervisor_node_key": None,
        "aggregator_node_key": None,
        "allow_intervention": True,
        "persist_events": True,
        "persist_chunks": False,
    }

    def get_run_option(self, key: str, default: Any = None) -> Any:
        """读取运行配置项，缺失时回落到 RUN_CONFIG_DEFAULTS"""
        cfg = self.run_config or {}
        if key in cfg and cfg[key] is not None:
            return cfg[key]
        if default is not None:
            return default
        return self.RUN_CONFIG_DEFAULTS.get(key)

    @property
    def is_dynamic_mode(self) -> bool:
        """是否为动态轮次调度模式（msghub/supervisor，不依赖静态边）"""
        return self.mode in TeamMode.DYNAMIC_MODES


class AgentTeamMember(Base, TenantMixin):
    """团队成员：引用 agent_config，并允许团队内覆盖"""
    __tablename__ = "agent_team_member"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(BigInteger, nullable=False, index=True, comment="所属团队 agent_team.id")

    # ── 引用现有 Agent 配置 ───────────────────────────────────────────────
    agent_config_id = Column(BigInteger, nullable=False, index=True, comment="引用 agent_config.id")

    # ── 团队内身份 ────────────────────────────────────────────────────────
    node_key = Column(String(64), nullable=False,
                      comment="节点标识（团队内唯一，供边引用/@提及，如 'researcher'）")
    role_name = Column(String(100), nullable=False, comment="团队内角色名（展示用，如 '风险研判专家'）")
    role_desc = Column(Text, nullable=True, comment="角色职责说明，注入 prompt 供其他成员理解分工")
    avatar = Column(String(200), nullable=True, comment="头像/图标")
    sort_order = Column(Integer, nullable=False, server_default="0",
                        comment="顺序（sequential 模式的执行序）")

    # ── 覆盖配置（NULL = 沿用 agent_config 原值）───────────────────────────
    override_system_prompt = Column(Text, nullable=True, comment="覆盖系统提示词")
    override_llm_config = Column(JSONB, nullable=True, comment="覆盖模型配置（深合并，可只改 temperature）")
    override_knowledge_bases = Column(JSONB, nullable=True, comment="覆盖知识库 ID 列表")
    override_tools = Column(JSONB, nullable=True, comment="覆盖工具列表")
    override_skills = Column(JSONB, nullable=True, comment="覆盖技能列表")

    # ── TeamSay 工具预设（设计文档 §12.4）──────────────────────────────────────
    # v2 单点追问（@提及）时固定挂载的可调用 persona 列表；为 NULL 时回退到团队全体成员。
    tool_preset = Column(JSONB, nullable=True, comment=(
        "TeamSay 工具预设：单点追问时可被 @提及 调起的成员 node_key 列表；"
        "NULL = 使用团队全部成员"
    ))

    # ── 节点行为 ──────────────────────────────────────────────────────────
    node_config = Column(JSONB, nullable=True, comment=(
        "节点配置 {input_mode, input_template, output_key, condition, retry, "
        "timeout_seconds, is_entry, is_terminal}"
    ))

    is_active = Column(Boolean, nullable=False, server_default="true", comment="是否启用")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("team_id", "node_key", name="uq_team_member_node_key"),
        Index("idx_team_member_team", "team_id"),
        Index("idx_team_member_agent", "agent_config_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentTeamMember team={self.team_id} node={self.node_key} role={self.role_name}>"

    #: node_config 各项默认值
    NODE_CONFIG_DEFAULTS: Dict[str, Any] = {
        "input_mode": NodeInputMode.CONCAT,
        "input_template": None,
        "output_key": None,
        "condition": None,
        "retry": 0,
        "timeout_seconds": None,
        "is_entry": False,
        "is_terminal": False,
    }

    def get_node_option(self, key: str, default: Any = None) -> Any:
        """读取节点配置项，缺失时回落到 NODE_CONFIG_DEFAULTS"""
        cfg = self.node_config or {}
        if key in cfg and cfg[key] is not None:
            return cfg[key]
        if default is not None:
            return default
        return self.NODE_CONFIG_DEFAULTS.get(key)


class AgentTeamEdge(Base, TenantMixin):
    """图边：定义节点间依赖关系，执行引擎的权威数据源"""
    __tablename__ = "agent_team_edge"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(BigInteger, nullable=False, index=True, comment="所属团队 agent_team.id")

    from_node_key = Column(String(64), nullable=False,
                           comment="上游节点 node_key；'__START__' 表示虚拟入口")
    to_node_key = Column(String(64), nullable=False,
                         comment="下游节点 node_key；'__END__' 表示虚拟出口")

    label = Column(String(100), nullable=True, comment="边标签（展示用）")
    condition = Column(Text, nullable=True, comment="条件边表达式（预留，为空=无条件）")
    sort_order = Column(Integer, nullable=False, server_default="0",
                        comment="同一 to_node 的多上游拼接顺序")
    edge_config = Column(JSONB, nullable=True, comment="边的前端样式等附加配置")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("team_id", "from_node_key", "to_node_key", name="uq_team_edge"),
        Index("idx_team_edge_team", "team_id"),
        Index("idx_team_edge_to", "team_id", "to_node_key"),
    )

    def __repr__(self) -> str:
        return f"<AgentTeamEdge {self.from_node_key}->{self.to_node_key}>"
