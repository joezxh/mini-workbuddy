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
from loguru import logger
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_entity_mention import KgEntityMention
from app.models.kb.kg_triple import KgTriple
from app.models.kb.kb_segment import KbSegment
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

    # ── Neo4j 投影（P2）────────────────────────────────────────────────
    # 全部为 best-effort：Neo4j 不可用时静默跳过，绝不阻断 PG 事实写入
    # （否则图库故障会连带打挂知识库本身）。投影可随时由 reconcile/rebuild 补齐。
    def _project_entity(self, entity: KgEntity) -> None:
        from app.services.kb.kg import kg_graph_store

        try:
            kg_graph_store.project_entity(self.db, entity)
        except Exception as exc:  # noqa: BLE001 - 兜底：投影层已内部消化，此处只防漏
            logger.warning(f"[kg] 实体投影跳过 entity={entity.id}: {exc}")

    def _project_triple(self, triple: KgTriple) -> None:
        from app.services.kb.kg import kg_graph_store

        try:
            kg_graph_store.project_relation(self.db, triple)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[kg] 关系投影跳过 triple={triple.id}: {exc}")

    def _unproject_entity(self, entity: KgEntity) -> None:
        from app.services.kb.kg import kg_graph_store

        try:
            kg_graph_store.unproject_entities(entity.knowledge_id, [entity])
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[kg] 实体撤销投影跳过 entity={entity.id}: {exc}")

    def _unproject_triple(self, triple: KgTriple) -> None:
        from app.services.kb.kg import kg_graph_store

        try:
            kg_graph_store.unproject_relations(self.db, [triple])
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[kg] 关系撤销投影跳过 triple={triple.id}: {exc}")

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
            self._project_entity(existing)
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
        self._project_entity(entity)
        return entity

    def _entity_filtered_stmt(
        self,
        type_code: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ):
        """实体过滤条件（列表与计数共用，保证两者口径一致）。"""
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
        return stmt

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
        stmt = self._entity_filtered_stmt(type_code, status, keyword)
        stmt = stmt.order_by(KgEntity.id).limit(max(1, limit)).offset(max(0, offset))
        return list(self.db.execute(stmt).scalars().all())

    def count_entities(
        self,
        *,
        type_code: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> int:
        """实体计数（与 ``list_entities`` 同一过滤口径）。"""
        self._guard()
        stmt = self._entity_filtered_stmt(type_code, status, keyword)
        total = self.db.execute(
            stmt.with_only_columns(func.count(KgEntity.id))
        ).scalar_one()
        return int(total or 0)

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
        self._project_entity(entity)
        return entity

    def delete_entity(self, entity_id: int) -> None:
        """删除实体（关联关系由外键 CASCADE 一并清理）。"""
        self._guard()
        entity = self.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="实体不存在")
        self._unproject_entity(entity)
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
        self._project_entity(entity)
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
        self._project_triple(triple)
        return triple

    def _triple_filtered_stmt(
        self,
        relation_code: Optional[str] = None,
        status: Optional[str] = None,
        from_entity_id: Optional[int] = None,
        to_entity_id: Optional[int] = None,
    ):
        """关系过滤条件（列表与计数共用）。"""
        stmt = self._triple_stmt()
        if relation_code is not None:
            stmt = stmt.where(KgTriple.relation_code == relation_code)
        if status:
            stmt = stmt.where(KgTriple.status == status)
        if from_entity_id is not None:
            stmt = stmt.where(KgTriple.from_entity_id == from_entity_id)
        if to_entity_id is not None:
            stmt = stmt.where(KgTriple.to_entity_id == to_entity_id)
        return stmt

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
        stmt = self._triple_filtered_stmt(
            relation_code, status, from_entity_id, to_entity_id
        )
        stmt = stmt.order_by(KgTriple.id).limit(max(1, limit)).offset(max(0, offset))
        return list(self.db.execute(stmt).scalars().all())

    def count_triples(
        self,
        *,
        relation_code: Optional[str] = None,
        status: Optional[str] = None,
        from_entity_id: Optional[int] = None,
        to_entity_id: Optional[int] = None,
    ) -> int:
        """关系计数（与 ``list_triples`` 同一过滤口径）。"""
        self._guard()
        stmt = self._triple_filtered_stmt(
            relation_code, status, from_entity_id, to_entity_id
        )
        total = self.db.execute(
            stmt.with_only_columns(func.count(KgTriple.id))
        ).scalar_one()
        return int(total or 0)

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
        """删除关系。

        投影侧只删这条边、保留端点实体（``DETACH DELETE`` 会误伤实体的其它边）。
        """
        self._guard()
        triple = self.get_triple(triple_id)
        if triple is None:
            raise HTTPException(status_code=404, detail="关系不存在")
        self._unproject_triple(triple)
        self.db.delete(triple)
        self.db.commit()

    # ── 图查询（子图 / 路径 / 邻接）────────────────────────────────────
    # 说明：走 PG 而非 Neo4j——PG 是可见性权威，且 BFS 在 ≤3 跳 + 限流下
    # 足以覆盖交互式查询；Neo4j 投影留给检索侧的 PPR 与大规模遍历。
    MAX_GRAPH_DEPTH = 3
    MAX_GRAPH_NODES = 1000

    def _entity_map(self, ids: set) -> dict:
        if not ids:
            return {}
        rows = self.db.execute(
            select(KgEntity).where(KgEntity.id.in_(list(ids)))
        ).scalars().all()
        return {
            e.id: {
                "id": e.id,
                "name": e.name,
                "code": e.type_code or "",
                "type_code": e.type_code or "",
                "entity_key": e.entity_key,
                "status": e.status,
            }
            for e in rows
        }

    def _triples_touching(self, frontier: set) -> list:
        if not frontier:
            return []
        stmt = select(KgTriple).where(
            or_(
                KgTriple.from_entity_id.in_(list(frontier)),
                KgTriple.to_entity_id.in_(list(frontier)),
            )
        )
        if self.tenant_id is not None:
            stmt = stmt.where(KgTriple.tenant_id == self.tenant_id)
        return list(self.db.execute(stmt).scalars().all())

    @staticmethod
    def _edge_dict(t: KgTriple) -> dict:
        return {
            "id": t.id,
            "from": t.from_entity_id,
            "to": t.to_entity_id,
            "relation_type": t.relation_code or "",
            "predicate": t.predicate,
            "weight": t.weight,
            "status": t.status,
        }

    def subgraph(self, entity_ids, *, depth: int = 1, limit: int = 200) -> dict:
        """以给定实体为种子取子图（层数 ≤3，节点数限流）。

        返回 ``{"nodes": [...], "edges": [...]}``，字段与标准中心 ``graph()``
        对齐（nodes: id/name/code；edges: id/from/to/relation_type），
        因此前端图组件可与标准中心共用同一套渲染代码。
        """
        d = max(1, min(self.MAX_GRAPH_DEPTH, int(depth)))
        cap = max(1, min(self.MAX_GRAPH_NODES, int(limit)))
        seeds = {int(e) for e in (entity_ids or []) if e}
        if not seeds:
            return {"nodes": [], "edges": []}

        visited: set = set(seeds)
        frontier: set = set(seeds)
        edges: dict = {}
        endpoint_ids: set = set(seeds)

        for _ in range(d):
            if not frontier or len(endpoint_ids) >= cap:
                break
            next_frontier: set = set()
            for t in self._triples_touching(frontier):
                edges[t.id] = self._edge_dict(t)
                for eid in (t.from_entity_id, t.to_entity_id):
                    endpoint_ids.add(eid)
                    if eid not in visited:
                        next_frontier.add(eid)
                if len(endpoint_ids) >= cap:
                    break
            visited |= next_frontier
            frontier = next_frontier

        nodes = self._entity_map(endpoint_ids)
        node_list = list(nodes.values())[:cap]
        node_ids = {n["id"] for n in node_list}
        edge_list = [
            e for e in edges.values()
            if e["from"] in node_ids and e["to"] in node_ids
        ]
        return {"nodes": node_list, "edges": edge_list}

    def neighbors(self, entity_id: int, *, depth: int = 1, limit: int = 100) -> dict:
        """单实体的邻接子图（检视面板「相邻关系」用）。"""
        return self.subgraph([entity_id], depth=depth, limit=limit)

    def paths(
        self, from_entity_id: int, to_entity_id: int, *, max_depth: int = 2,
        limit: int = 20,
    ) -> list:
        """两实体间的简单路径（≤max_depth 跳，最多 limit 条）。"""
        max_d = max(1, min(self.MAX_GRAPH_DEPTH, int(max_depth)))
        cap = max(1, min(100, int(limit)))
        src, tgt = int(from_entity_id), int(to_entity_id)
        if src == tgt:
            return []

        # 邻接表
        adj: dict = {}
        for t in self._triples_touching({src, tgt}):
            adj.setdefault(t.from_entity_id, []).append((t.to_entity_id, t))
            adj.setdefault(t.to_entity_id, []).append((t.from_entity_id, t))

        results: list = []

        def _dfs(node: int, path_nodes: list, path_edges: list, seen: set):
            if len(results) >= cap:
                return
            if node == tgt and path_edges:
                results.append(
                    {
                        "nodes": [
                            self._entity_map({n}).get(n)
                            for n in path_nodes
                        ],
                        "edges": [self._edge_dict(t) for t in path_edges],
                    }
                )
                return
            if len(path_edges) >= max_d:
                return
            for nxt, t in adj.get(node, []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                path_nodes.append(nxt)
                path_edges.append(t)
                _dfs(nxt, path_nodes, path_edges, seen)
                path_edges.pop()
                path_nodes.pop()
                seen.discard(nxt)

        _dfs(src, [src], [], {src})
        # 节点详情批量补全（避免 N+1 查询）
        all_ids = {n["id"] for r in results for n in r["nodes"] if n}
        detail = self._entity_map(all_ids)
        for r in results:
            r["nodes"] = [detail.get(n["id"], n) for n in r["nodes"] if n]
        return results

    def entity_mentions(self, entity_id: int) -> list:
        """实体提及的切片清单（溯源：这条实体出现在哪些切片里）。

        返回 ``[{segment_id, chunk_index, document_id, content, evidence}]``；
        内容取自 PG（可见性权威），切片已被删除的提及自动跳过。
        """
        mentions = self.db.execute(
            select(KgEntityMention).where(KgEntityMention.kg_entity_id == entity_id)
        ).scalars().all()
        out: list = []
        for m in mentions:
            seg = None
            if m.segment_id is not None:
                seg = self.db.get(KbSegment, m.segment_id)
            if seg is None:
                continue  # 切片已删 -> 提及不再可见
            out.append(
                {
                    "segment_id": seg.id,
                    "chunk_index": seg.chunk_index,
                    "document_id": seg.document_id,
                    "content": (seg.content or "")[:500],
                    "evidence": m.evidence,
                }
            )
        return out

    def labels(self) -> list:
        """实体类型分布（对齐 Yuxi /graph/labels）。"""
        stmt = select(KgEntity.type_code, func.count(KgEntity.id)).where(
            KgEntity.knowledge_id == self.knowledge_id
        )
        if self.tenant_id is not None:
            stmt = stmt.where(KgEntity.tenant_id == self.tenant_id)
        stmt = stmt.group_by(KgEntity.type_code)
        rows = self.db.execute(stmt).all()
        return [
            {"code": code or "", "name": code or "", "count": int(cnt)}
            for code, cnt in rows
        ]

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
