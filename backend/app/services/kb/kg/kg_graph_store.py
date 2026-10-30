"""PG → Neo4j 投影编排（P2）。

为什么要有这一层
----------------
:mod:`kg_neo4j_store` 只负责「给定 ID 与属性，写 Neo4j」这一件事，
而「PG 的一行事实该映射成什么 ID / 什么节点」属于**业务映射**，放在这里：

    kg_entity          ──▶ :Entity 节点
    kg_triple          ──▶ (:Entity)-[:RELATION]->(:Entity)
    kg_*_mention       ──▶ (:Chunk)-[:MENTIONS]->(:Entity)

单向性：只有 PG → Neo4j。Neo4j 永远可从 PG 重建（``rebuild`` / ``reconcile``）。

降级约定
--------
所有投影都是 **best-effort**：Neo4j 不可用时返回 ``False`` 并记日志，
**绝不阻断 PG 侧事实写入**（否则 Neo4j 故障会连带打挂知识库本身）。
构建服务据此把阶段标记为未完成，待 Neo4j 恢复后断点续跑。
"""
from __future__ import annotations

from typing import Iterable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_triple import KgTriple
from app.services.kb.kg.kg_neo4j_store import (
    KgNeo4jStore,
    KgNeo4jUnavailable,
    compute_chunk_id,
    compute_entity_id,
    compute_triple_id,
)


def node_id_for_entity(entity: KgEntity) -> str:
    """实体的 Neo4j 节点 ID：由 (知识库, 归一名, 类型) 确定性计算。"""
    return compute_entity_id(
        entity.knowledge_id, entity.entity_key or "", entity.type_code or ""
    )


def _resolve_entity(db: Session, entity_id: Optional[int]) -> Optional[KgEntity]:
    if entity_id is None:
        return None
    return db.get(KgEntity, entity_id)


def relation_id_for(
    triple: KgTriple, src: Optional[KgEntity], tgt: Optional[KgEntity]
) -> str:
    """三元组的 Neo4j 关系 ID：由 (知识库, 源节点, 关系类型, 目标节点) 确定性计算。

    端点实体取不到时退化为 ``#<id>``（不抛错）：宁可投影出一个孤立 ID，
    也不让一条边的失败打断整批写入——该边会在下次 ``reconcile`` 时补齐。
    """
    src_id = node_id_for_entity(src) if src is not None else f"#{triple.from_entity_id}"
    tgt_id = node_id_for_entity(tgt) if tgt is not None else f"#{triple.to_entity_id}"
    return compute_triple_id(
        triple.knowledge_id, src_id, triple.relation_code or "", tgt_id
    )


def _store(kb_id: int, store: Optional[KgNeo4jStore]) -> KgNeo4jStore:
    return store if store is not None else KgNeo4jStore(kb_id)


# ── 单条投影 ─────────────────────────────────────────────────────────────
def project_entity(
    db: Session, entity: KgEntity, *, store: Optional[KgNeo4jStore] = None
) -> bool:
    """把单个实体投影到 Neo4j。幂等：重复调用不产生重复节点。"""
    try:
        _store(entity.knowledge_id, store).upsert_entity(
            entity_id=node_id_for_entity(entity),
            name=entity.name,
            label=entity.type_code or "",
            normalized_name=entity.entity_key or "",
            attributes={
                "aliases": entity.aliases or [],
                "properties": entity.properties or {},
                "status": entity.status,
                **( {"pg_id": entity.id} if entity.id else {} ),
            },
        )
        return True
    except KgNeo4jUnavailable as exc:
        logger.debug(f"[kg] Neo4j 不可用，跳过实体投影 entity={entity.id}: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001 - 投影失败不得阻断 PG 事实写入
        logger.warning(f"[kg] 实体投影失败 entity={entity.id}: {exc}")
        return False


def project_relation(
    db: Session, triple: KgTriple, *, store: Optional[KgNeo4jStore] = None
) -> bool:
    """把单个三元组投影为 RELATION 边。幂等。"""
    src = _resolve_entity(db, triple.from_entity_id)
    tgt = _resolve_entity(db, triple.to_entity_id)
    if src is None or tgt is None:
        logger.warning(
            f"[kg] 三元组端点缺失，跳过投影 triple={triple.id} "
            f"from={triple.from_entity_id} to={triple.to_entity_id}"
        )
        return False
    try:
        st = _store(triple.knowledge_id, store)
        # 端点节点必须先存在（MERGE 保证幂等）
        st.upsert_entity(
            entity_id=node_id_for_entity(src), name=src.name,
            label=src.type_code or "", normalized_name=src.entity_key or "",
        )
        st.upsert_entity(
            entity_id=node_id_for_entity(tgt), name=tgt.name,
            label=tgt.type_code or "", normalized_name=tgt.entity_key or "",
        )
        st.upsert_relation(
            triple_id=relation_id_for(triple, src, tgt),
            src_entity_id=node_id_for_entity(src),
            tgt_entity_id=node_id_for_entity(tgt),
            relation_type=triple.relation_code or "",
            text=triple.predicate or "",
            extractor_type="manual",
        )
        return True
    except KgNeo4jUnavailable as exc:
        logger.debug(f"[kg] Neo4j 不可用，跳过关系投影 triple={triple.id}: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[kg] 关系投影失败 triple={triple.id}: {exc}")
        return False


def project_mention(
    *,
    kb_id: int,
    document_id: str,
    chunk_index: int,
    entity: KgEntity,
    content_preview: str = "",
    store: Optional[KgNeo4jStore] = None,
) -> bool:
    """投影「切片提及实体」：(:Chunk)-[:MENTIONS]->(:Entity)。幂等。"""
    chunk_id = compute_chunk_id(kb_id, document_id, chunk_index)
    try:
        st = _store(kb_id, store)
        st.upsert_chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=chunk_index,
            content_preview=content_preview,
        )
        st.upsert_entity(
            entity_id=node_id_for_entity(entity), name=entity.name,
            label=entity.type_code or "", normalized_name=entity.entity_key or "",
        )
        st.upsert_mention(
            chunk_id=chunk_id,
            entity_id=node_id_for_entity(entity),
            document_id=document_id,
        )
        return True
    except KgNeo4jUnavailable:
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[kg] 提及投影失败 doc={document_id}: {exc}")
        return False


# ── 撤销 ─────────────────────────────────────────────────────────────────
def unproject_entities(
    kb_id: int, entities: Iterable[KgEntity], *, store: Optional[KgNeo4jStore] = None
) -> int:
    """删除实体节点及其全部边（``DETACH DELETE``）。返回删除数。"""
    ids = [node_id_for_entity(e) for e in entities if e is not None]
    if not ids:
        return 0
    try:
        _store(kb_id, store).delete_entities(ids)
        return len(ids)
    except KgNeo4jUnavailable:
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[kg] 实体撤销投影失败: {exc}")
        return 0


def unproject_chunks(
    kb_id: int, document_id: str, chunk_indexes: Iterable[int],
    *, store: Optional[KgNeo4jStore] = None,
) -> int:
    """删除某文档贡献的 Chunk 节点（及其 MENTIONS 边）。"""
    ids = [compute_chunk_id(kb_id, document_id, i) for i in chunk_indexes]
    if not ids:
        return 0
    try:
        _store(kb_id, store).delete_chunks(ids)
        return len(ids)
    except KgNeo4jUnavailable:
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[kg] Chunk 撤销投影失败 doc={document_id}: {exc}")
        return 0


def unproject_relations(
    db: Session, triples: Iterable[KgTriple], *, store: Optional[KgNeo4jStore] = None
) -> int:
    """删除 RELATION 边（保留端点实体节点）。返回删除数。"""
    ids: list[str] = []
    for t in triples:
        if t is None:
            continue
        ids.append(relation_id_for(t, _resolve_entity(db, t.from_entity_id),
                                   _resolve_entity(db, t.to_entity_id)))
    ids = [i for i in ids if i]
    if not ids:
        return 0
    kb_id = next((t.knowledge_id for t in triples if t is not None), None)
    if kb_id is None:
        return 0
    try:
        _store(kb_id, store).delete_relations(ids)
        return len(ids)
    except KgNeo4jUnavailable:
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[kg] 关系撤销投影失败: {exc}")
        return 0


def unproject_kb(kb_id: int, *, store: Optional[KgNeo4jStore] = None) -> bool:
    """删除该知识库全部投影（删除知识库 / rebuild 前清场）。"""
    try:
        _store(kb_id, store).delete_kb()
        return True
    except KgNeo4jUnavailable:
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[kg] 知识库撤销投影失败 kb={kb_id}: {exc}")
        return False


# ── 对账 ─────────────────────────────────────────────────────────────────
def reconcile(
    db: Session,
    kb_id: int,
    tenant_id: Optional[int] = None,
    *,
    store: Optional[KgNeo4jStore] = None,
    limit: int = 5000,
) -> dict:
    """比对 PG 事实与 Neo4j 投影，补写缺失项（``reconcile`` 动作）。

    策略：**PG 是真相源**，因此不做「删除 Neo4j 多余项」的反向操作，
    只把 PG 中存在的实体/关系重新投影一遍（幂等），使投影收敛到 PG 事实。

    :return: ``{entities, relations, neo4j, ok}``
    """
    from sqlalchemy import select

    ent_stmt = select(KgEntity).where(KgEntity.knowledge_id == kb_id)
    rel_stmt = select(KgTriple).where(KgTriple.knowledge_id == kb_id)
    if tenant_id is not None:
        ent_stmt = ent_stmt.where(KgEntity.tenant_id == tenant_id)
        rel_stmt = rel_stmt.where(KgTriple.tenant_id == tenant_id)

    entities = list(db.execute(ent_stmt.limit(limit)).scalars().all())
    triples = list(db.execute(rel_stmt.limit(limit)).scalars().all())

    projected_e = sum(1 for e in entities if project_entity(db, e, store=store))
    projected_r = sum(1 for t in triples if project_relation(db, t, store=store))

    neo4j_stats: dict = {}
    try:
        neo4j_stats = _store(kb_id, store).stats()
    except Exception as exc:  # noqa: BLE001 - 统计失败不影响对账结论
        logger.debug(f"[kg] 对账取 Neo4j 统计失败: {exc}")

    return {
        "entities": len(entities),
        "relations": len(triples),
        "entities_projected": projected_e,
        "relations_projected": projected_r,
        "neo4j": neo4j_stats,
        "ok": projected_e == len(entities),
    }
