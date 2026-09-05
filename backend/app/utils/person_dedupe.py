"""人员去重辅助工具。

TODO: 域特定模型已移除，待 AgentScope 适配后重建。
"""
from collections import defaultdict
from typing import Dict, List, Optional

# TODO: 域特定模型已移除
# from app.models.risk_ext import RiskPersonExt
# from app.models.risk_person import RiskPerson


def person_display_dedupe_key(person: RiskPerson) -> tuple:
    """用于「是否为同一人」的粗粒度键：身份证哈希 > 姓名。"""
    ich = (person.id_card_hash or "").strip()
    if ich:
        return ("id_hash", ich)
    name = (person.real_name or "").strip()
    if name:
        return ("name", name.lower())
    return ("pid", person.person_id)


def person_ext_six_fill_score(pext: Optional[RiskPersonExt]) -> int:
    if not pext:
        return 0
    keys = (
        "family_info",
        "economic_status",
        "personality",
        "social_relations",
        "health_status",
        "other_info",
    )
    return sum(1 for k in keys if (getattr(pext, k, None) or "").strip())


def dedupe_persons_for_display(
    persons: List[RiskPerson],
    ext_by_id: Optional[Dict[int, RiskPersonExt]] = None,
) -> List[RiskPerson]:
    """
    对人员列表按 person_display_dedupe_key 分桶，每桶保留一条。
    优先保留六维文本填充更多者，其次 person_id 更大（通常对应较新抽取）。
    顺序：按原列表中「首次出现的桶」顺序输出。
    """
    ext_by_id = ext_by_id or {}
    groups: dict[tuple, List[RiskPerson]] = defaultdict(list)
    for p in persons:
        groups[person_display_dedupe_key(p)].append(p)

    def pick_canonical(group: List[RiskPerson]) -> RiskPerson:
        if len(group) == 1:
            return group[0]
        return max(
            group,
            key=lambda p: (
                person_ext_six_fill_score(ext_by_id.get(p.person_id)),
                p.person_id,
            ),
        )

    canonical = {k: pick_canonical(g) for k, g in groups.items()}
    seen: set = set()
    out: List[RiskPerson] = []
    for p in persons:
        k = person_display_dedupe_key(p)
        c = canonical[k]
        if c.person_id in seen:
            continue
        seen.add(c.person_id)
        out.append(c)
    return out
