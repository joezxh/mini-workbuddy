"""本体注册服务（模式层归属锚点 CRUD + 资产目录树，spec §3.2 / §6.5）。

约定（沿用 DataSourceService / MetaStandardCatalogService 范式）：
- 构造 ``(db, tenant_id)``，``tenant_id`` 为 None 直接拒绝（禁止无租户操作）；
- 读口径以 ``tenant_id`` 显式过滤，跨租户即视为不存在；
- **领域错误统一抛 :class:`ApiError`**（R3：{code,message,detail?}），由 main.py 处理器渲染；
- 事务边界在路由层（本服务只 ``flush``，不 ``commit``）。

D3 rev.2 无关：本服务只做注册/归属/目录树，不涉及 LLM 结构候选。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_CODE_DUPLICATED, ONTOLOGY_HAS_VERSIONS, ONTOLOGY_NOT_FOUND,
)
from app.models.dataops.data_source import DataSource
from app.models.dataops.meta import MetaTable
from app.models.ontology.ontology import MetaOntology, MetaOntologyVersion
from app.models.dataops.standard_cdm import (
    MetaObjectRelation, MetaObjectStandard, MetaStandardCatalog,
)
from app.services.dataops.data_source_service import enabled_types

# E40 目录树分组：family → 分类节点（不新增字典项，映射到既有 family 取值聚合）
_FAMILY_TO_KIND = {
    "excel": "file",
    "es": "search",
}
_KIND_LABELS = {
    "rdbms": "关系型数据库",
    "file": "文件数据源",
    "search": "搜索引擎",
}
_KIND_ORDER = ("rdbms", "file", "search")


class OntologyService:
    """本体注册 CRUD + 资产目录树（按 tenant_id 隔离）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ---------------------------------------------------------------- 查询

    def get_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id,
                MetaOntology.id == ontology_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    def _by_code(self, code: str) -> Optional[MetaOntology]:
        return self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id,
                MetaOntology.code == code,
            )
        ).scalar_one_or_none()

    def list_ontologies(
        self,
        *,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: str = "updated_at_desc",
    ) -> List[dict]:
        stmt = select(MetaOntology).where(MetaOntology.tenant_id == self.tenant_id)
        if status:
            stmt = stmt.where(MetaOntology.status == status)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(MetaOntology.code.ilike(like), MetaOntology.name.ilike(like)))
        if sort == "name_asc":
            stmt = stmt.order_by(MetaOntology.name, MetaOntology.id)
        else:
            stmt = stmt.order_by(MetaOntology.updated_at.desc(), MetaOntology.id.desc())
        ontologies = list(self.db.execute(stmt).scalars().all())
        stats = self._stats_for([o.id for o in ontologies])
        return [self.serialize(o, stats.get(o.id)) for o in ontologies]

    def _stats_for(self, ontology_ids: List[int]) -> dict:
        """按本体聚合：版本数 / 对象数 / 关系数（对象、关系经目录归属统计）。"""
        if not ontology_ids:
            return {}
        # 目录 → 本体映射
        catalog_rows = self.db.execute(
            select(MetaStandardCatalog.id, MetaStandardCatalog.ontology_id).where(
                MetaStandardCatalog.tenant_id == self.tenant_id,
                MetaStandardCatalog.ontology_id.in_(ontology_ids),
            )
        ).all()
        catalog_to_ontology = {cid: oid for cid, oid in catalog_rows}
        catalog_ids = list(catalog_to_ontology)

        object_counts: dict = {oid: 0 for oid in ontology_ids}
        relation_counts: dict = {oid: 0 for oid in ontology_ids}
        if catalog_ids:
            for cid, cnt in self.db.execute(
                select(MetaObjectStandard.catalog_id, func.count())
                .where(MetaObjectStandard.tenant_id == self.tenant_id,
                       MetaObjectStandard.catalog_id.in_(catalog_ids))
                .group_by(MetaObjectStandard.catalog_id)
            ).all():
                object_counts[catalog_to_ontology[cid]] += cnt
            for cid, cnt in self.db.execute(
                select(MetaObjectRelation.catalog_id, func.count())
                .where(MetaObjectRelation.tenant_id == self.tenant_id,
                       MetaObjectRelation.catalog_id.in_(catalog_ids))
                .group_by(MetaObjectRelation.catalog_id)
            ).all():
                relation_counts[catalog_to_ontology[cid]] += cnt

        version_counts: dict = {oid: 0 for oid in ontology_ids}
        for oid, cnt in self.db.execute(
            select(MetaOntologyVersion.ontology_id, func.count())
            .where(MetaOntologyVersion.tenant_id == self.tenant_id,
                   MetaOntologyVersion.ontology_id.in_(ontology_ids))
            .group_by(MetaOntologyVersion.ontology_id)
        ).all():
            version_counts[oid] = cnt

        return {
            oid: {
                "version_count": version_counts.get(oid, 0),
                "object_count": object_counts.get(oid, 0),
                "relation_count": relation_counts.get(oid, 0),
            }
            for oid in ontology_ids
        }

    # ---------------------------------------------------------------- 写入

    def create(
        self,
        code: str,
        name: str,
        *,
        description: Optional[str] = None,
        namespace_uri: Optional[str] = None,
        root_catalog_id: Optional[int] = None,
        creator_id: Optional[int] = None,
    ) -> MetaOntology:
        code = (code or "").strip()
        if not code:
            raise ApiError(ONTOLOGY_CODE_DUPLICATED, "本体编码不能为空")
        if self._by_code(code) is not None:
            raise ApiError(ONTOLOGY_CODE_DUPLICATED, f"本体编码已存在: {code}", detail={"code": code})
        obj = MetaOntology(
            tenant_id=self.tenant_id,
            code=code,
            name=(name or code).strip(),
            description=description,
            namespace_uri=namespace_uri or f"urn:mwb:ontology:{code}",
            status="draft",
            current_version=0,
            root_catalog_id=root_catalog_id,
            creator_id=creator_id,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, ontology_id: int, *, updater_id: Optional[int] = None, **fields) -> MetaOntology:
        obj = self.get_or_404(ontology_id)
        new_code = fields.get("code")
        if new_code is not None and new_code != obj.code:
            conflict = self._by_code(new_code)
            if conflict is not None and conflict.id != obj.id:
                raise ApiError(ONTOLOGY_CODE_DUPLICATED, f"本体编码已存在: {new_code}", detail={"code": new_code})
        editable = ("code", "name", "description", "namespace_uri", "status", "root_catalog_id")
        for key in editable:
            if key in fields and fields[key] is not None:
                setattr(obj, key, fields[key])
        obj.updater_id = updater_id
        self.db.flush()
        return obj

    def delete(self, ontology_id: int) -> None:
        """删除本体：有版本历史则拒绝（避免版本快照悬空）。"""
        obj = self.get_or_404(ontology_id)
        has_version = self.db.execute(
            select(MetaOntologyVersion.id)
            .where(MetaOntologyVersion.tenant_id == self.tenant_id,
                   MetaOntologyVersion.ontology_id == ontology_id)
            .limit(1)
        ).first()
        if has_version is not None:
            raise ApiError(
                ONTOLOGY_HAS_VERSIONS, "本体已有发布版本，禁止删除",
                detail={"ontology_id": ontology_id},
            )
        # 解除目录归属（不设外键，应用层清理）
        self.db.execute(
            MetaStandardCatalog.__table__.update()
            .where(MetaStandardCatalog.tenant_id == self.tenant_id,
                   MetaStandardCatalog.ontology_id == ontology_id)
            .values(ontology_id=None)
        )
        self.db.delete(obj)
        self.db.flush()

    # ------------------------------------------------------------ E40 目录树

    def assets_tree(self) -> List[dict]:
        """按数据源类型分类聚合的目录树（AF-01，不新建表，完全由既有数据拼出）。

        分组：``meta_data_source.source_type`` → 字典启用项 ``family`` → 粗分类
        （rdbms / file / search）；节点 ``count`` = 该源已扫描表数（``meta_table``）。
        """
        sources = list(self.db.execute(
            select(DataSource).where(DataSource.tenant_id == self.tenant_id)
            .order_by(DataSource.id)
        ).scalars().all())

        table_counts = dict(self.db.execute(
            select(MetaTable.source_id, func.count())
            .where(MetaTable.tenant_id == self.tenant_id)
            .group_by(MetaTable.source_id)
        ).all())

        types = enabled_types(self.db, self.tenant_id)

        buckets: dict = {kind: [] for kind in _KIND_ORDER}
        for s in sources:
            meta = types.get((s.source_type or "").lower()) or {}
            family = meta.get("family") or "rdbms"
            kind = _FAMILY_TO_KIND.get(family, "rdbms")
            buckets.setdefault(kind, []).append({
                "kind": "source",
                "id": s.id,
                "label": s.name,
                "source_type": s.source_type,
                "status": s.status,
                "count": int(table_counts.get(s.id, 0)),
            })

        tree: List[dict] = []
        for kind in _KIND_ORDER:
            children = buckets.get(kind, [])
            tree.append({
                "kind": "type",
                "code": kind,
                "label": _KIND_LABELS[kind],
                "count": sum(c["count"] for c in children),
                "children": children,
            })
        return tree

    # ---------------------------------------------------------------- 序列化

    @staticmethod
    def serialize(o: MetaOntology, stats: Optional[dict] = None) -> dict:
        data = {
            "id": o.id,
            "code": o.code,
            "name": o.name,
            "description": o.description,
            "namespace_uri": o.namespace_uri,
            "status": o.status,
            "current_version": o.current_version,
            "root_catalog_id": o.root_catalog_id,
            "has_draft_scope": bool(o.draft_scope_json),
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        }
        if stats:
            data.update(stats)
        return data
