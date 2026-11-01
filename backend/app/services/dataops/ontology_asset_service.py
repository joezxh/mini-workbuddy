"""资产目录检索与作用域草稿（P0-9：E28 assets/search + E33 draft-scope，spec §3.6 / §6.5 / §4.7）。

E40 ``assets/tree`` 已在 P0-2 的 :class:`OntologyService` 提供，本服务补齐检索与送数两翼。

**检索硬约束（§3.6，不得违反）**：排序与打分**禁用 ``similarity()`` / ``word_similarity()``**
（本环境 pg_trgm 对 CJK 恒返回 0）；``gin_trgm_ops`` 索引只用于加速 ``LIKE '%kw%'``，
打分用**三段确定性得分**：① 精确/前缀命中表名 ② 命中字段名 ③ 命中注释；同分按表名字典序。

送数（§4.7）：``draft-scope`` 只改 ``meta_ontology.draft_scope_json``，**绝不写结构表**，
避免"选了就是待审"的假候选污染审阅台；空清单且非显式清空 → ``DRAFT_SCOPE_EMPTY``。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, DRAFT_SCOPE_EMPTY, ONTOLOGY_NOT_FOUND, ONTOLOGY_STOPPED,
)
from app.models.dataops.asset_tag import MetaAssetTag, MetaAssetTagBinding
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.ontology import MetaOntology
from app.models.dataops.standard_cdm import MetaObjectStandard, MetaTableStandard

_COLUMN_DIGEST_LIMIT = 6


class OntologyAssetService:
    """资产检索与作用域草稿（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyAssetService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _base(self, stmt):
        return stmt.where(MetaTable.tenant_id == self.tenant_id)

    # ------------------------------------------------------------- E28 检索

    def search(
        self, *,
        kw: Optional[str] = None,
        source_id: Optional[int] = None,
        tag_ids: Optional[List[int]] = None,
        kind: str = "table",
        page: int = 1,
        size: int = 50,
    ) -> dict:
        q = (kw or "").strip()
        stmt = self._base(select(MetaTable))
        if source_id:
            stmt = stmt.where(MetaTable.source_id == source_id)
        if tag_ids:
            bound = select(MetaAssetTagBinding.asset_id).where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.asset_kind == "table",
                MetaAssetTagBinding.tag_id.in_(list(tag_ids)),
            )
            stmt = stmt.where(MetaTable.id.in_(bound))
        if q:
            like = f"%{q}%"
            col_hits = (
                select(MetaColumn.table_id)
                .where(MetaColumn.tenant_id == self.tenant_id,
                       or_(MetaColumn.column_name.ilike(like),
                           MetaColumn.column_comment.ilike(like)))
                .exists()
            )
            if kind == "column":
                stmt = stmt.where(col_hits)
            else:  # table：表名/注释命中，或含命中列的表
                stmt = stmt.where(or_(
                    MetaTable.table_name.ilike(like),
                    MetaTable.table_comment.ilike(like),
                    col_hits,
                ))
        tables = list(self.db.execute(
            stmt.order_by(MetaTable.table_name.asc())
        ).scalars().all())

        scored = [(self._score(t, q, kind), t) for t in tables]
        # 同分按表名字典序（SQL 已按 table_name 升序，稳定排序保序）
        scored.sort(key=lambda x: (-x[0], x[1].table_name))
        total = len(scored)
        window = scored[(page - 1) * size: (page - 1) * size + size]

        items = [self._card(t, sc, q) for sc, t in window]
        return {"total": total, "page": page, "size": size, "items": items}

    def _score(self, t: MetaTable, q: str, kind: str) -> int:
        """三段确定性得分（§3.6）：①表名精确/前缀 ②字段名 ③注释。"""
        if not q:
            return 0
        ql = q.lower()
        tl = (t.table_name or "").lower()
        if ql == tl or tl.startswith(ql):
            return 3
        if ql in tl:
            return 3 if kind == "table" else 2
        col_name_hit = self.db.execute(
            select(exists().where(
                MetaColumn.tenant_id == self.tenant_id,
                MetaColumn.table_id == t.id,
                MetaColumn.column_name.ilike(f"%{q}%"),
            ))
        ).scalar()
        if col_name_hit:
            return 2
        comment_hit = (
            (t.table_comment or "").lower().find(ql) != -1
            or self.db.execute(
                select(exists().where(
                    MetaColumn.tenant_id == self.tenant_id,
                    MetaColumn.table_id == t.id,
                    MetaColumn.column_comment.ilike(f"%{q}%"),
                ))
            ).scalar()
        )
        return 1 if comment_hit else 0

    def _card(self, t: MetaTable, score: int, q: str) -> dict:
        cols = list(self.db.execute(
            select(MetaColumn).where(
                MetaColumn.tenant_id == self.tenant_id, MetaColumn.table_id == t.id
            ).order_by(MetaColumn.ordinal).limit(_COLUMN_DIGEST_LIMIT)
        ).scalars().all())
        digest = " · ".join(
            f"{c.column_name} {c.data_type or ''} '{c.column_comment or c.biz_name or ''}'".strip()
            for c in cols
        )
        pii_max = self.db.execute(
            select(func.max(MetaColumn.pii_level)).where(
                MetaColumn.tenant_id == self.tenant_id, MetaColumn.table_id == t.id
            )
        ).scalar()
        # 已有映射回显（避免重复建模）
        bound = self.db.execute(
            select(MetaObjectStandard.code)
            .join(MetaTableStandard, MetaTableStandard.object_standard_id == MetaObjectStandard.id)
            .where(
                MetaTableStandard.tenant_id == self.tenant_id,
                MetaTableStandard.table_id == t.id,
                MetaTableStandard.status == "accepted",
            )
        ).scalar_one_or_none()
        return {
            "table_id": t.id,
            "source_id": t.source_id,
            "db_name": t.db_name,
            "database": t.database,
            "table_name": t.table_name,
            "table_comment": t.table_comment,
            "column_digest": digest,
            "column_count": t.column_count,
            "row_count": t.row_count,
            "pii_max_level": pii_max,
            "tags": self._tags_for(t.id),
            "bound_object_code": bound,
            "score": score,
        }

    def _tags_for(self, table_id: int) -> List[dict]:
        rows = self.db.execute(
            select(MetaAssetTag.code, MetaAssetTag.name, MetaAssetTag.color)
            .join(MetaAssetTagBinding, MetaAssetTagBinding.tag_id == MetaAssetTag.id)
            .where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.asset_kind == "table",
                MetaAssetTagBinding.asset_id == table_id,
            )
        ).all()
        return [{"code": c, "name": n, "color": col} for c, n, col in rows]

    # ------------------------------------------------------- E33 draft-scope

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    def get_draft_scope(self, ontology_id: int) -> dict:
        obj = self._ontology_or_404(ontology_id)
        return {"ontology_id": ontology_id, "draft_scope": obj.draft_scope_json}

    def put_draft_scope(self, ontology_id: int, scope: Optional[dict]) -> dict:
        """全量覆盖语义；空清单且非显式清空 → ``DRAFT_SCOPE_EMPTY``；``stopped`` 拒绝。"""
        obj = self._ontology_or_404(ontology_id)
        if obj.status == "stopped":
            raise ApiError(ONTOLOGY_STOPPED, f"本体已停止，拒绝送数: {obj.code}")
        payload = scope or {}
        non_empty = bool(payload.get("tables") or payload.get("tag_ids") or payload.get("catalog_ids"))
        if not non_empty and not payload.get("clear"):
            raise ApiError(DRAFT_SCOPE_EMPTY, "送数作用域为空（未勾选任何表/标签/目录）")
        obj.draft_scope_json = payload if non_empty else None
        self.db.flush()
        return {"ontology_id": ontology_id, "draft_scope": obj.draft_scope_json}

    def delete_draft_scope(self, ontology_id: int) -> dict:
        obj = self._ontology_or_404(ontology_id)
        obj.draft_scope_json = None
        self.db.flush()
        return {"ontology_id": ontology_id, "draft_scope": None}
