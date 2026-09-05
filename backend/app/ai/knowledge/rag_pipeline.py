"""KB RAG Pipeline - Ingest / Retrieve / Generate 三段式。

复用:
- VectorStore 抽象层 (BaseVectorStore): InMemoryVectorStore / PGVectorStore
- 项目现有 EmbeddingService (默认 Embedder): 可注入, 默认 hash 占位
- 通用 knowledge_document + 可选 Wiki 文章 collection

设计:
- 不引入 LangChain / LlamaIndex, 单文件 < 300 行, 易于测试
- LLM 由调用方注入 (兼容 AgentScope 2.0 ReActAgent; 测试用 _FakeLLM)
- 文本切片支持中英文, 默认按字符
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from app.ai.knowledge.vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


# ===================================================================
# 文本切片
# ===================================================================
class TextSplitter(ABC):
    @abstractmethod
    def split(self, text: str) -> List[str]: ...


class SimpleTextSplitter(TextSplitter):
    """按字符定长切分, 带 overlap。中文友好 (无 tokenize)。"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> List[str]:
        """按字符定长切分 (含 overlap)。末尾不足一个完整 chunk 的部分丢弃。

        例: chunk_size=10 overlap=2, text=20 chars → 产 2 个 [0:10] [8:18]
            chunk_size=10 overlap=2, text=50 chars → 产 5 个 [0:10][8:18]...[32:42]
        """
        if not text or not text.strip():
            return []
        n = len(text)
        if n <= self.chunk_size:
            return [text]
        chunks: List[str] = []
        step = self.chunk_size - self.chunk_overlap
        i = 0
        while i + self.chunk_size < n:
            piece = text[i:i + self.chunk_size]
            chunks.append(piece)
            i += step
        return chunks


# ===================================================================
# 数据结构
# ===================================================================
@dataclass
class RAGConfig:
    top_k: int = 5
    min_score: float = 0.0
    max_context_chars: int = 4000
    splitter_chunk_size: int = 500
    splitter_chunk_overlap: int = 50
    system_prompt: str = (
        "你是智能知识库助手。请仅基于下面的 sources 回答用户问题，"
        "在回答中用 [1] [2] 等标注引用。无法从 sources 得出结论时直接说明。"
    )


@dataclass
class IngestRecord:
    collection: str
    doc_id: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Citation:
    id: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class RAGResult:
    answer: str
    citations: List[Citation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
        }


# ===================================================================
# 协议 (类型提示)
# ===================================================================
class Embedder(Protocol):
    def __call__(self, text: str) -> List[float]: ...  # noqa: E704


class LLM(Protocol):
    async def generate(self, prompt: str, *, system: str = "", **kwargs) -> str: ...  # noqa: E704


def _default_embedder(text: str) -> List[float]:
    """稳定 hash 占位 - 8 维。"""
    h = abs(hash(text))
    return [(h >> (i * 4) & 0xFF) / 255.0 for i in range(8)]


def _default_llm():
    raise RuntimeError("RAGPipeline.llm not configured; pass llm=... at construction")


# ===================================================================
# Pipeline
# ===================================================================
class RAGPipeline:
    """KB RAG Pipeline - 三段式。

    Ingest:  文档 -> 切片 -> 向量化 -> upsert
    Retrieve: query -> 向量化 -> top_k 检索
    Generate: sources + question -> prompt -> LLM.answer
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedder: Optional[Embedder] = None,
        llm: Optional[LLM] = None,
        splitter: Optional[TextSplitter] = None,
        config: Optional[RAGConfig] = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder or _default_embedder
        self.llm = llm
        self.config = config or RAGConfig()
        self.splitter = splitter or SimpleTextSplitter(
            chunk_size=self.config.splitter_chunk_size,
            chunk_overlap=self.config.splitter_chunk_overlap,
        )

    # ---- Ingest ----
    async def ingest(self, record: IngestRecord) -> int:
        """文档切片 -> 向量化 -> upsert。返回入向量库条数。"""
        chunks = self.splitter.split(record.content)
        if not chunks:
            return 0
        n = 0
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{record.doc_id}#{idx}"
            vec = self.embedder(chunk)
            meta = {
                "title": record.title,
                "doc_id": record.doc_id,
                "chunk_index": idx,
                "snippet": chunk[:200],
                **record.metadata,
            }
            await self.vector_store.upsert(
                collection=record.collection,
                id=chunk_id,
                vector=vec,
                metadata=meta,
            )
            n += 1
        logger.info("ingested doc=%s collection=%s chunks=%d", record.doc_id, record.collection, n)
        return n

    # ---- Retrieve ----
    async def retrieve(
        self,
        collection: str,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        k = top_k or self.config.top_k
        vec = self.embedder(query)
        results = await self.vector_store.search(
            collection=collection, query_vector=vec, top_k=k, filter=filter,
        )
        # 阈值过滤
        if self.config.min_score > 0:
            results = [r for r in results if r.get("score", 0) >= self.config.min_score]
        return results

    # ---- Generate ----
    async def query(
        self,
        collection: str,
        question: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> RAGResult:
        sources = await self.retrieve(collection, question, top_k=top_k, filter=filter)
        citations = self._sources_to_citations(sources)
        if not citations:
            return RAGResult(answer="", citations=[])
        answer = await self._generate(question, citations)
        return RAGResult(answer=answer, citations=citations)

    async def query_multi(
        self,
        collections: List[str],
        question: str,
        top_k_per_collection: Optional[int] = None,
    ) -> RAGResult:
        """跨多个 collection 检索, 合并按 score 排序。"""
        k = top_k_per_collection or self.config.top_k
        all_sources: List[Dict[str, Any]] = []
        for c in collections:
            sources = await self.retrieve(c, question, top_k=k)
            all_sources.extend(sources)
        # 跨 collection 按 score 降序
        all_sources.sort(key=lambda r: r.get("score", 0), reverse=True)
        citations = self._sources_to_citations(all_sources[: self.config.top_k])
        if not citations:
            return RAGResult(answer="", citations=[])
        answer = await self._generate(question, citations)
        return RAGResult(answer=answer, citations=citations)

    # ---- 内部 ----
    def _sources_to_citations(self, sources: List[Dict[str, Any]]) -> List[Citation]:
        return [
            Citation(
                id=s["id"],
                title=s.get("metadata", {}).get("title", ""),
                snippet=s.get("metadata", {}).get("snippet", ""),
                score=s.get("score", 0),
                metadata=s.get("metadata", {}),
            )
            for s in sources
        ]

    async def _generate(self, question: str, citations: List[Citation]) -> str:
        if self.llm is None:
            raise RuntimeError("RAGPipeline.llm is None; pass llm=... at construction")
        # 拼 prompt
        ctx_lines: List[str] = []
        char_count = 0
        for i, c in enumerate(citations, start=1):
            snippet = (c.snippet or c.title or "").strip()
            line = f"[{i}] {c.title}: {snippet}"
            if char_count + len(line) > self.config.max_context_chars:
                break
            ctx_lines.append(line)
            char_count += len(line)
        ctx = "\n".join(ctx_lines) if ctx_lines else "(no sources)"
        prompt = (
            f"Question: {question}\n\n"
            f"Sources:\n{ctx}\n\n"
            f"Answer:"
        )
        return await self.llm.generate(prompt, system=self.config.system_prompt)


# ===================================================================
# 工厂 - 与项目现有 EmbeddingService / 业务 KB Service 集成
# ===================================================================
def build_default_pg_rag_pipeline(db, *, llm=None, config: Optional[RAGConfig] = None) -> RAGPipeline:
    """构造默认 PG RAG Pipeline。

    - VectorStore: PGVectorStore (通用知识库 collection)
    - Embedder: project EmbeddingService (gpustack / dashscope)
    """
    from app.ai.knowledge.pg_vector_store import PGVectorStore, VectorCollection
    from app.services.embedding_service import EmbeddingService

    store = PGVectorStore(db=db)
    # 通用知识文档 collection
    store.register_collection(VectorCollection(
        collection="knowledge_base",
        model_id="app.models.kms_document.KnowledgeDocument",
        vector_col="content_vector",
        text_col="content",
        pk_col="id",
        metadata_cols={"title": "title", "doc_type": "doc_type"},
    ))

    # Embedder: 复用项目 EmbeddingService
    embedding_svc = EmbeddingService(db=db)

    def embed(text: str) -> List[float]:
        return embedding_svc.embed_text_sync(text)

    return RAGPipeline(vector_store=store, embedder=embed, llm=llm, config=config)