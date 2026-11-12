"""PolicyHotChange —— Policy settings 版本化热变更。

对齐 dsh-superagent policyHotChange.ts —— version++ → 计算受影响活 Ticket → 送达 Assignment 通知。
不撤销 Mandate（不可变）。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from loguru import logger

from .policy import PolicyService


@dataclass
class HotChangeResult:
    affected_ticket_ids: list[str]
    new_version: str
    reinited_evals: int


class PolicyHotChange:
    """Policy 版本化热变更处理器。"""

    def __init__(self, engine: Any, policy: PolicyService):
        self.engine = engine
        self.policy = policy

    def apply_change(self, *, repo: Any, workspace_id: int,
                     new_policy: PolicyService | None = None,
                     reason: str = "manual") -> HotChangeResult:
        """Policy settings 变更 → 计算影响 → 送达 Assignment 通知 → 不撤销 Mandate。"""
        old_version = self.policy.version()
        new_policy = new_policy or self.policy
        new_version = new_policy.version()
        if old_version == new_version:
            logger.info(f"PolicyHotChange · version unchanged · {old_version}")
            return HotChangeResult([], new_version, 0)

        # 1. 计算变更影响 —— changes_from(self=self 为新策略, old_rules=旧策略的 rules)
        changes = new_policy.changes_from(
            self.policy.rules,
            old_admission=[(r.kind, r.cell, r.value) for r in self.policy.admission_rows],
        )

        # 2. 找所有活 Ticket → 给每个受影响 Ticket 的 Assignment 送达通知（不撤销 Mandate）
        with repo.atomic() as db:
            active_tickets = repo.list_tickets(db, workspace_id=workspace_id)
            affected = [
                t.id for t in active_tickets
                if t.status not in ("completed", "failed", "dropped")
            ]
            for tid in affected:
                repo.log_action(
                    db,
                    workspace_id=workspace_id,
                    action="policy_changed",
                    ticket_id=tid,
                    detail={
                        "old_version": old_version,
                        "new_version": new_version,
                        "reason": reason,
                        "changes": changes,
                    },
                )

        logger.info(
            f"PolicyHotChange · {old_version}→{new_version} · {len(affected)} affected · reason={reason}"
        )

        # 3. 更新 PolicyService 引用 + 重新运行运行中的 Eval（简化：暂不触发）
        self.policy.rules = new_policy.rules
        self.policy.admission_rows = new_policy.admission_rows
        self.policy.eval_mode = new_policy.eval_mode
        self.policy.allowed_senders = new_policy.allowed_senders
        self.policy.bots = new_policy.bots

        return HotChangeResult(affected, new_version, 0)
