"""关系标准服务（B4）：对象→对象关系 CRUD + 跨场景软提醒。

关系标准不复制字段，只声明「对象 A 与对象 B 之间应存在 relation_type 关系」，
由 ``StandardBindingService._check_relations`` 对照物理库推断出的 ``meta_relation``
落三态结论（hit / missing / conflict）。删除时校验结论随 CASCADE 清理。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaStandardCatalog,
)

#: 关系类型白名单（与 spec 一致）。
RELATION_TYPES = ("1:1", "1:N", "N:1", "N:N")


class MetaObjectRelationService:
    """关系标准读写（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaObjectRelationService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def get_or_404(self, relation_id: int) -> MetaObjectRelation:
        obj = self.db.execute(
            select(MetaObjectRelation).where(
                MetaObjectRelation.tenant_id == self.tenant_id,
                MetaObjectRelation.id == relation_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            raise KeyError(relation_id)
        return obj

    def _by_code(self, code: str) -> Optional[MetaObjectRelation]:
        return self.db.execute(
            select(MetaObjectRelation).where(
                MetaObjectRelation.tenant_id == self.tenant_id,
                MetaObjectRelation.code == code,
            )
        ).scalar_one_or_none()

    def _object(self, object_id: int) -> MetaObjectStandard:
        obj = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.id == object_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ValueError(f"对象标准不存在或跨租户: {object_id}")
        return obj

    def list(self, catalog_id: Optional[int] = None) -> List[MetaObjectRelation]:
        stmt = select(MetaObjectRelation).where(
            MetaObjectRelation.tenant_id == self.tenant_id
        )
        if catalog_id is not None:
            stmt = stmt.where(MetaObjectRelation.catalog_id == catalog_id)
        return list(self.db.execute(stmt.order_by(MetaObjectRelation.code)).scalars().all())

    def create(
        self,
        code: str,
        name: str,
        from_object_id: int,
        to_object_id: int,
        relation_type: str,
        *,
        catalog_id: Optional[int] = None,
        via_attribute_ids: Optional[list] = None,
        description: Optional[str] = None,
        creator_id: Optional[int] = None,
    ) -> MetaObjectRelation:
        if self._by_code(code) is not None:
            raise ValueError(f"关系标准编码已存在: {code}")
        if relation_type not in RELATION_TYPES:
            raise ValueError(f"非法关系类型: {relation_type}（可选 {'|'.join(RELATION_TYPES)}）")
        if from_object_id == to_object_id:
            raise ValueError("关系两端不能是同一个对象")
        self._object(from_object_id)
        self._object(to_object_id)
        obj = MetaObjectRelation(
            tenant_id=self.tenant_id,
            code=code,
            name=name,
            from_object_id=from_object_id,
            to_object_id=to_object_id,
            relation_type=relation_type,
            catalog_id=catalog_id,
            via_attribute_ids=via_attribute_ids or [],
            description=description,
            status="published",
            creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, relation_id: int, **fields) -> MetaObjectRelation:
        obj = self.get_or_404(relation_id)
        new_code = fields.get("code")
        if new_code is not None and new_code != obj.code:
            conflict = self._by_code(new_code)
            if conflict is not None and conflict.id != obj.id:
                raise ValueError(f"关系标准编码已存在: {new_code}")
        new_type = fields.get("relation_type")
        if new_type is not None and new_type not in RELATION_TYPES:
            raise ValueError(f"非法关系类型: {new_type}（可选 {'|'.join(RELATION_TYPES)}）")
        for key, value in fields.items():
            if value is None:
                continue
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, relation_id: int) -> None:
        """删除关系标准（校验结论 CASCADE 自动清理）。"""
        obj = self.get_or_404(relation_id)
        self.db.delete(obj)
        self.db.flush()

    def _catalog_root(self, catalog_id: Optional[int]) -> Optional[int]:
        """沿 parent_id 上溯到根目录（未归类返回 None）。"""
        current = catalog_id
        seen = set()
        while current is not None and current not in seen:
            seen.add(current)
            row = self.db.execute(
                select(MetaStandardCatalog.parent_id).where(
                    MetaStandardCatalog.tenant_id == self.tenant_id,
                    MetaStandardCatalog.id == current,
                )
            ).first()
            if row is None:
                return current
            if row[0] is None:
                return current
            current = row[0]
        return current

    def cross_catalog_warning(self, relation_id: int) -> Optional[str]:
        """两端对象属于不同场景子树时给出软提醒（不阻断创建）。"""
        rel = self.get_or_404(relation_id)
        from_root = self._catalog_root(self._object(rel.from_object_id).catalog_id)
        to_root = self._catalog_root(self._object(rel.to_object_id).catalog_id)
        if from_root is None or to_root is None:
            return None
        if from_root != to_root:
            return "关系两端对象属于不同场景目录，请确认这是跨场景关系"
        return None

    @staticmethod
    def serialize(r: MetaObjectRelation) -> dict:
        return {
            "id": r.id,
            "catalog_id": r.catalog_id,
            "code": r.code,
            "name": r.name,
            "from_object_id": r.from_object_id,
            "to_object_id": r.to_object_id,
            "relation_type": r.relation_type,
            "via_attribute_ids": r.via_attribute_ids or [],
            "description": r.description,
            "status": r.status,
        }
