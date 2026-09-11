"""本体版本快照与评审记录服务（Task 6）。

治理闭环的收口：对象类型/属性/关系/映射/CQ 的**冻结视图**（快照）+ 快照间
**变更追溯**（diff）。评审流程（Task 5 的候选 accepted/rejected）落定后，
由调用方打快照；快照链即评审记录。

边界（P4 计划 Task 6 明确）
--------------------------
**回滚不在本阶段** —— 本模块刻意不提供任何恢复/回滚接口；
`tests/ontology/test_version.py::test_no_rollback_api` 把这一点固化为断言，
未来引入回滚（P4.4 评估）时该用例应被显式修改而不是静默通过。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ontology.model import OntologyVersion
from app.models.ontology.ontology import Ontology
from app.services.ontology.modeling_service import ModelingService

logger = logging.getLogger(__name__)

__all__ = [
    "OntologyReviewService",
    "SnapshotDiff",
]


class SnapshotDiff:
    """两个快照之间的变更明细（按实体类型分组的 added/removed/status_changed）。"""

    def __init__(self, from_version: str, to_version: str) -> None:
        self.from_version = from_version
        self.to_version = to_version
        #: {entity: {"added": [...], "removed": [...], "status_changed": [...]}}
        self.changes: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def add(self, entity: str, bucket: str, item: Dict[str, Any]) -> None:
        self.changes.setdefault(entity, {"added": [], "removed": [], "status_changed": []})
        self.changes[entity][bucket].append(item)

    @property
    def is_empty(self) -> bool:
        return not any(any(b.values()) for b in self.changes.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "changes": self.changes,
        }


class OntologyReviewService:
    """本体快照服务：创建（冻结）、查询、对比。"""

    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int],
        code: str = "default",
    ) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._code = code
        # 快照服务只读本体（除写入 version 行外），复用 ModelingService 的租户链路
        self._modeling = ModelingService(db, tenant_id, code)

    # ── 内部 ─────────────────────────────────────────────────────────────────
    def _resolve_ontology(self) -> Optional[Ontology]:
        stmt = select(Ontology).where(
            Ontology.tenant_id == self._tenant_id,
            Ontology.code == self._code,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def _next_version(self, ontology_id: int) -> str:
        """`v{max+1}`：基于已有快照序号自增。"""
        rows = self._db.execute(
            select(OntologyVersion.version).where(
                OntologyVersion.ontology_id == ontology_id
            )
        ).scalars().all()
        max_n = 0
        for v in rows:
            if v.startswith("v") and v[1:].isdigit():
                max_n = max(max_n, int(v[1:]))
        return f"v{max_n + 1}"

    def _snapshot_body(self) -> Dict[str, Any]:
        """冻结当前建模 + OWL 状态为可 JSON 序列化的结构。"""
        svc = self._modeling
        object_types = svc.list_object_types()
        code_by_id = {ot.id: ot.code for ot in object_types}

        ot_items = [
            {
                "code": ot.code,
                "name": ot.name,
                "parent_code": code_by_id.get(ot.parent_id),
                "status": ot.status,
                "source": ot.source,
                "confidence": ot.confidence,
            }
            for ot in object_types
        ]
        properties = [
            {
                "object_type_code": code_by_id.get(p.object_type_id, str(p.object_type_id)),
                "code": p.code,
                "name": p.name,
                "data_type": p.data_type,
                "required": p.required,
                "status": p.status,
                "source": p.source,
                "confidence": p.confidence,
            }
            for ot in object_types
            for p in svc.list_properties(ot.code)
        ]
        link_types = [
            {
                "code": lt.code,
                "name": lt.name,
                "source_type_code": code_by_id.get(lt.source_type_id, str(lt.source_type_id)),
                "target_type_code": code_by_id.get(lt.target_type_id, str(lt.target_type_id)),
                "cardinality": lt.cardinality,
                "status": lt.status,
                "source": lt.source,
                "confidence": lt.confidence,
            }
            for lt in svc.list_link_types()
        ]
        mappings = [
            {
                "object_type_code": code_by_id.get(m.object_type_id, str(m.object_type_id)),
                "target_type": m.target_type,
                "database": m.database,
                "table_name": m.table_name,
                "column_name": m.column_name,
                "status": m.status,
            }
            for m in svc.list_mappings()
        ]
        cqs = [
            {
                "question": cq.question,
                "status": cq.status,
                "linked_object_types": list(cq.linked_object_types or []),
            }
            for cq in svc.list_cqs(status=None)
        ]
        return {
            "object_types": ot_items,
            "properties": properties,
            "link_types": link_types,
            "mappings": mappings,
            "cqs": cqs,
            "cq_coverage": svc.cq_coverage(),
            "owl_class_count": len(svc._repo.list_classes()),
        }

    # ── 对外 ─────────────────────────────────────────────────────────────────
    def create_snapshot(
        self,
        change_note: str = "",
        author_user_id: Optional[int] = None,
    ) -> OntologyVersion:
        """冻结当前本体状态为 `v{n}` 快照（评审落定后由调用方触发）。"""
        ontology = self._resolve_ontology()
        if ontology is None:
            raise ValueError(f"本体不存在（tenant={self._tenant_id}, code={self._code}），"
                             "无可快照内容")

        row = OntologyVersion(
            ontology_id=ontology.id,
            version=self._next_version(ontology.id),
            snapshot_json=self._snapshot_body(),
            change_note=change_note,
            author_user_id=author_user_id,
        )
        self._db.add(row)
        self._db.commit()
        logger.info(
            "ontology snapshot created: tenant=%s code=%s %s",
            self._tenant_id, self._code, row.version,
        )
        return row

    def list_snapshots(self) -> List[OntologyVersion]:
        """按版本号倒序列出快照（不含 snapshot_json 大对象）。"""
        ontology = self._resolve_ontology()
        if ontology is None:
            return []
        stmt = (
            select(
                OntologyVersion.id,
                OntologyVersion.version,
                OntologyVersion.change_note,
                OntologyVersion.author_user_id,
                OntologyVersion.created_at,
            )
            .where(OntologyVersion.ontology_id == ontology.id)
            .order_by(OntologyVersion.id.desc())
        )
        # 以轻量 ORM 形态返回（保持调用方兼容，无需单独 schema）
        return list(self._db.execute(stmt).all())

    def get_snapshot(self, version: str) -> Optional[OntologyVersion]:
        """按版本号取完整快照。"""
        ontology = self._resolve_ontology()
        if ontology is None:
            return None
        stmt = select(OntologyVersion).where(
            OntologyVersion.ontology_id == ontology.id,
            OntologyVersion.version == version,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def diff_snapshots(self, from_version: str, to_version: str) -> SnapshotDiff:
        """对比两个快照，产出变更明细（评审记录的核心输出）。

        对比维度：object_types / properties / link_types / cqs 的
        added（新出现）/ removed（消失）；object_types 与 link_types 额外对比
        status 变更（评审流转的直接痕迹）。
        """
        src = self.get_snapshot(from_version)
        dst = self.get_snapshot(to_version)
        if src is None or dst is None:
            raise ValueError(f"快照不存在: {from_version if src is None else to_version}")

        diff = SnapshotDiff(from_version, to_version)
        src_body: Dict[str, Any] = src.snapshot_json or {}
        dst_body: Dict[str, Any] = dst.snapshot_json or {}

        def _index(items: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
            return {item[key]: item for item in items if key in item}

        for entity, key in (
            ("object_types", "code"),
            ("properties", "key"),
            ("link_types", "code"),
            ("cqs", "question"),
        ):
            if entity == "properties":
                src_items = [
                    {**it, "key": f"{it.get('object_type_code')}.{it.get('code')}"}
                    for it in src_body.get(entity, [])
                ]
                dst_items = [
                    {**it, "key": f"{it.get('object_type_code')}.{it.get('code')}"}
                    for it in dst_body.get(entity, [])
                ]
            else:
                src_items = list(src_body.get(entity, []))
                dst_items = list(dst_body.get(entity, []))

            src_idx = _index(src_items, key)
            dst_idx = _index(dst_items, key)
            for k, item in dst_idx.items():
                if k not in src_idx:
                    diff.add(entity, "added", {"key": k, **item})
                elif item.get("status") != src_idx[k].get("status"):
                    diff.add(entity, "status_changed", {
                        "key": k,
                        "from": src_idx[k].get("status"),
                        "to": item.get("status"),
                    })
            for k, item in src_idx.items():
                if k not in dst_idx:
                    diff.add(entity, "removed", {"key": k, **item})
        return diff
