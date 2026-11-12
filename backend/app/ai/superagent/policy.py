"""PolicyService —— Policy 规则 + 准入 + 版本化热变更。

对齐 dsh-superagent policy.ts + SuperAgent spec.md FR9/FR12。
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger


DEFAULT_RULES = [
    {"id": "copy", "intent": "修复文案/标签/提示文本",
     "keywords": ["文案", "标签", "提示", "typo", "copy"]},
    {"id": "visual", "intent": "修复视觉/布局/样式",
     "keywords": ["样式", "布局", "视觉", "UI", "css"]},
]


@dataclass
class AdmissionRule:
    """AdmissionTable 2×2 cell：explicit / inferred / ignore。"""
    kind: str  # github.issues / github.pulls / github.comments / github.ci / feishu.group / feishu.dm / http
    cell: str  # listed_unaddressed / unlisted_addressed / unlisted_unaddressed
    value: Literal["explicit", "inferred", "ignore"] = "ignore"


@dataclass
class AssessmentOutcome:
    """Eval 输出：matched rules + direction + intent evidence。"""
    matched_rules: list[dict] = field(default_factory=list)
    direction: Literal["accept", "ignore", "block", "would_accept"] = "ignore"
    intent_evidence: str = ""
    gate_passed: bool = False

    def can_accept(self) -> bool:
        """三条件校验：matched>=1 + directionAllowed + intent_evidence 存在。"""
        return (
            len(self.matched_rules) >= 1
            and self.direction in ("accept", "would_accept")
            and bool(self.intent_evidence.strip())
        )


class PolicyService:
    """Policy 规则管理 + 准入计算 + 版本化 hash。"""

    def __init__(self, rules: list[dict] | None = None,
                 admission_rows: list[AdmissionRule] | None = None,
                 eval_mode: str = "auto",
                 allowed_senders: list[str] | None = None,
                 bots: list[str] | None = None):
        self.rules = rules or DEFAULT_RULES
        self.admission_rows = admission_rows or self._default_admission()
        self.eval_mode = eval_mode
        self.allowed_senders = set(allowed_senders or [])
        self.bots = set(bots or [])

    @staticmethod
    def _default_admission() -> list[AdmissionRule]:
        """dsh-superagent 默认 AdmissionTable —— GitHub 4 Trigger + Feishu 2 类。"""
        rows: list[AdmissionRule] = []
        for kind in ("github.issues", "github.pulls", "github.comments"):
            rows.extend([
                AdmissionRule(kind, "listed_unaddressed", "explicit"),
                AdmissionRule(kind, "unlisted_addressed", "explicit"),
                AdmissionRule(kind, "unlisted_unaddressed", "ignore"),
            ])
        # CI 无 sender → 默认 inferred
        rows.append(AdmissionRule("github.ci", "unlisted_unaddressed", "inferred"))
        rows.append(AdmissionRule("feishu.group", "unlisted_addressed", "explicit"))
        rows.append(AdmissionRule("feishu.group", "unlisted_unaddressed", "ignore"))
        rows.append(AdmissionRule("feishu.dm", "unlisted_unaddressed", "explicit"))
        return rows

    # ---- Policy version hash ----
    def version(self) -> str:
        """Policy 版本 hash —— 覆盖 rules + eval_mode + admission_table。"""
        data = json.dumps({
            "rules": self.rules,
            "eval_mode": self.eval_mode,
            "admission": [(r.kind, r.cell, r.value) for r in self.admission_rows],
        }, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    # ---- 准入 gate ----
    def gate(self, *, source_kind: str, source: str,
             sender_id: str | None, addressed: bool) -> AdmissionRule:
        """查找 AdmissionTable cell —— 返回命中的 AdmissionRule。"""
        if source_kind == "github.ci" or sender_id is None:
            cell_key = "unlisted_unaddressed"
        else:
            sender_in_listed = (
                sender_id in self.allowed_senders or sender_id in self.bots
            )
            if sender_in_listed and addressed:
                cell_key = "listed_unaddressed"
            elif not sender_in_listed and addressed:
                cell_key = "unlisted_addressed"
            else:
                cell_key = "unlisted_unaddressed"
        for ar in self.admission_rows:
            if ar.kind == source_kind and ar.cell == cell_key:
                return ar
        return AdmissionRule(source_kind, cell_key, "ignore")

    # ---- 评估 ----
    def assess(self, *, source_kind: str, source: str,
               sender_id: str | None, addressed: bool,
               trigger_text: str, sender_name: str = "") -> AssessmentOutcome:
        """MasterAssessor：匹配 rules + admission gate。"""
        admission = self.gate(
            source_kind=source_kind, source=source,
            sender_id=sender_id, addressed=addressed,
        )
        matched: list[dict] = []
        text_lc = trigger_text.lower()
        for rule in self.rules:
            kw = rule.get("keywords", [])
            hit = next((k for k in kw if k.lower() in text_lc), None)
            if hit:
                matched.append({
                    "rule_id": rule["id"],
                    "reason": f"关键词 '{hit}' 命中",
                })
        outcome = AssessmentOutcome(
            matched_rules=matched,
            direction=(
                "ignore" if admission.value == "ignore"
                else ("accept" if admission.value == "explicit" else "would_accept")
            ),
            intent_evidence=(
                f"sender={sender_id or 'unknown'} ({sender_name}) · "
                f"triggered={addressed} · text={trigger_text[:200]}"
                if trigger_text else ""
            ),
            gate_passed=admission.value != "ignore",
        )
        # 额外校验
        if admission.value == "ignore":
            outcome.direction = "ignore"
        elif len(matched) == 0:
            outcome.direction = "ignore"
        elif not trigger_text.strip():
            outcome.intent_evidence = ""
            outcome.direction = "ignore"
        return outcome

    # ---- Policy 热变更影响计算 ----
    def changes_from(self, old_rules: list[dict],
                     old_admission: list[tuple] | None = None) -> list[dict]:
        """Policy settings 变更 → 计算受影响的活 Ticket 列表。"""
        affected: list[dict] = []
        old_rule_ids = {r["id"] for r in old_rules}
        new_rule_ids = {r["id"] for r in self.rules}
        removed = old_rule_ids - new_rule_ids
        added = new_rule_ids - old_rule_ids
        if removed:
            affected.append({
                "reason": f"Rule removed: {removed}",
                "impact": "may revoke existing accepts",
            })
        if added:
            affected.append({
                "reason": f"Rule added: {added}",
                "impact": "may trigger new accepts",
            })
        logger.info(f"Policy changes: {affected or 'none'}")
        return affected

    # ---- 7.1 Policy 热变更：受影响活 Ticket 计算 + 完整应用 ----

    def policy_effects(self, open_tickets: list[dict], old_policy: "PolicyService",
                       source_scope: dict | None = None) -> dict[str, dict]:
        """计算 Policy 变更对每个活 Ticket 的影响（对齐 dsh policyEffects()）。

        self = 新 Policy，old_policy = 变更前 Policy。
        只有「Mandate.matched_rules 引用了被移除 rule id」的 Ticket 受影响：
          {"kind": "rules_removed", "rules": [被移除且被引用的 rule id]}
        修改 rule instruction / 新增 rule / allowed 变更均不影响已 accept Ticket
        （Mandate 不可变）。

        Args:
            open_tickets: [{"ticket_id", "mandate_matched_rules", "title", ...}]，
                mandate_matched_rules 元素支持 [{"rule_id": ...}] 或纯 rule id 字符串。
            old_policy: 变更前的 PolicyService。
            source_scope: 预留（per-Source scope 判断，dsh 对齐位）。
        """
        removed = ({r["id"] for r in old_policy.rules}
                   - {r["id"] for r in self.rules})
        effects: dict[str, dict] = {}
        if not removed:
            return effects
        for t in open_tickets or []:
            refs = _mandate_rule_ids(t.get("mandate_matched_rules") or [])
            hit = sorted(refs & removed)
            if hit:
                effects[str(t.get("ticket_id"))] = {"kind": "rules_removed", "rules": hit}
        logger.info(
            f"PolicyService.policy_effects · removed={sorted(removed)} · "
            f"affected={list(effects)}"
        )
        return effects

    async def apply_change(self, old_policy: "PolicyService",
                           engine: Any | None = None,
                           effects_queue: Any | None = None) -> dict:
        """完整变更应用流程（Task 7.1）：
          1. 计算新 version；
          2. 收集活 Ticket → policy_effects；
          3. 每个受影响 Ticket → engine.tickets.ticket_report(kind="progress",
             message="policy_changed: ...") 记录 + effects_queue.enqueue(kind="reply",
             payload={"ticket_id", "text": "⚠️ Policy 已更新：...", "channel": "sse"})。

        engine / effects_queue 为 None 时纯计算模式（只返回统计，不落通知）。
        """
        new_version = self.version()
        open_tickets = self._collect_open_tickets(engine) if engine is not None else []
        effects = self.policy_effects(open_tickets, old_policy)
        ws_by_ticket = {
            str(t.get("ticket_id")): (t.get("workspace_id") or 1)
            for t in open_tickets or []
        }
        for ticket_id, effect in effects.items():
            text = f"⚠️ Policy 已更新：以下规则已变更 {', '.join(effect.get('rules', []))}"
            if engine is not None:
                try:
                    engine.tickets.ticket_report(ticket_id, {
                        "kind": "progress",
                        "message": f"policy_changed: {effect}",
                    })
                except Exception as e:
                    logger.warning(f"apply_change · ticket_report failed · ticket={ticket_id}: {e}")
            if effects_queue is not None:
                try:
                    await effects_queue.enqueue(
                        workspace_id=ws_by_ticket.get(ticket_id, 1),
                        kind="reply",
                        payload={"ticket_id": ticket_id, "text": text, "channel": "sse"},
                    )
                except Exception as e:
                    logger.warning(f"apply_change · reply enqueue failed · ticket={ticket_id}: {e}")
            logger.info(f"apply_change · ticket={ticket_id} · effect={effect}")
        return {"affected": len(effects), "new_version": new_version}

    @staticmethod
    def _collect_open_tickets(engine: Any) -> list[dict]:
        """从 Engine 收集活 Ticket + Mandate.matched_rules（查询失败按空处理）。"""
        repo = getattr(engine, "repository", None)
        if repo is None:
            return []
        try:
            from app.models.superagent import SuperAgentTicket
            out: list[dict] = []
            with repo.atomic() as db:
                rows = db.query(SuperAgentTicket).filter(
                    SuperAgentTicket.status.in_(LIVE_TICKET_STATUSES),
                ).all()
                for t in rows:
                    mandate = repo.get_mandate(db, ticket_id=t.id)
                    out.append({
                        "ticket_id": t.id,
                        "workspace_id": t.workspace_id,
                        "title": t.title,
                        "mandate_matched_rules": list(mandate.matched_rules or []) if mandate else [],
                    })
            return out
        except Exception as e:
            logger.warning(f"PolicyService.apply_change · 收集活 Ticket 失败（按空处理）: {e}")
            return []


def _mandate_rule_ids(matched_rules: list) -> set[str]:
    """Mandate.matched_rules → rule id 集合（兼容 dict 与纯字符串两种形态）。"""
    ids: set[str] = set()
    for entry in matched_rules or []:
        if isinstance(entry, dict):
            rid = entry.get("rule_id") or entry.get("id")
        else:
            rid = entry
        if rid:
            ids.add(str(rid))
    return ids


# 视为「活 Ticket」的状态（未终态；completed/failed/dropped 不参与 Policy 热变更通知）
LIVE_TICKET_STATUSES = ("open", "working", "waiting_hitl", "waiting_person", "waiting_follows")
