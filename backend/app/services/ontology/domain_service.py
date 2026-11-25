"""本体领域字典服务（分组维度 CRUD，按 tenant_id 隔离）。

与 OntologyTagService 同构：构造要求 tenant_id 非空，读一律显式过滤租户，
业务错误抛 ApiError（{code,message,detail?}），事务边界在路由层（本服务只 flush）。

删除策略：领域为可选标注，外键 ON DELETE SET NULL 会自动解除 meta_table /
onto_ontology 的引用，故删除不做"被引用即拒绝"守卫，但要回传清零数量便于前端提示。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_error import ApiError, DOMAIN_CODE_DUPLICATED, DOMAIN_NOT_FOUND
from app.models.dataops.meta import MetaTable
from app.models.ontology.domain import OntoDomain
from app.models.ontology.ontology import MetaOntology

_VALID_STATUS = ("active", "disabled")


class OntologyDomainService:
    """本体领域 CRUD + 引用计数（按 tenant_id 隔离）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyDomainService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _domain_or_404(self, domain_id: int) -> OntoDomain:
        obj = self.db.execute(
            select(OntoDomain).where(
                OntoDomain.tenant_id == self.tenant_id, OntoDomain.id == domain_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(DOMAIN_NOT_FOUND, "本体领域不存在", http_status=404, detail={"id": domain_id})
        return obj

    def resolve(self, domain_id: Optional[int]) -> Optional[OntoDomain]:
        """校验本体/元数据表提交的领域 ID：空=未分类；非空须同租户且 active。"""
        if domain_id is None:
            return None
        obj = self._domain_or_404(int(domain_id))
        if obj.status != "active":
            raise ApiError(DOMAIN_NOT_FOUND, "本体领域已停用", detail={"id": domain_id, "status": obj.status})
        return obj

    def domain_names(self, ids: List[int]) -> dict:
        """一次 IN 批量取 id→name，消除列表序列化的 N+1。"""
        valid = [int(i) for i in ids if i is not None]
        if not valid:
            return {}
        rows = self.db.execute(
            select(OntoDomain.id, OntoDomain.name).where(
                OntoDomain.tenant_id == self.tenant_id, OntoDomain.id.in_(valid)
            )
        ).all()
        return {int(r.id): r.name for r in rows}

    @staticmethod
    def serialize(o: OntoDomain, reference_count: Optional[int] = None) -> dict:
        data = {
            "id": o.id,
            "code": o.code,
            "name": o.name,
            "description": o.description,
            "sort_order": o.sort_order,
            "status": o.status,
            "creator_id": o.creator_id,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        }
        if reference_count is not None:
            data["reference_count"] = int(reference_count)
        return data

    def list_domains(self, *, status: Optional[str] = None, keyword: Optional[str] = None) -> List[dict]:
        stmt = select(OntoDomain).where(OntoDomain.tenant_id == self.tenant_id)
        if status:
            stmt = stmt.where(OntoDomain.status == status)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(OntoDomain.code.ilike(like), OntoDomain.name.ilike(like)))
        rows = list(self.db.execute(
            stmt.order_by(OntoDomain.sort_order, OntoDomain.id)
        ).scalars().all())
        counts: dict = {}
        if rows:
            for table in (MetaTable, MetaOntology):
                for did, cnt in self.db.execute(
                    select(table.domain_id, func.count())
                    .where(table.tenant_id == self.tenant_id, table.domain_id.in_([o.id for o in rows]))
                    .group_by(table.domain_id)
                ).all():
                    counts[int(did)] = counts.get(int(did), 0) + int(cnt)
        return [self.serialize(o, counts.get(o.id, 0)) for o in rows]

    def create_domain(self, *, code: str, name: str, description: Optional[str] = None,
                      sort_order: int = 0, status: str = "active",
                      creator_id: Optional[int] = None) -> dict:
        code = (code or "").strip()
        name = (name or "").strip()
        if not code or not name:
            raise ApiError(DOMAIN_CODE_DUPLICATED, "领域编码与名称不能为空")
        if status not in _VALID_STATUS:
            status = "active"
        dup = self.db.execute(
            select(OntoDomain.id).where(
                OntoDomain.tenant_id == self.tenant_id, OntoDomain.code == code
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise ApiError(DOMAIN_CODE_DUPLICATED, f"领域编码已存在: {code}",
                           http_status=409, detail={"code": code})
        obj = OntoDomain(
            tenant_id=self.tenant_id, code=code, name=name, description=description,
            sort_order=int(sort_order or 0), status=status, creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        return self.serialize(obj, 0)

    def update_domain(self, domain_id: int, *, updater_id: Optional[int] = None, **fields) -> dict:
        obj = self._domain_or_404(domain_id)
        if "code" in fields and fields["code"] is not None:
            new_code = str(fields["code"]).strip()
            dup = self.db.execute(
                select(OntoDomain.id).where(
                    OntoDomain.tenant_id == self.tenant_id,
                    OntoDomain.code == new_code, OntoDomain.id != domain_id,
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise ApiError(DOMAIN_CODE_DUPLICATED, f"领域编码已存在: {new_code}",
                               http_status=409, detail={"code": new_code})
            obj.code = new_code
        for key in ("name", "description", "sort_order", "status"):
            if key in fields and fields[key] is not None:
                setattr(obj, key, fields[key])
        if obj.status not in _VALID_STATUS:
            obj.status = "active"
        obj.updater_id = updater_id
        self.db.flush()
        return self.serialize(obj, self._reference_count(domain_id))

    def toggle_domain(self, domain_id: int, *, status: str,
                      updater_id: Optional[int] = None) -> dict:
        if status not in _VALID_STATUS:
            raise ApiError(DOMAIN_NOT_FOUND, "status 必须为 active 或 disabled", detail={"status": status})
        obj = self._domain_or_404(domain_id)
        obj.status = status
        obj.updater_id = updater_id
        self.db.flush()
        return self.serialize(obj, self._reference_count(domain_id))

    def delete_domain(self, domain_id: int) -> dict:
        obj = self._domain_or_404(domain_id)
        affected = self._reference_count(domain_id)
        self.db.delete(obj)
        self.db.flush()
        return {"id": domain_id, "detached": affected}

    def _reference_count(self, domain_id: int) -> int:
        a = self.db.execute(
            select(func.count()).select_from(MetaTable).where(
                MetaTable.tenant_id == self.tenant_id, MetaTable.domain_id == domain_id
            )
        ).scalar_one()
        b = self.db.execute(
            select(func.count()).select_from(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.domain_id == domain_id
            )
        ).scalar_one()
        return int(a) + int(b)
