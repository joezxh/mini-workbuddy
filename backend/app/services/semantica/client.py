"""semantica 延迟导入与能力探测的薄封装。

设计要点：
- 所有 ``import semantica.*`` 延迟到方法调用时发生（``_import``），因此未安装
  semantica 时本类仍可导入，调用时再以 ``SemanticaUnavailable`` 显式失败
  （fail-closed，不像旧 rdflib 那样 warning 后继续）。
- 连接信息从 ``app.config.settings`` 注入：PostgreSQL(pgvector) 用 ``settings.db_url``，
  Neo4j 用 ``NEO4J_*``；命名空间 / 集合名 / label 经 ``TenantScope`` 隔离。
"""
from __future__ import annotations

import importlib
from typing import Any, List, Optional

from loguru import logger

from app.config import settings


class SemanticaUnavailable(RuntimeError):
    """semantica 或其存储后端不可用时抛出（fail-closed）。"""


def _import(module: str):
    try:
        return importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - 依赖缺失路径
        raise SemanticaUnavailable(f"semantica 模块 {module} 不可用: {exc}") from exc


def _as_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return getattr(obj, "__dict__", obj)


def _entity_type():
    from semantica.semantic_extract.types import Entity

    return Entity


def _to_entities(values: Any) -> Any:
    """实体入参归一：``list[dict]`` → ``list[Entity]``；已是对象则原样返回。

    :meth:`SemanticaClient.extract_entities` 的产物是 **dict**（``_as_dict``），
    而 ``RelationExtractor`` / ``TripletExtractor`` 内部按 ``entity.text`` / ``.label``
    取属性。dict 原样透传会抛 ``AttributeError: 'dict' object has no attribute
    'text'``，关系抽取因此**整批失败**（表现为抽取成功但 relations 恒为 0）。
    偏移量缺失时以 0 兜底：抽取器只用 ``text``/``label`` 组三元组，坐标不参与语义。
    """
    if not values or not isinstance(values, (list, tuple)):
        return values
    if not any(isinstance(v, dict) for v in values):
        return list(values)
    Entity = _entity_type()
    out: List[Any] = []
    for v in values:
        if isinstance(v, Entity):
            out.append(v)
            continue
        if not isinstance(v, dict):
            # 字符串形态：只带名字，类型未知
            out.append(Entity(
                text=str(v), label="", start_char=0, end_char=len(str(v)),
            ))
            continue
        text = str(v.get("text") or v.get("name") or v.get("entity") or "")
        if not text:
            continue
        out.append(Entity(
            text=text,
            label=str(v.get("label") or v.get("type") or ""),
            start_char=int(v.get("start_char") or 0),
            end_char=int(v.get("end_char") or 0),
            confidence=v.get("confidence"),
            metadata=v.get("metadata") or {},
        ))
    return out


def _to_relations(values: Any) -> Any:
    """关系入参归一：其 subject/object 同样可能是 dict。"""
    if not values or not isinstance(values, (list, tuple)):
        return values
    Entity = _entity_type()
    out: List[Any] = []
    for v in values:
        if not isinstance(v, dict):
            out.append(v)
            continue
        row = dict(v)
        for key in ("subject", "object"):
            val = row.get(key)
            if isinstance(val, dict):
                row[key] = _to_entities([val])[0]
            elif isinstance(val, str):
                row[key] = Entity(
                    text=val, label="", start_char=0, end_char=len(val),
                )
        out.append(row)
    return out


class SemanticaClient:
    """semantica 能力的统一入口。

    方法对应 semantica 高层 API：
      ingest / semantic_extract / kg / conflicts / deduplication / vector_store /
      graph_store / export / provenance。
    """

    def __init__(self, scope: "TenantScope | None" = None) -> None:
        self._scope = scope

    # ---- 能力探测 ----
    @staticmethod
    def is_available() -> bool:
        try:
            _import("semantica")
            return True
        except SemanticaUnavailable:
            return False

    # ---- 语义抽取（semantic_extract） ----
    def extract_entities(self, text: str, **options) -> List[dict]:
        ner = _import("semantica.semantic_extract.named_entity_recognizer").NamedEntityRecognizer()
        return [_as_dict(e) for e in ner.extract_entities(text, **options)]

    def extract_relations(self, text, entities, **kwargs) -> List[dict]:
        rel = _import("semantica.semantic_extract.relation_extractor").RelationExtractor()
        return [_as_dict(r) for r in rel.extract(text, _to_entities(entities), **kwargs)]

    def extract_triplets(self, text, entities=None, relations=None, **kwargs) -> List[dict]:
        te = _import("semantica.semantic_extract.triplet_extractor").TripletExtractor()
        return [
            _as_dict(t)
            for t in te.extract_triplets(
                text,
                entities=_to_entities(entities),
                relations=_to_relations(relations),
                **kwargs,
            )
        ]

    # ---- 冲突检测 / 实体去重（conflicts / deduplication） ----
    def detect_conflicts(self, entities: List[dict], **kwargs) -> List[Any]:
        return _import("semantica.conflicts").detect_conflicts(entities, **kwargs)

    def deduplicate(self, entities: List[dict], **kwargs) -> List[Any]:
        return _import("semantica.deduplication").detect_duplicates(entities, **kwargs)

    # ---- 图存储（graph_store：Neo4j） ----
    def neo4j_store(self):
        if not settings.NEO4J_ENABLED:
            raise SemanticaUnavailable("NEO4J_ENABLED=false，图存储后端不可用")
        store = _import("semantica.graph_store").Neo4jStore(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
        logger.debug("semantica Neo4jStore 已连接 {}", settings.NEO4J_URI)
        return store

    # ---- 图谱构建（kg） ----
    def build_graph(self, entities: List[dict], relationships: List[dict], **kwargs) -> Any:
        kg = _import("semantica.kg")
        graph_store = self.neo4j_store() if settings.NEO4J_ENABLED else None
        builder = kg.GraphBuilder(graph_store=graph_store, **kwargs)
        sources = kg.KnowledgeGraph(entities=entities, relationships=relationships)
        return builder.build(sources)

    # ---- 向量存储（vector_store：pgvector） ----
    def vector_store(self, kind: str = "entity", dimension: Optional[int] = None):
        vs = _import("semantica.vector_store")
        table_name = self._scope.collection(kind) if self._scope else kind
        return vs.PgVectorStore(
            connection_string=settings.db_url,
            table_name=table_name,
            dimension=dimension or settings.SEMANTICA_VECTOR_DIM,
            distance_metric="cosine",
        )

    # ---- 导出（export） ----
    def export_rdf(self, data, file_path, **kwargs) -> None:
        return _import("semantica.export").export_rdf(data, file_path, **kwargs)

    def export_owl(self, ontology, file_path, **kwargs) -> None:
        return _import("semantica.export").export_owl(ontology, file_path, **kwargs)

    # ---- 溯源（provenance） ----
    def provenance_manager(self, storage_path: Optional[str] = None):
        return _import("semantica.provenance").ProvenanceManager(storage_path=storage_path)
