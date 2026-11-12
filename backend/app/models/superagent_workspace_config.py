"""SuperAgent Workspace 配置模型 —— sa_workspace_config（一张表绑定全部配置）。

对齐 spec「Workspace 绑定的数据层设计」：
  - 模型配置重用 AiChatModel（default_model_id）
  - MCP 配置重用 AiMcpApiKey（mcp_ids）
  - KB 绑定复用现有 KB 管理（kb_ids / kb_weights）
  - Policy / 执行参数 / 安全设置为 SuperAgent 专属字段

launch Effect 的 worker 并发从 max_workers 解析（无配置回落默认 3）。
"""
from sqlalchemy import (
    String, JSON, Integer, BigInteger, Boolean, Float, TIMESTAMP, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class SuperAgentWorkspaceConfig(Base):
    """一张表绑定 workspace 的全部 SuperAgent 专属配置。"""
    __tablename__ = "sa_workspace_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_workspace.id"),
        unique=True, nullable=False, index=True)

    # ---- 模型（重用 AiChatModel）----
    default_model_id: Mapped[int | None] = mapped_column(Integer, index=True,
        comment="默认模型 → ai_chat_model.id（松引用不建硬 FK，避免跨模块建表耦合）")
    jev_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    jev_router: Mapped[str] = mapped_column(String(20), default="jev-first", nullable=False,
        comment="jev-first | llm-only | jev-only")
    jev_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)

    # ---- Policy ----
    policy_rules: Mapped[list] = mapped_column(JSON, default=list, nullable=False,
        comment='[{"source":"http","pattern":".*","allow":true}]')
    jev_accept_threshold: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    proactive_auto_accept: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- KB（复用现有 KB 管理 + pgvector）----
    kb_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False, comment="[5, 8, 12]")
    kb_weights: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, comment='{"5": 1.5}')
    auto_ingest_worker_output: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ---- MCP（引用 AiMcpApiKey）----
    mcp_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # ---- 执行 ----
    max_workers: Mapped[int] = mapped_column(Integer, default=3, nullable=False,
        comment="launch Effect 并发上限")
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    eval_timeout_ms: Mapped[int] = mapped_column(Integer, default=60000, nullable=False)
    effect_concurrency: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False,
        comment='per-kind 并发覆盖 {"assessment": 4, "launch": 3, ...}')

    # ---- 安全 ----
    default_permission_mode: Mapped[str] = mapped_column(String(20), default="confirm", nullable=False)
    playwright_domain_whitelist: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    require_hitl_for_high_risk: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.now(),
        onupdate=func.now(), nullable=False)
