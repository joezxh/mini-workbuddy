"""本体发布服务（P0-5：E11 发布 + E12 版本列表 + E13 版本快照，spec §4.5 / §6.1）。

发布 = 一个事务内完成三件事（§4.5 末）：
1. 写 ``onto_ontology_version``（冻结 snapshot + diff + gate 结论）；
2. 快照元素 ``status=published``（object / relation 有 status 列；mapping 侧沿用
   ``suggested|accepted|rejected`` 语义，不再叠 ``published``）；
3. ``onto_ontology.current_version`` 自增、``status=published``。

**先写快照再改指针**：保证成为 ``current_version`` 的版本号必然已有对应快照行。

快照血统（决策 D1/D2/D3 rev.2）：本体没有"元素归属"外键，唯一可靠来源是
``build_item(status='accepted').element_id``——按 kind 反查结构行；mapping 由已采纳
object **派生**（``meta_table_standard`` / ``meta_column_standard``），规避 mapping 候选
``element_id`` 在两张表间歧义的问题。

三层防线的**防线③（出口层）先行、不参与 override**（§5.7 / R2 风险第 11 条）：
快照含 ``source='llm_draft'`` 即 ``PUBLISH_BLOCKED_UNREVIEWED_SOURCE``，写在 5 项门禁之前。

门禁 5 项（§4.5）：
1. 无未决候选（``build_item.status='suggested'`` 计数=0，可 ``override_pending`` 放行）；
2. 结构完整性（关系两端对象存在且已采纳、属性归属对象存在、映射的表/列真实存在）；
3. 无回归（对比上一版：被现存关系引用的对象消失 → regression）；
4. CQ 覆盖度 ≥ 60%（**无独立错误码，§6.1 枚举对齐**：仅记 ``warn``，不阻断）；
5. 敏感列脱敏覆盖（已映射且 ``pii_level>=L2`` 的列须有 ``mask_rule`` / 降级 override / 豁免）。

事务边界在路由层：本服务只 flush。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, PUBLISH_BLOCKED_INTEGRITY, PUBLISH_BLOCKED_MASK_COVERAGE,
    PUBLISH_BLOCKED_PENDING_REVIEW, PUBLISH_BLOCKED_REGRESSION,
    PUBLISH_BLOCKED_UNREVIEWED_SOURCE, ONTOLOGY_NOT_FOUND,
)
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.ontology.ontology import (
    MetaOntology, MetaOntologyBuildItem, MetaOntologyBuildJob, MetaOntologyCq,
    MetaOntologyVersion,
)
from app.models.dataops.standard import MetaColumnStandard, MetaStandard
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute, MetaTableStandard,
)

#: 门禁 4：CQ 覆盖度阈值（§4.5 默认 0.6，本期常量，无 CQ 时 warn 放行）
CQ_COVERAGE_THRESHOLD = 0.6

#: 敏感列脱敏门禁命中阈值（L2 及以上需脱敏覆盖，§4.5 第 5 项）
_SENSITIVE_PII = {"L2", "L3"}


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


class OntologyPublishService:
    """发布、版本快照与门禁（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyPublishService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------ 基础查询

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    def _job_ids(self, ontology_id: int) -> List[int]:
        return list(self.db.execute(
            select(MetaOntologyBuildJob.id).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.ontology_id == ontology_id,
            )
        ).scalars().all())

    def _accepted_element_ids(self, job_ids: List[int]) -> Dict[str, List[int]]:
        """按 kind 收集已采纳候选的 ``element_id``（结构行主键，mapping 除外）。"""
        out: Dict[str, List[int]] = {"object": [], "relation": [], "property": []}
        if not job_ids:
            return out
        rows = self.db.execute(
            select(
                MetaOntologyBuildItem.element_kind, MetaOntologyBuildItem.element_id
            ).where(
                MetaOntologyBuildItem.tenant_id == self.tenant_id,
                MetaOntologyBuildItem.job_id.in_(job_ids),
                MetaOntologyBuildItem.status == "accepted",
                MetaOntologyBuildItem.element_id.isnot(None),
            )
        ).all()
        for kind, element_id in rows:
            if kind in out and element_id is not None:
                out[kind].append(int(element_id))
        return out

    # ------------------------------------------------------------ 快照构建

    def build_snapshot(self, ontology_id: int) -> dict:
        """冻结当前本体全量结构：对象 / 关系 / 属性 + 派生映射 + CQ。"""
        job_ids = self._job_ids(ontology_id)
        ids = self._accepted_element_ids(job_ids)

        objects = list(self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.id.in_(ids["object"]),
            ).order_by(MetaObjectStandard.code)
        ).scalars().all()) if ids["object"] else []

        relations = list(self.db.execute(
            select(MetaObjectRelation).where(
                MetaObjectRelation.tenant_id == self.tenant_id,
                MetaObjectRelation.id.in_(ids["relation"]),
            ).order_by(MetaObjectRelation.code)
        ).scalars().all()) if ids["relation"] else []

        attributes = list(self.db.execute(
            select(MetaObjectStandardAttribute).where(
                MetaObjectStandardAttribute.tenant_id == self.tenant_id,
                MetaObjectStandardAttribute.id.in_(ids["property"]),
            ).order_by(MetaObjectStandardAttribute.id)
        ).scalars().all()) if ids["property"] else []

        object_ids = [o.id for o in objects]

        # 映射：由已采纳对象派生（表→对象 accepted；列→标准 accepted 且属这些表）
        table_maps = []
        if object_ids:
            table_maps = list(self.db.execute(
                select(MetaTableStandard).where(
                    MetaTableStandard.tenant_id == self.tenant_id,
                    MetaTableStandard.object_standard_id.in_(object_ids),
                    MetaTableStandard.status == "accepted",
                ).order_by(MetaTableStandard.id)
            ).scalars().all())
        table_ids = [tm.table_id for tm in table_maps]
        standard_ids = sorted({a.standard_id for a in attributes})
        column_maps = []
        if table_ids and standard_ids:
            column_maps = list(self.db.execute(
                select(MetaColumnStandard).where(
                    MetaColumnStandard.tenant_id == self.tenant_id,
                    MetaColumnStandard.status == "accepted",
                    MetaColumnStandard.standard_id.in_(standard_ids),
                    MetaColumnStandard.column_id.in_(
                        select(MetaColumn.id).where(
                            MetaColumn.tenant_id == self.tenant_id,
                            MetaColumn.table_id.in_(table_ids),
                        )
                    ),
                ).order_by(MetaColumnStandard.id)
            ).scalars().all())

        cq_rows = list(self.db.execute(
            select(MetaOntologyCq).where(
                MetaOntologyCq.tenant_id == self.tenant_id,
                MetaOntologyCq.ontology_id == ontology_id,
            ).order_by(MetaOntologyCq.id)
        ).scalars().all())

        return {
            "objects": [
                {"id": o.id, "code": o.code, "name": o.name, "domain": o.domain,
                 "aliases": o.aliases_json or [],
                 "source": o.source, "review_status": o.review_status,
                 "confidence": o.confidence}
                for o in objects
            ],
            "relations": [
                {"id": r.id, "code": r.code, "name": r.name,
                 "from_object_id": r.from_object_id, "to_object_id": r.to_object_id,
                 "relation_type": r.relation_type, "source": r.source,
                 "review_status": r.review_status}
                for r in relations
            ],
            "properties": [
                {"id": a.id, "object_id": a.object_id, "standard_id": a.standard_id,
                 "required": a.required, "review_status": a.review_status}
                for a in attributes
            ],
            "mappings": {
                "table": [
                    {"id": tm.id, "table_id": tm.table_id,
                     "object_standard_id": tm.object_standard_id, "source": tm.source}
                    for tm in table_maps
                ],
                "column": [
                    {"id": cm.id, "column_id": cm.column_id,
                     "standard_id": cm.standard_id, "source": cm.source}
                    for cm in column_maps
                ],
            },
            "cq": [
                {"id": c.id, "question": c.question, "category": c.category,
                 "verify_status": c.verify_status, "version": c.version}
                for c in cq_rows
            ],
        }

    # ------------------------------------------------------------ 防线③：source 断言

    def _assert_source(self, snapshot: dict) -> None:
        """D3 rev.2 出口层：快照元素 ``source`` 必须 ∈ {{rule, human}}，不得含 ``llm_draft``。

        先行于 5 项门禁、**不参与 override**（§5.7 / §4.5 附加强断言）。
        """
        offenders: List[str] = []
        for o in snapshot["objects"]:
            if o["source"] == "llm_draft":
                offenders.append(f"object:{o['code']}")
        for r in snapshot["relations"]:
            if r["source"] == "llm_draft":
                offenders.append(f"relation:{r['code']}")
        for tm in snapshot["mappings"]["table"]:
            if tm["source"] == "llm_draft":
                offenders.append(f"table_mapping:{tm['id']}")
        for cm in snapshot["mappings"]["column"]:
            if cm["source"] == "llm_draft":
                offenders.append(f"column_mapping:{cm['id']}")
        if offenders:
            raise ApiError(
                PUBLISH_BLOCKED_UNREVIEWED_SOURCE,
                "发布被阻断：快照含未人工确认的 LLM 草稿来源元素",
                detail={"offenders": offenders[:50], "count": len(offenders)},
            )

    # ------------------------------------------------------------ 门禁 1~5

    def _gate1_pending(self, job_ids: List[int], override: bool) -> dict:
        pending = 0
        if job_ids:
            pending = int(self.db.execute(
                select(func.count()).select_from(MetaOntologyBuildItem).where(
                    MetaOntologyBuildItem.tenant_id == self.tenant_id,
                    MetaOntologyBuildItem.job_id.in_(job_ids),
                    MetaOntologyBuildItem.status == "suggested",
                )
            ).scalar_one())
        check = {"gate": 1, "name": "no_pending_candidates", "passed": pending == 0 or override,
                 "pending": pending}
        if pending and not override:
            check["blocked_code"] = PUBLISH_BLOCKED_PENDING_REVIEW
            check["reason"] = f"仍有 {pending} 条未决候选"
        elif pending and override:
            check["override"] = True
        return check

    def _gate2_integrity(self, snapshot: dict) -> dict:
        obj_ids = {o["id"] for o in snapshot["objects"]}
        issues: List[str] = []
        # 关系两端对象必须存在且已采纳
        accepted_obj = {o["id"] for o in snapshot["objects"] if o["review_status"] == "accepted"}
        for r in snapshot["relations"]:
            if r["from_object_id"] not in obj_ids:
                issues.append(f"relation:{r['code']} 缺失 from 对象")
            elif r["from_object_id"] not in accepted_obj:
                issues.append(f"relation:{r['code']} from 对象未采纳")
            if r["to_object_id"] not in obj_ids:
                issues.append(f"relation:{r['code']} 缺失 to 对象")
            elif r["to_object_id"] not in accepted_obj:
                issues.append(f"relation:{r['code']} to 对象未采纳")
        # 属性归属对象必须存在
        for a in snapshot["properties"]:
            if a["object_id"] not in obj_ids:
                issues.append(f"property:{a['id']} 归属对象缺失")
        # 映射的表/列必须真实存在
        table_ids = {tm["table_id"] for tm in snapshot["mappings"]["table"]}
        if table_ids:
            existing = set(self.db.execute(
                select(MetaTable.id).where(
                    MetaTable.tenant_id == self.tenant_id, MetaTable.id.in_(list(table_ids))
                )
            ).scalars().all())
            for tid in table_ids - existing:
                issues.append(f"table_mapping 引用不存在的表 id={tid}")
        col_ids = {cm["column_id"] for cm in snapshot["mappings"]["column"]}
        if col_ids:
            existing_cols = set(self.db.execute(
                select(MetaColumn.id).where(
                    MetaColumn.tenant_id == self.tenant_id, MetaColumn.id.in_(list(col_ids))
                )
            ).scalars().all())
            for cid in col_ids - existing_cols:
                issues.append(f"column_mapping 引用不存在的列 id={cid}")
        check = {"gate": 2, "name": "structural_integrity", "passed": not issues}
        if issues:
            check["blocked_code"] = PUBLISH_BLOCKED_INTEGRITY
            check["reason"] = "；".join(issues[:20])
            check["issues"] = issues[:50]
        return check

    def _gate3_regression(self, snapshot: dict, prev: Optional[dict]) -> dict:
        regressions: List[str] = []
        if prev:
            cur_obj_codes = {o["code"] for o in snapshot["objects"]}
            prev_obj_codes = {o["code"] for o in prev.get("objects", [])}
            removed = prev_obj_codes - cur_obj_codes
            # 被现存关系引用的对象消失 → 回归
            code_to_id = {o["code"]: o["id"] for o in prev.get("objects", [])}
            for r in snapshot["relations"]:
                for side in ("from_object_id", "to_object_id"):
                    rid = r[side]
                    removed_code = next(
                        (c for c in removed if code_to_id.get(c) == rid), None
                    )
                    if removed_code:
                        regressions.append(
                            f"关系 {r['code']} 仍引用已消失对象 {removed_code}"
                        )
        check = {"gate": 3, "name": "no_regression", "passed": not regressions}
        if regressions:
            check["blocked_code"] = PUBLISH_BLOCKED_REGRESSION
            check["reason"] = "；".join(regressions[:10])
        return check

    def _gate4_cq_coverage(self, snapshot: dict) -> dict:
        cq = snapshot.get("cq", [])
        total = len(cq)
        passed = sum(1 for c in cq if c["verify_status"] == "passed")
        ratio = (passed / total) if total else None
        check = {"gate": 4, "name": "cq_coverage", "total": total, "passed": passed,
                 "ratio": ratio, "threshold": CQ_COVERAGE_THRESHOLD}
        if total == 0:
            check["passed"] = True
            check["warn"] = "无 CQ，跳过覆盖度校验"
        elif ratio is not None and ratio < CQ_COVERAGE_THRESHOLD:
            # §6.1 错误码枚举无 CQ 专用码 → 本期记 warn 不阻断（保持契约对齐）
            check["passed"] = True
            check["warn"] = f"CQ 通过率 {ratio:.0%} 低于阈值 {CQ_COVERAGE_THRESHOLD:.0%}"
        else:
            check["passed"] = True
        return check

    def _gate5_mask_coverage(self, snapshot: dict, exemptions: List[int]) -> dict:
        column_maps = snapshot["mappings"]["column"]
        if not column_maps:
            return {"gate": 5, "name": "mask_coverage", "passed": True, "sensitive": 0}
        col_ids = [cm["column_id"] for cm in column_maps]
        std_ids = sorted({cm["standard_id"] for cm in column_maps})
        # 列 pii_level
        pii_map = dict(self.db.execute(
            select(MetaColumn.id, MetaColumn.pii_level).where(
                MetaColumn.tenant_id == self.tenant_id, MetaColumn.id.in_(col_ids)
            )
        ).all())
        # 标准 mask_rule
        mask_map = dict(self.db.execute(
            select(MetaStandard.id, MetaStandard.mask_rule).where(
                MetaStandard.tenant_id == self.tenant_id, MetaStandard.id.in_(std_ids)
            )
        ).all())
        override_map = {cm["column_id"]: cm for cm in column_maps}
        missing: List[str] = []
        exempt_set = set(exemptions or [])
        for cm in column_maps:
            pii = pii_map.get(cm["column_id"])
            if pii not in _SENSITIVE_PII:
                continue
            if cm["column_id"] in exempt_set:
                continue
            mask = mask_map.get(cm["standard_id"])
            # 已绑定标准且 mask_rule 非空 → 覆盖
            if mask:
                continue
            # 安全等级显式降级至 L1 以下 → 覆盖
            ovr = (override_map.get(cm["column_id"]) or {}).get("security_level_override")
            if ovr and ovr not in _SENSITIVE_PII:
                continue
            missing.append(f"column:{cm['column_id']} pii={pii}")
        check = {"gate": 5, "name": "mask_coverage", "passed": not missing,
                 "sensitive": sum(1 for c in column_maps if pii_map.get(c['column_id']) in _SENSITIVE_PII)}
        if missing:
            check["blocked_code"] = PUBLISH_BLOCKED_MASK_COVERAGE
            check["reason"] = f"{len(missing)} 个敏感列缺脱敏覆盖"
            check["missing"] = missing[:50]
        return check

    # ------------------------------------------------------------ diff

    def _diff(self, snapshot: dict, prev: Optional[dict]) -> dict:
        if not prev:
            return {
                "added": {
                    "objects": [o["code"] for o in snapshot["objects"]],
                    "relations": [r["code"] for r in snapshot["relations"]],
                    "properties": len(snapshot["properties"]),
                },
                "removed": {"objects": [], "relations": []},
                "changed": [],
                "regressions": [],
            }
        cur_o = {o["code"]: o for o in snapshot["objects"]}
        prev_o = {o["code"]: o for o in prev.get("objects", [])}
        cur_r = {r["code"]: r for r in snapshot["relations"]}
        prev_r = {r["code"]: r for r in prev.get("relations", [])}
        added_obj = sorted(set(cur_o) - set(prev_o))
        removed_obj = sorted(set(prev_o) - set(cur_o))
        added_rel = sorted(set(cur_r) - set(prev_r))
        removed_rel = sorted(set(prev_r) - set(cur_r))
        changed = []
        for code in set(cur_o) & set(prev_o):
            if cur_o[code]["name"] != prev_o[code]["name"]:
                changed.append({"kind": "object", "code": code,
                                "from": prev_o[code]["name"], "to": cur_o[code]["name"]})
        for code in set(cur_r) & set(prev_r):
            if (cur_r[code]["from_object_id"], cur_r[code]["to_object_id"]) != (
                prev_r[code]["from_object_id"], prev_r[code]["to_object_id"]
            ):
                changed.append({"kind": "relation", "code": code, "field": "endpoints"})
        # 回归明细（与门禁 3 同源，供 diff 展示）
        regressions = []
        code_to_prev_id = {o["code"]: o["id"] for o in prev.get("objects", [])}
        for r in snapshot["relations"]:
            for side in ("from_object_id", "to_object_id"):
                gone = next((c for c in removed_obj if code_to_prev_id.get(c) == r[side]), None)
                if gone:
                    regressions.append(f"relation:{r['code']} → 缺失对象 {gone}")
        return {
            "added": {"objects": added_obj, "relations": added_rel,
                      "properties": max(0, len(snapshot["properties"]) - len(prev.get("properties", [])))},
            "removed": {"objects": removed_obj, "relations": removed_rel},
            "changed": changed,
            "regressions": regressions,
        }

    # ------------------------------------------------------------ E11 发布

    def publish(
        self, ontology_id: int, *,
        change_note: Optional[str] = None,
        author_user_id: Optional[int] = None,
        override_pending: bool = False,
        mask_exemptions: Optional[List[int]] = None,
    ) -> dict:
        ontology = self._ontology_or_404(ontology_id)
        job_ids = self._job_ids(ontology_id)
        snapshot = self.build_snapshot(ontology_id)

        # 防线③（出口层）先行、不参与 override
        self._assert_source(snapshot)

        # 上一版本快照（回归 / diff 基线）
        prev: Optional[dict] = None
        if ontology.current_version and ontology.current_version > 0:
            prev_row = self.db.execute(
                select(MetaOntologyVersion).where(
                    MetaOntologyVersion.tenant_id == self.tenant_id,
                    MetaOntologyVersion.ontology_id == ontology_id,
                    MetaOntologyVersion.version == ontology.current_version,
                )
            ).scalar_one_or_none()
            if prev_row is not None:
                prev = prev_row.snapshot_json

        checks = [
            self._gate1_pending(job_ids, override_pending),
            self._gate2_integrity(snapshot),
            self._gate3_regression(snapshot, prev),
            self._gate4_cq_coverage(snapshot),
            self._gate5_mask_coverage(snapshot, mask_exemptions or []),
        ]
        blocked = [c for c in checks if not c.get("passed")]
        gate_json = {
            "passed": not blocked,
            "checks": checks,
            "blocked_reasons": [f"#{c['gate']} {c.get('reason', '')}".strip() for c in blocked],
            "exemptions": list(mask_exemptions or []),
        }
        if blocked:
            first = blocked[0]
            raise ApiError(
                first.get("blocked_code", "PUBLISH_BLOCKED"),
                f"发布门禁未通过：第 {first['gate']} 项 {first['name']} 失败",
                detail={"gate_json": gate_json},
            )

        diff_json = self._diff(snapshot, prev)
        new_version = int(ontology.current_version or 0) + 1

        # 先写快照 → 元素 status=published → current_version 自增（§4.5 顺序）
        version_row = MetaOntologyVersion(
            tenant_id=self.tenant_id,
            ontology_id=ontology_id,
            version=new_version,
            snapshot_json=snapshot,
            diff_json=diff_json,
            gate_json=gate_json,
            change_note=change_note,
            author_user_id=author_user_id,
        )
        self.db.add(version_row)

        obj_ids = [o["id"] for o in snapshot["objects"]]
        if obj_ids:
            self.db.execute(
                MetaObjectStandard.__table__.update()
                .where(MetaObjectStandard.tenant_id == self.tenant_id,
                       MetaObjectStandard.id.in_(obj_ids))
                .values(status="published")
            )
        rel_ids = [r["id"] for r in snapshot["relations"]]
        if rel_ids:
            self.db.execute(
                MetaObjectRelation.__table__.update()
                .where(MetaObjectRelation.tenant_id == self.tenant_id,
                       MetaObjectRelation.id.in_(rel_ids))
                .values(status="published")
            )

        ontology.current_version = new_version
        ontology.status = "published"
        self.db.flush()

        return self.serialize_version(version_row)

    # ------------------------------------------------------------ E12 版本列表

    def list_versions(self, ontology_id: int) -> List[dict]:
        self._ontology_or_404(ontology_id)
        rows = self.db.execute(
            select(MetaOntologyVersion).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
            ).order_by(MetaOntologyVersion.version.desc())
        ).scalars().all()
        return [self.serialize_version(r, summary=True) for r in rows]

    # ------------------------------------------------------------ E13 版本快照

    def get_version(self, ontology_id: int, version: int) -> dict:
        self._ontology_or_404(ontology_id)
        row = self.db.execute(
            select(MetaOntologyVersion).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
                MetaOntologyVersion.version == version,
            )
        ).scalar_one_or_none()
        if row is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "版本不存在", http_status=404,
                           detail={"ontology_id": ontology_id, "version": version})
        return self.serialize_version(row, full=True)

    # ------------------------------------------------------------ 序列化

    @staticmethod
    def serialize_version(r: MetaOntologyVersion, *, summary: bool = False, full: bool = False) -> dict:
        payload: dict = {
            "id": r.id,
            "ontology_id": r.ontology_id,
            "version": r.version,
            "change_note": r.change_note,
            "author_user_id": r.author_user_id,
            "created_at": _iso(r.created_at),
        }
        if summary:
            snap = r.snapshot_json or {}
            payload["counts"] = {
                "objects": len(snap.get("objects", [])),
                "relations": len(snap.get("relations", [])),
                "properties": len(snap.get("properties", [])),
            }
            gate = r.gate_json or {}
            payload["gate_passed"] = gate.get("passed")
            return payload
        payload["gate_json"] = r.gate_json
        payload["diff_json"] = r.diff_json
        if full:
            payload["snapshot_json"] = r.snapshot_json
        return payload
