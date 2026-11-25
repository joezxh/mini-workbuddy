"""一次性幂等修正：供应链图谱（KB 12）tenant 混乱导致前端只看到残缺数据。

背景
----
KB 12 的 kms_knowledge.tenant_id 为 NULL，而离线 rebuild 脚本从知识库行取租户，
导致完整抽取产物（984 实体 / 1550 关系，2026-11-25 01:14–02:38）落成
tenant_id=NULL；前端按当前用户 tenant_id=0 查询，只看到 09:17–09:18 前端
触发的一次残缺重建（61 实体 / 68 关系），两套数据 entity_key 还相互冲突。

本脚本只动 KB 12：
1. 删除 tenant_id=0 的旧残缺数据（实体/关系/提及）；
2. 把 tenant_id IS NULL 的完整数据更新为 0（含提及）；
3. 打印修正后分布。可重复执行（第二次运行时无 NULL 数据、无旧数据）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402

KB_ID = 12
TENANT = 0

with SessionLocal() as db:
    old_e = db.execute(text(
        "select count(*) from kg_entity where knowledge_id=:kid and tenant_id=0"),
        {"kid": KB_ID}).scalar()
    old_t = db.execute(text(
        "select count(*) from kg_triple where knowledge_id=:kid and tenant_id=0"),
        {"kid": KB_ID}).scalar()
    new_e = db.execute(text(
        "select count(*) from kg_entity where knowledge_id=:kid and tenant_id is null"),
        {"kid": KB_ID}).scalar()
    new_t = db.execute(text(
        "select count(*) from kg_triple where knowledge_id=:kid and tenant_id is null"),
        {"kid": KB_ID}).scalar()
    print(f"[pre] 旧(tenant=0): {old_e} 实体 / {old_t} 关系；"
          f"新(NULL): {new_e} 实体 / {new_t} 关系")

    # 1) 删除旧残缺数据（只限 KB 12 + tenant_id=0）
    db.execute(text(
        "delete from kg_entity_mention where kg_entity_id in "
        "(select id from kg_entity where knowledge_id=:kid and tenant_id=0)"),
        {"kid": KB_ID})
    db.execute(text(
        "delete from kg_triple_mention where kg_triple_id in "
        "(select id from kg_triple where knowledge_id=:kid and tenant_id=0)"),
        {"kid": KB_ID})
    db.execute(text(
        "delete from kg_triple where knowledge_id=:kid and tenant_id=0"),
        {"kid": KB_ID})
    db.execute(text(
        "delete from kg_entity where knowledge_id=:kid and tenant_id=0"),
        {"kid": KB_ID})

    # 2) 完整数据 NULL → 0
    db.execute(text(
        "update kg_entity set tenant_id=:t where knowledge_id=:kid and tenant_id is null"),
        {"t": TENANT, "kid": KB_ID})
    db.execute(text(
        "update kg_triple set tenant_id=:t where knowledge_id=:kid and tenant_id is null"),
        {"t": TENANT, "kid": KB_ID})
    db.execute(text(
        "update kg_entity_mention set tenant_id=:t where tenant_id is null "
        "and kg_entity_id in (select id from kg_entity where knowledge_id=:kid)"),
        {"t": TENANT, "kid": KB_ID})
    db.execute(text(
        "update kg_triple_mention set tenant_id=:t where tenant_id is null "
        "and kg_triple_id in (select id from kg_triple where knowledge_id=:kid)"),
        {"t": TENANT, "kid": KB_ID})
    db.commit()

    for table in ("kg_entity", "kg_triple", "kg_entity_mention", "kg_triple_mention"):
        dist = db.execute(text(
            f"select tenant_id, count(*) from {table} group by tenant_id")).all()
        print(f"[post] {table}: {dist}")
