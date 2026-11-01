"""资产目录检索与作用域草稿（P0-9：E28 assets/search + E33 draft-scope，spec §3.6 / §6.5 / §4.7）。

E40 ``assets/tree`` 已在 P0-2 的 :class:`OntologyService` 提供，本服务补齐检索与送数两翼。

**检索硬约束（§3.6，不得违反）**：排序与打分**禁用 ``similarity()`` / ``word_similarity()``**
（本环境 pg_trgm 对 CJK 恒返回 0）；``gin_trgm_ops`` 索引只用于加速 ``LIKE '%kw%'``，
打分用**三段确定性得分**：① 精确/前缀命中表名 ② 命中字段名 ③ 命中注释；同分按表名字典序。

送数（§4.7）：``draft-scope`` 只改 ``onto_ontology.draft_scope_json``，**绝不写结构表**，
避免"选了就是待审"的假候选污染审阅台；空清单且非显式清空 → ``DRAFT_SCOPE_EMPTY``。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, BUILD_SCOPE_SINGLE_SOURCE, DRAFT_SCOPE_EMPTY,
    ONTOLOGY_NOT_FOUND, ONTOLOGY_STOPPED,
)
from app.models.ontology.asset_tag import MetaAssetTag, MetaAssetTagBinding
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.ontology.ontology import MetaOntology
from app.models.dataops.standard_cdm import MetaObjectStandard, MetaTableStandard

_COLUMN_DIGEST_LIMIT = 6
_EPOCH_MIN = datetime(1970, 1, 1)  # updated_at 缺失行在 sort=updated 时恒落尾部


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
        table_type: Optional[str] = None,
        sort: str = "score",
    ) -> dict:
        q = (kw or "").strip()
        stmt = self._base(select(MetaTable))
        if source_id:
            stmt = stmt.where(MetaTable.source_id == source_id)
        if table_type == "BASE TABLE":
            # 扫描器历史行可能未落 table_type，NULL 视同基表（AF-07）
            stmt = stmt.where(or_(MetaTable.table_type == table_type,
                                  MetaTable.table_type.is_(None)))
        elif table_type:
            stmt = stmt.where(MetaTable.table_type == table_type)
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
            else:  # table：库名/表名/表注释命中，或含命中列的表（AF-02 补 database 分支）
                stmt = stmt.where(or_(
                    MetaTable.table_name.ilike(like),
                    MetaTable.database.ilike(like),
                    MetaTable.table_comment.ilike(like),
                    col_hits,
                ))
        tables = list(self.db.execute(
            stmt.order_by(MetaTable.table_name.asc())
        ).scalars().all())

        # 批量预载列命中，消除逐表 EXISTS 的 N+1（AF-02）
        hits_map = self._column_hit_map(tables, q) if q else {}
        scored = [(self._score(t, q, kind, hits_map.get(t.id, (False, False))), t) for t in tables]
        # 排序三档（AF-02/07）：score 同分恒按表名字典序（Global Constraint 3，可复现）
        if sort == "updated":
            scored.sort(key=lambda x: (x[1].updated_at or _EPOCH_MIN), reverse=True)
        elif sort == "rows":
            scored.sort(key=lambda x: (-(x[1].row_count or 0), x[1].table_name))
        else:
            scored.sort(key=lambda x: (-x[0], x[1].table_name))
        total = len(scored)
        window = scored[(page - 1) * size: (page - 1) * size + size]

        items = [self._card(t, sc, q) for sc, t in window]
        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    def _score(t: MetaTable, q: str, kind: str, hits: tuple) -> int:
        """三段确定性得分（§3.6 原型口径）：3=表名∪库名∪表注释；2=字段名；1=仅字段注释。

        纯函数：``hits=(列名命中, 列注释命中)`` 由 :meth:`_column_hit_map` 批量预载，
        打分阶段不再发 SQL（禁 similarity，Global Constraint 1）。
        """
        if not q:
            return 0
        ql = q.lower()
        if ql in (t.table_name or "").lower() or ql in (t.database or "").lower() \
           or ql in (t.table_comment or "").lower():
            return 3
        name_hit, comment_hit = hits
        if name_hit:
            return 2
        if comment_hit:
            return 1
        return 0

    def _column_hit_map(self, tables: List[MetaTable], q: str) -> Dict[int, tuple]:
        """一次 IN 批量取各表的 (列名命中, 列注释命中)，消除逐表 EXISTS 的 N+1。"""
        like = f"%{q}%"
        ids = [t.id for t in tables] or [-1]
        rows = self.db.execute(
            select(MetaColumn.table_id,
                   func.bool_or(MetaColumn.column_name.ilike(like)).label("nh"),
                   func.bool_or(MetaColumn.column_comment.ilike(like)).label("ch"))
            .where(MetaColumn.tenant_id == self.tenant_id,
                   MetaColumn.table_id.in_(ids)).group_by(MetaColumn.table_id)
        ).all()
        return {r.table_id: (bool(r.nh), bool(r.ch)) for r in rows}

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
        columns = [
            {"name": c.column_name, "type": c.data_type or "",
             "comment": (c.column_comment or c.biz_name or ""), "pii": c.pii_level or "L0"}
            for c in cols
        ]
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
            "columns": columns,
            "column_count": t.column_count,
            "row_count": t.row_count,
            "pii_max_level": pii_max,
            "tags": self._tags_for(t.id),
            "bound_object_code": bound,
            "score": score,
        }

    def _tags_for(self, table_id: int) -> List[dict]:
        rows = self.db.execute(
            select(MetaAssetTag.id, MetaAssetTag.code, MetaAssetTag.name, MetaAssetTag.color)
            .join(MetaAssetTagBinding, MetaAssetTagBinding.tag_id == MetaAssetTag.id)
            .where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.asset_kind == "table",
                MetaAssetTagBinding.asset_id == table_id,
            )
        ).all()
        return [{"id": tid, "code": c, "name": n, "color": col} for tid, c, n, col in rows]

    # ------------------------------------------------- E-编辑 元数据（AF-06）

    def update_table_meta(
        self, table_id: int, *,
        source_id: Optional[int] = None,
        table_comment: Optional[str] = None,
        biz_name: Optional[str] = None,
        biz_description: Optional[str] = None,
        columns: Optional[List[dict]] = None,
    ) -> dict:
        """编辑扫描元数据（表/列说明、业务名称/描述）：仅写 ``meta_table``/``meta_column``，非结构变更。

        租户 +（可选）``source_id`` 定位表，缺失 → ``ONTOLOGY_NOT_FOUND`` 404。字段仅在非 ``None``
        时覆盖（部分更新）；列按 ``column_name`` 匹配，未知列名静默跳过并回传 ``skipped``。
        """
        stmt = select(MetaTable).where(
            MetaTable.tenant_id == self.tenant_id, MetaTable.id == table_id
        )
        if source_id is not None:
            stmt = stmt.where(MetaTable.source_id == source_id)
        t = self.db.execute(stmt).scalar_one_or_none()
        if t is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "表不存在或不属于该数据源",
                           http_status=404, detail={"table_id": table_id})
        if table_comment is not None:
            t.table_comment = table_comment
        if biz_name is not None:
            t.biz_name = biz_name
        if biz_description is not None:
            t.biz_description = biz_description

        updated = 0
        skipped: List[str] = []
        for item in columns or []:
            cname = (item or {}).get("column_name")
            if not cname:
                continue
            c = self.db.execute(
                select(MetaColumn).where(
                    MetaColumn.tenant_id == self.tenant_id,
                    MetaColumn.table_id == table_id,
                    MetaColumn.column_name == cname,
                )
            ).scalar_one_or_none()
            if c is None:
                skipped.append(cname)
                continue
            if item.get("column_comment") is not None:
                c.column_comment = item["column_comment"]
            if item.get("biz_name") is not None:
                c.biz_name = item["biz_name"]
            updated += 1
        self.db.flush()
        return {
            "table_id": table_id,
            "table_comment": t.table_comment,
            "biz_name": t.biz_name,
            "biz_description": t.biz_description,
            "columns_updated": updated,
            "skipped": skipped,
        }

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
        """回显送数作用域；tables 模式下失效表静默剔除并回传条数（Q4 裁决，AF-08）。"""
        obj = self._ontology_or_404(ontology_id)
        scope = obj.draft_scope_json or {}
        tables = [t for t in (scope.get("tables") or []) if t]
        removed = 0
        if tables and scope.get("source_id") and scope.get("mode", "tables") == "tables":
            live = set(self.db.execute(
                select(MetaTable.table_name).where(
                    MetaTable.tenant_id == self.tenant_id,
                    MetaTable.source_id == scope["source_id"],
                    MetaTable.table_name.in_(tables))
            ).scalars().all())
            removed = len([t for t in tables if t not in live])
            if removed:
                obj.draft_scope_json = {**scope, "tables": [t for t in tables if t in live]}
                self.db.flush()
        return {"ontology_id": ontology_id,
                "draft_scope": obj.draft_scope_json, "removed_stale": removed}

    def put_draft_scope(self, ontology_id: int, scope: Optional[dict]) -> dict:
        """全量覆盖语义；空清单且非显式清空 → ``DRAFT_SCOPE_EMPTY``；``stopped`` 拒绝。"""
        obj = self._ontology_or_404(ontology_id)
        if obj.status == "stopped":
            raise ApiError(ONTOLOGY_STOPPED, f"本体已停止，拒绝送数: {obj.code}")
        payload = scope or {}
        non_empty = bool(payload.get("tables") or payload.get("tag_ids") or payload.get("catalog_ids"))
        if not non_empty and not payload.get("clear"):
            raise ApiError(DRAFT_SCOPE_EMPTY, "送数作用域为空（未勾选任何表/标签/目录）")
        # 服务端单源终防线（AF-08）：tables 模式实查 meta_table，跨源/失表一律拦截；显式清空跳过
        if non_empty and payload.get("mode", "tables") == "tables":
            src = payload.get("source_id")
            names = [t for t in (payload.get("tables") or []) if t]
            if not src:
                raise ApiError(BUILD_SCOPE_SINGLE_SOURCE, "送数作用域缺少 source_id")
            found = set(self.db.execute(
                select(MetaTable.table_name).where(
                    MetaTable.tenant_id == self.tenant_id, MetaTable.source_id == src,
                    MetaTable.table_name.in_(names or ["__none__"]))
            ).scalars().all())
            missing = sorted(set(names) - found)
            if missing:
                raise ApiError(BUILD_SCOPE_SINGLE_SOURCE,
                               f"表不属于锁定数据源 {src}: {', '.join(missing[:5])}",
                               detail={"source_id": src, "missing": missing})
        obj.draft_scope_json = payload if non_empty else None
        self.db.flush()
        return {"ontology_id": ontology_id, "draft_scope": obj.draft_scope_json}

    def delete_draft_scope(self, ontology_id: int) -> dict:
        obj = self._ontology_or_404(ontology_id)
        obj.draft_scope_json = None
        self.db.flush()
        return {"ontology_id": ontology_id, "draft_scope": None}
