"""WikiOwlEngine - 基于 rdflib 的 OWL 本体引擎。

功能:
- 注册 OWL Class (含 label / comment / parent)
- 查询类层级 (hierarchy / ancestors / descendants)
- TTL 导入 / 导出
- 文章 OWL 类标注 (article ↔ class 关联)

设计:
- 使用 rdflib.Graph 做内存本体存储
- 命名空间: 默认 WIKI_NS (可通过构造参数覆盖)
- 线程安全: 内部加锁 (本体操作非并发安全)
"""
from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
    from rdflib.plugins.parsers.notation3 import BadSyntax
    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False
    logger.warning("rdflib 未安装, OWL 功能不可用。pip install rdflib")


# 默认命名空间
DEFAULT_WIKI_NS = "http://minworkbuddy.local/ontology/wiki#"
DEFAULT_ONTOLOGY_NS = "http://minworkbuddy.local/ontology/"


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
    """基于 rdflib 的 OWL 本体引擎。

    用法:
        engine = WikiOwlEngine()
        engine.register_class("http://example.org/Person", label="人物", parent_uris=[...])
        hierarchy = engine.get_hierarchy()
        ttl_str = engine.export_ttl()
    """

    def __init__(
        self,
        wiki_ns: str = DEFAULT_WIKI_NS,
        ontology_ns: str = DEFAULT_ONTOLOGY_NS,
    ) -> None:
        if not HAS_RDFLIB:
            raise RuntimeError("rdflib 未安装, 请执行: pip install rdflib")
        self._lock = threading.RLock()
        self._graph = Graph()
        self._wiki_ns = Namespace(wiki_ns)
        self._ontology_ns = Namespace(ontology_ns)
        self._graph.bind("wiki", self._wiki_ns)
        self._graph.bind("onto", self._ontology_ns)
        # 注册基础 OWL 公理
        self._graph.add((self._ontology_ns["wiki"], RDF.type, OWL.Ontology))
        logger.info("WikiOwlEngine 初始化完成 (ns=%s)", wiki_ns)

    # ---- 类注册 ----
    def register_class(
        self,
        uri: str,
        *,
        label: str = "",
        comment: str = "",
        parent_uris: Optional[List[str]] = None,
    ) -> OwlClass:
        """注册一个 OWL Class。"""
        with self._lock:
            subj = URIRef(uri)
            self._graph.add((subj, RDF.type, OWL.Class))
            if label:
                self._graph.set((subj, RDFS.label, Literal(label, lang="zh")))
            if comment:
                self._graph.set((subj, RDFS.comment, Literal(comment, lang="zh")))
            for parent_uri in (parent_uris or []):
                self._graph.add((subj, RDFS.subClassOf, URIRef(parent_uri)))
            logger.info("registered OWL class: %s (%s)", uri, label)
            return OwlClass(uri=uri, label=label, comment=comment, parent_uris=parent_uris or [])

    def unregister_class(self, uri: str) -> bool:
        """移除一个 OWL Class 及其所有三元组。"""
        with self._lock:
            subj = URIRef(uri)
            triples = list(self._graph.triples((subj, None, None)))
            if not triples:
                return False
            for t in triples:
                self._graph.remove(t)
            # 同时移除作为宾语的关系 (如 subClassOf)
            triples2 = list(self._graph.triples((None, None, subj)))
            for t in triples2:
                self._graph.remove(t)
            return True

    # ---- 类查询 ----
    def get_class(self, uri: str) -> Optional[OwlClass]:
        """获取单个 OWL Class 信息。"""
        with self._lock:
            subj = URIRef(uri)
            if not any(self._graph.triples((subj, RDF.type, OWL.Class))):
                return None
            label = str(self._graph.value(subj, RDFS.label, default=""))
            comment = str(self._graph.value(subj, RDFS.comment, default=""))
            parents = [
                str(o) for o in self._graph.objects(subj, RDFS.subClassOf)
            ]
            return OwlClass(uri=uri, label=label, comment=comment, parent_uris=parents)

    def list_classes(self) -> List[OwlClass]:
        """列出所有已注册 OWL Class。"""
        with self._lock:
            results = []
            for subj in self._graph.subjects(RDF.type, OWL.Class):
                uri = str(subj)
                label = str(self._graph.value(subj, RDFS.label, default=""))
                comment = str(self._graph.value(subj, RDFS.comment, default=""))
                parents = [str(o) for o in self._graph.objects(subj, RDFS.subClassOf)]
                results.append(OwlClass(uri=uri, label=label, comment=comment, parent_uris=parents))
            return results

    def get_ancestors(self, uri: str) -> List[str]:
        """获取指定类的所有祖先 URI (递归向上)。"""
        with self._lock:
            visited: Set[str] = set()
            stack = [uri]
            while stack:
                current = stack.pop()
                for parent in self._graph.objects(URIRef(current), RDFS.subClassOf):
                    parent_str = str(parent)
                    if parent_str not in visited:
                        visited.add(parent_str)
                        stack.append(parent_str)
            return list(visited)

    def get_descendants(self, uri: str) -> List[str]:
        """获取指定类的所有后代 URI (递归向下)。"""
        with self._lock:
            visited: Set[str] = set()
            stack = [uri]
            while stack:
                current = stack.pop()
                for child in self._graph.subjects(RDFS.subClassOf, URIRef(current)):
                    child_str = str(child)
                    if child_str not in visited:
                        visited.add(child_str)
                        stack.append(child_str)
            return list(visited)

    def get_hierarchy(self) -> List[HierarchyNode]:
        """构建完整类层级树 (返回根节点列表)。"""
        with self._lock:
            all_classes = set()
            has_parent: Set[str] = set()
            parent_map: Dict[str, List[str]] = {}

            for subj in self._graph.subjects(RDF.type, OWL.Class):
                uri = str(subj)
                all_classes.add(uri)
                parents = [str(o) for o in self._graph.objects(subj, RDFS.subClassOf)]
                if parents:
                    has_parent.add(uri)
                    parent_map[uri] = parents
                    for p in parents:
                        all_classes.add(p)  # 确保父类也在集合中

            # 构建 children map
            children_map: Dict[str, List[str]] = {}
            for uri, parents in parent_map.items():
                for p in parents:
                    children_map.setdefault(p, []).append(uri)

            # 根节点 = 没有 parent 的类
            roots = [uri for uri in all_classes if uri not in has_parent]

            def _build_node(uri: str) -> HierarchyNode:
                label = str(self._graph.value(URIRef(uri), RDFS.label, default=uri.split("#")[-1] or uri))
                children = children_map.get(uri, [])
                return HierarchyNode(
                    uri=uri,
                    label=label,
                    children=[_build_node(c) for c in sorted(children)],
                )

            return [_build_node(r) for r in sorted(roots)]

    # ---- 文章标注 ----
    def annotate_article(self, article_uri: str, class_uris: List[str]) -> None:
        """为文章标注 OWL 类 (rdf:type)。"""
        with self._lock:
            subj = URIRef(article_uri)
            for cls_uri in class_uris:
                self._graph.add((subj, RDF.type, URIRef(cls_uri)))
            logger.info("annotated article %s with %d classes", article_uri, len(class_uris))

    def get_article_classes(self, article_uri: str) -> List[str]:
        """获取文章关联的所有 OWL 类 URI。"""
        with self._lock:
            return [
                str(o) for o in self._graph.objects(URIRef(article_uri), RDF.type)
                if str(o) not in (str(OWL.Class), str(RDF.type))
            ]

    def get_articles_by_class(self, class_uri: str) -> List[str]:
        """获取属于指定 OWL 类的所有文章 URI。"""
        with self._lock:
            return [
                str(s) for s in self._graph.subjects(RDF.type, URIRef(class_uri))
            ]

    # ---- TTL 导入/导出 ----
    def import_ttl(self, ttl_content: str) -> int:
        """从 TTL 字符串导入本体。返回新增三元组数。"""
        with self._lock:
            before = len(self._graph)
            try:
                self._graph.parse(data=ttl_content, format="turtle")
            except Exception as exc:
                raise ValueError(f"TTL 解析失败: {exc}") from exc
            after = len(self._graph)
            added = after - before
            logger.info("imported TTL: %d new triples (total=%d)", added, after)
            return added

    def export_ttl(self) -> str:
        """导出本体为 TTL 字符串。"""
        with self._lock:
            return self._graph.serialize(format="turtle")

    # ---- 统计 ----
    def stats(self) -> Dict[str, int]:
        """返回本体统计信息。"""
        with self._lock:
            class_count = sum(1 for _ in self._graph.subjects(RDF.type, OWL.Class))
            return {
                "total_triples": len(self._graph),
                "class_count": class_count,
            }
