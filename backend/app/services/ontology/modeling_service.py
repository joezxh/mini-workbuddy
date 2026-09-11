"""本体建模服务（P4.2）—— 六张治理表的租户安全读写与 CQ 覆盖度。

背景
----
P4.1 的 `OntologyRepository` 服务于 OWL 引擎（类/标注/TTL 原文）；
本服务面向**治理**：对象类型、属性、关系类型、物理映射、能力问题（CQ）。
借鉴 ontomind 的 CQ 驱动建模方法——先写下业务要回答的问题（CQ），
再围绕它建模对象类型/关系，`cq_coverage()` 量化建模进度。

租户安全（P4.2 关键设计）
------------------------
六张建模表**不带 `tenant_id`**（spec §5.2），经 `ontology_id` 归属到本体。
因此本服务的每一个方法都遵循同一条链路：

    tenant_id + code → 解析 ontology 行 → 用该 ontology_id 过滤子表

绝不接收裸 `ontology_id` 直查子表——租户 A 的服务实例访问租户 B 的本体，
行为等同「不存在」。这是「子表无租户列」的安全前提，有测试固化
（`test_modeling.py::test_cross_tenant_access_is_isolated`）。

事务
----
写方法默认即时提交；批量写场景可传 `auto_commit=False`（只 flush，
提交权交回调用方——与 P4.1 仓储的 IM-05 事务收口约定一致）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ontology.model import (
    SOURCES,
    OntologyCq,
    OntologyLinkType,
    OntologyMapping,
    OntologyObjectType,
    OntologyProperty,
)
from app.models.ontology.ontology import Ontology
from app.services.dataops.rule_engine import CONF_AUTO_ACCEPT, CONF_SUGGEST_MIN
from app.services.ontology.ontology_repository import OntologyRepository

logger = logging.getLogger(__name__)

#: CQ 状态（CQ 不参与 suggested/accepted 评审流转）
CQ_STATUSES = ("active", "archived")

#: 关系基数合法取值
CARDINALITIES = ("1:1", "1:N", "N:1", "N:M")

#: 映射目标类型
MAPPING_TARGET_TYPES = ("table", "column")


class ModelingError(ValueError):
    """建模服务校验错误（ValueError 子类：路由层可按 400 客户端错误处理）。"""


# ── P2 元数据投影（候选生成的抽象输入）───────────────────────────────────────
# 字段对齐 P2 计划的 `meta_table` / `meta_column` 模型（唯一键
# `(source_id, database, table_name)`）与 `relation_inference` 的列对产出。
# P2 的 ORM 落地后，补一个「ORM 行 → 数据类」薄适配即可接入，接口不变。

@dataclass
class MetaTableRef:
    """P2 `meta_table` 投影：一张被扫描到的物理表。"""

    source_id: str
    database: str
    table_name: str
    comment: str = ""
    #: 表级置信度。表扫描本身不带评分（表存在是客观事实），None → 候选
    #: status=suggested（进入人工评审，spec §8 联动主链路）。
    confidence: Optional[float] = None


@dataclass
class MetaColumnRef:
    """P2 `meta_column` 投影：一列及其规则标注置信度。"""

    source_id: str
    database: str
    table_name: str
    column_name: str
    data_type: str = "string"
    comment: str = ""
    #: 来自 P2 rule_engine 的列置信度。None（未标注）→ suggested 人工兜底。
    confidence: Optional[float] = None


@dataclass
class ColumnPairOverlap:
    """P2 `relation_inference` 投影：一对列的重叠度（join 候选）。"""

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    overlap_ratio: float


@dataclass
class CandidateReport:
    """候选生成结果统计（created/skipped 明细，供 API 与 Tool 复用）。"""

    created: Dict[str, int] = field(default_factory=dict)
    skipped: Dict[str, int] = field(default_factory=dict)

    def bump(self, kind: str, created: bool) -> None:
        bucket = self.created if created else self.skipped
        bucket[kind] = bucket.get(kind, 0) + 1


# ── 一致性校验（Task 3）───────────────────────────────────────────────────────

@dataclass
class ConsistencyIssue:
    """一条一致性问题。

    kind:    dangling_parent | cyclic_inheritance | uri_conflict
    layer:   modeling（ontology_object_type）| owl（ontology_class）
    severity: error | warning
    subject: 对象类型 code 或 OWL 类 uri
    """

    kind: str
    layer: str
    severity: str
    subject: str
    detail: str


@dataclass
class ConsistencyReport:
    """一致性校验报告（纯读产出，不做任何修复）。"""

    issues: List[ConsistencyIssue] = field(default_factory=list)

    def by_kind(self, kind: str) -> List[ConsistencyIssue]:
        return [i for i in self.issues if i.kind == kind]

    @property
    def is_clean(self) -> bool:
        return not self.issues


class ModelingService:
    """本体建模服务：对象类型 / 属性 / 关系 / 映射 / CQ 的租户安全读写。"""

    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int],
        code: str = "default",
        *,
        auto_commit: bool = True,
    ) -> None:
        """
        :param auto_commit: 写方法是否即时提交。批量写传 False，由调用方
            在一个显式事务里收口（评审 IM-05 的约定）。
        """
        self._db = db
        self._tenant_id = tenant_id
        self._code = code
        self._auto_commit = auto_commit
        # 复用 P4.1 仓储的本体行幂等创建（savepoint + IntegrityError 兜底并发）。
        # 仓储侧**强制只 flush**：提交权统一收口到本服务的 `_commit()`。
        # 否则 `_require_ontology()` 的 get_or_create 会在后续校验（如悬空
        # parent_code / 跨租户引用被拒）抛 ModelingError **之前**就把空本体行
        # 提交进库，每个被拒绝的请求都留下一个孤儿本体行（复审探针实证）。
        self._repo = OntologyRepository(db, tenant_id, code, auto_commit=False)

    # ── 内部 ─────────────────────────────────────────────────────────────────
    def _commit(self) -> None:
        if self._auto_commit:
            self._db.commit()
        else:
            self._db.flush()

    def _write(self, body):
        """在 savepoint 内执行写主体，校验失败回滚 savepoint。

        `_require_ontology()` 可能幂等创建本体行；若其后的库依赖校验
        （对象类型不存在 / code 重复 / 跨租户引用被拒等）抛 ModelingError，
        直接冒泡会把已 INSERT 的本体行留在事务里，随调用方之后的任意
        commit 一起入库。用 `begin_nested()` 包住写主体：失败回滚 savepoint，
        既不留孤儿行，也不影响调用方事务里其它未提交的工作。
        """
        try:
            with self._db.begin_nested():
                row = body()
        except ModelingError:
            raise
        self._commit()
        return row

    @staticmethod
    def _validate_confidence(value: Optional[float]) -> Optional[float]:
        """confidence 必须落在 [0,1]（复审探针 B1/B2：越界值原样入库）。"""
        if value is not None and not (0.0 <= value <= 1.0):
            raise ModelingError(f"confidence 必须在 [0,1] 内，实际 {value}")
        return value

    @staticmethod
    def _validate_non_empty(value: str, field: str) -> str:
        """非空校验（列 nullable=False 只挡 NULL，空串/纯空白照样入库）。"""
        cleaned = (value or "").strip()
        if not cleaned:
            raise ModelingError(f"{field} 不能为空")
        return cleaned

    def _resolve_ontology(self, *, create: bool) -> Optional[Ontology]:
        """按租户链路解析本体行。

        :param create: True（写路径）时不存在则幂等创建；False（读路径）时
            不存在返回 None，**绝不静默建行**。
        """
        if create:
            return self._repo.get_or_create_ontology()
        stmt = select(Ontology).where(
            Ontology.tenant_id == self._tenant_id,
            Ontology.code == self._code,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def _require_ontology(self) -> Ontology:
        """写路径的本体行（不存在则幂等创建）。"""
        return self._resolve_ontology(create=True)

    @staticmethod
    def _validate_choice(value: str, allowed: tuple, field: str) -> str:
        if value not in allowed:
            raise ModelingError(
                f"非法的{field} '{value}'，允许取值：{'|'.join(allowed)}"
            )
        return value

    def _get_object_type_row(self, ontology_id: int, code: str) -> Optional[OntologyObjectType]:
        stmt = select(OntologyObjectType).where(
            OntologyObjectType.ontology_id == ontology_id,
            OntologyObjectType.code == code,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def _require_object_type(self, ontology_id: int, code: str) -> OntologyObjectType:
        row = self._get_object_type_row(ontology_id, code)
        if row is None:
            raise ModelingError(f"对象类型不存在: {code}")
        return row

    # ── 对象类型 ─────────────────────────────────────────────────────────────
    def add_object_type(
        self,
        code: str,
        name: str,
        description: Optional[str] = None,
        *,
        parent_code: Optional[str] = None,
        status: str = "suggested",
        source: str = "human",
        confidence: Optional[float] = None,
        evidence: Optional[dict] = None,
    ) -> OntologyObjectType:
        """新增对象类型。code 本体内唯一；`parent_code` 必须是同本体已有类型。"""
        self._validate_choice(status, ("suggested", "accepted", "rejected"), "评审状态")
        self._validate_choice(source, SOURCES, "来源")
        self._validate_confidence(confidence)
        code = self._validate_non_empty(code, "对象类型编码")
        name = self._validate_non_empty(name, "对象类型名称")

        def _body() -> OntologyObjectType:
            ontology = self._require_ontology()
            if self._get_object_type_row(ontology.id, code) is not None:
                raise ModelingError(f"对象类型已存在: {code}")
            parent_id = None
            if parent_code is not None:
                parent_id = self._require_object_type(ontology.id, parent_code).id
            row = OntologyObjectType(
                ontology_id=ontology.id,
                code=code,
                name=name,
                description=description,
                parent_id=parent_id,
                status=status,
                source=source,
                confidence=confidence,
                evidence_json=evidence,
                **self._audit_kwargs(),
            )
            self._db.add(row)
            return row

        return self._write(_body)

    def get_object_type(self, code: str) -> Optional[OntologyObjectType]:
        """按 code 取对象类型；本体不存在或类型不存在返回 None（读路径不建行）。"""
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return None
        return self._get_object_type_row(ontology.id, code)

    def list_object_types(self, status: Optional[str] = None) -> List[OntologyObjectType]:
        """列出对象类型（按 code 排序），可按评审状态过滤。"""
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return []
        if status is not None:
            self._validate_choice(status, ("suggested", "accepted", "rejected"), "评审状态")
        stmt = (
            select(OntologyObjectType)
            .where(OntologyObjectType.ontology_id == ontology.id)
            .order_by(OntologyObjectType.code)
        )
        if status is not None:
            stmt = stmt.where(OntologyObjectType.status == status)
        return list(self._db.execute(stmt).scalars().all())

    def update_object_type_status(self, code: str, status: str) -> OntologyObjectType:
        """评审状态流转（suggested → accepted / rejected，可逆）。"""
        self._validate_choice(status, ("suggested", "accepted", "rejected"), "评审状态")

        def _body() -> OntologyObjectType:
            ontology = self._require_ontology()
            row = self._require_object_type(ontology.id, code)
            row.status = status
            return row

        return self._write(_body)

    # ── 属性 ─────────────────────────────────────────────────────────────────
    def add_property(
        self,
        object_type_code: str,
        code: str,
        name: str,
        data_type: str = "string",
        *,
        required: bool = False,
        semantic_type: Optional[str] = None,
        status: str = "suggested",
        source: str = "human",
        confidence: Optional[float] = None,
    ) -> OntologyProperty:
        """为对象类型新增属性；类型不存在或属性 code 重复抛 ModelingError。"""
        self._validate_choice(status, ("suggested", "accepted", "rejected"), "评审状态")
        self._validate_choice(source, SOURCES, "来源")
        self._validate_confidence(confidence)
        code = self._validate_non_empty(code, "属性编码")
        name = self._validate_non_empty(name, "属性名称")
        data_type = self._validate_non_empty(data_type, "数据类型")

        def _body() -> OntologyProperty:
            ontology = self._require_ontology()
            object_type = self._require_object_type(ontology.id, object_type_code)
            dup = self._db.execute(
                select(OntologyProperty).where(
                    OntologyProperty.object_type_id == object_type.id,
                    OntologyProperty.code == code,
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise ModelingError(f"属性已存在: {object_type_code}.{code}")
            row = OntologyProperty(
                object_type_id=object_type.id,
                code=code,
                name=name,
                data_type=data_type,
                required=required,
                semantic_type=semantic_type,
                status=status,
                source=source,
                confidence=confidence,
                **self._audit_kwargs(),
            )
            self._db.add(row)
            return row

        return self._write(_body)

    def list_properties(self, object_type_code: str) -> List[OntologyProperty]:
        """列出对象类型的属性（读路径，本体/类型不存在返回空）。"""
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return []
        object_type = self._get_object_type_row(ontology.id, object_type_code)
        if object_type is None:
            return []
        stmt = (
            select(OntologyProperty)
            .where(OntologyProperty.object_type_id == object_type.id)
            .order_by(OntologyProperty.code)
        )
        return list(self._db.execute(stmt).scalars().all())

    # ── 关系类型 ─────────────────────────────────────────────────────────────
    def add_link_type(
        self,
        code: str,
        name: str,
        source_type_code: str,
        target_type_code: str,
        cardinality: str = "N:M",
        *,
        status: str = "suggested",
        source: str = "human",
        confidence: Optional[float] = None,
        evidence: Optional[dict] = None,
    ) -> OntologyLinkType:
        """新增关系类型；两端对象类型必须存在，code 本体内唯一。"""
        self._validate_choice(status, ("suggested", "accepted", "rejected"), "评审状态")
        self._validate_choice(source, SOURCES, "来源")
        self._validate_choice(cardinality, CARDINALITIES, "基数")
        self._validate_confidence(confidence)
        code = self._validate_non_empty(code, "关系类型编码")
        name = self._validate_non_empty(name, "关系类型名称")

        def _body() -> OntologyLinkType:
            ontology = self._require_ontology()
            dup = self._db.execute(
                select(OntologyLinkType).where(
                    OntologyLinkType.ontology_id == ontology.id,
                    OntologyLinkType.code == code,
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise ModelingError(f"关系类型已存在: {code}")
            source_type = self._require_object_type(ontology.id, source_type_code)
            target_type = self._require_object_type(ontology.id, target_type_code)
            row = OntologyLinkType(
                ontology_id=ontology.id,
                code=code,
                name=name,
                source_type_id=source_type.id,
                target_type_id=target_type.id,
                cardinality=cardinality,
                status=status,
                source=source,
                confidence=confidence,
                evidence_json=evidence,
                **self._audit_kwargs(),
            )
            self._db.add(row)
            return row

        return self._write(_body)

    def list_link_types(self) -> List[OntologyLinkType]:
        """列出关系类型（读路径）。"""
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return []
        stmt = (
            select(OntologyLinkType)
            .where(OntologyLinkType.ontology_id == ontology.id)
            .order_by(OntologyLinkType.code)
        )
        return list(self._db.execute(stmt).scalars().all())

    # ── 映射 ─────────────────────────────────────────────────────────────────
    def add_mapping(
        self,
        object_type_code: str,
        target_type: str,
        table_name: str,
        *,
        column_name: Optional[str] = None,
        database: Optional[str] = None,
        source_id: Optional[str] = None,
        status: str = "suggested",
        source: str = "human",
        confidence: Optional[float] = None,
    ) -> OntologyMapping:
        """新增对象类型 ↔ 物理表/列映射；`target_type=column` 时 column_name 必填。"""
        self._validate_choice(target_type, MAPPING_TARGET_TYPES, "映射目标类型")
        if target_type == "column" and not column_name:
            raise ModelingError("target_type=column 时必须提供 column_name")
        self._validate_choice(status, ("suggested", "accepted", "rejected"), "评审状态")
        self._validate_choice(source, SOURCES, "来源")
        self._validate_confidence(confidence)
        table_name = self._validate_non_empty(table_name, "物理表名")

        def _body() -> OntologyMapping:
            ontology = self._require_ontology()
            object_type = self._require_object_type(ontology.id, object_type_code)
            row = OntologyMapping(
                ontology_id=ontology.id,
                object_type_id=object_type.id,
                target_type=target_type,
                source_id=source_id,
                database=database,
                table_name=table_name,
                column_name=column_name,
                status=status,
                source=source,
                confidence=confidence,
                **self._audit_kwargs(),
            )
            self._db.add(row)
            return row

        return self._write(_body)

    def list_mappings(self) -> List[OntologyMapping]:
        """列出映射（读路径）。"""
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return []
        stmt = (
            select(OntologyMapping)
            .where(OntologyMapping.ontology_id == ontology.id)
            .order_by(OntologyMapping.table_name, OntologyMapping.column_name)
        )
        return list(self._db.execute(stmt).scalars().all())

    # ── 能力问题（CQ）───────────────────────────────────────────────────────
    def add_cq(
        self,
        question: str,
        answer_hint: Optional[str] = None,
        *,
        linked_object_codes: Optional[List[str]] = None,
        status: str = "active",
    ) -> OntologyCq:
        """新增能力问题。`linked_object_codes` 引用的对象类型必须已存在。"""
        self._validate_choice(status, CQ_STATUSES, "CQ 状态")
        question = self._validate_non_empty(question, "question")
        linked = list(dict.fromkeys(linked_object_codes or []))  # 去重，保持顺序

        def _body() -> OntologyCq:
            ontology = self._require_ontology()
            for object_code in linked:
                self._require_object_type(ontology.id, object_code)
            row = OntologyCq(
                ontology_id=ontology.id,
                question=question,
                answer_hint=answer_hint,
                status=status,
                linked_object_types=linked,
                **self._audit_kwargs(),
            )
            self._db.add(row)
            return row

        return self._write(_body)

    def list_cqs(self, status: Optional[str] = "active") -> List[OntologyCq]:
        """列出 CQ（默认只列 active；status=None 列全部）。"""
        if status is not None:
            self._validate_choice(status, CQ_STATUSES, "CQ 状态")
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return []
        stmt = (
            select(OntologyCq)
            .where(OntologyCq.ontology_id == ontology.id)
            .order_by(OntologyCq.id)
        )
        if status is not None:
            stmt = stmt.where(OntologyCq.status == status)
        return list(self._db.execute(stmt).scalars().all())

    def cq_coverage(self) -> float:
        """CQ 覆盖度：`linked_object_types` 非空的 active CQ 占比。

        口径（P4 计划 Task 4 示例为权威）：2 个 CQ、1 个关联了对象类型 → 0.5。
        无 active CQ 时返回 0.0（防除零）。
        """
        cqs = self.list_cqs(status="active")
        if not cqs:
            return 0.0
        covered = sum(1 for cq in cqs if cq.linked_object_types)
        return covered / len(cqs)

    # ── 审计 ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _audit_kwargs() -> dict:
        """审计列由调用方/中间件填充，此处统一留空。"""
        return {"creator_id": None, "updater_id": None}

    # ── P2 元数据 → 本体候选（Task 5）────────────────────────────────────────
    @staticmethod
    def _tier(confidence: Optional[float], *, none_means: str = "suggested") -> str:
        """按 P2/P4 共用的置信度分层把候选落到评审状态。

        * `confidence >= CONF_AUTO_ACCEPT (0.85)` → accepted（自动接受）
        * `CONF_SUGGEST_MIN (0.65) <= confidence` → suggested（人工评审）
        * 低于 CONF_SUGGEST_MIN → "drop"（不生成候选）
        * confidence 为 None → `none_means`（默认 suggested：未评分走人工兜底）
        """
        if confidence is None:
            return none_means
        if confidence >= CONF_AUTO_ACCEPT:
            return "accepted"
        if confidence >= CONF_SUGGEST_MIN:
            return "suggested"
        return "drop"

    @staticmethod
    def _normalize_object_code(table_name: str) -> str:
        """物理表名 → 对象类型 code（小写、非法字符转下划线）。"""
        return re.sub(r"[^0-9a-z_]+", "_", table_name.strip().lower()) or "unnamed"

    def generate_candidates(
        self,
        tables: List[MetaTableRef],
        columns: List[MetaColumnRef],
        column_pairs: List[ColumnPairOverlap],
    ) -> CandidateReport:
        """把 P2 元数据产出转换为本体候选（Task 5，spec §5.3）。

        * 表 → `ontology_object_type` 候选 + 同名 `ontology_mapping`；
        * 列 → 所属对象类型的 `ontology_property` 候选（按置信度分层）；
        * 高重叠列对 → `ontology_link_type` 候选（同表对的多列对合并进 evidence）。

        幂等：已存在的对象类型/属性/关系/映射一律跳过（计入 report.skipped）。
        整个批次在一个 savepoint 内执行，任何非预期错误整体回滚。
        """
        def _body() -> CandidateReport:
            report = CandidateReport()
            ontology = self._require_ontology()

            # 1) 表 → 对象类型候选 + mapping
            # 校验与 add_object_type 同源：候选批量入口同样不许脏数据绕过
            # （复审探针教训：空表名经 _normalize_object_code 会变成 "unnamed"）
            for t in tables:
                self._validate_non_empty(t.table_name, "表名")
                self._validate_confidence(t.confidence)
            for c in columns:
                self._validate_non_empty(c.column_name, "列名")
                self._validate_confidence(c.confidence)

            table_code_map: Dict[str, OntologyObjectType] = {}
            for t in tables:
                code = self._normalize_object_code(t.table_name)
                status = self._tier(t.confidence)
                existing = self._get_object_type_row(ontology.id, code)
                if existing is not None:
                    table_code_map[t.table_name] = existing
                    report.bump("object_type", False)
                elif status == "drop":
                    report.bump("object_type", False)
                    continue
                else:
                    row = OntologyObjectType(
                        ontology_id=ontology.id,
                        code=code,
                        name=t.comment or t.table_name,
                        description=f"来自 P2 元数据扫描（database={t.database}）",
                        status=status,
                        source="rule",
                        confidence=t.confidence,
                        evidence_json={
                            "origin": "p2_meta_scan",
                            "source_id": t.source_id,
                            "database": t.database,
                            "table_name": t.table_name,
                        },
                        **self._audit_kwargs(),
                    )
                    self._db.add(row)
                    self._db.flush()
                    table_code_map[t.table_name] = row
                    report.bump("object_type", True)

                # mapping（表级）：同一 object_type + table_name 已存在则跳过
                ot = table_code_map[t.table_name]
                dup_mapping = self._db.execute(
                    select(OntologyMapping).where(
                        OntologyMapping.ontology_id == ontology.id,
                        OntologyMapping.object_type_id == ot.id,
                        OntologyMapping.target_type == "table",
                        OntologyMapping.table_name == t.table_name,
                    )
                ).scalar_one_or_none()
                if dup_mapping is not None:
                    report.bump("mapping", False)
                else:
                    # 注意：spec §5.2 的 ontology_mapping 无 evidence_json 列——
                    # 它本身就是溯源结构（source_id/database/table_name）。
                    self._db.add(
                        OntologyMapping(
                            ontology_id=ontology.id,
                            object_type_id=ot.id,
                            target_type="table",
                            source_id=t.source_id,
                            database=t.database,
                            table_name=t.table_name,
                            status=status if status != "drop" else "suggested",
                            source="rule",
                            confidence=t.confidence,
                            **self._audit_kwargs(),
                        )
                    )
                    report.bump("mapping", True)

            # 2) 列 → 属性候选（按置信度分层）
            for c in columns:
                ot = table_code_map.get(c.table_name) or self._get_object_type_row(
                    ontology.id, self._normalize_object_code(c.table_name)
                )
                if ot is None:
                    # 列所属表未在本次输入/库中 —— 无法挂靠，跳过
                    report.bump("property", False)
                    continue
                status = self._tier(c.confidence)
                if status == "drop":
                    report.bump("property", False)
                    continue
                dup = self._db.execute(
                    select(OntologyProperty).where(
                        OntologyProperty.object_type_id == ot.id,
                        OntologyProperty.code == c.column_name,
                    )
                ).scalar_one_or_none()
                if dup is not None:
                    report.bump("property", False)
                    continue
                self._db.add(
                    OntologyProperty(
                        object_type_id=ot.id,
                        code=c.column_name,
                        name=c.comment or c.column_name,
                        data_type=c.data_type or "string",
                        status=status,
                        source="rule",
                        confidence=c.confidence,
                        **self._audit_kwargs(),
                    )
                )
                report.bump("property", True)

            # 3) 高重叠列对 → 关系候选（同表对合并）
            pairs_by_table: Dict[tuple, List[ColumnPairOverlap]] = {}
            for p in column_pairs:
                if p.overlap_ratio < CONF_SUGGEST_MIN:
                    report.bump("link_type", False)
                    continue
                pairs_by_table.setdefault((p.left_table, p.right_table), []).append(p)

            for (lt, rt), pairs in pairs_by_table.items():
                code = f"rel_{self._normalize_object_code(lt)}__{self._normalize_object_code(rt)}"
                source_ot = table_code_map.get(lt) or self._get_object_type_row(
                    ontology.id, self._normalize_object_code(lt)
                )
                target_ot = table_code_map.get(rt) or self._get_object_type_row(
                    ontology.id, self._normalize_object_code(rt)
                )
                if source_ot is None or target_ot is None:
                    report.bump("link_type", False)
                    continue
                dup = self._db.execute(
                    select(OntologyLinkType).where(
                        OntologyLinkType.ontology_id == ontology.id,
                        OntologyLinkType.code == code,
                    )
                ).scalar_one_or_none()
                if dup is not None:
                    report.bump("link_type", False)
                    continue
                self._db.add(
                    OntologyLinkType(
                        ontology_id=ontology.id,
                        code=code,
                        name=f"{lt} ↔ {rt}（推断）",
                        source_type_id=source_ot.id,
                        target_type_id=target_ot.id,
                        cardinality="N:M",
                        status="suggested",
                        source="rule",
                        confidence=max(p.overlap_ratio for p in pairs),
                        evidence_json={
                            "origin": "p2_relation_inference",
                            "pairs": [
                                {
                                    "left_column": p.left_column,
                                    "right_column": p.right_column,
                                    "overlap_ratio": p.overlap_ratio,
                                }
                                for p in pairs
                            ],
                        },
                        **self._audit_kwargs(),
                    )
                )
                report.bump("link_type", True)

            return report

        return self._write(_body)

    # ── 一致性校验（Task 3，纯读）────────────────────────────────────────────
    @staticmethod
    def _find_dangling_parents(
        items: List[tuple],
        known_keys: Optional[set] = None,
    ) -> List[tuple]:
        """悬空父类检测（纯函数）。

        :param items: ``[(key, parent_key_or_None, label)]`` —— 注意 items 只
            含**有父引用**的节点；`known_keys` 必须传入**全集**（含无父引用的
            节点），否则"已注册但无父"的合法类会被误判为悬空。
        :param known_keys: 全部合法 key 集合；None 时退化为 items 的 key 集
            （仅建模层这样用——每行都有条目）。
        :return: ``[(label, missing_parent_label)]``
        """
        keys = set(known_keys) if known_keys is not None else {k for k, _, _ in items}
        label_of = {k: label for k, _, label in items}
        return [
            (label, label_of.get(pk, str(pk)))
            for k, pk, label in items
            if pk is not None and pk not in keys
        ]

    @staticmethod
    def _find_parent_cycles(items: List[tuple]) -> List[List[str]]:
        """父类链环检测（纯函数），每个环只报告一次，路径含回边。

        :param items: 同 `_find_dangling_parents`
        :return: 环路径列表，如 ``["A", "B", "A"]``
        """
        parent_of = {k: pk for k, pk, _ in items}
        label_of = {k: label for k, _, label in items}
        reported: set = set()
        cycles: List[List[str]] = []
        for start_key, _, _ in items:
            path: List = []
            seen: set = set()
            cur = start_key
            while cur is not None and cur not in seen:
                seen.add(cur)
                path.append(cur)
                cur = parent_of.get(cur)
            if cur is not None and cur in seen:
                idx = path.index(cur)
                cycle_keys = path[idx:]
                frozen = frozenset(cycle_keys)
                if frozen not in reported:
                    reported.add(frozen)
                    labels = [label_of.get(k, str(k)) for k in cycle_keys]
                    cycles.append(labels + [labels[0]])
        return cycles

    @staticmethod
    def _find_uri_conflicts(uris: List[str]) -> List[tuple]:
        """URI 规范化冲突（纯函数）：小写化、去尾部 ``#``/``/`` 后相同的 uri 组。

        `http://x#Risk` 与 `http://x#risk` 在 Turtle 里是两个合法 URIRef，
        但极易混淆且跨工具往返时可能被折叠 —— severity 用 warning。
        """
        groups: Dict[str, List[str]] = {}
        for uri in uris:
            groups.setdefault(uri.strip().lower().rstrip("#/"), []).append(uri)
        return [tuple(sorted(g)) for g in groups.values() if len(g) > 1]

    def check_consistency(self) -> ConsistencyReport:
        """对建模层与 OWL 层做三类基础一致性校验（Task 3，纯读）。

        建模层：`ontology_object_type.parent_id` 链（悬空 / 成环）；
        OWL 层：`ontology_class.parent_uris` 图（悬空 / 成环）+ URI 规范化冲突。
        """
        report = ConsistencyReport()
        ontology = self._resolve_ontology(create=False)
        if ontology is None:
            return report

        # ── 1. 建模层 ────────────────────────────────────────────────────────
        object_types = self.list_object_types()
        ot_items = [(ot.id, ot.parent_id, ot.code) for ot in object_types]
        for label, missing in self._find_dangling_parents(ot_items):
            report.issues.append(
                ConsistencyIssue(
                    kind="dangling_parent",
                    layer="modeling",
                    severity="error",
                    subject=label,
                    detail=f"父对象类型 '{missing}' 不存在（正常路径被 DB 外键阻止，"
                    "出现即意味着数据被绕过服务修改过）",
                )
            )
        for cycle in self._find_parent_cycles(ot_items):
            report.issues.append(
                ConsistencyIssue(
                    kind="cyclic_inheritance",
                    layer="modeling",
                    severity="error",
                    subject=cycle[0],
                    detail="对象类型父类链成环: " + " -> ".join(cycle),
                )
            )

        # ── 2. OWL 层 ────────────────────────────────────────────────────────
        records = self._repo.list_classes()
        uris = {r.uri for r in records}
        owl_items = [(r.uri, p, r.uri) for r in records for p in r.parent_uris]
        for label, missing in self._find_dangling_parents(owl_items, known_keys=uris):
            report.issues.append(
                ConsistencyIssue(
                    kind="dangling_parent",
                    layer="owl",
                    severity="error",
                    subject=label,
                    detail=f"父类 '{missing}' 未在本体中注册"
                    "（parent_uris 是 JSONB 无外键，允许悬空；层级展示会容忍，"
                    "但推理/导出语义不完整）",
                )
            )
        for cycle in self._find_parent_cycles(owl_items):
            report.issues.append(
                ConsistencyIssue(
                    kind="cyclic_inheritance",
                    layer="owl",
                    severity="error",
                    subject=cycle[0],
                    detail="OWL 类父类链成环: " + " -> ".join(cycle),
                )
            )
        for pair in self._find_uri_conflicts(sorted(uris)):
            report.issues.append(
                ConsistencyIssue(
                    kind="uri_conflict",
                    layer="owl",
                    severity="warning",
                    subject=pair[0],
                    detail=f"以下 URI 仅大小写/尾分隔符不同，极易混淆: {', '.join(pair)}",
                )
            )

        return report
