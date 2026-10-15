"""临时：查看模型管理中的向量化模型（type=5）与知识库容器设置。"""
import logging

logging.disable(logging.INFO)

import sys

sys.path.insert(0, r"d:\projects\MinWorkBuddy\backend")

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402

db = SessionLocal()
try:
    print("--- ai_api_key ---")
    for r in db.execute(text(
            "SELECT id, name, platform, url, status FROM ai_api_key ORDER BY id")).fetchall():
        print(f"  id={r[0]} {r[1]} platform={r[2]} url={r[3]} status={r[4]}")

    print("--- ai_chat_model type=5 (向量化) ---")
    for r in db.execute(text(
            "SELECT id, code, name, model, platform, key_id, dimensions, is_default, status "
            "FROM ai_chat_model WHERE type=5 ORDER BY id")).fetchall():
        print(f"  id={r[0]} code={r[1]} name={r[2]} model={r[3]} platform={r[4]} "
              f"key_id={r[5]} dim={r[6]} default={r[7]} status={r[8]}")

    print("--- kms_knowledge (index_mode) ---")
    for r in db.execute(text(
            "SELECT id, name, index_mode FROM kms_knowledge ORDER BY id")).fetchall():
        print(f"  id={r[0]} name={r[1]} index_mode={r[2]}")

    print("--- kms_segment 文档分布 ---")
    for r in db.execute(text(
            "SELECT collection, document_id, COUNT(*) FROM kms_segment "
            "GROUP BY collection, document_id ORDER BY collection")).fetchall():
        print(f"  {r[0]} {r[1]} chunks={r[2]}")
finally:
    db.close()
