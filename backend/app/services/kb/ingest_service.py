"""知识库文档摄取：文本切块 → 向量生成 → 写入 PGVectorStore（P1 Task 3）。

把「向量生成 / embedding 接入」接到摄取链路：调用方提供已切好的 ``SegmentInput``
（``content`` 必填），缺失 ``embedding`` 的切片由注入的 ``embed_fn`` 生成。默认
``embed_fn`` 走 GPUStack / DashScope（见 ``app.ai.embedding_client``）。

与 ``PGVectorStore``（纯存储层）解耦——向量生成通过 ``embed_fn`` 注入，便于测试时用
假向量替换真实 GPUStack 调用，也便于后续替换 embedding 后端。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from app.ai.embedding_client import get_embedding_client
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput


# embed_fn：接收一批文本，返回与输入顺序一致的向量列表
EmbedFn = Callable[[List[str]], List[List[float]]]


def build_embed_fn(code: Optional[str] = None) -> EmbedFn:
    """构造默认 ``embed_fn``：复用全局 EmbeddingClient 的同步批量接口。

    :param code: 可选；传 DB 模式 code（``ai_chat_model``），否则用 .env 默认配置。
    """
    client = get_embedding_client(code)

    def _fn(texts: List[str]) -> List[List[float]]:
        return client.embed_batch_sync(texts)

    return _fn


class KbIngestService:
    """文档摄取服务：负责把切片落库并补齐向量。

    向量生成与存储解耦，``embed_fn`` 可注入（测试 / 替换后端）。
    """

    def __init__(self, store: PGVectorStore, embed_fn: EmbedFn):
        self.store = store
        self._embed_fn = embed_fn

    @classmethod
    def from_session(
        cls, db, tenant_id: int, embedding_code: Optional[str] = None
    ) -> "KbIngestService":
        """从 SQLAlchemy 会话 + 租户构造（生产路径，使用默认 embed_fn）。"""
        store = PGVectorStore(db, tenant_id)
        return cls(store, build_embed_fn(embedding_code))

    def ingest_document(
        self, collection: str, document_id: str, segments: List[SegmentInput]
    ) -> int:
        """摄取文档：补齐缺失向量后写入。

        :param segments: 已切好的切片；``content`` 必填，``embedding`` 可留空（自动生成）。
        :return: upsert 的切片数
        """
        # 维度校验：集合已存在时，生成的向量维度必须与集合声明的维度一致
        # （保障后续 768/1024 维度混用验收项在接口层尽早失败）
        coll = self.store.get_collection(collection)
        expected_dim = coll.dimensions if coll is not None else None

        pending = [s for s in segments if s.embedding is None and s.content]
        if pending:
            vectors = self._embed_fn([s.content for s in pending])
            if len(vectors) != len(pending):
                raise ValueError(
                    f"embed_fn 返回向量数 {len(vectors)} 与待生成切片数 {len(pending)} 不一致"
                )
            for seg, vec in zip(pending, vectors):
                if expected_dim is not None and len(vec) != expected_dim:
                    raise ValueError(
                        f"向量维度 {len(vec)} 与集合 {collection!r} 声明维度 {expected_dim} 不一致"
                    )
                seg.embedding = vec

        return self.store.insert(collection, document_id, segments)
