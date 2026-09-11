"""P3 Task 8 · 中文检索质量对比（验收前置基线）。

对比两种检索模式在「同一批外部知识库语料」上的中文召回质量：

- **Mode A · 只读直连词项打分**：本地对拉取的文档做字符/二元组词项 TF 余弦打分
  （对应 spec §8 只读直连的本地加权词项打分，无 embedding）。
- **Mode B · 同步落库向量检索**：把同一批语料摄取进 P1 的 ``PGVectorStore`` 后走
  ``KbRetrievalService.hybrid_search_by_text``（向量 + 中文 trigram 关键词 + RRF 融合）。

为保证可复现、不依赖 GPUStack 网络，embedding 用确定性「字符/二元组哈希」伪向量
（与 ``scripts/kb_perf_baseline.py`` 同款）。该伪向量只编码「字面字符共现」，
**无法度量真正的语义泛化增益**——这一点在结论中显式说明。

用法（backend/ 目录）：
    .venv/Scripts/python.exe scripts/kb_external_retrieval_bench.py
    .venv/Scripts/python.exe scripts/kb_external_retrieval_bench.py --out results.json
    .venv/Scripts/python.exe scripts/kb_external_retrieval_bench.py --topk 5
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.models.kb.kb_collection import KbCollection  # noqa: E402
from app.models.kb.kb_ref import KbRef  # noqa: E402
from app.models.kb.kb_segment import KbSegment  # noqa: E402
from app.services.kb.ingest_service import KbIngestService  # noqa: E402
from app.services.kb.pgvector_store import PGVectorStore, SegmentInput  # noqa: E402
from app.services.kb.retrieval_service import KbRetrievalService  # noqa: E402

DIM = 768
TENANT_BENCH = 999002

PUNCT = set(
    "，。、；：？！（）()[]{}…—“”‘’《》〈〉/\\|.,;:!?\"'<>~`@#$%^&*-_=+ \t\n\r"
)

# --------------------------------------------------------------------------- #
# 合成中文知识库语料（模拟外部平台拉取的文档片段，每篇一个切片）。
# doc_id 即「金标准」文档标识，每个 query 对应一个 gold doc_id。
# --------------------------------------------------------------------------- #
CORPUS: List[Dict[str, str]] = [
    {"doc_id": "d_OverdueLoan", "content":
        "逾期贷款处置流程规定：M1 阶段客户在 7 日内进行电话催收，M2 阶段发送书面催收函并上报风控，M3 阶段移交外包催收机构。"},
    {"doc_id": "d_OrderAmount", "content":
        "订单金额字段口径定义：订单金额为含税总价，单位人民币元，包含商品金额与运费，不含平台补贴与优惠券。"},
    {"doc_id": "d_Refund", "content":
        "退款申请处理流程：用户在订单完成后 7 天内发起退款，客服审核后 3 个工作日内原路退回，退款状态实时同步。"},
    {"doc_id": "d_Invoice", "content":
        "电子发票开具规范：订单完成且确认收货后自动开具增值税电子普通发票，发票抬头以用户账户信息为准。"},
    {"doc_id": "d_Privacy", "content":
        "用户隐私保护要求：手机号、身份证号等敏感字段在日志与下游系统中必须脱敏，仅授权风控场景可解密。"},
    {"doc_id": "d_DataSync", "content":
        "数据同步任务调度：每日凌晨 2 点执行全量同步，增量同步每 15 分钟一次，失败自动重试三次。"},
    {"doc_id": "d_RBAC", "content":
        "权限管理模型：采用 RBAC 角色访问控制，管理员可分配读写权限，普通成员仅可读取所属空间文档。"},
    {"doc_id": "d_Reimburse", "content":
        "员工报销政策：差旅费需在出差结束后 30 天内提交，需附行程单与发票，超标部分需部门负责人审批。"},
    {"doc_id": "d_AccountSec", "content":
        "账号安全策略：登录密码长度不少于 8 位且包含数字与字母，连续 5 次登录失败锁定账号 30 分钟。"},
    {"doc_id": "d_CsSla", "content":
        "客服响应时效标准：在线咨询首响不超过 30 秒，工单类问题 4 小时内首次回复，重大投诉 24 小时内升级。"},
    {"doc_id": "d_Inventory", "content":
        "库存管理规则：仓库实行先进先出（FIFO）原则，临期商品提前 30 天预警，库存低于安全水位自动触发补货。"},
    {"doc_id": "d_Backup", "content":
        "数据库备份策略：核心业务库每日增量备份，每周日全量备份，备份保留 90 天，异地容灾副本延迟不超过 5 分钟。"},
]

# 20 条中文查询，gold 为期望命中的文档。
QUERIES: List[Dict[str, str]] = [
    {"q": "逾期贷款怎么催收", "gold": "d_OverdueLoan"},
    {"q": "M1 阶段电话催收", "gold": "d_OverdueLoan"},
    {"q": "订单金额含税吗", "gold": "d_OrderAmount"},
    {"q": "订单金额字段口径", "gold": "d_OrderAmount"},
    {"q": "退款多久到账", "gold": "d_Refund"},
    {"q": "退款原路退回", "gold": "d_Refund"},
    {"q": "电子发票怎么开", "gold": "d_Invoice"},
    {"q": "发票抬头", "gold": "d_Invoice"},
    {"q": "手机号脱敏", "gold": "d_Privacy"},
    {"q": "敏感字段脱敏", "gold": "d_Privacy"},
    {"q": "数据同步频率", "gold": "d_DataSync"},
    {"q": "增量同步每 15 分钟", "gold": "d_DataSync"},
    {"q": "RBAC 权限", "gold": "d_RBAC"},
    {"q": "普通成员只读", "gold": "d_RBAC"},
    {"q": "差旅报销期限", "gold": "d_Reimburse"},
    {"q": "报销超标审批", "gold": "d_Reimburse"},
    {"q": "登录密码锁定", "gold": "d_AccountSec"},
    {"q": "连续登录失败锁定", "gold": "d_AccountSec"},
    {"q": "库存先进先出", "gold": "d_Inventory"},
    {"q": "数据库备份保留天数", "gold": "d_Backup"},
]


# --------------------------------------------------------------------------- #
# Mode A · 词项打分检索器（无 embedding）
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> List[str]:
    """字符一元 + 相邻二元组（剔除空白与标点），作为中文「词项」。"""
    chars = [c for c in text if c not in PUNCT]
    tokens = list(chars)
    tokens += [f"{a}{b}" for a, b in zip(chars, chars[1:])]
    return tokens


class LexiconRetriever:
    """本地词项 TF 余弦打分（sublinear TF），对应只读直连的本地打分。"""

    def __init__(self) -> None:
        self._docs: Dict[str, Dict[str, float]] = {}
        self._df: Dict[str, int] = {}
        self._n = 0

    def build(self, corpus: List[Dict[str, str]]) -> "LexiconRetriever":
        for d in corpus:
            self.add(d["doc_id"], d["content"])
        return self

    def add(self, doc_id: str, content: str) -> None:
        tf: Dict[str, float] = {}
        for tok in tokenize(content):
            tf[tok] = 1.0 + math.log1p(tf.get(tok, 0.0))
        for tok in tf:
            self._df[tok] = self._df.get(tok, 0) + 1
        self._docs[doc_id] = tf
        self._n += 1

    def _vec(self, tokens: List[str]) -> Dict[str, float]:
        tf: Dict[str, float] = {}
        for tok in tokens:
            tf[tok] = 1.0 + math.log1p(tf.get(tok, 0.0))
        # 归一化：cosine 仅关心方向
        norm = math.sqrt(sum(v * v for v in tf.values())) or 1.0
        return {t: v / norm for t, v in tf.items()}

    def search(self, query: str, top_k: int = 5) -> List[str]:
        qv = self._vec(tokenize(query))
        scored = []
        for doc_id, dtf in self._docs.items():
            dot = sum(v * dtf.get(t, 0.0) for t, v in qv.items())
            scored.append((dot, doc_id))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc_id for _, doc_id in scored[:top_k]]


# --------------------------------------------------------------------------- #
# 确定性伪 embedding（字符/二元组哈希，无需真实 API）
# --------------------------------------------------------------------------- #
def fake_embed_fn(dim: int = DIM):
    def _fn(texts: List[str]) -> List[List[float]]:
        out = []
        for t in texts:
            vec = [0.0] * dim
            chars = [c for c in t if c not in PUNCT]
            for c in chars:
                vec[ord(c) % dim] += 1.0
            for a, b in zip(chars, chars[1:]):
                vec[(ord(a) * 131 + ord(b)) % dim] += 0.5
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out

    return _fn


# --------------------------------------------------------------------------- #
# 指标
# --------------------------------------------------------------------------- #
def dedup_doc_ids(results: List) -> List[str]:
    seen, ordered = set(), []
    for r in results:
        did = getattr(r, "document_id", None)
        if did is not None and did not in seen:
            seen.add(did)
            ordered.append(did)
    return ordered


def recall_at_k(ranked: List[str], gold: str, k: int) -> int:
    return 1 if gold in ranked[:k] else 0


def mrr(ranked: List[str], gold: str) -> float:
    for i, did in enumerate(ranked, start=1):
        if did == gold:
            return 1.0 / i
    return 0.0


def run_comparison(
    corpus: List[Dict[str, str]],
    queries: List[Dict[str, str]],
    top_k: int,
    store: PGVectorStore,
    embed_fn,
) -> Dict:
    """在给定 store（已绑定租户/sehema）上跑两路对比，返回指标与逐条明细。"""
    # Mode A
    lex = LexiconRetriever().build(corpus)
    # Mode B：摄取
    collection = "ext_bench"
    if store.get_collection(collection) is None:
        store.create_collection(collection, DIM)
    ingest = KbIngestService(store, embed_fn)
    for d in corpus:
        ingest.ingest_document(
            collection, d["doc_id"], [SegmentInput(chunk_index=0, content=d["content"])]
        )
    retriever = KbRetrievalService(store, embed_fn)

    per_query = []
    a_rec1 = a_rec5 = b_rec1 = b_rec5 = 0
    a_mrr = b_mrr = 0.0
    for item in queries:
        q, gold = item["q"], item["gold"]
        a_rank = lex.search(q, top_k)
        b_results = retriever.hybrid_search_by_text(collection, q, top_k=top_k)
        b_rank = dedup_doc_ids(b_results)

        a_rec1 += recall_at_k(a_rank, gold, 1)
        a_rec5 += recall_at_k(a_rank, gold, top_k)
        a_mrr += mrr(a_rank, gold)
        b_rec1 += recall_at_k(b_rank, gold, 1)
        b_rec5 += recall_at_k(b_rank, gold, top_k)
        b_mrr += mrr(b_rank, gold)
        per_query.append(
            {
                "q": q,
                "gold": gold,
                "modeA_top": a_rank,
                "modeB_top": b_rank,
                "modeA_hit@k": gold in a_rank[:top_k],
                "modeB_hit@k": gold in b_rank[:top_k],
            }
        )

    n = len(queries)
    return {
        "top_k": top_k,
        "n_queries": n,
        "modeA": {
            "recall@1": round(a_rec1 / n, 4),
            "recall@5": round(a_rec5 / n, 4),
            "mrr": round(a_mrr / n, 4),
        },
        "modeB": {
            "recall@1": round(b_rec1 / n, 4),
            "recall@5": round(b_rec5 / n, 4),
            "mrr": round(b_mrr / n, 4),
        },
        "per_query": per_query,
    }


# --------------------------------------------------------------------------- #
# 独立 schema 运行环境（镜像 kb_perf_baseline.Bench）
# --------------------------------------------------------------------------- #
def _bench_db_url() -> str:
    from urllib.parse import quote_plus

    password = quote_plus(settings.DB_PASSWORD)
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/minworkbuddy_test"
    )


class Bench:
    def __init__(self) -> None:
        self.schema = f"ext_bench_{uuid.uuid4().hex[:8]}"
        self.engine = create_engine(_bench_db_url())
        event.listens_for(self.engine, "connect")(self._bind_schema)
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        Base.metadata.create_all(
            self.engine,
            tables=[KbCollection.__table__, KbSegment.__table__, KbRef.__table__],
        )
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_kb_segment_content_trgm "
                    "ON kb_segment USING gin (content gin_trgm_ops)"
                )
            )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

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


def _render_markdown(result: Dict, dim: int) -> str:
    a, b = result["modeA"], result["modeB"]
    delta = round(b["recall@5"] - a["recall@5"], 4)
    lines = [
        "#### 10.1 中文检索质量对比基线（P3 Task 8，2026-09-12）",
        "",
        "> 基线目的：量化「只读直连词项打分（Mode A）」与「同步落库向量检索（Mode B）」",
        "> 在合成中文语料上的召回差异。embedding 采用确定性伪向量（字符/二元组哈希，",
        f"维度 {dim}），**仅刻画字面字符共现，不度量语义泛化**。",
        "",
        "| 指标 | Mode A 只读直连(词项打分) | Mode B 同步落库(混合向量) |",
        "|---|---|---|",
        f"| Recall@1 | {a['recall@1']} | {b['recall@1']} |",
        f"| Recall@{result['top_k']} | {a['recall@5']} | {b['recall@5']} |",
        f"| MRR | {a['mrr']} | {b['mrr']} |",
        "",
        f"语料规模：{len(CORPUS)} 篇文档；查询集：{result['n_queries']} 条中文 query。",
        "",
        f"**结论**：在 *字面对齐* 信号下，两路 Recall@{result['top_k']} 分别为 "
        f"{a['recall@5']}（Mode A）与 {b['recall@5']}（Mode B），差值 {delta}——"
        "字面/关键词类中文 query 上两者基本持平。本基线使用的伪向量（字符/二元组哈希）"
        "与 Mode A 共享同一套字面对齐特征，故**无法体现真实 embedding（如 Qwen3-Embedding）"
        "带来的语义泛化增益**——尤其同义改写、缩写展开等场景，那才是同步落库模式的价值所在。"
        "要真正验证「同步落库价值」，需在生产 embedding 下重跑本脚本（将 `fake_embed_fn` "
        "替换为 `app.services.kb.ingest_service.build_embed_fn`）并补充同义/改写类 query 对比召回。",
        "",
        "复现：`.venv/Scripts/python.exe scripts/kb_external_retrieval_bench.py --out results.json`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="P3 Task 8 中文检索质量对比")
    ap.add_argument("--topk", type=int, default=5)
    default_out = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs",
        "superpowers",
        "specs",
        "2026-09-10-external-kb-retrieval-bench.json",
    )
    ap.add_argument("--out", type=str, default=default_out, help="结果 JSON 输出路径")
    args = ap.parse_args()

    bench = Bench()
    try:
        db = bench.Session()
        store = PGVectorStore(db, TENANT_BENCH)
        ef = fake_embed_fn(DIM)
        result = run_comparison(CORPUS, QUERIES, args.topk, store, ef)
        db.commit()
        db.close()
    finally:
        bench.close()

    print("\n=== P3 Task 8 · 中文检索质量对比 ===")
    print(f"语料 {len(CORPUS)} 篇 / 查询 {result['n_queries']} 条 / top_k={result['top_k']}")
    print(f"Mode A 只读直连(词项打分): {result['modeA']}")
    print(f"Mode B 同步落库(混合向量): {result['modeB']}")
    print("\n" + _render_markdown(result, DIM))

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[ok] JSON 已写出: {args.out}")


if __name__ == "__main__":
    main()
