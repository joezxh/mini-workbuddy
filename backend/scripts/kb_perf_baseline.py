"""知识库端到端 + 检索性能基线脚本（P1 Task 11）。

用法（在 backend/ 目录下）：
    .venv/Scripts/python.exe scripts/kb_perf_baseline.py                 # e2e + perf(2万切片)
    .venv/Scripts/python.exe scripts/kb_perf_baseline.py --segments 100000  # 10万切片基线
    .venv/Scripts/python.exe scripts/kb_perf_baseline.py --mode e2e      # 仅端到端
    .venv/Scripts/python.exe scripts/kb_perf_baseline.py --mode perf     # 仅性能

数据落在 ``minworkbuddy_test`` 库的独立 schema（kb_bench_<ts>），结束即 DROP；
embedding 用确定性伪随机单位向量（聚类簇结构），不依赖 GPUStack 网络。
"""
from __future__ import annotations

import argparse
import random
import statistics
import os
import sys
import time
import uuid
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.models.kb.kb_collection import KbCollection  # noqa: E402
from app.models.kb.kb_ref import KbRef  # noqa: E402
from app.models.kb.kb_segment import KbSegment  # noqa: E402
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput  # noqa: E402

TENANT_BENCH = 999001
NUM_CLUSTERS = 10
NUM_KEYWORDS = 50


def _bench_db_url() -> str:
    password = quote_plus(settings.DB_PASSWORD)
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/minworkbuddy_test"
    )


def make_vector(rng: random.Random, dim: int, cluster: int) -> list:
    """以簇中心 + 高斯噪声生成归一化向量（确定性检索语义）。"""
    center = [0.0] * dim
    center[cluster % dim] = 1.0
    vec = [center[i] + rng.gauss(0.0, 0.05) for i in range(dim)]
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]


def fake_embed_fn(dim: int):
    """确定性伪 embed_fn：按字符/二元组哈希落桶，共享字词越多越相似。

    比「纯随机向量」更贴近真实语义检索（同字必命中），且不依赖 GPUStack 网络。
    """

    def _fn(texts):
        out = []
        for t in texts:
            vec = [0.0] * dim
            chars = [c for c in t if not c.isspace()]
            for c in chars:
                vec[ord(c) % dim] += 1.0
            for a, b in zip(chars, chars[1:]):
                vec[(ord(a) * 131 + ord(b)) % dim] += 0.5
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out

    return _fn


class Bench:
    """一次性基准环境：独立 schema + kb 三表 + HNSW/trgm 索引（镜像迁移 006）。"""

    def __init__(self, create_indexes_now: bool = True) -> None:
        self.schema = f"kb_bench_{uuid.uuid4().hex[:8]}"
        self.engine = create_engine(_bench_db_url())
        event.listens_for(self.engine, "connect")(self._bind_schema)
        with self.engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        Base.metadata.create_all(
            self.engine,
            tables=[KbCollection.__table__, KbSegment.__table__, KbRef.__table__],
        )
        if create_indexes_now:
            self.create_indexes()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_indexes(self) -> None:
        """建 HNSW + trigram 索引（perf 模式在数据灌完后调用，构建更快）。"""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX ix_kb_segment_embedding ON kb_segment "
                    "USING hnsw (embedding vector_cosine_ops) "
                    "WITH (m = 16, ef_construction = 64)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_kb_segment_content_trgm ON kb_segment "
                    "USING gin (content gin_trgm_ops)"
                )
            )

    def _bind_schema(self, dbapi_conn, _record):  # noqa: ANN001, ANN202
        with dbapi_conn.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{self.schema}", public')

    def close(self) -> None:
        self.engine.dispose()
        admin = create_engine(_bench_db_url())
        try:
            with admin.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '30s'"))
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE'))
        finally:
            admin.dispose()


def _p50_p95(lat_ms: list) -> dict:
    lat = sorted(lat_ms)
    return {
        "p50": round(statistics.median(lat), 2),
        "p95": round(lat[max(0, int(len(lat) * 0.95) - 1)], 2),
        "mean": round(statistics.mean(lat), 2),
    }


def run_perf(segments: int, doc_size: int, queries: int, dim: int) -> dict:
    bench = Bench(create_indexes_now=False)
    try:
        db = bench.Session()
        store = PGVectorStore(db, TENANT_BENCH)
        collection = "kb_bench"
        store.create_collection(collection, dim)

        rng = random.Random(20260911)
        n_docs = (segments + doc_size - 1) // doc_size
        t0 = time.perf_counter()
        for doc in range(n_docs):
            rows = []
            for i in range(doc_size):
                idx = doc * doc_size + i
                if idx >= segments:
                    break
                cluster = idx % NUM_CLUSTERS
                rows.append(
                    SegmentInput(
                        chunk_index=i,
                        content=(
                            f"文档{doc}第{i}段：关于关键词kw{idx % NUM_KEYWORDS}的"
                            f"业务说明与口径定义，所属主题簇 cluster{cluster}。"
                        ),
                        embedding=make_vector(rng, dim, cluster),
                        metadata={"doc": doc, "cluster": cluster},
                    )
                )
            store.insert(collection, f"bench-doc-{doc}", rows)
            db.commit()
        ingest_s = time.perf_counter() - t0

        # 数据灌完后建索引（批量加载的标准做法，构建远快于边插边维护）
        t_idx = time.perf_counter()
        bench.create_indexes()
        index_s = time.perf_counter() - t_idx

        vec_lat, hy_lat, vec_hits, hy_hits = [], [], [], []
        for q in range(queries):
            cluster = q % NUM_CLUSTERS
            qvec = make_vector(random.Random(7_000_000 + q), dim, cluster)
            qtext = f"关键词kw{q % NUM_KEYWORDS}的口径定义"

            t = time.perf_counter()
            res = store.search(collection, qvec, top_k=5)
            vec_lat.append((time.perf_counter() - t) * 1000)
            vec_hits.append(len(res))

            t = time.perf_counter()
            res = store.hybrid_search(collection, qvec, qtext, top_k=5)
            hy_lat.append((time.perf_counter() - t) * 1000)
            hy_hits.append(len(res))
            db.commit()

        stats = {
            "segments": segments,
            "dim": dim,
            "ingest_seconds": round(ingest_s, 2),
            "ingest_rps": round(segments / max(ingest_s, 1e-6)),
            "index_seconds": round(index_s, 2),
            "vector_ms": _p50_p95(vec_lat),
            "hybrid_ms": _p50_p95(hy_lat),
            "vector_avg_hits": round(statistics.mean(vec_hits), 2),
            "hybrid_avg_hits": round(statistics.mean(hy_hits), 2),
        }
        db.close()
        return stats
    finally:
        bench.close()


def run_e2e() -> None:
    """建 KB → 入库（伪向量补齐）→ 纯向量/混合检索命中断言 → 计数回写。"""
    from app.services.kb.kb_ref_service import KbRefService
    from app.services.kb.ingest_service import KbIngestService
    from app.services.kb.retrieval_service import KbRetrievalService

    dim = 768
    bench = Bench()
    db = bench.Session()
    try:
        ref_svc = KbRefService(db, TENANT_BENCH)
        ref = ref_svc.create_kb_ref("基准测试库", "P1 Task 11 e2e", creator_id=0)
        db.commit()
        print(f"[e2e] 1/4 建 KB：kb_id={ref.kb_id} as_user_id={ref.as_user_id}")

        collection = "kb_e2e"
        store = PGVectorStore(db, TENANT_BENCH)
        store.create_collection(collection, dim)
        ingest = KbIngestService(store, fake_embed_fn(dim))
        n = ingest.ingest_document(
            collection,
            "policy-doc",
            [
                SegmentInput(chunk_index=0, content="逾期贷款处置流程规定：M1 客户 7 日内电催。"),
                SegmentInput(chunk_index=1, content="订单金额字段口径：含税总价，单位人民币元。"),
            ],
        )
        db.commit()
        print(f"[e2e] 2/4 入库：{n} 个切片（含向量补齐链路）")

        retriever = KbRetrievalService(store, fake_embed_fn(dim))
        hits = retriever.search_by_text(collection, "逾期贷款催收流程", top_k=2)
        assert hits and "逾期" in (hits[0].content or ""), "向量检索未命中"
        print(f"[e2e] 3/4 向量检索命中：score={hits[0].score:.4f}")

        hy = retriever.hybrid_search_by_text(collection, "订单金额字段口径", top_k=2)
        assert hy and "订单金额" in (hy[0].content or ""), "混合检索未命中"
        print(f"[e2e] 4/4 混合检索命中：rrf={hy[0].score:.4f}")

        assert ref_svc.update_counts(ref.kb_id, 1, n) is not None
        db.commit()
        print("[e2e] 端到端链路 OK（建 KB → 入库 → 检索命中 → 计数回写）")
    finally:
        db.close()
        bench.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="KB e2e + 性能基线（P1 Task 11）")
    parser.add_argument("--mode", choices=["all", "e2e", "perf"], default="all")
    parser.add_argument("--segments", type=int, default=20000)
    parser.add_argument("--doc-size", type=int, default=100)
    parser.add_argument("--queries", type=int, default=50)
    parser.add_argument("--dim", type=int, default=768)
    args = parser.parse_args()

    if args.mode in ("all", "e2e"):
        run_e2e()
    if args.mode in ("all", "perf"):
        stats = run_perf(args.segments, args.doc_size, args.queries, args.dim)
        print("\n=== 性能基线（PostgreSQL + pgvector HNSW） ===")
        print(f"切片数: {stats['segments']}  维度: {stats['dim']}")
        print(f"入库: {stats['ingest_seconds']}s（{stats['ingest_rps']} rows/s），索引构建 {stats['index_seconds']}s")
        v = stats["vector_ms"]
        h = stats["hybrid_ms"]
        print(f"纯向量检索 ms: P50={v['p50']} P95={v['p95']} mean={v['mean']}")
        print(f"混合检索   ms: P50={h['p50']} P95={h['p95']} mean={h['mean']}")
        print(f"平均命中数: 向量={stats['vector_avg_hits']} 混合={stats['hybrid_avg_hits']}")


if __name__ == "__main__":
    main()
