"""目录/场景树服务（B2）。

目录（``meta_standard_catalog``）是标准中心的组织骨架：用自引用树圈定对象标准与
关系标准。租户隔离 + 删除 RESTRICT（有子节点 / 被对象或关系引用即拒绝）。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaStandardCatalog,
)


class MetaStandardCatalogService:
    """目录/场景树读写（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("MetaStandardCatalogService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def get_or_404(self, catalog_id: int) -> MetaStandardCatalog:
        obj = self.db.execute(
            select(MetaStandardCatalog).where(
                MetaStandardCatalog.tenant_id == self.tenant_id,
                MetaStandardCatalog.id == catalog_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            raise KeyError(catalog_id)
        return obj

    def _by_code(self, code: str) -> Optional[MetaStandardCatalog]:
        return self.db.execute(
            select(MetaStandardCatalog).where(
                MetaStandardCatalog.tenant_id == self.tenant_id,
                MetaStandardCatalog.code == code,
            )
        ).scalar_one_or_none()

    def list_all(self) -> List[MetaStandardCatalog]:
        return list(
            self.db.execute(
                select(MetaStandardCatalog)
                .where(MetaStandardCatalog.tenant_id == self.tenant_id)
                .order_by(MetaStandardCatalog.sort_order, MetaStandardCatalog.id)
            ).scalars().all()
        )

    def list_tree(self) -> List[dict]:
        """整棵树（一次查询后在内存组树，避免 N+1）。"""
        catalogs = self.list_all()
        nodes = {c.id: {**self.serialize(c), "children": []} for c in catalogs}
        roots: List[dict] = []
        for c in catalogs:
            parent = nodes.get(c.parent_id) if c.parent_id else None
            (parent["children"] if parent else roots).append(nodes[c.id])
        return roots

    def create(
        self,
        code: str,
        name: str,
        *,
        parent_id: Optional[int] = None,
        icon: Optional[str] = None,
        description: Optional[str] = None,
        creator_id: Optional[int] = None,
    ) -> MetaStandardCatalog:
        if self._by_code(code) is not None:
            raise ValueError(f"目录编码已存在: {code}")
        if parent_id is not None:
            self.get_or_404(parent_id)  # 父节点必须存在且同租户
        obj = MetaStandardCatalog(
            tenant_id=self.tenant_id,
            code=code,
            name=name,
            parent_id=parent_id,
            icon=icon,
            description=description,
            status="published",
            creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, catalog_id: int, **fields) -> MetaStandardCatalog:
        obj = self.get_or_404(catalog_id)
        new_code = fields.get("code")
        if new_code is not None and new_code != obj.code:
            conflict = self._by_code(new_code)
            if conflict is not None and conflict.id != obj.id:
                raise ValueError(f"目录编码已存在: {new_code}")
        for key, value in fields.items():
            if value is None:
                continue
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def move(self, catalog_id: int, parent_id: Optional[int]) -> MetaStandardCatalog:
        """挂到新父节点（None=移为根）；禁止移入自身或自身子树。"""
        obj = self.get_or_404(catalog_id)
        if parent_id is not None:
            if parent_id == obj.id:
                raise ValueError("不能把目录移动到自身之下")
            self.get_or_404(parent_id)
            if parent_id in self._descendant_ids(obj.id):
                raise ValueError("不能把目录移动到自己的子目录之下")
        obj.parent_id = parent_id
        self.db.flush()
        return obj

    def _descendant_ids(self, catalog_id: int) -> set:
        children: dict = {}
        for c in self.list_all():
            children.setdefault(c.parent_id, []).append(c.id)
        found, stack = set(), [catalog_id]
        while stack:
            for child_id in children.get(stack.pop(), []):
                if child_id not in found:
                    found.add(child_id)
                    stack.append(child_id)
        return found

    def delete(self, catalog_id: int) -> None:
        """删除目录（RESTRICT：有子节点 / 被对象或关系引用即拒绝）。"""
        obj = self.get_or_404(catalog_id)
        if self.db.execute(
            select(MetaStandardCatalog.id).where(MetaStandardCatalog.parent_id == catalog_id)
        ).first() is not None:
            raise ValueError("目录存在子节点，禁止删除")
        if self.db.execute(
            select(MetaObjectStandard.id).where(MetaObjectStandard.catalog_id == catalog_id)
        ).first() is not None:
            raise ValueError("目录被对象标准引用，禁止删除")
        if self.db.execute(
            select(MetaObjectRelation.id).where(MetaObjectRelation.catalog_id == catalog_id)
        ).first() is not None:
            raise ValueError("目录被关系标准引用，禁止删除")
        self.db.delete(obj)
        self.db.flush()

    @staticmethod
    def serialize(c: MetaStandardCatalog) -> dict:
        return {
            "id": c.id,
            "parent_id": c.parent_id,
            "code": c.code,
            "name": c.name,
            "description": c.description,
            "icon": c.icon,
            "sort_order": c.sort_order,
            "status": c.status,
        }
