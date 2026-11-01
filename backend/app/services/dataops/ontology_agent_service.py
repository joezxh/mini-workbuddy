"""本体 Agent 只读语义导航（P0-7：E24 manifest + E25 browse + E26 resolve，spec §6.4 / §6.1）。

D4「最小消费面」：三个**只读**端点，元素口径一律 ``review_status=accepted``（§6.4）。
不写库、不建任务、不发布，供对话式 Agent 只读导航 schema。

约束（§6.4）：
- ``manifest``：版本自述，单次 ≤ 2KB（仅对象 code 概览，非全量结构）；``current_version=0``
  返回 ``needs_build=true``；
- ``browse``：**空 query 拒绝全量枚举**（返回 ``rejected`` 而非倾倒全部元素）；结果 ≤ 6 条；
- ``resolve``：按 code 定点解析，≤ 5 个 code；本租户不可见的 code 归 ``not_found``
  （租户拦截器已做行级隔离，跨租户不泄露存在性，故不返回 ``forbidden``）。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import ApiError, ONTOLOGY_NOT_FOUND
from app.models.dataops.ontology import MetaOntology
from app.services.dataops.ontology_publish_service import OntologyPublishService

BROWSE_LIMIT = 6
RESOLVE_LIMIT = 5


class OntologyAgentService:
    """Agent 只读导航（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyAgentService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    def _accepted(self, ontology_id: int) -> dict:
        snap = OntologyPublishService(self.db, self.tenant_id).build_snapshot(ontology_id)
        objects = [o for o in snap["objects"] if o["review_status"] == "accepted"]
        relations = [r for r in snap["relations"] if r["review_status"] == "accepted"]
        properties = [p for p in snap["properties"] if p["review_status"] == "accepted"]
        return {"objects": objects, "relations": relations, "properties": properties,
                "mappings": snap["mappings"], "cq": snap["cq"]}

    # ------------------------------------------------------------- E24 manifest

    def manifest(self, ontology_id: int) -> dict:
        ontology = self._ontology_or_404(ontology_id)
        data = self._accepted(ontology_id)
        cq = data["cq"]
        cq_passed = sum(1 for c in cq if c["verify_status"] == "passed")
        cq_rate = round(cq_passed / len(cq), 4) if cq else None
        return {
            "ontology_code": ontology.code,
            "version": int(ontology.current_version or 0),
            "needs_build": (ontology.current_version or 0) == 0,
            "stage": "published" if (ontology.current_version or 0) > 0 else "draft",
            "objects": [o["code"] for o in data["objects"]],   # 概览，控体积
            "relations_count": len(data["relations"]),
            "properties_count": len(data["properties"]),
            "cq_pass_rate": cq_rate,
            "usage_hint": "browse 只读浏览(≤6, 需 query) / resolve 按 code 定点解析(≤5)",
        }

    # ------------------------------------------------------------- E25 browse

    def browse(self, ontology_id: int, query: Optional[str]) -> dict:
        self._ontology_or_404(ontology_id)
        q = (query or "").strip().lower()
        if not q:
            # 拒绝全量枚举：空 query 不倾倒所有元素
            return {"rejected": True, "reason": "empty_query",
                    "hint": "browse 需要非空 query，避免全量枚举",
                    "objects": [], "relations": []}
        data = self._accepted(ontology_id)

        def _hit(o: dict) -> bool:
            if q in (o["code"] or "").lower() or q in (o["name"] or "").lower():
                return True
            aliases = o.get("aliases") or []
            return any(q in str(a).lower() for a in aliases)

        obj_hits = [o for o in data["objects"] if _hit(o)][:BROWSE_LIMIT]
        rel_hits = [
            r for r in data["relations"]
            if q in (r["code"] or "").lower() or q in (r["name"] or "").lower()
        ][: max(0, BROWSE_LIMIT - len(obj_hits))]
        return {
            "rejected": False,
            "query": query,
            "objects": [{"code": o["code"], "name": o["name"]} for o in obj_hits],
            "relations": [{"code": r["code"], "name": r["name"],
                           "from_object_id": r["from_object_id"],
                           "to_object_id": r["to_object_id"]} for r in rel_hits],
            "limited": len(data["objects"]) > BROWSE_LIMIT or len(obj_hits) == BROWSE_LIMIT,
        }

    # ------------------------------------------------------------- E26 resolve

    def resolve(self, ontology_id: int, codes: Optional[List[str]]) -> dict:
        self._ontology_or_404(ontology_id)
        req = [c for c in (codes or []) if c][:RESOLVE_LIMIT]
        data = self._accepted(ontology_id)
        obj_by_code = {o["code"]: o for o in data["objects"]}
        obj_id_to_code = {o["id"]: o["code"] for o in data["objects"]}

        resolved_objects, not_found = [], []
        for c in req:
            o = obj_by_code.get(c)
            if o is None:
                not_found.append(c)
                continue
            props = [p for p in data["properties"] if p["object_id"] == o["id"]]
            rels = [
                r for r in data["relations"]
                if r["from_object_id"] == o["id"] or r["to_object_id"] == o["id"]
            ]
            tmaps = [tm for tm in data["mappings"]["table"]
                     if tm["object_standard_id"] == o["id"]]
            resolved_objects.append({
                "code": o["code"], "name": o["name"], "domain": o["domain"],
                "properties": [{"standard_id": p["standard_id"], "required": p["required"]}
                               for p in props],
                "relations": [{"code": r["code"], "relation_type": r["relation_type"],
                               "from": obj_id_to_code.get(r["from_object_id"]),
                               "to": obj_id_to_code.get(r["to_object_id"])} for r in rels],
                "table_mappings": [{"table_id": tm["table_id"]} for tm in tmaps],
            })
        return {
            "objects": resolved_objects,
            "not_found": not_found,
            "forbidden": [],   # 租户拦截器已隔离，跨租户不泄露存在性
            "codes_requested": len(req),
            "truncated": len(codes or []) > RESOLVE_LIMIT,
        }
