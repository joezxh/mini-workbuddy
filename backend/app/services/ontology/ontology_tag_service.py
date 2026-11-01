"""资产标签体系（P0-10：E29 列表 + E30 新建 + E31 改删 + E32 批量打标，spec §3.2 / §6.1）。

补 AF-03：此前全仓无任何 ``*tag*`` 表。两表已在 P0-1 建好——
- ``onto_asset_tag``：租户内唯一 code；
- ``onto_asset_tag_binding``：标签↔资产绑定，``asset_id`` **故意不建外键**，
  元数据重扫会重建 ``meta_table`` 行，强外键会连带删掉人工标签（OntoMind 证据丢失同构问题）。

删除守卫：存在绑定时拒绝 ``ASSET_TAG_IN_USE``（须先摘标）；编码冲突 ``TAG_CODE_DUPLICATED``。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ASSET_TAG_IN_USE, ONTOLOGY_NOT_FOUND, TAG_CODE_DUPLICATED,
)
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.ontology.asset_tag import MetaAssetTag, MetaAssetTagBinding

_TAG_KINDS = {"biz", "security", "quality", "custom"}
# security 自动打标命中的敏感等级（字符串枚举，L2/L3 达阈）
_SENSITIVE_PII_LEVELS = ("L2", "L3")
_SECURITY_PII_TAG_CODE = "pii"


class OntologyTagService:
    """标签 CRUD 与批量绑定（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyTagService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _tag_or_404(self, tag_id: int) -> MetaAssetTag:
        tag = self.db.execute(
            select(MetaAssetTag).where(
                MetaAssetTag.tenant_id == self.tenant_id, MetaAssetTag.id == tag_id
            )
        ).scalar_one_or_none()
        if tag is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "标签不存在", http_status=404, detail={"tag_id": tag_id})
        return tag

    # ------------------------------------------------------------- E29 列表

    def list_tags(self, *, kind: Optional[str] = None) -> List[dict]:
        stmt = select(MetaAssetTag).where(MetaAssetTag.tenant_id == self.tenant_id)
        if kind:
            stmt = stmt.where(MetaAssetTag.tag_kind == kind)
        tags = list(self.db.execute(stmt.order_by(MetaAssetTag.code)).scalars().all())
        counts = dict(self.db.execute(
            select(MetaAssetTagBinding.tag_id, func.count())
            .where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.tag_id.in_([t.id for t in tags] or [-1]),
            )
            .group_by(MetaAssetTagBinding.tag_id)
        ).all())
        return [
            {"id": t.id, "code": t.code, "name": t.name, "color": t.color,
             "tag_kind": t.tag_kind, "description": t.description,
             "binding_count": int(counts.get(t.id, 0))}
            for t in tags
        ]

    # ------------------------------------------------------------- E30 新建

    def create_tag(self, *, code: str, name: str, color: Optional[str] = None,
                   tag_kind: str = "custom", description: Optional[str] = None,
                   creator_id: Optional[int] = None) -> dict:
        if tag_kind not in _TAG_KINDS:
            tag_kind = "custom"
        dup = self.db.execute(
            select(MetaAssetTag.id).where(
                MetaAssetTag.tenant_id == self.tenant_id, MetaAssetTag.code == code
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise ApiError(TAG_CODE_DUPLICATED, f"标签编码已存在: {code}",
                           http_status=409, detail={"code": code})
        tag = MetaAssetTag(
            tenant_id=self.tenant_id, code=code, name=name, color=color,
            tag_kind=tag_kind, description=description, creator_id=creator_id,
        )
        self.db.add(tag)
        self.db.flush()
        return {"id": tag.id, "code": tag.code, "name": tag.name, "color": tag.color,
                "tag_kind": tag.tag_kind, "description": tag.description, "binding_count": 0}

    # ------------------------------------------------------------- E31 改/删

    def update_tag(
        self, tag_id: int, *,
        name: Optional[str] = None, color: Optional[str] = None,
        tag_kind: Optional[str] = None, description: Optional[str] = None,
    ) -> dict:
        tag = self._tag_or_404(tag_id)
        if name is not None:
            tag.name = name
        if color is not None:
            tag.color = color
        if tag_kind is not None and tag_kind in _TAG_KINDS:
            tag.tag_kind = tag_kind
        if description is not None:
            tag.description = description
        self.db.flush()
        return {"id": tag.id, "code": tag.code, "name": tag.name, "color": tag.color,
                "tag_kind": tag.tag_kind, "description": tag.description}

    def delete_tag(self, tag_id: int) -> None:
        tag = self._tag_or_404(tag_id)
        bound = self.db.execute(
            select(func.count()).select_from(MetaAssetTagBinding).where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.tag_id == tag_id,
            )
        ).scalar_one()
        if bound:
            raise ApiError(ASSET_TAG_IN_USE, f"标签被 {int(bound)} 个资产引用，请先摘标",
                           http_status=409, detail={"tag_id": tag_id, "binding_count": int(bound)})
        self.db.delete(tag)
        self.db.flush()

    # ------------------------------------------------------------- E32 批量打标/摘标

    def bind(self, *, tag_id: int, asset_kind: str, asset_ids: List[int], op: str = "bind",
             created_by: Optional[int] = None) -> dict:
        """``op=bind`` 幂等新增绑定；``op=unbind`` 删除绑定。"""
        self._tag_or_404(tag_id)
        if asset_kind not in ("table", "column"):
            raise ApiError(ASSET_TAG_IN_USE, "asset_kind 必须为 table|column")  # 复用参数错误语义
        ids = [int(a) for a in (asset_ids or []) if a is not None]
        if not ids:
            return {"tag_id": tag_id, "op": op, "affected": 0}
        if op == "unbind":
            deleted = self.db.execute(
                MetaAssetTagBinding.__table__.delete().where(
                    MetaAssetTagBinding.tenant_id == self.tenant_id,
                    MetaAssetTagBinding.tag_id == tag_id,
                    MetaAssetTagBinding.asset_kind == asset_kind,
                    MetaAssetTagBinding.asset_id.in_(ids),
                )
            ).rowcount
            self.db.flush()
            return {"tag_id": tag_id, "op": op, "affected": int(deleted or 0)}
        existing = set(self.db.execute(
            select(MetaAssetTagBinding.asset_id).where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.tag_id == tag_id,
                MetaAssetTagBinding.asset_kind == asset_kind,
                MetaAssetTagBinding.asset_id.in_(ids),
            )
        ).scalars().all())
        added = 0
        for aid in ids:
            if aid in existing:
                continue
            self.db.add(MetaAssetTagBinding(
                tenant_id=self.tenant_id, tag_id=tag_id, asset_kind=asset_kind,
                asset_id=aid, source="human", created_by=created_by,
            ))
            added += 1
        self.db.flush()
        return {"tag_id": tag_id, "op": op, "affected": added, "skipped": len(ids) - added}

    # ------------------------------------------- E-自动打标 security 规则（AF-03）

    def apply_security_rule(self, source_id: Optional[int] = None) -> dict:
        """按 ``pii_level >= L2`` 规则自动重打 ``pii`` 安全标签（幂等，rule/human 分治）。

        口径（spec §5.2）：
        - 仅当租户已有 ``tag_kind='security' AND code='pii'`` 标签才打标，**不自动建标签**（缺失→``{"tag": None}``）；
        - 先删本批作用域内该标签的 ``source='rule'`` 旧绑定，再对敏感表重打（同表已有 human 则跳过，避开 uq 冲突）；
        - ``source='human'`` 永不触碰；``source_id`` 缺省＝租户全量（供手动重分级）。
        返回 ``{"tag": code|None, "bound": 新增 rule 数, "removed": 删除 rule 数}``。
        """
        tag = self.db.execute(
            select(MetaAssetTag).where(
                MetaAssetTag.tenant_id == self.tenant_id,
                MetaAssetTag.tag_kind == "security",
                MetaAssetTag.code == _SECURITY_PII_TAG_CODE,
            )
        ).scalar_one_or_none()
        if tag is None:
            return {"tag": None, "bound": 0, "removed": 0}

        # 作用域内的快照表（可限定本批扫描涉及源）
        scope_stmt = select(MetaTable.id).where(MetaTable.tenant_id == self.tenant_id)
        if source_id is not None:
            scope_stmt = scope_stmt.where(MetaTable.source_id == source_id)
        scope_ids = set(self.db.execute(scope_stmt).scalars().all())
        if not scope_ids:
            return {"tag": tag.code, "bound": 0, "removed": 0}

        # 敏感表：含任一 L2/L3 列
        sensitive_ids = set(self.db.execute(
            select(MetaColumn.table_id)
            .where(
                MetaColumn.tenant_id == self.tenant_id,
                MetaColumn.table_id.in_(scope_ids),
                MetaColumn.pii_level.in_(_SENSITIVE_PII_LEVELS),
            )
            .group_by(MetaColumn.table_id)
        ).scalars().all())

        # 删除作用域内该标签的 rule 旧绑定（human 保留）
        removed = int(self.db.execute(
            delete(MetaAssetTagBinding).where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.tag_id == tag.id,
                MetaAssetTagBinding.asset_kind == "table",
                MetaAssetTagBinding.source == "rule",
                MetaAssetTagBinding.asset_id.in_(scope_ids),
            )
        ).rowcount or 0)

        # human 已覆盖的敏感表不重建 rule（同一 (tag,asset) 唯一约束）
        human_ids = set(self.db.execute(
            select(MetaAssetTagBinding.asset_id).where(
                MetaAssetTagBinding.tenant_id == self.tenant_id,
                MetaAssetTagBinding.tag_id == tag.id,
                MetaAssetTagBinding.asset_kind == "table",
                MetaAssetTagBinding.source == "human",
                MetaAssetTagBinding.asset_id.in_(sensitive_ids or [-1]),
            )
        ).scalars().all())

        bound = 0
        for tid in sorted(sensitive_ids):
            if tid in human_ids:
                continue
            self.db.add(MetaAssetTagBinding(
                tenant_id=self.tenant_id, tag_id=tag.id, asset_kind="table",
                asset_id=tid, source="rule",
            ))
            bound += 1
        self.db.flush()
        return {"tag": tag.code, "bound": bound, "removed": removed}
