"""字段↔标准绑定服务（P2 Task 11，规则通道）。

主流程（spec §5.6）：
1. 用 ``RuleEngine.detect_semantic`` 给每列做**规则标注**（语义类型 + PII 等级）；
2. 用 ``RuleEngine.match_standard`` 把列匹配到 ``MetaStandard`` 标准项；
3. 落 ``meta_column_standard``（source=rule，评审状态由置信度分层决定），并写变更历史。

安全/幂等：
- 已存在且为「人工 accepted」的绑定**不覆盖**（尊重人工裁决）；
- 其它情况 upsert（按 column_id 唯一），每次重绑写一条 history；
- 低于 ``CONF_SUGGEST_MIN`` 的标准匹配不落库（drop）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.dataops.rule_engine import TIER_ACCEPTED, RuleEngine, tier
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.standard import (
    MetaColumnStandard, MetaColumnStandardHistory, MetaStandard,
)
from app.services.dataops.standard_service import MetaStandardService


@dataclass
class BindReport:
    """绑定结果统计。"""

    tables: int = 0
    columns: int = 0
    annotated: int = 0          # 规则标注（语义/PII）生效列数
    bound: int = 0              # 新建标准绑定
    updated: int = 0            # 更新已有绑定
    skipped_human: int = 0      # 跳过人工 accepted 绑定
    details: List[dict] = field(default_factory=list)


class StandardBindingService:
    """字段↔标准绑定（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("StandardBindingService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _standards(self) -> List[dict]:
        svc = MetaStandardService(self.db, self.tenant_id)
        return [MetaStandardService.serialize(s) for s in svc.list_standards(status="published")]

    def _annotate(self, col: MetaColumn) -> bool:
        profile = col.profile_json or {}
        ann = RuleEngine.detect_semantic(
            col.column_name,
            data_type=col.data_type,
            comment=col.column_comment,
            profile_top_values=profile.get("top_values"),
        )
        if ann.semantic_type is None:
            return False
        col.semantic_type = ann.semantic_type
        col.pii_level = ann.pii_level
        return True

    def _bind_column(self, col: MetaColumn, standards: List[dict], report: BindReport) -> None:
        matched = RuleEngine.match_standard(
            col.column_name, col.column_comment, col.data_type, standards
        )
        if matched is None:
            return
        existing = self.db.execute(
            select(MetaColumnStandard).where(MetaColumnStandard.column_id == col.id)
        ).scalar_one_or_none()

        status = tier(matched.confidence)
        if status == "drop":
            return

        if existing is not None:
            # 尊重人工裁决：已 accepted 的人工绑定不覆盖
            if existing.source == "human" and existing.status == TIER_ACCEPTED:
                report.skipped_human += 1
                report.details.append({"column": col.column_name, "action": "skip_human"})
                return
            existing.standard_id = matched.standard_id
            existing.standard_version = None
            existing.confidence = matched.confidence
            existing.evidence_json = matched.evidence
            existing.status = status
            existing.source = "rule"
            report.updated += 1
            action = "bind_update"
        else:
            existing = MetaColumnStandard(
                tenant_id=self.tenant_id,
                column_id=col.id,
                standard_id=matched.standard_id,
                standard_version=None,
                confidence=matched.confidence,
                evidence_json=matched.evidence,
                status=status,
                source="rule",
            )
            self.db.add(existing)
            self.db.flush()
            report.bound += 1
            action = "bind_new"

        self.db.add(
            MetaColumnStandardHistory(
                tenant_id=self.tenant_id,
                column_id=col.id,
                standard_id=matched.standard_id,
                standard_version=None,
                action=action,
                snapshot_json={
                    "standard_code": matched.standard_code,
                    "confidence": matched.confidence,
                    "status": status,
                    "evidence": matched.evidence,
                },
            )
        )
        report.details.append(
            {"column": col.column_name, "standard": matched.standard_code,
             "confidence": matched.confidence, "status": status, "action": action}
        )

    def bind_table(self, table_id: int) -> BindReport:
        table = self.db.execute(
            select(MetaTable).where(
                MetaTable.tenant_id == self.tenant_id, MetaTable.id == table_id
            )
        ).scalar_one_or_none()
        if table is None:
            raise KeyError(table_id)
        standards = self._standards()
        report = BindReport(tables=1)
        cols = self.db.execute(
            select(MetaColumn).where(MetaColumn.table_id == table_id)
        ).scalars().all()
        for col in cols:
            report.columns += 1
            if self._annotate(col):
                report.annotated += 1
            self._bind_column(col, standards, report)
        return report

    def bind_source(self, source_id: int, database: Optional[str] = None) -> BindReport:
        stmt = select(MetaTable).where(
            MetaTable.tenant_id == self.tenant_id, MetaTable.source_id == source_id
        )
        if database:
            stmt = stmt.where(MetaTable.database == database)
        tables = list(self.db.execute(stmt.scalars()).all())
        report = BindReport(tables=len(tables))
        for t in tables:
            sub = self.bind_table(t.id)
            report.columns += sub.columns
            report.annotated += sub.annotated
            report.bound += sub.bound
            report.updated += sub.updated
            report.skipped_human += sub.skipped_human
            report.details.extend(sub.details)
        return report
