"""WikiOwlEngine - 基于 rdflib 的 OWL 本体引擎（持久化后端）。

功能:
- 注册 OWL Class (含 label / comment / parent)
- 查询类层级 (hierarchy / ancestors / descendants)
- TTL 导入 / 导出
- 文章 OWL 类标注 (article ↔ class 关联)

设计:
- 存储后端可插拔：默认持久化到数据库（`OntologyRepository`，按租户隔离），
  也可传入内存 store（`InMemoryOntologyStore`，仅离线/单测使用）；
  rdflib 只负责 TTL 的解析与序列化，不再作为运行期存储 —— 这样本体
  **重启不丢**且**不跨租户共享**（修复了改造前的进程级内存单例缺陷）。
- **单一真相源**（评审 R2-01 / R2-02，用户授权）：`ontology.ttl_content` 保存
  规范化后的**全量原文**；`ontology_class` / `ontology_annotation` 是从原文
  派生的**查询索引**，随时可由 `_reindex()` 重建，不承担真相职责。
  所有写操作（`register_class` / `unregister_class` / `annotate_article` /
  `import_ttl`）统一走「先改原文图 → 写回 `ttl_content` → 由原文重建索引」。
  `export_ttl()` = 基础公理 + 原文，不再用索引补增量。
- 空节点合并用**同构感知差集**，不用「规范化标签相等」的集合并集（评审 R2-03）。
- 命名空间: 默认 WIKI_NS (可通过构造参数覆盖)
- 线程安全: 内部加锁 (本体操作非并发安全)

用法:
    # 生产（按租户持久化）
    engine = WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))
    # 离线/单测（内存）
    engine = WikiOwlEngine()
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:  # 仅类型提示，避免运行时循环导入
    from app.services.ontology.ontology_repository import (
        ClassRecord,
        OntologyStoreProtocol,
    )

logger = logging.getLogger(__name__)

try:
    from rdflib import BNode, Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL
    from rdflib.compare import isomorphic
    HAS_RDFLIB = True
except ImportError:  # pragma: no cover - rdflib 已列入依赖
    HAS_RDFLIB = False
    logger.warning("rdflib 未安装, OWL 功能不可用。pip install rdflib")


# 默认命名空间
DEFAULT_WIKI_NS = "http://minworkbuddy.local/ontology/wiki#"
DEFAULT_ONTOLOGY_NS = "http://minworkbuddy.local/ontology/"

# RDF/RDFS/OWL 标准词汇表前缀。
# `a <X>` 的宾语落在这些前缀下时是**本体元词汇声明**（owl:Restriction、
# owl:TransitiveProperty、rdf:Property …），不是「文章属于某个类」的标注，
# 不应写入 `ontology_annotation`。按前缀判断而不是逐个白名单，避免词汇表
# 扩展时出现漏网之鱼（评审 CR-01 / MI-03）。
_STANDARD_VOCAB_PREFIXES = (
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2001/XMLSchema#",
)


def _is_standard_vocabulary(uri: str) -> bool:
    """`uri` 是否属于 RDF/RDFS/OWL/XSD 标准词汇。"""
    return uri.startswith(_STANDARD_VOCAB_PREFIXES)


def _serialize(graph: "Graph", prefix_source: Optional["Graph"] = None) -> str:
    """序列化为 TTL，复用 `prefix_source`（或图自身）的前缀声明以保持可读。"""
    source = graph if prefix_source is None else prefix_source
    for prefix, namespace in source.namespaces():
        graph.bind(prefix, namespace, replace=True)
    return graph.serialize(format="turtle")


def _has_blank_node(graph: "Graph") -> bool:
    """图中是否含空节点（空节点是跨导入合并的唯一风险来源）。"""
    return any(
        isinstance(term, BNode) for triple in graph for term in triple
    )


def _connected_components(graph: "Graph") -> List["Graph"]:
    """按「共享节点」把图切成连通分量，每个分量返回一个独立图。

    空节点只在自己所在的连通分量里有意义，跨图比较空节点结构必须**整分量**比较：
    只比较「空节点邻域」会把「结构相同但语义不同」的空节点误判为同一个
    （评审 R2-03）。
    """
    parent: Dict[Any, Any] = {}

    def _find(node: Any) -> Any:
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:  # 路径压缩
            parent[node], node = root, parent[node]
        return root

    for subj, _pred, obj in graph:
        parent.setdefault(subj, subj)
        parent.setdefault(obj, obj)
        subj_root, obj_root = _find(subj), _find(obj)
        if subj_root != obj_root:
            parent[obj_root] = subj_root

    buckets: Dict[Any, "Graph"] = {}
    for triple in graph:
        buckets.setdefault(_find(triple[0]), Graph()).add(triple)
    return list(buckets.values())


def _rename_blank_nodes(graph: "Graph") -> "Graph":
    """给分量里的空节点换一套全新标签，保证并入目标图后仍彼此独立。"""
    mapping: Dict[Any, Any] = {}

    def _remap(term: Any) -> Any:
        if isinstance(term, BNode):
            if term not in mapping:
                mapping[term] = BNode()
            return mapping[term]
        return term

    renamed = Graph()
    for subj, pred, obj in graph:
        renamed.add((_remap(subj), pred, _remap(obj)))
    return renamed


def _merge_graphs(stored: "Graph", incoming: "Graph") -> "Graph":
    """把 `incoming` 并入 `stored`，返回合并后的新图。

    合并规则（评审 R2-03）：
    * **不含空节点**的分量：纯集合并集 —— URI/Literal 三元组天然去重，
      重复导入 `added == 0`。
    * **含空节点**的分量：只有当库中已存在**同构**分量时才算重复并跳过；
      否则以**新的空节点标签**整分量并入。`rdflib.compare.isomorphic` 只重映射
      空节点、**不重映射 URIRef**，因此「A 的限制」与「B 的限制」不会被判为同构，
      两次导入里结构相同的空节点不会被并成一个。
    """
    merged = Graph()
    for triple in stored:
        merged.add(triple)

    stored_components = [c for c in _connected_components(stored) if _has_blank_node(c)]
    for component in _connected_components(incoming):
        if not _has_blank_node(component):
            for triple in component:
                merged.add(triple)
            continue
        if any(isomorphic(existing, component) for existing in stored_components):
            continue  # 结构已存在（URIRef 一一对应），不重复写入
        for triple in _rename_blank_nodes(component):
            merged.add(triple)
    return merged


@dataclass
class OwlClass:
    """OWL 类描述。"""
    uri: str
    label: str = ""
    comment: str = ""
    parent_uris: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "label": self.label,
            "comment": self.comment,
            "parent_uris": self.parent_uris,
        }


@dataclass
class HierarchyNode:
    """层级树节点。"""
    uri: str
    label: str
    children: List["HierarchyNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "label": self.label,
            "children": [c.to_dict() for c in self.children],
        }


class WikiOwlEngine:
    """基于 rdflib（解析/序列化）+ 可插拔存储后端的 OWL 本体引擎。

    用法:
        engine = WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))
        engine.register_class("http://example.org/Person", label="人物", parent_uris=[...])
        hierarchy = engine.get_hierarchy()
        ttl_str = engine.export_ttl()
    """

    def __init__(
        self,
        store: Optional["OntologyStoreProtocol"] = None,
        *,
        wiki_ns: str = DEFAULT_WIKI_NS,
        ontology_ns: str = DEFAULT_ONTOLOGY_NS,
    ) -> None:
        if not HAS_RDFLIB:
            raise RuntimeError("rdflib 未安装, 请执行: pip install rdflib")
        self._lock = threading.RLock()
        self._wiki_ns = Namespace(wiki_ns)
        self._ontology_ns = Namespace(ontology_ns)

        if store is None:
            from app.services.ontology.ontology_repository import InMemoryOntologyStore

            logger.warning(
                "WikiOwlEngine 未传入持久化 store，使用内存后端（重启即丢，仅用于离线/测试）"
            )
            store = InMemoryOntologyStore()
        self._store = store
        logger.info("WikiOwlEngine 初始化完成 (ns=%s, store=%s)", wiki_ns, type(store).__name__)

    @classmethod
    def from_store(
        cls,
        store: "OntologyStoreProtocol",
        *,
        wiki_ns: str = DEFAULT_WIKI_NS,
        ontology_ns: str = DEFAULT_ONTOLOGY_NS,
    ) -> "WikiOwlEngine":
        """用指定存储后端构造引擎（生产入口：按租户的 `OntologyRepository`）。"""
        return cls(store=store, wiki_ns=wiki_ns, ontology_ns=ontology_ns)

    # ---- 类注册 ----
    def register_class(
        self,
        uri: str,
        *,
        label: str = "",
        comment: str = "",
        parent_uris: Optional[List[str]] = None,
    ) -> OwlClass:
        """注册一个 OWL Class。

        语义与改造前保持一致：
        - `label` / `comment` 为空时不覆盖已有值（旧实现 `if label: graph.set(...)`）；
        - `parent_uris` 与已有父类取**并集**（旧实现是 `graph.add`，不是替换）；
        - 返回值中的 `parent_uris` 为本次入参（同改造前）。

        写入落在 `ttl_content`（唯一真相源），索引随后由原文重建（评审 R2-01）。
        """
        with self._lock:
            from app.services.ontology.ontology_repository import validate_uri

            parents = list(parent_uris or [])
            validate_uri(uri)
            for parent in parents:
                validate_uri(parent)

            graph = self._content_graph()
            subj = URIRef(uri)
            graph.add((subj, RDF.type, OWL.Class))
            if label:
                graph.set((subj, RDFS.label, Literal(label, lang="zh")))
            if comment:
                graph.set((subj, RDFS.comment, Literal(comment, lang="zh")))
            existing_parents = set(graph.objects(subj, RDFS.subClassOf))
            for parent in parents:
                parent_ref = URIRef(parent)
                if parent_ref not in existing_parents:
                    graph.add((subj, RDFS.subClassOf, parent_ref))

            self._persist(graph)
            return OwlClass(uri=uri, label=label, comment=comment, parent_uris=parents)

    def unregister_class(self, uri: str) -> bool:
        """移除一个 OWL Class **及其所有引用**。

        与改造前 `rdflib` 实现对齐：旧实现会同时删除
        `<uri> ?p ?o`、`?s ?p <uri>` 与 `<target> a <uri>`，
        因此这里也要清理「其它类把它当父类」和「文章标注了它」两处引用，
        否则类删除后 `get_articles_by_class(uri)` 仍返回悬挂引用（评审 IM-04）。

        原文是唯一真相源，所以**先删原文三元组**（R2-02：只删索引行会让类
        继续出现在 `export_ttl()` / `stats()` 里），再删索引行并重建索引。
        """
        with self._lock:
            graph = self._content_graph()
            subj = URIRef(uri)
            outgoing = list(graph.triples((subj, None, None)))
            if not outgoing:
                return False
            for triple in outgoing:
                graph.remove(triple)
            for triple in list(graph.triples((None, None, subj))):
                graph.remove(triple)
            # 索引行 + 父类引用 + 标注引用，三步在仓储内部**同一事务**内完成
            self._store.unregister(uri)
            self._persist(graph)
            return True

    # ---- 类查询 ----
    def get_class(self, uri: str) -> Optional[OwlClass]:
        """获取单个 OWL Class 信息，不存在返回 None。"""
        with self._lock:
            record = self._store.get_class(uri)
            if record is None:
                return None
            return self._to_owl_class(record)

    def list_classes(self) -> List[OwlClass]:
        """列出所有已注册 OWL Class（按 URI 排序）。"""
        with self._lock:
            return [self._to_owl_class(r) for r in self._store.list_classes()]

    def get_ancestors(self, uri: str) -> List[str]:
        """获取指定类的所有祖先 URI (递归向上，带循环保护)。"""
        with self._lock:
            parent_map = self._parent_map()
            visited: Set[str] = set()
            stack = [uri]
            while stack:
                current = stack.pop()
                for parent in parent_map.get(current, []):
                    if parent not in visited:
                        visited.add(parent)
                        stack.append(parent)
            return sorted(visited)

    def get_descendants(self, uri: str) -> List[str]:
        """获取指定类的所有后代 URI (递归向下，带循环保护)。"""
        with self._lock:
            children_map = self._children_map()
            visited: Set[str] = set()
            stack = [uri]
            while stack:
                current = stack.pop()
                for child in children_map.get(current, []):
                    if child not in visited:
                        visited.add(child)
                        stack.append(child)
            return sorted(visited)

    def get_hierarchy(self) -> List[HierarchyNode]:
        """构建完整类层级树 (返回根节点列表)。

        循环父类防护：任一类若在自身祖先链上重复出现，则在该处截断，
        不会无限递归（改造前的实现在 `root -> A -> B -> A` 这类结构下会 RecursionError）。
        """
        with self._lock:
            records = self._store.list_classes()
            all_classes: Set[str] = set()
            has_parent: Set[str] = set()
            parent_map: Dict[str, List[str]] = {}
            labels: Dict[str, str] = {}

            for record in records:
                uri = record.uri
                labels[uri] = record.label
                all_classes.add(uri)
                if record.parent_uris:
                    has_parent.add(uri)
                    parent_map[uri] = list(record.parent_uris)
                    for p in record.parent_uris:
                        all_classes.add(p)  # 确保父类也在集合中

            children_map: Dict[str, List[str]] = {}
            for uri, parents in parent_map.items():
                for p in parents:
                    children_map.setdefault(p, []).append(uri)

            roots = sorted(u for u in all_classes if u not in has_parent)

            def _build_node(uri: str, path: frozenset) -> HierarchyNode:
                label = labels.get(uri) or self._default_label(uri)
                if uri in path:  # 循环保护：祖先链上已出现过
                    logger.warning("检测到循环父类继承, 在 %s 处截断", uri)
                    return HierarchyNode(uri=uri, label=label, children=[])
                next_path = path | {uri}
                return HierarchyNode(
                    uri=uri,
                    label=label,
                    children=[_build_node(c, next_path) for c in sorted(children_map.get(uri, []))],
                )

            return [_build_node(r, frozenset()) for r in roots]

    # ---- 文章标注 ----
    def annotate_article(self, article_uri: str, class_uris: List[str]) -> None:
        """为文章标注 OWL 类 (rdf:type)。

        与改造前一致：只**追加** `<article> a <Class>`（旧实现是 `graph.add`）。
        标注同样写进 `ttl_content`（唯一真相源），索引随后由原文重建。
        """
        with self._lock:
            from app.services.ontology.ontology_repository import (
                validate_target_id,
                validate_uri,
            )

            validate_target_id(article_uri)
            for class_uri in class_uris or []:
                validate_uri(class_uri)

            graph = self._content_graph()
            subj = URIRef(article_uri)
            for class_uri in class_uris or []:
                graph.add((subj, RDF.type, URIRef(class_uri)))

            self._persist(graph)
            logger.info("annotated article %s with %d classes", article_uri, len(class_uris or []))

    def get_article_classes(self, article_uri: str) -> List[str]:
        """获取文章关联的所有 OWL 类 URI。"""
        with self._lock:
            record = self._store.get_annotation(article_uri)
            return list(record.class_uris) if record else []

    def get_articles_by_class(self, class_uri: str) -> List[str]:
        """获取属于指定 OWL 类的所有文章 URI。"""
        with self._lock:
            return [
                record.target_id
                for record in self._store.list_annotations()
                if class_uri in record.class_uris
            ]

    # ---- TTL 导入/导出 ----
    def import_ttl(self, ttl_content: str) -> int:
        """从 TTL 字符串导入本体。返回新增三元组数。

        存储策略（评审 CR-01 B 案 + R2-03）：
        - `ontology.ttl_content` 存**全量原文**（唯一真相源），
          `ontology_class` / `ontology_annotation` 只是由原文派生的查询索引；
        - 合并用**同构感知差集**（`_merge_graphs`）：不含空节点的分量走集合并集，
          含空节点的分量按连通分量做 `isomorphic` 判定后再决定跳过或整分量并入，
          因此既保留「重复导入 `added == 0`」的幂等性，也不会把两次导入里
          「结构相同但语义不同」的空节点并成一个；
        - 索引只接受 `URIRef`，空节点不会退化成假 URI 落库。
        """
        with self._lock:
            parsed = Graph()
            try:
                parsed.parse(data=ttl_content, format="turtle")
            except Exception as exc:
                raise ValueError(f"TTL 解析失败: {exc}") from exc

            # 导出的 `onto:wiki a owl:Ontology` 公理由引擎自动附加，不作为内容存储，
            # 否则「导出 → 再导入」会被算成 1 条新增，破坏幂等。
            parsed.remove((self._ontology_ns["wiki"], RDF.type, OWL.Ontology))

            stored = self._content_graph()
            merged = _merge_graphs(stored, parsed)
            added = len(merged) - len(stored)

            self._persist(merged, prefix_source=parsed)
            logger.info("imported TTL: %d new triples (total=%d)", added, len(merged))
            return added

    def export_ttl(self) -> str:
        """导出本体为 TTL 字符串（基础公理 + 全量原文）。"""
        with self._lock:
            return self._build_graph().serialize(format="turtle")

    # ---- 统计 ----
    def stats(self) -> Dict[str, int]:
        """返回本体统计信息。"""
        with self._lock:
            graph = self._build_graph()
            return {
                "total_triples": len(graph),
                "class_count": len(self._store.list_classes()),
            }

    # ---- 内部 ----
    def _content_graph(self) -> "Graph":
        """读取持久化的全量 TTL 原文（`ttl_content`）—— 本体的唯一真相源。"""
        graph = Graph()
        graph.bind("wiki", self._wiki_ns)
        graph.bind("onto", self._ontology_ns)
        raw = (self._store.get_ttl_content() or "").strip()
        if raw:
            try:
                graph.parse(data=raw, format="turtle")
            except Exception:  # pragma: no cover - 存量脏数据兜底
                logger.exception("本体存量 TTL 内容解析失败, 导出时已忽略")
        return graph

    def _persist(self, graph: "Graph", *, prefix_source: Optional["Graph"] = None) -> None:
        """把图写回 `ttl_content`，再按图重建索引。

        顺序固定为「**先写原文、再建索引**」：批量导入（`/import-ttl`）的字段长度
        校验发生在 `_reindex()` 阶段，先写原文才能让 `auto_commit=False` 的事务边界
        真正覆盖到 `ttl_content` —— 这正是 `test_failed_import_leaves_no_partial_data`
        守护的契约（评审 IM-05 / R2-06）。
        """
        self._store.set_ttl_content(_serialize(graph, prefix_source))
        self._reindex(graph)

    def _build_graph(self) -> "Graph":
        """重建 rdflib 图 = 基础公理 + 全量原文。

        `ttl_content` 是**唯一真相源**，导出时不再用索引补增量。旧实现的
        「原文已声明该类 → 整类跳过」会让 API 注册的 label / 父类在 TTL 导入后
        静默丢失（评审 R2-01），并让已注销的类继续出现在导出与统计里（R2-02）。
        """
        graph = Graph()
        graph.bind("wiki", self._wiki_ns)
        graph.bind("onto", self._ontology_ns)
        # 注册基础 OWL 公理（与改造前一致）
        graph.add((self._ontology_ns["wiki"], RDF.type, OWL.Ontology))

        for triple in self._content_graph():
            graph.add(triple)
        return graph

    def _reindex(self, graph: "Graph") -> None:
        """把图里的类与文章标注**按原文重建**进索引表。

        索引是纯派生结构，因此这里用**覆盖语义**（`merge_parents=False` /
        `merge=False`）：索引必须逐字镜像原文，不能保留上一版的残留值。

        索引只接受 `URIRef`：空节点（`owl:Restriction` 等）没有稳定 URI，
        落库会变成形如 `n38afbef…` 的假父类/假标注（评审 CR-01）。
        """
        class_uris: Set[str] = set()
        for subj in graph.subjects(RDF.type, OWL.Class):
            if not isinstance(subj, URIRef):
                continue  # 空节点声明的类无法用 URI 索引
            class_uris.add(str(subj))

        for uri in sorted(class_uris):
            subj = URIRef(uri)
            label = graph.value(subj, RDFS.label)
            comment = graph.value(subj, RDFS.comment)
            parents = [
                str(o) for o in graph.objects(subj, RDFS.subClassOf) if isinstance(o, URIRef)
            ]
            self._store.upsert_class(
                uri,
                label=str(label) if label is not None else "",
                comment=str(comment) if comment is not None else "",
                parent_uris=parents,
                merge_parents=False,
            )

        # 文章标注：<target> a <Class>（排除类自身声明与 RDF/RDFS/OWL 元词汇）
        annotations: Dict[str, Set[str]] = {}
        for subj, obj in graph.subject_objects(RDF.type):
            if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
                continue
            if str(subj) in class_uris or _is_standard_vocabulary(str(obj)):
                continue
            annotations.setdefault(str(subj), set()).add(str(obj))

        for target_id, uris in sorted(annotations.items()):
            self._store.upsert_annotation(target_id, sorted(uris), merge=False)

    def _parent_map(self) -> Dict[str, List[str]]:
        return {r.uri: list(r.parent_uris) for r in self._store.list_classes()}

    def _children_map(self) -> Dict[str, List[str]]:
        children: Dict[str, List[str]] = {}
        for uri, parents in self._parent_map().items():
            for p in parents:
                children.setdefault(p, []).append(uri)
        return children

    @staticmethod
    def _default_label(uri: str) -> str:
        return uri.split("#")[-1] or uri

    @staticmethod
    def _to_owl_class(record: "ClassRecord") -> OwlClass:
        return OwlClass(
            uri=record.uri,
            label=record.label,
            comment=record.comment,
            parent_uris=list(record.parent_uris),
        )
