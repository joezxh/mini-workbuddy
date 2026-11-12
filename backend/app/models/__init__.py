"""SuperAgent 引擎核心 ORM 模型聚合导出（Task 1.2 2026-11-08）。

注：全量模型登记（建表单一事实来源）在 app/db/init_models.py，
此处按 tasks.md 1.2 要求显式导出 sa_* 八表，供外部按
`from app.models import SuperAgentTicket` 方式引用。
"""
from app.models.superagent import (                                          # noqa: F401
    SuperAgentTrigger, SuperAgentTicket, SuperAgentEffect,
    SuperAgentThread, SuperAgentSubscription, SuperAgentMandate,
    SuperAgentAssignment, SuperAgentAuditLog,
)

__all__ = [
    "SuperAgentTrigger",
    "SuperAgentTicket",
    "SuperAgentEffect",
    "SuperAgentThread",
    "SuperAgentSubscription",
    "SuperAgentMandate",
    "SuperAgentAssignment",
    "SuperAgentAuditLog",
]
