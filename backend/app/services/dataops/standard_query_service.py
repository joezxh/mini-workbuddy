"""标准中心只读查询 + NL 检索（B4）。

``graph`` / ``stats`` 是纯聚合（不改数据）；``nl_query`` 把范围内的对象/关系压成
紧凑提示词交给 ``app.ai.research.llm.llm_json``，让模型返回结构化选择器
（高亮哪些对象/关系 + 一句话解释）。LLM 任何异常都降级为 ``degraded=True`` 的
200 响应，绝不 500 —— 图浏览不依赖 AI。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dataops.meta import MetaTable
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaRelationCheck, MetaStandardCatalog,
    MetaTableStandard,
)


class StandardQueryService:
    """标准中心只读查询（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("StandardQueryService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ── 目录子树 ────────────────────────────────────────────────────
    def _subtree_catalog_ids(self, catalog_id: int) -> set:
        """从 catalog_id 开始向下展开（含自身）。"""
        rows = self.db.execute(
            select(MetaStandardCatalog.id, MetaStandardCatalog.parent_id).where(
                MetaStandardCatalog.tenant_id == self.tenant_id
            )
        ).all()
        children: dict = {}
        for cid, parent_id in rows:
            children.setdefault(parent_id, []).append(cid)
        found, stack = {catalog_id}, [catalog_id]
        while stack:
            for child_id in children.get(stack.pop(), []):
                if child_id not in found:
                    found.add(child_id)
                    stack.append(child_id)
        return found

    # ── 图 ──────────────────────────────────────────────────────────
    def graph(self, catalog_id: Optional[int] = None) -> dict:
        """nodes=对象标准，edges=关系标准；给定 catalog 时只取该子树。"""
        object_stmt = select(MetaObjectStandard).where(
            MetaObjectStandard.tenant_id == self.tenant_id
        )
        relation_stmt = select(MetaObjectRelation).where(
            MetaObjectRelation.tenant_id == self.tenant_id
        )
        scope: Optional[set] = None
        if catalog_id is not None:
            scope = self._subtree_catalog_ids(catalog_id)
            object_stmt = object_stmt.where(MetaObjectStandard.catalog_id.in_(scope))

        objects = list(self.db.execute(object_stmt).scalars().all())
        object_ids = {o.id for o in objects}
        nodes = [
            {
                "id": o.id, "code": o.code, "name": o.name,
                "catalog_id": o.catalog_id, "domain": o.domain, "status": o.status,
            }
            for o in objects
        ]

        relations = list(self.db.execute(relation_stmt).scalars().all())
        edges = []
        for r in relations:
            if r.from_object_id not in object_ids or r.to_object_id not in object_ids:
                continue
            if scope is not None and r.catalog_id is not None and r.catalog_id not in scope:
                continue
            edges.append(
                {
                    "id": r.id, "code": r.code, "name": r.name,
                    "from": r.from_object_id, "to": r.to_object_id,
                    "relation_type": r.relation_type, "catalog_id": r.catalog_id,
                }
            )
        return {"nodes": nodes, "edges": edges}

    # ── 统计 ────────────────────────────────────────────────────────
    def stats(self) -> dict:
        catalog_count = self.db.execute(
            select(func.count()).select_from(MetaStandardCatalog)
            .where(MetaStandardCatalog.tenant_id == self.tenant_id)
        ).scalar()
        object_count = self.db.execute(
            select(func.count()).select_from(MetaObjectStandard)
            .where(MetaObjectStandard.tenant_id == self.tenant_id)
        ).scalar()
        relation_count = self.db.execute(
            select(func.count()).select_from(MetaObjectRelation)
            .where(MetaObjectRelation.tenant_id == self.tenant_id)
        ).scalar()
        verdicts = dict(
            self.db.execute(
                select(MetaRelationCheck.verdict, func.count())
                .where(MetaRelationCheck.tenant_id == self.tenant_id)
                .group_by(MetaRelationCheck.verdict)
            ).all()
        )
        return {
            "catalogs": catalog_count,
            "objects": object_count,
            "relations": relation_count,
            "relation_check": {
                "hit": verdicts.get("hit", 0),
                "missing": verdicts.get("missing", 0),
                "conflict": verdicts.get("conflict", 0),
            },
        }

    # ── 检视辅助：关系校验结论 / 对象绑定表 ──────────────────────────
    def relation_checks(self, relation_id: int) -> List[dict]:
        rows = self.db.execute(
            select(MetaRelationCheck).where(
                MetaRelationCheck.tenant_id == self.tenant_id,
                MetaRelationCheck.standard_relation_id == relation_id,
            ).order_by(MetaRelationCheck.source_id, MetaRelationCheck.database)
        ).scalars().all()
        return [
            {
                "id": c.id,
                "source_id": c.source_id,
                "database": c.database,
                "verdict": c.verdict,
                "confidence": c.confidence,
                "inferred_relation_id": c.inferred_relation_id,
                "evidence": c.evidence_json or {},
                "checked_at": c.checked_at.isoformat() if c.checked_at else None,
            }
            for c in rows
        ]

    def object_bindings(self, object_id: int) -> List[dict]:
        """对象标准被哪些物理表绑定（检视面板下钻入口）。"""
        rows = self.db.execute(
            select(MetaTableStandard, MetaTable)
            .join(MetaTable, MetaTable.id == MetaTableStandard.table_id)
            .where(
                MetaTableStandard.tenant_id == self.tenant_id,
                MetaTableStandard.object_standard_id == object_id,
            )
            .order_by(MetaTable.source_id, MetaTable.database, MetaTable.table_name)
        ).all()
        return [
            {
                "table_id": t.id,
                "source_id": t.source_id,
                "db_name": t.db_name,
                "database": t.database,
                "table_name": t.table_name,
                "status": b.status,
                "source": b.source,
                "confidence": b.confidence,
            }
            for b, t in rows
        ]

    # ── NL 检索 ────────────────────────────────────────────────────
    async def nl_query(
        self,
        question: str,
        catalog_id: Optional[int] = None,
        model_id: Optional[int] = None,
    ) -> dict:
        """自然语言 → 结构化选择器（高亮对象/关系 + 一句话解释）。"""
        from app.ai.research.llm import llm_json

        graph = self.graph(catalog_id)
        id2code = {n["id"]: n["code"] for n in graph["nodes"]}
        compact = {
            "objects": [{"code": n["code"], "name": n["name"], "domain": n["domain"]}
                        for n in graph["nodes"]],
            "relations": [
                {
                    "code": e["code"],
                    "from": id2code.get(e["from"]),
                    "to": id2code.get(e["to"]),
                    "relation_type": e["relation_type"],
                }
                for e in graph["edges"]
            ],
        }
        prompt = (
            "你是元数据治理助手。给定标准图谱（对象/关系）与用户问题，找出最相关的对象与关系。"
            "只输出 JSON，形如 "
            '{"highlight_object_codes": [], "highlight_relation_codes": [], '
            '"focus_catalog_code": null, "summary": "中文一句话"}。\n'
            f"图谱：{compact}\n问题：{question}"
        )
        try:
            data = await llm_json(prompt, model_id=model_id)
        except Exception as exc:  # noqa: BLE001 降级不 500
            return {
                "degraded": True,
                "error": str(exc),
                "highlight_object_codes": [],
                "highlight_relation_codes": [],
                "focus_catalog_code": None,
                "summary": "AI 检索暂不可用",
            }
        if not isinstance(data, dict):
            return {
                "degraded": True,
                "error": "LLM 返回非 JSON 对象",
                "highlight_object_codes": [],
                "highlight_relation_codes": [],
                "focus_catalog_code": None,
                "summary": "AI 检索暂不可用",
            }
        return {
            "degraded": False,
            "highlight_object_codes": data.get("highlight_object_codes") or [],
            "highlight_relation_codes": data.get("highlight_relation_codes") or [],
            "focus_catalog_code": data.get("focus_catalog_code"),
            "summary": data.get("summary") or "",
        }
