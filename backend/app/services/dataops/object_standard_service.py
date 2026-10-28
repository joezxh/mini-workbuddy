"""对象标准服务（B2）：对象 CRUD + 引用属性（全量替换）。

对象标准是「表级」标准模板：它不复制属性定义，而是引用全局属性标准
（``meta_standard``），落地属性跨对象复用。删除保护：被关系引用或已被物理表
绑定即拒绝（RESTRICT）；引用属性关联随对象 CASCADE。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.dataops.standard import MetaStandard
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaObjectStandardAttribute,
    MetaTableStandard,
)


class MetaObjectStandardService:
    """对象标准读写（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaObjectStandardService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def get_or_404(self, object_id: int) -> MetaObjectStandard:
        obj = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.id == object_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            raise KeyError(object_id)
        return obj

    def _by_code(self, code: str) -> Optional[MetaObjectStandard]:
        return self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.code == code,
            )
        ).scalar_one_or_none()

    def list(self, catalog_id: Optional[int] = None) -> List[MetaObjectStandard]:
        stmt = select(MetaObjectStandard).where(MetaObjectStandard.tenant_id == self.tenant_id)
        if catalog_id is not None:
            stmt = stmt.where(MetaObjectStandard.catalog_id == catalog_id)
        return list(self.db.execute(stmt.order_by(MetaObjectStandard.code)).scalars().all())

    def create(
        self,
        code: str,
        name: str,
        *,
        catalog_id: Optional[int] = None,
        aliases: Optional[list] = None,
        domain: Optional[str] = None,
        description: Optional[str] = None,
        creator_id: Optional[int] = None,
    ) -> MetaObjectStandard:
        if self._by_code(code) is not None:
            raise ValueError(f"对象标准编码已存在: {code}")
        obj = MetaObjectStandard(
            tenant_id=self.tenant_id,
            code=code,
            name=name,
            catalog_id=catalog_id,
            aliases_json=aliases or [],
            domain=domain,
            description=description,
            status="published",
            creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, object_id: int, **fields) -> MetaObjectStandard:
        obj = self.get_or_404(object_id)
        new_code = fields.get("code")
        if new_code is not None and new_code != obj.code:
            conflict = self._by_code(new_code)
            if conflict is not None and conflict.id != obj.id:
                raise ValueError(f"对象标准编码已存在: {new_code}")
        aliases = fields.pop("aliases", None)
        if aliases is not None:
            obj.aliases_json = aliases
        for key, value in fields.items():
            if value is None:
                continue
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, object_id: int) -> None:
        """删除对象标准（被关系引用 / 已被物理表绑定即拒绝）。"""
        obj = self.get_or_404(object_id)
        if self.db.execute(
            select(MetaObjectRelation.id).where(
                (MetaObjectRelation.from_object_id == object_id)
                | (MetaObjectRelation.to_object_id == object_id)
            )
        ).first() is not None:
            raise ValueError("对象被关系标准引用，禁止删除")
        if self.db.execute(
            select(MetaTableStandard.id).where(
                MetaTableStandard.object_standard_id == object_id
            )
        ).first() is not None:
            raise ValueError("对象已被物理表绑定，禁止删除")
        self.db.delete(obj)
        self.db.flush()

    def set_attributes(self, object_id: int, items: List[dict]) -> None:
        """全量替换对象的引用属性列表（先清后插，顺序取 sort_order）。"""
        obj = self.get_or_404(object_id)
        self.db.execute(
            delete(MetaObjectStandardAttribute).where(
                MetaObjectStandardAttribute.object_id == obj.id
            )
        )
        for index, item in enumerate(items):
            standard_id = item["standard_id"]
            exists = self.db.execute(
                select(MetaStandard.id).where(
                    MetaStandard.id == standard_id,
                    MetaStandard.tenant_id == self.tenant_id,
                )
            ).first()
            if exists is None:
                raise ValueError(f"属性标准不存在或跨租户: {standard_id}")
            self.db.add(
                MetaObjectStandardAttribute(
                    tenant_id=self.tenant_id,
                    object_id=obj.id,
                    standard_id=standard_id,
                    required=bool(item.get("required", False)),
                    sort_order=int(item.get("sort_order", index)),
                    security_level_override=item.get("security_level_override"),
                    note=item.get("note"),
                )
            )
        self.db.flush()

    def get_attributes(self, object_id: int) -> List[dict]:
        rows = self.db.execute(
            select(MetaObjectStandardAttribute, MetaStandard)
            .join(MetaStandard, MetaStandard.id == MetaObjectStandardAttribute.standard_id)
            .where(
                MetaObjectStandardAttribute.object_id == object_id,
                MetaObjectStandardAttribute.tenant_id == self.tenant_id,
            )
            .order_by(
                MetaObjectStandardAttribute.sort_order,
                MetaObjectStandardAttribute.id,
            )
        ).all()
        return [
            {
                "standard_id": attr.standard_id,
                "code": standard.code,
                "name": standard.name,
                "semantic_type": standard.semantic_type,
                "security_level": attr.security_level_override or standard.security_level,
                "required": attr.required,
                "sort_order": attr.sort_order,
                "note": attr.note,
            }
            for attr, standard in rows
        ]

    @staticmethod
    def serialize(o: MetaObjectStandard) -> dict:
        return {
            "id": o.id,
            "catalog_id": o.catalog_id,
            "code": o.code,
            "name": o.name,
            "aliases": o.aliases_json or [],
            "domain": o.domain,
            "description": o.description,
            "status": o.status,
            "current_version": o.current_version,
        }
