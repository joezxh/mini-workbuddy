"""图谱知识库 · 实例层服务（实体 / 关系的 CRUD 与评审流转）。

Spec: ``docs/superpowers/specs/2026-10-30-kg-knowledge-base-design.md`` §3 / §5

设计要点
--------
* **单一真相源在 PG**：本服务只操作 ``kg_entity`` / ``kg_triple`` 两张实例表；
  Neo4j 投影是 P2 的派生视图，不在本层出现。
* **租户 + 知识库双重隔离**：所有查询强制 ``tenant_id`` + ``knowledge_id`` 过滤；
  跨租户访问他人知识库直接 404（不泄露存在性）。
* **类型守卫**：仅 ``type=4``（图谱库）可调用，其余类型 422——
  与 ``validate_external_type`` 的既有 fail-closed 风格一致。
* **幂等去重**：实体按 ``entity_key``、关系按 (起点, 关系类型, 终点) upsert，
  重复提交不产生重复行（抽取管线重复执行的前提）。
* **评审词表沿用 dataops**：实体 ``suggested→active/deprecated``，
  关系 ``suggested→accepted/rejected``，**不发明新词**；非法流转一律 422。
"""
from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_triple import KgTriple
from app.models.wiki.wiki_knowledge import WikiKnowledge
from app.services.kb.kb_format import GRAPH_KB_TYPE

# 实体状态机（沿用 dataops 评审语义）
ENTITY_STATUS_SUGGESTED = "suggested"
ENTITY_STATUS_ACTIVE = "active"
ENTITY_STATUS_DEPRECATED = "deprecated"

# 关系状态机
TRIPLE_STATUS_SUGGESTED = "suggested"
TRIPLE_STATUS_ACCEPTED = "accepted"
TRIPLE_STATUS_REJECTED = "rejected"

_TERM_RE = re.compile(r"\s+")
_WHITESPACE = re.compile(r"\s+")


def normalize_entity_key(type_code: Optional[str], name: str) -> str:
    """生成规范化去重键：``{类型}:{归一化名称}``。

    类型缺失时用 ``entity`` 前缀；名称内部连续空白折叠为单个空格，
    保证「同一实体不同写法」收敛到同一把键。
    """
    prefix = (type_code or "").strip() or "entity"
    normalized = _TERM_RE.sub(" ", (name or "").strip())
    return f"{prefix}:{normalized}"


def _merge_list(old: Optional[list], new: Optional[list]) -> Optional[list]:
    """列表并集（保序去重）；两侧皆空返回 None。"""
    if not old and not new:
        return old if old is not None else new
    out: list = []
    for item in list(old or []) + list(new or []):
        if item not in out:
            out.append(item)
    return out


class KgService:
    """图谱实例层服务（一个实例服务一个知识库）。"""

    def __init__(self, db: Session, tenant_id: Optional[int], knowledge_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.knowledge_id = knowledge_id

    # ── 守卫 ────────────────────────────────────────────────────────────
    def _guard(self) -> WikiKnowledge:
        """校验知识库存在、属于本租户、且为图谱库（type=4）。"""
        kb = self.db.get(WikiKnowledge, self.knowledge_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="知识库不存在")
        if (
            self.tenant_id is not None
            and kb.tenant_id is not None
            and kb.tenant_id != self.tenant_id
        ):
            # 跨租户：不暴露存在性
            raise HTTPException(status_code=404, detail="知识库不存在")
        if kb.type != GRAPH_KB_TYPE:
            raise HTTPException(
                status_code=422, detail="仅知识图谱库（type=4）支持图谱实例操作"
            )
        return kb

    def _entity_stmt(self):
        stmt = select(KgEntity).where(
            KgEntity.knowledge_id == self.knowledge_id,
        )
        if self.tenant_id is not None:
            stmt = stmt.where(KgEntity.tenant_id == self.tenant_id)
        return stmt

    def _triple_stmt(self):
        stmt = select(KgTriple).where(
            KgTriple.knowledge_id == self.knowledge_id,
        )
        if self.tenant_id is not None:
            stmt = stmt.where(KgTriple.tenant_id == self.tenant_id)
        return stmt

    # ── 实体 ────────────────────────────────────────────────────────────
    def create_entity(
        self,
        *,
        name: str,
        entity_key: Optional[str] = None,
        type_code: Optional[str] = None,
        aliases: Optional[list] = None,
        properties: Optional[dict] = None,
        source_segment_ids: Optional[list] = None,
        source_document_ids: Optional[list] = None,
    ) -> KgEntity:
        """新建实体；``entity_key`` 相同则合并返回既有实体（幂等 upsert）。"""
        self._guard()
        clean_name = (name or "").strip()
        if not clean_name:
            raise HTTPException(status_code=422, detail="实体名不能为空")
        key = (entity_key or "").strip() or normalize_entity_key(type_code, clean_name)

        existing = self.db.execute(
            self._entity_stmt().where(KgEntity.entity_key == key)
        ).scalar_one_or_none()
        if existing is not None:
            existing.aliases = _merge_list(existing.aliases, aliases)
            if properties:
                merged = dict(existing.properties or {})
                merged.update(properties)
                existing.properties = merged
            if source_segment_ids:
                existing.source_segment_ids = _merge_list(
                    existing.source_segment_ids, source_segment_ids
                )
            if source_document_ids:
                existing.source_document_ids = _merge_list(
                    existing.source_document_ids, source_document_ids
                )
            self.db.commit()
            return existing

        entity = KgEntity(
            tenant_id=self.tenant_id,
            knowledge_id=self.knowledge_id,
            collection=f"kb_{self.knowledge_id}",
            entity_key=key,
            name=clean_name,
            type_code=(type_code or None),
            aliases=aliases,
            properties=properties,
            source_segment_ids=source_segment_ids,
            source_document_ids=source_document_ids,
            status=ENTITY_STATUS_SUGGESTED,
        )
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def list_entities(
        self,
        *,
        type_code: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[KgEntity]:
        """列出实体（按类型 / 状态 / 关键词过滤，关键词命中名称或别名）。"""
        self._guard()
        stmt = self._entity_stmt()
        if type_code:
            stmt = stmt.where(KgEntity.type_code == type_code)
        if status:
            stmt = stmt.where(KgEntity.status == status)
        if keyword:
            like = f"%{_WHITESPACE.sub(' ', keyword.strip())}%"
            stmt = stmt.where(
                or_(
                    KgEntity.name.ilike(like),
                    KgEntity.entity_key.ilike(like),
                    # aliases 是 JSONB 数组，PG 不支持 JSONB ~~*，需显式转文本匹配
                    cast(KgEntity.aliases, String).ilike(like),
                )
            )
        stmt = stmt.order_by(KgEntity.id).limit(max(1, limit)).offset(max(0, offset))
        return list(self.db.execute(stmt).scalars().all())

    def get_entity(self, entity_id: int) -> Optional[KgEntity]:
        """取实体（受租户 + 知识库双重约束）。"""
        self._guard()
        return self.db.execute(
            self._entity_stmt().where(KgEntity.id == entity_id)
        ).scalar_one_or_none()

    def update_entity(self, entity_id: int, **fields: Any) -> KgEntity:
        """编辑实体（名称 / 类型 / 别名 / 属性）。

        ``entity_key`` 是身份锚点，**不可改**——改名不应改变去重键。
        """
        self._guard()
        entity = self.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")
        if "name" in fields and fields["name"] is not None:
            clean = str(fields["name"]).strip()
            if not clean:
                raise HTTPException(status_code=422, detail="实体名不能为空")
            entity.name = clean
        if "type_code" in fields:
            entity.type_code = fields["type_code"] or None
        if "aliases" in fields and fields["aliases"] is not None:
            entity.aliases = fields["aliases"]
        if "properties" in fields and fields["properties"] is not None:
            entity.properties = fields["properties"]
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete_entity(self, entity_id: int) -> None:
        """删除实体（关联关系由外键 CASCADE 一并清理）。"""
        self._guard()
        entity = self.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")
        self.db.delete(entity)
        self.db.commit()

    def accept_entity(self, entity_id: int) -> KgEntity:
        """评审通过：``suggested → active``（已采纳的实体不可重复流转）。"""
        self._guard()
        entity = self.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")
        if entity.status != ENTITY_STATUS_SUGGESTED:
            raise HTTPException(
                status_code=422,
                detail=f"实体当前状态为 {entity.status}，仅待评审实体可采纳",
            )
        entity.status = ENTITY_STATUS_ACTIVE
        self.db.commit()
        self.db.refresh(entity)
        return entity

    # ── 关系 ────────────────────────────────────────────────────────────
    def _require_entity(self, entity_id: int) -> KgEntity:
        """取实体并确认其属于本知识库（防跨库挂边）。"""
        entity = self.db.execute(
            self._entity_stmt().where(KgEntity.id == entity_id)
        ).scalar_one_or_none()
        if entity is None:
            raise HTTPException(
                status_code=422, detail="关系两端的实体必须属于当前知识库"
            )
        return entity

    def create_triple(
        self,
        *,
        from_entity_id: int,
        to_entity_id: int,
        relation_code: Optional[str] = None,
        predicate: Optional[str] = None,
        weight: float = 0.0,
        properties: Optional[dict] = None,
        evidence: Optional[dict] = None,
        source_segment_ids: Optional[list] = None,
        source_document_ids: Optional[list] = None,
    ) -> KgTriple:
        """新建关系；同一 (起点, 关系类型, 终点) 重复提交则合并返回既有边。"""
        self._guard()
        src = self._require_entity(from_entity_id)
        dst = self._require_entity(to_entity_id)
        code = (relation_code or "").strip()

        existing = self.db.execute(
            self._triple_stmt().where(
                KgTriple.from_entity_id == src.id,
                KgTriple.relation_code == code,
                KgTriple.to_entity_id == dst.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if predicate and not existing.predicate:
                existing.predicate = predicate
            if weight:
                existing.weight = weight
            if properties:
                merged = dict(existing.properties or {})
                merged.update(properties)
                existing.properties = merged
            if evidence:
                existing.evidence = evidence
            self.db.commit()
            return existing

        triple = KgTriple(
            tenant_id=self.tenant_id,
            knowledge_id=self.knowledge_id,
            collection=f"kb_{self.knowledge_id}",
            relation_code=code,
            from_entity_id=src.id,
            to_entity_id=dst.id,
            predicate=predicate,
            weight=weight,
            properties=properties,
            evidence=evidence,
            source_segment_ids=source_segment_ids,
            source_document_ids=source_document_ids,
            status=TRIPLE_STATUS_SUGGESTED,
        )
        self.db.add(triple)
        self.db.commit()
        self.db.refresh(triple)
        return triple

    def list_triples(
        self,
        *,
        relation_code: Optional[str] = None,
        status: Optional[str] = None,
        from_entity_id: Optional[int] = None,
        to_entity_id: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[KgTriple]:
        """列出关系（按类型 / 状态 / 端点过滤）。"""
        self._guard()
        stmt = self._triple_stmt()
        if relation_code is not None:
            stmt = stmt.where(KgTriple.relation_code == relation_code)
        if status:
            stmt = stmt.where(KgTriple.status == status)
        if from_entity_id is not None:
            stmt = stmt.where(KgTriple.from_entity_id == from_entity_id)
        if to_entity_id is not None:
            stmt = stmt.where(KgTriple.to_entity_id == to_entity_id)
        stmt = stmt.order_by(KgTriple.id).limit(max(1, limit)).offset(max(0, offset))
        return list(self.db.execute(stmt).scalars().all())

    def get_triple(self, triple_id: int) -> Optional[KgTriple]:
        """取关系（受租户 + 知识库双重约束）。"""
        self._guard()
        return self.db.execute(
            self._triple_stmt().where(KgTriple.id == triple_id)
        ).scalar_one_or_none()

    def entity_adjacent_triples(self, entity_id: int) -> list[KgTriple]:
        """取某实体相邻的全部关系（出边 + 入边），供检视面板展示。"""
        self._guard()
        stmt = self._triple_stmt().where(
            or_(KgTriple.from_entity_id == entity_id, KgTriple.to_entity_id == entity_id)
        )
        return list(self.db.execute(stmt.order_by(KgTriple.id)).scalars().all())

    def review_triple(self, triple_id: int, verdict: str) -> KgTriple:
        """关系评审：``suggested → accepted | rejected``。"""
        self._guard()
        if verdict not in (TRIPLE_STATUS_ACCEPTED, TRIPLE_STATUS_REJECTED):
            raise HTTPException(
                status_code=422, detail=f"评审结论非法: {verdict!r}（应为 accepted/rejected）"
            )
        triple = self.get_triple(triple_id)
        if triple is None:
            raise HTTPException(status_code=404, detail="关系不存在")
        if triple.status != TRIPLE_STATUS_SUGGESTED:
            raise HTTPException(
                status_code=422,
                detail=f"关系当前状态为 {triple.status}，仅待评审关系可流转",
            )
        triple.status = verdict
        self.db.commit()
        self.db.refresh(triple)
        return triple

    def delete_triple(self, triple_id: int) -> None:
        """删除关系。"""
        self._guard()
        triple = self.get_triple(triple_id)
        if triple is None:
            raise HTTPException(status_code=404, detail="关系不存在")
        self.db.delete(triple)
        self.db.commit()

    # ── 统计 ────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        """概览统计：实体 / 关系计数与类型分布。"""
        self._guard()
        entity_rows = self.db.execute(
            self._entity_stmt()
            .with_only_columns(KgEntity.type_code, func.count(KgEntity.id))
            .group_by(KgEntity.type_code)
        ).all()
        relation_rows = self.db.execute(
            self._triple_stmt()
            .with_only_columns(KgTriple.relation_code, func.count(KgTriple.id))
            .group_by(KgTriple.relation_code)
        ).all()
        total_entities = self.db.execute(
            self._entity_stmt().with_only_columns(func.count(KgEntity.id))
        ).scalar_one()
        total_relations = self.db.execute(
            self._triple_stmt().with_only_columns(func.count(KgTriple.id))
        ).scalar_one()
        return {
            "entities": int(total_entities or 0),
            "relations": int(total_relations or 0),
            "by_type": {(code or ""): int(n) for code, n in entity_rows},
            "by_relation": {(code or ""): int(n) for code, n in relation_rows},
        }
