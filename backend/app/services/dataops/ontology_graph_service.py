"""本体消费面读取服务（P0-6：E16 schema 图 + E17 证据链，spec §4.6 / §6.6 / §6.1）。

**只读口径**（§4.6）：图取 ``review_status=accepted`` 的对象与关系；``status`` 不参与，
故草稿态也能预览。元素归属沿用发布血统（``build_item(status='accepted').element_id``），
复用 :meth:`OntologyPublishService.build_snapshot`，避免"本体归属"的第二套定义漂移。

双视图（§6.6，AF-12 轻量等价物）：同一份数据两套布局——
- ``architecture``：仅对象 + 关系（力导向，回答"本体长什么样"）；
- ``workflow``：数据源表节点 + 对象节点 + 表→对象连线（分层，回答"数据怎么走到对象"）。

证据链（E17）：按 ``element_kind + element_code`` 检索 ``meta_ontology_evidence``，
原始依据 ``payload_json`` 原样透出供复核。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import ApiError, ONTOLOGY_NOT_FOUND
from app.models.dataops.meta import MetaTable
from app.models.dataops.ontology import MetaOntology, MetaOntologyEvidence
from app.services.dataops.ontology_publish_service import OntologyPublishService


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


class OntologyGraphService:
    """schema 图与证据链读取（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyGraphService 要求 tenant_id，禁止无租户操作")
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

    # ------------------------------------------------------------- E16 schema 图

    def graph(self, ontology_id: int, *, view: str = "workflow") -> dict:
        ontology = self._ontology_or_404(ontology_id)
        snap = OntologyPublishService(self.db, self.tenant_id).build_snapshot(ontology_id)

        # 只取已采纳对象/关系（§4.6：review_status=accepted，status 不参与）
        acc_objects = [o for o in snap["objects"] if o["review_status"] == "accepted"]
        obj_id_set = {o["id"] for o in acc_objects}
        acc_relations = [
            r for r in snap["relations"]
            if r["review_status"] == "accepted"
            and r["from_object_id"] in obj_id_set and r["to_object_id"] in obj_id_set
        ]

        nodes: List[dict] = []
        edges: List[dict] = []

        # 对象节点（两视图共有）
        for o in acc_objects:
            nodes.append({
                "id": f"obj:{o['id']}", "type": "object", "code": o["code"],
                "label": o["name"] or o["code"], "domain": o["domain"],
                "confidence": o["confidence"],
            })
        # 关系边（两视图共有）
        for r in acc_relations:
            edges.append({
                "id": f"rel:{r['id']}", "source": f"obj:{r['from_object_id']}",
                "target": f"obj:{r['to_object_id']}", "type": "relation",
                "relation_type": r["relation_type"], "label": r["name"] or r["code"],
                "code": r["code"],
            })

        if view == "workflow":
            # 追加数据源表节点 + 表→对象连线
            table_maps = snap["mappings"]["table"]
            table_ids = sorted({tm["table_id"] for tm in table_maps})
            names = {}
            if table_ids:
                rows = self.db.execute(
                    select(MetaTable.id, MetaTable.table_name, MetaTable.database).where(
                        MetaTable.tenant_id == self.tenant_id, MetaTable.id.in_(table_ids)
                    )
                ).all()
                names = {rid: (tname, dbn) for rid, tname, dbn in rows}
            for tm in table_maps:
                tid = tm["table_id"]
                tname, dbn = names.get(tid, (f"table#{tid}", None))
                node_id = f"tbl:{tid}"
                if all(n["id"] != node_id for n in nodes):
                    nodes.append({
                        "id": node_id, "type": "table", "label": tname,
                        "database": dbn, "code": tname,
                    })
                edges.append({
                    "id": f"map:{tm['id']}", "source": node_id,
                    "target": f"obj:{tm['object_standard_id']}", "type": "mapping",
                    "label": "maps_to",
                })

        return {
            "ontology_id": ontology_id,
            "view": view if view in ("workflow", "architecture") else "workflow",
            "stage": "published" if ontology.current_version and ontology.current_version > 0 else "draft",
            "counts": {
                "object_nodes": len(acc_objects),
                "relation_edges": len(acc_relations),
                "table_nodes": sum(1 for n in nodes if n["type"] == "table"),
            },
            "nodes": nodes,
            "edges": edges,
        }

    # ------------------------------------------------------------- E17 证据链

    def evidence(
        self, ontology_id: int, *,
        element_kind: Optional[str] = None,
        element_code: Optional[str] = None,
    ) -> dict:
        self._ontology_or_404(ontology_id)
        stmt = select(MetaOntologyEvidence).where(
            MetaOntologyEvidence.tenant_id == self.tenant_id,
            MetaOntologyEvidence.ontology_id == ontology_id,
        )
        if element_kind:
            stmt = stmt.where(MetaOntologyEvidence.element_kind == element_kind)
        if element_code:
            stmt = stmt.where(MetaOntologyEvidence.element_code == element_code)
        rows = list(self.db.execute(
            stmt.order_by(MetaOntologyEvidence.id.desc())
        ).scalars().all())
        return {
            "ontology_id": ontology_id,
            "element_kind": element_kind,
            "element_code": element_code,
            "total": len(rows),
            "items": [
                {
                    "id": e.id,
                    "element_kind": e.element_kind,
                    "element_code": e.element_code,
                    "evidence_kind": e.evidence_kind,
                    "confidence": e.confidence,
                    "payload": e.payload_json,
                    "created_at": _iso(e.created_at),
                }
                for e in rows
            ],
        }
