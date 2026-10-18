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
        return [_as_dict(r) for r in rel.extract(text, entities, **kwargs)]

    def extract_triplets(self, text, entities=None, relations=None, **kwargs) -> List[dict]:
        te = _import("semantica.semantic_extract.triplet_extractor").TripletExtractor()
        return [
            _as_dict(t)
            for t in te.extract_triplets(
                text, entities=entities, relations=relations, **kwargs
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
