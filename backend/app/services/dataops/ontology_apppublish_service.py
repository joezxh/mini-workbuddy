"""本体应用发布登记（P0-11：E34 列表 + E35 登记 + E36 启停，spec §4.6 / §6.1）。

只做**登记与绑定**（``meta_ontology_publish``），不重复建设运行时：Skill 运行时复用既有
``ai_skill`` / ``ai_tools``（§3.2 补 AF-17/AF-18/AF-22）。

口径（§4.6）：
- 列表 ``stale=true`` 当登记版本落后于 ``meta_ontology.current_version``；
- 登记**仅钉 ``version=current_version``**；``current_version=0``（草稿态）时**强制 ``status=disabled``**
  （模型约束：``=0 表示引用草稿态，仅允许 status=disabled``）；
- 启停只翻 ``enabled|disabled``；未找到 → ``PUBLISH_TARGET_NOT_FOUND``。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, PUBLISH_TARGET_NOT_FOUND,
)
from app.models.dataops.ontology import MetaOntology, MetaOntologyPublish

_TARGET_TYPES = {"skill", "http", "mcp"}


class OntologyAppPublishService:
    """应用发布登记（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyAppPublishService 要求 tenant_id，禁止无租户操作")
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

    @staticmethod
    def _serialize(p: MetaOntologyPublish, current_version: int) -> dict:
        return {
            "id": p.id, "ontology_id": p.ontology_id, "version": p.version,
            "target_type": p.target_type, "code": p.code, "name": p.name,
            "description": p.description, "payload": p.payload_json, "status": p.status,
            "stale": p.version != current_version,
        }

    # ------------------------------------------------------------- E34 列表

    def list_publishes(self, ontology_id: int) -> List[dict]:
        ontology = self._ontology_or_404(ontology_id)
        rows = self.db.execute(
            select(MetaOntologyPublish).where(
                MetaOntologyPublish.tenant_id == self.tenant_id,
                MetaOntologyPublish.ontology_id == ontology_id,
            ).order_by(MetaOntologyPublish.id.desc())
        ).scalars().all()
        return [self._serialize(p, ontology.current_version or 0) for p in rows]

    # ------------------------------------------------------------- E35 登记

    def register(
        self, ontology_id: int, *,
        target_type: str, code: str, name: Optional[str] = None,
        description: Optional[str] = None, payload: Optional[dict] = None,
        creator_id: Optional[int] = None,
    ) -> dict:
        ontology = self._ontology_or_404(ontology_id)
        if target_type not in _TARGET_TYPES:
            raise ApiError(PUBLISH_TARGET_NOT_FOUND, f"不支持的目标类型: {target_type}",
                           http_status=400, detail={"target_type": target_type})
        version = int(ontology.current_version or 0)
        # 草稿态（version=0）强制 disabled；已发布默认 enabled
        status = "disabled" if version == 0 else "enabled"
        # 幂等：命中 (tenant, target_type, code) 视为重新登记（改钉到当前版本）
        existing = self.db.execute(
            select(MetaOntologyPublish).where(
                MetaOntologyPublish.tenant_id == self.tenant_id,
                MetaOntologyPublish.target_type == target_type,
                MetaOntologyPublish.code == code,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.ontology_id = ontology_id
            existing.version = version
            existing.name = name if name is not None else existing.name
            existing.description = description if description is not None else existing.description
            existing.payload_json = payload if payload is not None else existing.payload_json
            existing.status = status
            self.db.flush()
            return self._serialize(existing, version)
        pub = MetaOntologyPublish(
            tenant_id=self.tenant_id, ontology_id=ontology_id, version=version,
            target_type=target_type, code=code, name=name, description=description,
            payload_json=payload, status=status, creator_id=creator_id,
        )
        self.db.add(pub)
        self.db.flush()
        return self._serialize(pub, version)

    # ------------------------------------------------------------- E36 启停

    def toggle(self, ontology_id: int, publish_id: int, *, status: str) -> dict:
        ontology = self._ontology_or_404(ontology_id)
        if status not in ("enabled", "disabled"):
            raise ApiError(PUBLISH_TARGET_NOT_FOUND, "status 必须为 enabled|disabled",
                           http_status=400, detail={"status": status})
        pub = self.db.execute(
            select(MetaOntologyPublish).where(
                MetaOntologyPublish.tenant_id == self.tenant_id,
                MetaOntologyPublish.id == publish_id,
                MetaOntologyPublish.ontology_id == ontology_id,
            )
        ).scalar_one_or_none()
        if pub is None:
            raise ApiError(PUBLISH_TARGET_NOT_FOUND, "发布登记不存在", http_status=404,
                           detail={"publish_id": publish_id})
        # 草稿态（version=0）不允许 enabled（模型约束）
        if status == "enabled" and (pub.version or 0) == 0:
            raise ApiError(PUBLISH_TARGET_NOT_FOUND, "草稿态（未发布）登记不可启用",
                           http_status=400, detail={"version": pub.version})
        pub.status = status
        self.db.flush()
        return self._serialize(pub, ontology.current_version or 0)
