"""临时验证：维度对齐迁移 + 嵌入链路端到端可用性。"""
import asyncio
import sys

sys.path.insert(0, r"d:\projects\MinWorkBuddy\backend")

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal, engine  # noqa: E402
from app.db.startup_migrations import align_vector_dimensions  # noqa: E402
from app.services.kb.embedding_config import (  # noqa: E402
    describe_embedding_config,
    resolve_embedding_config_with_fallback,
)
from app.services.kb.rag.embedding_factory import build_embedding_model  # noqa: E402

print("=== 迁移前 ===")
with engine.begin() as c:
    print("atttypmod =", c.execute(text(
        "SELECT a.atttypmod FROM pg_attribute a JOIN pg_class cl ON cl.oid=a.attrelid "
        "WHERE cl.relname='kms_segment' AND a.attname='embedding'")).scalar())

align_vector_dimensions(engine)

print("=== 迁移后 ===")
with engine.begin() as c:
    print("atttypmod =", c.execute(text(
        "SELECT a.atttypmod FROM pg_attribute a JOIN pg_class cl ON cl.oid=a.attrelid "
        "WHERE cl.relname='kms_segment' AND a.attname='embedding'")).scalar())
    print("hnsw index =", [r[0] for r in c.execute(text(
        "select indexname from pg_indexes where tablename='kms_segment' "
        "and indexname like '%hnsw%'")).fetchall()])

cfg = resolve_embedding_config_with_fallback(None)
print("config =", describe_embedding_config(cfg))

model = build_embedding_model(None)
out = asyncio.run(model(["端到端验证：季度指标报表"]))
vecs = list(out.embeddings)
print("EMBED OK dim =", len(vecs[0]))
