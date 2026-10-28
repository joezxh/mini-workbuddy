"""字段↔标准绑定服务（P2 Task 11，规则通道）。

主流程（spec §5.6）：
1. 用 ``RuleEngine.detect_semantic`` 给每列做**规则标注**（语义类型 + PII 等级）；
2. 用 ``RuleEngine.match_standard`` 把列匹配到 ``MetaStandard`` 标准项；
3. 落 ``meta_column_standard``（source=rule，评审状态由置信度分层决定），并写变更历史。

CDM 扩展（B3/B4）：
4. 用 ``RuleEngine.match_object`` 把**表**匹配到 ``MetaObjectStandard``，落
   ``meta_table_standard``（表侧 1:1，评审语义与列绑定一致）；
5. 按 (source, database) 校验已发布关系标准，落 ``meta_relation_check``。

安全/幂等：
- 已存在且为「人工 accepted」的绑定**不覆盖**（尊重人工裁决，列/表同策略）；
- 其它情况 upsert（按 column_id / table_id 唯一），每次重绑写一条 history；
- 低于 ``CONF_SUGGEST_MIN`` 的标准匹配不落库（drop）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.dataops.rule_engine import TIER_ACCEPTED, RuleEngine, tier
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.meta_relation import MetaRelation
from app.models.dataops.standard import (
    MetaColumnStandard, MetaColumnStandardHistory, MetaStandard,
)
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaRelationCheck, MetaTableStandard,
    MetaTableStandardHistory,
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
    # 表→对象绑定（B3）
    objects_bound: int = 0
    objects_updated: int = 0
    objects_skipped_human: int = 0
    # 关系校验（B4）
    relation_checked: int = 0
    hit: int = 0
    missing: int = 0
    conflict: int = 0
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

    def _object_standards(self) -> List[dict]:
        """本租户已发布的对象标准（供 ``match_object`` 消费）。"""
        objs = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.status == "published",
            )
        ).scalars().all()
        return [
            {"id": o.id, "code": o.code, "name": o.name, "aliases": o.aliases_json or []}
            for o in objs
        ]

    def _bind_table_object(
        self, table: MetaTable, object_standards: List[dict], report: BindReport
    ) -> None:
        """把物理表绑定到对象标准（尊重人工 accepted；无命中/降级则跳过）。"""
        if not object_standards:
            return
        matched = RuleEngine.match_object(
            table.table_name, getattr(table, "table_comment", None), object_standards
        )
        if matched is None or matched.object_id is None:
            return
        status = tier(matched.confidence)
        if status == "drop":
            return

        existing = self.db.execute(
            select(MetaTableStandard).where(MetaTableStandard.table_id == table.id)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.source == "human" and existing.status == TIER_ACCEPTED:
                report.objects_skipped_human += 1
                report.details.append({"table": table.table_name, "action": "skip_human"})
                return
            existing.object_standard_id = matched.object_id
            existing.confidence = matched.confidence
            existing.evidence_json = matched.evidence
            existing.status = status
            existing.source = "rule"
            report.objects_updated += 1
            action = "bind_update"
        else:
            self.db.add(
                MetaTableStandard(
                    tenant_id=self.tenant_id,
                    table_id=table.id,
                    object_standard_id=matched.object_id,
                    confidence=matched.confidence,
                    evidence_json=matched.evidence,
                    status=status,
                    source="rule",
                )
            )
            report.objects_bound += 1
            action = "bind_new"
            self.db.flush()

        self.db.add(
            MetaTableStandardHistory(
                tenant_id=self.tenant_id,
                table_id=table.id,
                object_standard_id=matched.object_id,
                action=action,
                snapshot_json={
                    "object_code": matched.object_code,
                    "confidence": matched.confidence,
                    "status": status,
                },
            )
        )
        report.details.append(
            {"table": table.table_name, "object": matched.object_code,
             "confidence": matched.confidence, "status": status, "action": action}
        )

    # ── 关系校验（B4）─────────────────────────────────────────────────
    def _bound_tables(self, object_id: int, source_id: int, database: str) -> List[str]:
        """对象在某数据源/库下已绑定的物理表名。"""
        rows = self.db.execute(
            select(MetaTable.table_name)
            .join(MetaTableStandard, MetaTableStandard.table_id == MetaTable.id)
            .where(
                MetaTableStandard.object_standard_id == object_id,
                MetaTable.source_id == source_id,
                MetaTable.database == database,
            )
        ).all()
        return [r[0] for r in rows]

    def _check_relations(self, source_id: int, database: str) -> None:
        """按 (source, database) 全量校验已发布关系标准（幂等 upsert）。

        verdict 语义：
        - ``hit``：存在同向推断关系；
        - ``conflict``：只存在反方向推断（left/right 与标准 from/to 相反）；
        - ``missing``：无任何推断关系。
        任一端对象在该库无绑定表 → 无法定位比对范围，跳过。
        """
        relations = self.db.execute(
            select(MetaObjectRelation).where(
                MetaObjectRelation.tenant_id == self.tenant_id,
                MetaObjectRelation.status == "published",
            )
        ).scalars().all()
        for rel in relations:
            from_tables = self._bound_tables(rel.from_object_id, source_id, database)
            to_tables = self._bound_tables(rel.to_object_id, source_id, database)
            if not from_tables or not to_tables:
                continue
            from_set, to_set = set(from_tables), set(to_tables)
            forward = self.db.execute(
                select(MetaRelation).where(
                    MetaRelation.tenant_id == self.tenant_id,
                    MetaRelation.source_id == source_id,
                    MetaRelation.database == database,
                    MetaRelation.left_table.in_(from_set),
                    MetaRelation.right_table.in_(to_set),
                )
            ).scalars().first()
            reverse = self.db.execute(
                select(MetaRelation).where(
                    MetaRelation.tenant_id == self.tenant_id,
                    MetaRelation.source_id == source_id,
                    MetaRelation.database == database,
                    MetaRelation.left_table.in_(to_set),
                    MetaRelation.right_table.in_(from_set),
                )
            ).scalars().first()
            if forward is not None:
                verdict, inferred_id, conf = "hit", forward.id, forward.confidence
            elif reverse is not None:
                verdict, inferred_id, conf = "conflict", reverse.id, reverse.confidence
            else:
                verdict, inferred_id, conf = "missing", None, None
            self._upsert_relation_check(
                rel.id, source_id, database, verdict, inferred_id, conf,
                {
                    "from_tables": sorted(from_set),
                    "to_tables": sorted(to_set),
                    "relation_type": rel.relation_type,
                },
            )

    def _upsert_relation_check(
        self,
        relation_id: int,
        source_id: int,
        database: str,
        verdict: str,
        inferred_id: Optional[int],
        confidence: Optional[float],
        evidence: dict,
    ) -> None:
        row = self.db.execute(
            select(MetaRelationCheck).where(
                MetaRelationCheck.standard_relation_id == relation_id,
                MetaRelationCheck.source_id == source_id,
                MetaRelationCheck.database == database,
            )
        ).scalar_one_or_none()
        if row is None:
            row = MetaRelationCheck(
                tenant_id=self.tenant_id,
                standard_relation_id=relation_id,
                source_id=source_id,
                database=database,
            )
            self.db.add(row)
        row.verdict = verdict
        row.inferred_relation_id = inferred_id
        row.confidence = confidence
        row.evidence_json = evidence
        self.db.flush()

    def _source_databases(self, source_id: int, database: Optional[str] = None) -> List[str]:
        """校验作用域：显式库优先，否则取该源下快照里出现过的全部库。"""
        if database:
            return [database]
        rows = self.db.execute(
            select(MetaTable.database)
            .where(
                MetaTable.tenant_id == self.tenant_id,
                MetaTable.source_id == source_id,
            )
            .distinct()
        ).all()
        return [r[0] for r in rows]

    def _tally_relation_verdicts(
        self, report: BindReport, source_id: int, database: Optional[str] = None
    ) -> None:
        stmt = (
            select(MetaRelationCheck.verdict, func.count())
            .where(
                MetaRelationCheck.tenant_id == self.tenant_id,
                MetaRelationCheck.source_id == source_id,
            )
            .group_by(MetaRelationCheck.verdict)
        )
        if database:
            stmt = stmt.where(MetaRelationCheck.database == database)
        counts = {verdict: count for verdict, count in self.db.execute(stmt).all()}
        report.hit = counts.get("hit", 0)
        report.missing = counts.get("missing", 0)
        report.conflict = counts.get("conflict", 0)
        report.relation_checked = report.hit + report.missing + report.conflict

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
        # 列 → 属性 之后：表 → 对象
        self._bind_table_object(table, self._object_standards(), report)
        return report

    def bind_source(self, source_id: int, database: Optional[str] = None) -> BindReport:
        stmt = select(MetaTable).where(
            MetaTable.tenant_id == self.tenant_id, MetaTable.source_id == source_id
        )
        if database:
            stmt = stmt.where(MetaTable.database == database)
        tables = list(self.db.execute(stmt).scalars().all())
        report = BindReport(tables=len(tables))
        for t in tables:
            sub = self.bind_table(t.id)
            report.columns += sub.columns
            report.annotated += sub.annotated
            report.bound += sub.bound
            report.updated += sub.updated
            report.skipped_human += sub.skipped_human
            report.objects_bound += sub.objects_bound
            report.objects_updated += sub.objects_updated
            report.objects_skipped_human += sub.objects_skipped_human
            report.details.extend(sub.details)
        # 表→对象 落库之后：关系标准 vs 推断关系的三态校验
        for db_name in self._source_databases(source_id, database):
            self._check_relations(source_id, db_name)
        self._tally_relation_verdicts(report, source_id, database)
        return report
