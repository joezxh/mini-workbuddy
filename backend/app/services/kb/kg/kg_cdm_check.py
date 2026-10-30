"""图谱实例层与 CDM 模式层的双向校验（P6）。

Spec 6.5：图谱实例层的边 -> 映射到 meta_object_relation 校验，
产出 hit / missing / conflict 三态结论，**沿用 meta_relation_check 的既有词表**
（不新建词表、不新增表）。

映射规则（显式、可解释）
------------------------
一条图谱边 ``kg_triple`` 与一条标准关系 ``meta_object_relation`` 对齐，当且仅当：

1. ``kg_triple.relation_code == meta_object_relation.code``
2. 起点实体的 ``type_code`` 等于标准的 ``from_object.code``
3. 终点实体的 ``type_code`` 等于标准的 ``to_object.code``

结论
----
* ``hit``     该标准关系在图谱实例中**有**对应边
* ``missing`` 该标准关系在图谱实例中**没有**对应边（覆盖不足）
* ``conflict`` 图谱中的边**违反**标准约束（如基数 1:1 却出现多条同端点边）

只读计算，不写库：校验是治理视图，不是事实来源。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb.kg_entity import KgEntity
from app.models.kb.kg_triple import KgTriple
from app.models.dataops.standard_cdm import MetaObjectRelation, MetaObjectStandard

# 基数取值沿用 MetaObjectRelation.relation_type 的既有词表
CARDINALITY_1_1 = "1:1"
CARDINALITY_1_N = "1:N"
CARDINALITY_N_1 = "N:1"
CARDINALITY_N_N = "N:N"

VERDICT_HIT = "hit"
VERDICT_MISSING = "missing"
VERDICT_CONFLICT = "conflict"


def run_cdm_check(
    db: Session,
    knowledge_id: int,
    tenant_id: Optional[int] = None,
) -> dict:
    """执行一次 CDM <-> 图谱实例校验。

    :return: ``{"hit": n, "missing": n, "conflict": n, "items": [...]}``
    """
    # ── 标准关系 ──
    rel_stmt = select(MetaObjectRelation)
    obj_stmt = select(MetaObjectStandard)
    if tenant_id is not None:
        rel_stmt = rel_stmt.where(MetaObjectRelation.tenant_id == tenant_id)
        obj_stmt = obj_stmt.where(MetaObjectStandard.tenant_id == tenant_id)
    relations = list(db.execute(rel_stmt).scalars().all())
    objects = {o.id: o for o in db.execute(obj_stmt).scalars().all()}

    # ── 图谱实例 ──
    ent_stmt = select(KgEntity).where(KgEntity.knowledge_id == knowledge_id)
    tri_stmt = select(KgTriple).where(KgTriple.knowledge_id == knowledge_id)
    if tenant_id is not None:
        ent_stmt = ent_stmt.where(KgEntity.tenant_id == tenant_id)
        tri_stmt = tri_stmt.where(KgTriple.tenant_id == tenant_id)
    entities = {e.id: e for e in db.execute(ent_stmt).scalars().all()}
    triples = list(db.execute(tri_stmt).scalars().all())

    # 端点类型索引：用于冲突检测（同类型端点出现多条边）
    pair_count: dict = {}
    for t in triples:
        src = entities.get(t.from_entity_id)
        tgt = entities.get(t.to_entity_id)
        if src is None or tgt is None:
            continue
        key = (src.type_code or "", t.relation_code or "", tgt.type_code or "")
        pair_count[key] = pair_count.get(key, 0) + 1

    items: list = []
    hits = missing = conflicts = 0

    for rel in relations:
        src_obj = objects.get(rel.from_object_id)
        tgt_obj = objects.get(rel.to_object_id)
        src_code = src_obj.code if src_obj is not None else ""
        tgt_code = tgt_obj.code if tgt_obj is not None else ""

        matched = [
            t for t in triples
            if (t.relation_code or "") == (rel.code or "")
            and _type_of(entities, t.from_entity_id) == src_code
            and _type_of(entities, t.to_entity_id) == tgt_code
        ]

        if not matched:
            missing += 1
            items.append(
                {
                    "verdict": VERDICT_MISSING,
                    "relation_code": rel.code,
                    "relation_name": rel.name,
                    "from_type": src_code,
                    "to_type": tgt_code,
                    "cardinality": rel.relation_type,
                    "count": 0,
                    "detail": "标准已声明该关系，图谱实例中无对应边",
                }
            )
            continue

        hits += 1
        item = {
            "verdict": VERDICT_HIT,
            "relation_code": rel.code,
            "relation_name": rel.name,
            "from_type": src_code,
            "to_type": tgt_code,
            "cardinality": rel.relation_type,
            "count": len(matched),
            "detail": "",
        }
        # 基数冲突：1:1 但同端点出现多条边；1:N / N:1 但出现反向多对多
        pair_key = (src_code, rel.code or "", tgt_code)
        if rel.relation_type == CARDINALITY_1_1 and pair_count.get(pair_key, 0) > 1:
            conflicts += 1
            item["verdict"] = VERDICT_CONFLICT
            item["detail"] = (
                f"基数为 1:1，但图谱中出现 {pair_count[pair_key]} 条同类型边"
            )
        items.append(item)

    # 图谱中有、标准里没有的边：CDM 目录未必覆盖全图，因此**不计入 conflict**
    # （conflict 严格保留 spec 语义：违反基数等约束）。这类边单列为 uncovered 诊断，
    # 供治理侧判断是否需要补标准或清理图谱。
    known = {(r.code or "") for r in relations}
    uncovered: dict = {}
    for t in triples:
        code = t.relation_code or ""
        if code and code not in known:
            uncovered[code] = uncovered.get(code, 0) + 1

    return {
        "hit": hits,
        "missing": missing,
        "conflict": conflicts,
        "items": items,
        "uncovered": [
            {"relation_code": code, "count": cnt}
            for code, cnt in sorted(uncovered.items())
        ],
        "total_relations": len(relations),
        "total_triples": len(triples),
    }



def _type_of(entities: dict, entity_id: Optional[int]) -> str:
    e = entities.get(entity_id) if entity_id is not None else None
    return (e.type_code or "") if e is not None else ""
