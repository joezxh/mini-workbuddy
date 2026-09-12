"""Agent 配置表 - 重构版本 (AgentScope 2.0.5)

合并了原 AgentStrategy 的能力，策略配置通过数据字典字段管理。
状态通过 Redis 存储，执行历史通过 AgentExecution 表记录。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, Integer,
    TIMESTAMP, JSON, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class ExecutionMode(str):
    """执行模式枚举"""
    LLM = "llm"
    WORKFLOW = "workflow"
    SKILL = "skill"
    KNOWLEDGE = "knowledge"
    HARNESS = "harness"
    PLAN = "plan"
    TEAM = "team"


class AgentConfig(Base, TenantMixin):
    """Agent 配置表"""
    __tablename__ = "agent_config"

    # ── 基础信息 ───────────────────────────────────────────────────────────
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_code = Column(String(100), nullable=False, unique=True, index=True, comment="唯一标识码")
    name = Column(String(200), nullable=False, comment="Agent名称")
    agent_type = Column(String(20), nullable=False, comment="实现类型: CHAT/WORKFLOW/SKILL")
    category = Column(String(50), nullable=True, comment="用途分类（数据字典: agent_category）")

    # ── 策略配置（合并原 AgentStrategy）──────────────────────────────────
    strategy_code = Column(String(100), nullable=True, index=True, comment="策略代码（数据字典: agent_strategy）")
    execution_mode = Column(String(50), nullable=False, default=ExecutionMode.LLM, comment="执行模式")
    system_prompt = Column(Text, nullable=True, comment="系统提示词")

    # ── 工具与资源 ────────────────────────────────────────────────────────
    tools = Column(JSONB, nullable=True, comment="可用工具列表")
    skills = Column(JSONB, nullable=True, comment="可用 Skill 列表")
    mcp_servers = Column(JSONB, nullable=True, comment="MCP 服务器配置")
    knowledge_bases = Column(JSONB, nullable=True, comment="关联知识库 ID 列表")

    # ── 模型配置 ──────────────────────────────────────────────────────────
    llm_config = Column("model_config", JSONB, nullable=True, comment="模型配置 {provider, model, base_url, temperature, max_tokens}")

    # ── 执行配置 ──────────────────────────────────────────────────────────
    hitl_config = Column(JSONB, nullable=True, comment="HITL 配置 {enabled, confirm_tools, plan_approval}")
    react_config = Column(JSONB, nullable=True, comment="ReAct 配置 {max_iters, timeout_seconds}")
    context_config = Column(JSONB, nullable=True, comment="上下文配置 {max_tokens, compression_enabled}")

    # ── 模式特定配置 ───────────────────────────────────────────────────────
    config = Column(JSONB, nullable=True, comment="类型特定配置")

    # ── 元数据 ─────────────────────────────────────────────────────────────
    description = Column(Text, nullable=True, comment="描述")
    is_active = Column(Boolean, nullable=False, server_default="true", comment="是否启用")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="排序权重")
    workspace_id = Column(BigInteger, nullable=True, comment="多租户隔离")
    workflow_id = Column(BigInteger, nullable=True, comment="FK → workflow_flow.id")

    # ── 审计字段 ──────────────────────────────────────────────────────────
    created_by = Column(BigInteger, nullable=True, comment="创建人ID")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false", comment="软删除")

    __table_args__ = (
        Index("idx_agent_config_category", "category"),
        Index("idx_agent_config_strategy", "strategy_code"),
        Index("idx_agent_config_mode", "execution_mode"),
        Index("idx_agent_config_active", "is_active"),
        Index("idx_agent_config_workflow", "workflow_id"),
    )

    def __repr__(self):
        return f"<AgentConfig {self.agent_code}:{self.name}>"

    def to_agent_kwargs(self) -> Dict[str, Any]:
        """转换为 engine/factory 消费的 Agent 构造参数。

        形状需与 AgentExecutionEngine（agent_config 读取）及
        AgentFactory.build_agent（model_config / mcp_servers / tools / skills）一致：
            {
              "agent_code": "...",       # 身份标识（技能型装配/审计用）
              "agent_type": "...",       # 实现类型 CHAT/WORKFLOW/SKILL（模板装配依据）
              "model_config": {...},     # 含 model_code 或 provider/model
              "mcp_servers": [...],
              "tools": [...],
              "skills": [...],
              "system_prompt": "...",
              "hitl_config": {...},
              "execution_mode": "...",
            }
        """
        return {
            "agent_code": self.agent_code,
            "agent_type": self.agent_type,
            "model_config": self.llm_config or {},
            "mcp_servers": self.mcp_servers or [],
            "tools": self.tools or [],
            "skills": self.skills or [],
            "system_prompt": self.system_prompt,
            "hitl_config": self.hitl_config or {},
            "react_config": self.react_config or {},
            "execution_mode": self.execution_mode or "llm",
        }
