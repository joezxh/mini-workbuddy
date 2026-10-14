"""临时：确认 kms_segment.embedding 当前维度与目标维度。"""
import sys

sys.path.insert(0, r"d:\projects\MinWorkBuddy\backend")

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services.kb.embedding_config import (  # noqa: E402
    resolve_embedding_config_with_fallback,
)

db = SessionLocal()
try:
    cur = db.execute(text(
        "SELECT a.atttypmod FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "WHERE c.relname='kms_segment' AND a.attname='embedding'")).scalar()
    print("column atttypmod =", cur)
finally:
    db.close()

cfg = resolve_embedding_config_with_fallback(None)
print("resolved dim =", cfg.dimension, "model =", cfg.model)
print("settings.NVIDIA_EMBEDDING_DIMENSION =", settings.NVIDIA_EMBEDDING_DIMENSION)
print("settings.GPUSTACK_EMBEDDING_DIMENSION =", settings.GPUSTACK_EMBEDDING_DIMENSION)
print("settings.EMBEDDING_PROVIDER =", settings.EMBEDDING_PROVIDER)
