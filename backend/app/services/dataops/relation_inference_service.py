"""表间关系推断（P2 Task 13，三方投票）。

三种独立证据各投一票，综合置信度取各票最大值；低于 ``CONF_SUGGEST_MIN``
的关系不入库（drop）。产出持久化到 ``meta_relation``，并同时返回供 P4 候选生成
消费的 ``InferredPair`` 列表（字段对齐 P4 的 ``ColumnPairOverlap``）。

三方投票
--------
1. **键/外键命名法（vote_key）**：主键/唯一键列 + 对方列名呈 ``<表>_id`` 形态 →
   强外键信号（0.85）；单方列名 ``_id`` 词干命中对方表名 → 0.7。
2. **同名属性法（vote_name）**：两表存在同名属性（非 id/name 等泛化列）→
   共享维度的弱信号（0.65）；归一化词干相同 → 0.55。
3. **采样重叠率法（vote_overlap）**：经方言适配器 ``overlap_ratio`` 估算左列去重值
   命中右列的比例（需要实时连接；不传 engine 则本票缺省）。

综合：``confidence = max(非空票)``；评审状态由置信度分层（≥0.85 accepted）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.ai.dataops.connection import build_engine
from app.ai.dataops.dialects.registry import get_adapter
from app.ai.dataops.rule_engine import CONF_SUGGEST_MIN, tier
from app.models.dataops.data_source import DataSource
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.meta_relation import MetaRelation
from app.services.dataops.data_source_service import DataSourceService


@dataclass
class InferredPair:
    """推断出的列对关系（供 P4 候选生成消费，字段对齐 ColumnPairOverlap）。"""

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    overlap_ratio: float


@dataclass
class InferReport:
    """关系推断结果统计。"""

    scanned_pairs: int = 0
    relations: int = 0
    pairs: List[InferredPair] = field(default_factory=list)
    details: List[dict] = field(default_factory=list)


def _stem(name: str) -> str:
    """去掉 ``_id`` 后缀并小写，用于外键词干比对。"""
    n = name.strip().lower()
    return re.sub(r"_id$", "", n)


def _refers_to(stem: str, table: str) -> bool:
    """外键词干是否指向某表（兼容 user→users 单复数）。"""
    tl = table.lower()
    return stem == tl or stem == tl.rstrip("s") or (stem + "s") == tl


def _vote_key(c1: str, k1: Optional[str], t1: str, c2: str, k2: Optional[str], t2: str):
    """键/外键命名法投票。返回 (confidence: float|None, why: str)。"""
    t1l, t2l = t1.lower(), t2.lower()
    c1l, c2l = c1.lower(), c2.lower()
    # 主键/唯一键 列 + 对方列名 == 本表名 / 形如 <本表>_id / 词干命中本表（兼容单复数）
    if k1 in ("PRI", "UNI") and (c2l == t1l or c2l == f"{t1l}_id" or _refers_to(_stem(c2l), t1)):
        return 0.85, f"{c1} 是键且 {c2} 形如/指向 {t1}"
    if k2 in ("PRI", "UNI") and (c1l == t2l or c1l == f"{t2l}_id" or _refers_to(_stem(c1l), t2)):
        return 0.85, f"{c2} 是键且 {c1} 形如/指向 {t2}"
    # 单方列名 _id 词干命中对方表名（无键，弱信号）
    if c2l.endswith("_id") and _refers_to(_stem(c2l), t1):
        return 0.6, f"{c2} 词干命中表 {t1}"
    if c1l.endswith("_id") and _refers_to(_stem(c1l), t2):
        return 0.6, f"{c1} 词干命中表 {t2}"
    return None, ""


def _vote_name(c1: str, c2: str):
    """同名属性法投票。返回 (confidence: float|None, why: str)。"""
    c1l, c2l = c1.lower(), c2.lower()
    if c1l == c2l:
        if c1l in ("id", "name"):
            return 0.5, f"同名泛化列 {c1}"  # 过于泛化，弱信号
        return 0.65, f"同名属性 {c1}"
    if _stem(c1l) == _stem(c2l) and _stem(c1l):
        return 0.55, f"归一化词干相同 {_stem(c1l)}"
    return None, ""


class RelationInferenceService:
    """表间关系三方投票推断（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("RelationInferenceService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._ds = DataSourceService(db, tenant_id)

    def _load(self, source_id: int, database: Optional[str]):
        stmt = select(MetaTable).where(
            MetaTable.tenant_id == self.tenant_id, MetaTable.source_id == source_id
        )
        if database:
            stmt = stmt.where(MetaTable.database == database)
        tables = list(self.db.execute(stmt).scalars().all())
        cols = (
            self.db.execute(
                select(MetaColumn)
                .join(MetaTable, MetaColumn.table_id == MetaTable.id)
                .where(MetaTable.tenant_id == self.tenant_id, MetaTable.source_id == source_id)
            )
            .scalars()
            .all()
        )
        return tables, cols

    def _overlap_vote(self, engine: Engine, source_type: str, database: str,
                      t1: str, c1: str, t2: str, c2: str):
        try:
            adapter = get_adapter(source_type)
            from app.ai.dataops.dialect_base import ColRef

            with engine.connect() as conn:
                return adapter.overlap_ratio(conn, database, ColRef(t1, c1), ColRef(t2, c2))
        except Exception:  # noqa: BLE001 - 重叠估算失败（类型不可比等）本票缺省
            return None

    def infer(
        self,
        source_id: int,
        database: Optional[str] = None,
        *,
        engine: Optional[Engine] = None,
        with_overlap: bool = False,
    ) -> InferReport:
        """对数据源（可选限定库）做三方投票关系推断。

        :param engine: 实时连接（用于 overlap 投票）；不传则仅运行 key/name 两票。
        :param with_overlap: True 时自动按数据源建连跑 overlap（需 engine 或可用凭据）。
        """
        ds = self._ds.get_or_404(source_id)  # 租户隔离校验
        tables, cols = self._load(source_id, database)
        table_names = [t.table_name for t in tables]

        # 列按其 table_id 归并到表名，供两两配对
        tid_to_name = {t.id: t.table_name for t in tables}
        cols_by_table: dict = {t.table_name: [] for t in tables}
        for c in cols:
            tn = tid_to_name.get(c.table_id)
            if tn:
                cols_by_table[tn].append(c)

        report = InferReport()
        seen: dict = {}
        auto_engine = None
        if with_overlap and engine is None:
            password = self._ds.reveal_password(ds.id)
            auto_engine = build_engine(
                ds.source_type, ds.host, ds.port, ds.username, password, ds.database
            )
        try:
            for i in range(len(table_names)):
                for j in range(i + 1, len(table_names)):
                    t1, t2 = table_names[i], table_names[j]
                    for c1 in cols_by_table.get(t1, []):
                        for c2 in cols_by_table.get(t2, []):
                            report.scanned_pairs += 1
                            vk, wk = _vote_key(c1.column_name, c1.column_key, t1, c2.column_name, c2.column_key, t2)
                            vn, wn = _vote_name(c1.column_name, c2.column_name)
                            vo = None
                            wo = ""
                            if (with_overlap or engine is not None) and (auto_engine or engine):
                                vo = self._overlap_vote(
                                    auto_engine or engine, ds.source_type,
                                    database or ds.database, t1, c1.column_name, t2, c2.column_name
                                )
                                if vo is not None:
                                    wo = f"overlap_ratio={vo}"
                            votes = [v for v in (vk, vn, vo) if v is not None]
                            if not votes:
                                continue
                            confidence = max(votes)
                            if confidence < CONF_SUGGEST_MIN:
                                continue
                            # 规范化左右顺序（避免 A↔B 与 B↔A 重复入库）
                            left = (t1, c1.column_name)
                            right = (t2, c2.column_name)
                            if (right, left) < (left, right):
                                left, right = right, left
                            key = (left[0], left[1], right[0], right[1])
                            if key in seen and seen[key] >= confidence:
                                continue
                            seen[key] = confidence

                            status = tier(confidence)
                            existing = self.db.execute(
                                select(MetaRelation).where(
                                    MetaRelation.tenant_id == self.tenant_id,
                                    MetaRelation.left_table == left[0],
                                    MetaRelation.left_column == left[1],
                                    MetaRelation.right_table == right[0],
                                    MetaRelation.right_column == right[1],
                                )
                            ).scalar_one_or_none()
                            if existing is None:
                                rel = MetaRelation(
                                    tenant_id=self.tenant_id,
                                    source_id=source_id,
                                    database=database or ds.database,
                                    left_table=left[0], left_column=left[1],
                                    right_table=right[0], right_column=right[1],
                                    vote_key=vk, vote_name=vn, vote_overlap=vo,
                                    confidence=round(confidence, 4),
                                    method_votes_json={"key": wk, "name": wn, "overlap": wo},
                                    status=status, source="rule",
                                )
                                self.db.add(rel)
                                self.db.flush()
                                report.relations += 1
                            report.pairs.append(
                                InferredPair(left[0], left[1], right[0], right[1], round(confidence, 4))
                            )
                            report.details.append(
                                {"pair": f"{left[0]}.{left[1]} ↔ {right[0]}.{right[1]}",
                                 "confidence": round(confidence, 4), "status": status,
                                 "votes": {"key": vk, "name": vn, "overlap": vo}}
                            )
        finally:
            if auto_engine is not None:
                auto_engine.dispose()
        return report
