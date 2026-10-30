"""图谱知识库的 Neo4j 图结构投影层（P2）。

职责边界
--------
**只做图结构投影，不做事实存储**。PG 是唯一真相源（spec §5.1），Neo4j 永远可从 PG 重建：

    PG(kg_entity/kg_triple/*_mention)  ──单向投影──▶  Neo4j(:Entity/:Chunk)

设计要点（全部对齐 spec §2.2 的 Yuxi 约定 / §3.8）：

* **三段式 label**：``:Entity:MwbKG:`mwb_kb_{kid}` `` / ``:Chunk:MwbKG:`mwb_kb_{kid}` ``
  —— ``MwbKG`` 是基础 label（与 graphiti / semantica 的 ``minworkbuddy_*`` 前缀无交集），
  ``mwb_kb_{kid}`` 是每知识库 label，构成租户/知识库级隔离。
* **关系类型仅两种**：``MENTIONS``(Chunk→Entity) 与 ``RELATION``(Entity→Entity)，
  语义关系类型存**关系属性** ``type``（与 Yuxi 一致：Cypher 简单、写入幂等）。
* **全部 Cypher 集中本文件**，业务代码禁止散落 Cypher 字符串。
* **label 名白名单校验**（``safe_neo4j_label``，``^mwb_kb_\\d+$``）防 Cypher 注入 ——
  label 无法作为参数化占位符，只能拼接，因此必须先校验再拼。
* **稳定 hash ID**：实体/三元组/切片的 Neo4j ID 由内容确定性计算，
  重复投影同一事实永远命中同一节点（幂等 ``MERGE`` 的前提）。
* **写入方向单向**：不存在 Neo4j → PG 的反向同步。

不可用时行为：写方法抛 :class:`KgNeo4jUnavailable`，由调用方（构建服务）决定
降级策略（标记阶段未完成、可断点续跑）；**读路径**则按 spec §6.2 降级为空，不阻断主检索。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Optional, Sequence

from loguru import logger

from app.config import settings

# ── label 校验：label 不能参数化，只能拼接，故必须白名单 ──────────────────
BASE_LABEL = "MwbKG"
_LABEL_RE = re.compile(r"^mwb_kb_\d+$")


class KgNeo4jUnavailable(RuntimeError):
    """Neo4j 不可用（未启用 / 连接失败 / 驱动缺失）。"""


def safe_neo4j_label(kb_id: int) -> str:
    """生成并校验每知识库 label（``mwb_kb_{kid}``）。

    :raises ValueError: kb_id 非正整数（等于阻断任何越出白名单的拼接）
    """
    try:
        kid = int(kb_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"kb_id 必须是整数: {kb_id!r}") from exc
    if kid <= 0:
        raise ValueError(f"kb_id 必须为正整数: {kb_id!r}")
    label = f"mwb_kb_{kid}"
    if not _LABEL_RE.match(label):  # 防御：上面的约束已保证，双保险
        raise ValueError(f"label 未通过白名单校验: {label!r}")
    return label


def _hash32(*parts: Any) -> str:
    """Yuxi hashstr 同款：确定性 32 位十六进制 ID。"""
    raw = "\x1f".join("" if p is None else str(p) for p in parts)
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=16).hexdigest()


def compute_entity_id(kb_id: int, normalized_name: str, label: str) -> str:
    return _hash32(kb_id, "entity", normalized_name, label)


def compute_triple_id(
    kb_id: int, src_entity_id: str, relation_type: str, tgt_entity_id: str
) -> str:
    return _hash32(kb_id, "triple", src_entity_id, relation_type, tgt_entity_id)


def compute_chunk_id(kb_id: int, document_id: str, chunk_index: int) -> str:
    return _hash32(kb_id, "chunk", document_id, chunk_index)


# ── Cypher 模板（集中一处；label 已在 safe_neo4j_label 校验后拼接）────────
CYPHER_UPSERT_ENTITY = """
MERGE (e:Entity:{base}:`{kb}` {{entity_id: $entity_id}})
SET e.kb_id = $kb_id,
    e.name = $name,
    e.label = $label,
    e.normalized_name = $normalized_name,
    e.attributes = $attributes
RETURN e.entity_id AS entity_id
"""

CYPHER_UPSERT_CHUNK = """
MERGE (c:Chunk:{base}:`{kb}` {{chunk_id: $chunk_id}})
SET c.kb_id = $kb_id,
    c.document_id = $document_id,
    c.chunk_index = $chunk_index,
    c.content_preview = $content_preview
RETURN c.chunk_id AS chunk_id
"""

CYPHER_UPSERT_MENTION = """
MERGE (c:Chunk:{base}:`{kb}` {{chunk_id: $chunk_id}})
MERGE (e:Entity:{base}:`{kb}` {{entity_id: $entity_id}})
MERGE (c)-[r:MENTIONS {{kb_id: $kb_id}}]->(e)
SET r.chunk_id = $chunk_id, r.document_id = $document_id
RETURN r.chunk_id AS chunk_id
"""

CYPHER_UPSERT_RELATION = """
MERGE (s:Entity:{base}:`{kb}` {{entity_id: $src_entity_id}})
MERGE (t:Entity:{base}:`{kb}` {{entity_id: $tgt_entity_id}})
MERGE (s)-[r:RELATION {{kb_id: $kb_id, triple_id: $triple_id}}]->(t)
SET r.type = $relation_type,
    r.text = $text,
    r.chunk_id = $chunk_id,
    r.extractor_type = $extractor_type
RETURN r.triple_id AS triple_id
"""

CYPHER_DELETE_ENTITIES = """
UNWIND $entity_ids AS eid
MATCH (e:Entity:{base}:`{kb}` {{entity_id: eid}})
DETACH DELETE e
"""

CYPHER_DELETE_CHUNKS = """
UNWIND $chunk_ids AS cid
MATCH (c:Chunk:{base}:`{kb}` {{chunk_id: cid}})
DETACH DELETE c
"""

# 单删边：按 triple_id 属性定位（关系类型统一为 RELATION，故不能用类型区分）
CYPHER_DELETE_RELATIONS = """
UNWIND $triple_ids AS tid
MATCH ()-[r:RELATION {{kb_id: $kb_id, triple_id: tid}}]->()
DELETE r
"""

CYPHER_DELETE_KB = """
MATCH (n:{base}:`{kb}`)
DETACH DELETE n
"""

# 种子子图：depth 已钳制为 1..3（spec 多跳硬封顶）
CYPHER_SEED_SUBGRAPH = """
UNWIND $seed_ids AS sid
MATCH (s:Entity:{base}:`{kb}` {{entity_id: sid}})
CALL apoc.path.subgraphAll(s, {{maxLevel: $depth, limit: $limit}})
YIELD nodes, relationships
RETURN nodes, relationships
"""

# 无 apoc 时的等价实现（可变跳数无法参数化，故由 depth 白名单选择模板）
# 注意：字面量花括号（如 `{entity_id: sid}`）必须写成 `{{...}}`，否则会被 .format 吞掉
_SEED_SUBGRAPH_FALLBACK = {
    1: """
UNWIND $seed_ids AS sid
MATCH (s:Entity:{base}:`{kb}` {{entity_id: sid}})-[r]-(n)
RETURN collect(DISTINCT s) + collect(DISTINCT n) AS nodes, collect(DISTINCT r) AS relationships
""",
    2: """
UNWIND $seed_ids AS sid
MATCH (s:Entity:{base}:`{kb}` {{entity_id: sid}})-[r*1..2]-(n)
RETURN collect(DISTINCT s) + collect(DISTINCT n) AS nodes,
       [rel IN collect(DISTINCT last(r)) | rel] AS relationships
""",
    3: """
UNWIND $seed_ids AS sid
MATCH (s:Entity:{base}:`{kb}` {{entity_id: sid}})-[r*1..3]-(n)
RETURN collect(DISTINCT s) + collect(DISTINCT n) AS nodes,
       [rel IN collect(DISTINCT last(r)) | rel] AS relationships
""",
}

CYPHER_PATHS_1 = """
MATCH p = (a:Entity:{base}:`{kb}` {{entity_id: $src}})-[r]-(b:Entity:{base}:`{kb}` {{entity_id: $tgt}})
RETURN p LIMIT $limit
"""

CYPHER_STATS = """
MATCH (n:{base}:`{kb}`)
RETURN labels(n) AS labels, count(*) AS c
"""

# ── 驱动管理：长生命周期单例（neo4j 驱动线程安全）────────────────────────
_driver = None
_driver_failed = False


def _get_driver():
    """惰性创建 Neo4j 驱动；失败只记一次，避免每次调用都打日志。"""
    global _driver, _driver_failed
    if _driver is not None:
        return _driver
    if _driver_failed or not settings.NEO4J_ENABLED:
        raise KgNeo4jUnavailable("NEO4J_ENABLED=false 或驱动此前已失败")
    try:
        from neo4j import GraphDatabase

        _driver = GraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        return _driver
    except Exception as exc:  # noqa: BLE001 - 驱动创建失败统一降级
        _driver_failed = True
        raise KgNeo4jUnavailable(f"Neo4j 驱动创建失败: {exc}") from exc


def reset_driver() -> None:
    """关闭并清空驱动单例（测试 / 配置变更后重建）。"""
    global _driver, _driver_failed
    if _driver is not None:
        try:
            _driver.close()
        except Exception:  # noqa: BLE001 - 关闭失败无需传播
            pass
    _driver = None
    _driver_failed = False


def is_available() -> bool:
    """连通性探测（``RETURN 1``）。失败返回 False，不抛。"""
    if not settings.NEO4J_ENABLED:
        return False
    try:
        driver = _get_driver()
        with driver.session() as session:
            session.run("RETURN 1").single()
        return True
    except Exception:  # noqa: BLE001 - 探测失败即不可用
        return False


class KgNeo4jStore:
    """单个知识库的图结构投影读写口。

    :param kb_id: 知识库主键（决定隔离 label）
    :param session_factory: 可注入的会话工厂，仅用于测试注入假驱动
    """

    def __init__(self, kb_id: int, *, session_factory=None) -> None:
        self.kb_id = int(kb_id)
        self.label = safe_neo4j_label(self.kb_id)
        self._session_factory = session_factory

    # ── 内部：会话获取 + 模板渲染 ────────────────────────────────────────
    def _session(self):
        if self._session_factory is not None:
            return self._session_factory()
        return _get_driver().session()

    def _render(self, template: str) -> str:
        return template.format(base=BASE_LABEL, kb=self.label)

    def _run(self, template: str, **params) -> list[dict]:
        query = self._render(template)
        with self._session() as session:
            result = session.run(query, **params)
            return [dict(r) for r in result]

    # ── 写入（幂等 MERGE）────────────────────────────────────────────────
    def upsert_chunk(
        self, *, chunk_id: str, document_id: str, chunk_index: int, content_preview: str
    ) -> None:
        self._run(
            CYPHER_UPSERT_CHUNK,
            chunk_id=chunk_id,
            kb_id=self.kb_id,
            document_id=document_id,
            chunk_index=chunk_index,
            content_preview=(content_preview or "")[:500],
        )

    def upsert_entity(
        self,
        *,
        entity_id: str,
        name: str,
        label: str,
        normalized_name: str,
        attributes: Optional[dict] = None,
    ) -> None:
        self._run(
            CYPHER_UPSERT_ENTITY,
            entity_id=entity_id,
            kb_id=self.kb_id,
            name=name,
            label=label,
            normalized_name=normalized_name,
            attributes=attributes or {},
        )

    def upsert_mention(self, *, chunk_id: str, entity_id: str, document_id: str) -> None:
        self._run(
            CYPHER_UPSERT_MENTION,
            chunk_id=chunk_id,
            entity_id=entity_id,
            kb_id=self.kb_id,
            document_id=document_id,
        )

    def upsert_relation(
        self,
        *,
        triple_id: str,
        src_entity_id: str,
        tgt_entity_id: str,
        relation_type: str,
        text: Optional[str] = None,
        chunk_id: Optional[str] = None,
        extractor_type: Optional[str] = None,
    ) -> None:
        self._run(
            CYPHER_UPSERT_RELATION,
            triple_id=triple_id,
            src_entity_id=src_entity_id,
            tgt_entity_id=tgt_entity_id,
            kb_id=self.kb_id,
            relation_type=relation_type,
            text=text or "",
            chunk_id=chunk_id or "",
            extractor_type=extractor_type or "",
        )

    def delete_entities(self, entity_ids: Sequence[str]) -> None:
        ids = [e for e in entity_ids if e]
        if not ids:
            return
        self._run(CYPHER_DELETE_ENTITIES, entity_ids=ids)

    def delete_chunks(self, chunk_ids: Sequence[str]) -> None:
        ids = [c for c in chunk_ids if c]
        if not ids:
            return
        self._run(CYPHER_DELETE_CHUNKS, chunk_ids=ids)

    def delete_relations(self, triple_ids: Sequence[str], *, kb_id: Optional[int] = None) -> None:
        """按 triple_id 删除 RELATION 边（实体节点保留）。"""
        ids = [t for t in triple_ids if t]
        if not ids:
            return
        self._run(
            CYPHER_DELETE_RELATIONS,
            triple_ids=ids,
            kb_id=self.kb_id if kb_id is None else int(kb_id),
        )

    def delete_kb(self) -> None:
        """删除该知识库全部投影节点（rebuild / 删除知识库时用）。"""
        self._run(CYPHER_DELETE_KB)

    # ── 读取 ─────────────────────────────────────────────────────────────
    def seed_subgraph(
        self, seed_ids: Sequence[str], *, depth: int = 2, limit: int = 1000
    ) -> dict:
        """以实体为种子取子图；返回 ``{nodes, edges}``（与 PG 侧结构对齐）。

        depth 硬钳制 1..3（spec：多跳硬封顶 3 跳）。
        优先 apoc；不可用时退回等价展开模板（结果可能不严格去重上限，由调用方限流）。
        """
        d = max(1, min(3, int(depth)))
        ids = list(seed_ids or [])
        if not ids:
            return {"nodes": [], "edges": []}
        try:
            rows = self._run(
                CYPHER_SEED_SUBGRAPH, seed_ids=ids, depth=d, limit=int(limit)
            )
            return _normalize_subgraph(rows)
        except Exception as exc:  # noqa: BLE001 - apoc 缺失等 → 退回展开模板
            logger.debug(f"[kg] apoc 子图不可用，退回展开模板: {exc}")
            rows = self._run(_SEED_SUBGRAPH_FALLBACK[d], seed_ids=ids)
            return _normalize_subgraph(rows)

    def paths(self, src_entity_id: str, tgt_entity_id: str, *, limit: int = 20) -> list:
        """两实体间路径（1~2 跳）；返回节点/边序列列表。"""
        rows = self._run(
            CYPHER_PATHS_1, src=src_entity_id, tgt=tgt_entity_id, limit=int(limit)
        )
        return [_path_to_dict(r.get("p")) for r in rows if r.get("p") is not None]

    def stats(self) -> dict:
        """按 label 计数（调试 / 对账用）。"""
        try:
            rows = self._run(CYPHER_STATS)
        except KgNeo4jUnavailable:
            return {}
        out: dict[str, int] = {}
        for r in rows:
            labels = r.get("labels") or []
            key = next((l for l in labels if l not in (BASE_LABEL, self.label)), "unknown")
            out[key] = out.get(key, 0) + int(r.get("c") or 0)
        return out


# ── 结果归一化 ───────────────────────────────────────────────────────────
def _node_to_dict(node: Any) -> Optional[dict]:
    if node is None:
        return None
    props = dict(getattr(node, "_properties", {}) or {})
    labels = list(getattr(node, "labels", []) or [])
    kind = "Entity" if "Entity" in labels else "Chunk" if "Chunk" in labels else "Node"
    if kind == "Entity":
        return {
            "id": props.get("entity_id"),
            "name": props.get("name"),
            "label": props.get("label"),
            "kind": kind,
        }
    return {
        "id": props.get("chunk_id"),
        "name": props.get("content_preview", "")[:80],
        "label": "Chunk",
        "kind": kind,
        "document_id": props.get("document_id"),
        "chunk_index": props.get("chunk_index"),
    }


def _rel_to_dict(rel: Any) -> Optional[dict]:
    if rel is None:
        return None
    props = dict(getattr(rel, "_properties", {}) or {})
    rtype = getattr(rel, "type", None) or "RELATION"
    start = getattr(rel, "start_node", None)
    end = getattr(rel, "end_node", None)
    sid = (dict(getattr(start, "_properties", {}) or {}).get("entity_id")
           or dict(getattr(start, "_properties", {}) or {}).get("chunk_id"))
    eid = (dict(getattr(end, "_properties", {}) or {}).get("entity_id")
           or dict(getattr(end, "_properties", {}) or {}).get("chunk_id"))
    return {
        "id": props.get("triple_id") or f"{sid}-{rtype}-{eid}",
        "from": sid,
        "to": eid,
        "relation_type": props.get("type") or rtype,
        "neo4j_type": rtype,
    }


def _normalize_subgraph(rows: Iterable[dict]) -> dict:
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for row in rows:
        for n in row.get("nodes") or []:
            d = _node_to_dict(n)
            if d and d.get("id"):
                nodes[d["id"]] = d
        for r in row.get("relationships") or []:
            d = _rel_to_dict(r)
            if d and d.get("id"):
                edges[d["id"]] = d
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def _path_to_dict(path: Any) -> dict:
    nodes = [_node_to_dict(n) for n in getattr(path, "nodes", []) or []]
    rels = [_rel_to_dict(r) for r in getattr(path, "relationships", []) or []]
    return {
        "nodes": [n for n in nodes if n],
        "edges": [r for r in rels if r],
    }
