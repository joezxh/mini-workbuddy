"""本体审阅服务（P0-4：待审队列 E9 + 采纳/驳回 E10，spec §4.5 / §6.1）。

为什么以 ``build_item`` 为队列主体：
- 每次构建的候选天然按 job→ontology 归属，跨 job 聚合即"本体的当前候选台账"；
- 结构表元素的 ``catalog_id`` 可能为空（新建租户无根目录），用目录子树反查会漏；
  build_item 记 ``element_id`` 直连结构行，稳妥；
- D3 rev.2 防线②：``origin='llm'`` 候选只能停 ``suggested``，人工采纳才落结构并把 ``source`` 改写为
  ``human``；规则候选采纳后 ``source`` 维持 ``rule``（§5.1 三值迁移表）。

事务边界在路由层：本服务只 flush。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_error import ApiError, REVIEW_ITEM_NOT_FOUND
from app.models.ontology.ontology import (
    MetaOntology, MetaOntologyBuildItem, MetaOntologyBuildJob,
)
from app.models.dataops.standard import MetaColumnStandard
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute, MetaTableStandard,
)

_KIND_TO_MODEL = {
    "object": MetaObjectStandard,
    "relation": MetaObjectRelation,
    "property": MetaObjectStandardAttribute,
}


class OntologyReviewService:
    """审阅队列与批量采纳/驳回（按 tenant_id 隔离）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyReviewService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError("ONTOLOGY_NOT_FOUND", "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    def _job_ids(self, ontology_id: int) -> List[int]:
        return list(self.db.execute(
            select(MetaOntologyBuildJob.id).where(
                MetaOntologyBuildJob.tenant_id == self.tenant_id,
                MetaOntologyBuildJob.ontology_id == ontology_id,
            )
        ).scalars().all())

    # --------------------------------------------------------------- E9 队列

    def review_queue(
        self, ontology_id: int, *,
        kind: Optional[str] = None,
        status: str = "suggested",
        origin: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        self._ontology_or_404(ontology_id)
        job_ids = self._job_ids(ontology_id)
        if not job_ids:
            return {"total": 0, "page": page, "size": size, "pending": self.pending_count(ontology_id),
                    "items": []}
        stmt = select(MetaOntologyBuildItem).where(
            MetaOntologyBuildItem.tenant_id == self.tenant_id,
            MetaOntologyBuildItem.job_id.in_(job_ids),
        )
        if status:
            stmt = stmt.where(MetaOntologyBuildItem.status == status)
        if kind:
            stmt = stmt.where(MetaOntologyBuildItem.element_kind == kind)
        if origin:
            stmt = stmt.where(MetaOntologyBuildItem.origin == origin)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        rows = list(self.db.execute(
            stmt.order_by(MetaOntologyBuildItem.element_kind, MetaOntologyBuildItem.id)
            .offset((page - 1) * size).limit(size)
        ).scalars().all())
        return {
            "total": int(total), "page": page, "size": size,
            "pending": self.pending_count(ontology_id),
            "items": [self._serialize_item(r) for r in rows],
        }

    def pending_count(self, ontology_id: int) -> dict:
        """门禁第 1 项所需的各类未决（suggested）计数。"""
        job_ids = self._job_ids(ontology_id)
        out = {"object": 0, "property": 0, "relation": 0, "mapping": 0, "total": 0}
        if not job_ids:
            return out
        rows = self.db.execute(
            select(MetaOntologyBuildItem.element_kind, func.count())
            .where(
                MetaOntologyBuildItem.tenant_id == self.tenant_id,
                MetaOntologyBuildItem.job_id.in_(job_ids),
                MetaOntologyBuildItem.status == "suggested",
            )
            .group_by(MetaOntologyBuildItem.element_kind)
        ).all()
        for kind, cnt in rows:
            if kind in out:
                out[kind] = int(cnt)
            out["total"] += int(cnt)
        return out

    @staticmethod
    def _serialize_item(r: MetaOntologyBuildItem) -> dict:
        return {
            "id": r.id,
            "job_id": r.job_id,
            "element_kind": r.element_kind,
            "element_code": r.element_code,
            "action": r.action,
            "origin": r.origin,
            "verdict": r.verdict,
            "verdict_reason": r.verdict_reason,
            "confidence": r.confidence,
            "status": r.status,
            "element_id": r.element_id,
            "delta": r.delta_json,
        }

    # --------------------------------------------------------------- E10 采纳/驳回

    def review(
        self, ontology_id: int, *,
        items: Optional[List[dict]] = None,
        accept_all: bool = False,
        reject_all: bool = False,
        reviewed_by: Optional[int] = None,
    ) -> dict:
        """批量审阅：``items=[{id, action}]`` 精确操作；``accept_all``/``reject_all`` 作用于全部 suggested。

        D3 rev.2 防线②：origin='llm' 候选采纳 → 结构行 ``source='human'``（改写），
        origin='rule' 采纳 → ``source`` 维持 ``rule``。驳回仅置 ``rejected``，元素不入发布快照。
        """
        self._ontology_or_404(ontology_id)
        job_ids = self._job_ids(ontology_id)
        accepted = rejected = 0

        if (accept_all or reject_all) and job_ids:
            act = "accept" if accept_all else "reject"
            targets = list(self.db.execute(
                select(MetaOntologyBuildItem).where(
                    MetaOntologyBuildItem.tenant_id == self.tenant_id,
                    MetaOntologyBuildItem.job_id.in_(job_ids),
                    MetaOntologyBuildItem.status == "suggested",
                )
                # #2：object 先于 relation 处理，保证 LLM 关系采纳时两端对象已落库
                .order_by(MetaOntologyBuildItem.element_kind, MetaOntologyBuildItem.id)
            ).scalars().all())
            for it in targets:
                self._apply(it, act, reviewed_by)
                accepted += act == "accept"
                rejected += act == "reject"

        for spec in (items or []):
            item_id = spec.get("id")
            action = (spec.get("action") or "").lower()
            if action not in ("accept", "reject"):
                continue
            it = self.db.execute(
                select(MetaOntologyBuildItem).where(
                    MetaOntologyBuildItem.tenant_id == self.tenant_id,
                    MetaOntologyBuildItem.id == item_id,
                )
            ).scalar_one_or_none()
            if it is None:
                raise ApiError(REVIEW_ITEM_NOT_FOUND, "审阅项不存在", http_status=404,
                               detail={"id": item_id})
            self._apply(it, action, reviewed_by)
            accepted += action == "accept"
            rejected += action == "reject"

        self.db.flush()
        return {"accepted": accepted, "rejected": rejected,
                "pending": self.pending_count(ontology_id)}

    def _apply(self, it: MetaOntologyBuildItem, action: str, reviewed_by: Optional[int]) -> None:
        new_status = "accepted" if action == "accept" else "rejected"
        it.status = new_status
        self._sync_structural(it, new_status, reviewed_by)

    def _sync_structural(
        self, it: MetaOntologyBuildItem, new_status: str, reviewed_by: Optional[int]
    ) -> None:
        """把候选结论回写到结构行（object/relation/property 直接；mapping 尽力而为）。

        #2 采纳闭环：``origin='llm'`` 候选在构建期只落 ``build_item``、**不建结构行**
        （``element_id`` 为空，D3 防线①）；此处人工采纳时依 ``delta_json`` 落结构行并回填
        ``element_id``，来源写死 ``human``（llm 值本就非法，人工确认即 human，见 §5.1 三值迁移）。
        """
        kind = it.element_kind
        if kind in _KIND_TO_MODEL:
            if it.element_id is None and new_status == "accepted" and it.origin == "llm":
                mid = self._materialize_llm_element(it, reviewed_by)
                if mid is not None:
                    it.element_id = mid
            if it.element_id:
                model = _KIND_TO_MODEL[kind]
                row = self.db.get(model, it.element_id)
                if row is not None:
                    row.review_status = new_status
                    if kind in ("object", "relation"):
                        if reviewed_by is not None:
                            row.reviewed_by = reviewed_by
                        row.reviewed_at = func.now()
                        # D3 防线②：LLM 候选被人工采纳 → 改写来源为 human（llm 值本就非法）
                        if new_status == "accepted" and row.source == "llm_draft":
                            row.source = "human"
                    return
        # mapping：按 element_id 落 meta_table_standard / meta_column_standard
        if kind == "mapping" and it.element_id:
            for model in (MetaTableStandard, MetaColumnStandard):
                row = self.db.get(model, it.element_id)
                if row is not None:
                    row.status = new_status
                    if reviewed_by is not None:
                        row.reviewed_by = reviewed_by
                    row.reviewed_at = func.now()
                    if new_status == "accepted" and getattr(row, "source", None) == "llm_draft":
                        row.source = "human"
                    break

    # ------------------------------------------- #2 LLM 候选采纳→落结构行

    def _materialize_llm_element(
        self, it: MetaOntologyBuildItem, reviewed_by: Optional[int]
    ) -> Optional[int]:
        """人工采纳 ``origin='llm'`` 候选时依 ``delta_json`` 创建结构行，返回 element_id。

        幂等：同租户内同 code 的结构行已存在则直接复用（防 ``uq(tenant, code)`` 冲突）；
        relation 需 ``from``/``to`` 两端对象均已存在（同批 accept_all 时对象先于关系处理，
        因为队列按 element_kind 排序：object < relation）；任一端无法解析则不建关系行，
        候选仍保持 accepted 状态但不入发布快照（发布门禁第 3 项完整性校验会兜底）。
        """
        delta = it.delta_json or {}
        if it.element_kind == "object":
            return self._materialize_object(it, delta, reviewed_by)
        if it.element_kind == "relation":
            return self._materialize_relation(it, delta, reviewed_by)
        return None

    def _materialize_object(
        self, it: MetaOntologyBuildItem, delta: dict, reviewed_by: Optional[int]
    ) -> Optional[int]:
        existing = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.code == it.element_code,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id
        name = str(delta.get("name") or it.element_code)[:200]
        row = MetaObjectStandard(
            tenant_id=self.tenant_id, catalog_id=None, code=it.element_code[:64],
            name=name, description=delta.get("definition") or delta.get("description"),
            domain=None, status="draft", source="human",
            review_status="accepted", reviewed_by=reviewed_by, reviewed_at=func.now(),
            confidence=it.confidence,
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    def _materialize_relation(
        self, it: MetaOntologyBuildItem, delta: dict, reviewed_by: Optional[int]
    ) -> Optional[int]:
        existing = self.db.execute(
            select(MetaObjectRelation).where(
                MetaObjectRelation.tenant_id == self.tenant_id,
                MetaObjectRelation.code == it.element_code,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id
        left = self._find_object(delta.get("from") or delta.get("from_object_code"))
        right = self._find_object(delta.get("to") or delta.get("to_object_code"))
        if left is None or right is None:
            return None
        row = MetaObjectRelation(
            tenant_id=self.tenant_id, catalog_id=None, code=it.element_code[:64],
            name=str(delta.get("name") or f"{left.name}→{right.name}")[:200],
            from_object_id=left.id, to_object_id=right.id,
            relation_type=str(delta.get("relation_type") or "N:1")[:16],
            description=delta.get("definition") or delta.get("description"),
            status="draft", source="human",
            review_status="accepted", reviewed_by=reviewed_by, reviewed_at=func.now(),
            confidence=it.confidence,
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    def _find_object(self, code) -> Optional[MetaObjectStandard]:
        if not code:
            return None
        return self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.code == str(code)[:64],
            )
        ).scalar_one_or_none()
