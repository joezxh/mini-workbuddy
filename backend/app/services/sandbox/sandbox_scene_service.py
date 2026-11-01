"""场景生命周期服务（spec §4.1 sandbox_scene_service）。

职责：校验世界来源本体已发布 + 存在 enabled 未过期应用登记（钉版）→ 建景落 draft
→ 建基线分支 → 投递后台克隆 → 提供 get/list/patch/delete。

边界（V1 红线）：只读 ``onto_ontology*``/publish 登记，对沙箱域自身的写通过
``onto_sandbox_*`` 表完成；无任何生产写路径（验收 A7）。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, ONTOLOGY_NOT_PUBLISHED, SCENE_NOT_FOUND,
)
from app.models.ontology.ontology import MetaOntology, MetaOntologyVersion
from app.models.sandbox.sandbox import SandboxBranch, SandboxScene
from app.services.ontology.ontology_apppublish_service import OntologyAppPublishService

logger = logging.getLogger(__name__)

# 克隆上限默认与硬顶（Global Constraints / spec §8）
_DEFAULT_MAX_ENTITIES = 500
_DEFAULT_MAX_RELATIONS = 2000
_HARD_MAX_ENTITIES = 5000
_HARD_MAX_RELATIONS = 20000


class SandboxSceneService:
    """推演场景生命周期（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("SandboxSceneService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    # ------------------------------------------------------------- 建景 S1

    def create_scene(
        self, *, ontology_id: int, name: str, clone_scope: dict,
        tick_max: int = 12, exec_mode: str = "auto", creator_id: Optional[int] = None,
    ) -> dict:
        on = self.db.get(MetaOntology, ontology_id)
        if on is None or on.tenant_id != self.tenant_id:
            raise ApiError(ONTOLOGY_NOT_FOUND, "世界来源本体不存在", http_status=404)
        if on.status != "published" or (on.current_version or 0) == 0:
            raise ApiError(ONTOLOGY_NOT_PUBLISHED, "世界来源必须为已发布本体应用", http_status=400)
        pubs = OntologyAppPublishService(self.db, self.tenant_id).list_publishes(ontology_id)
        if not any(p["status"] == "enabled" and not p["stale"] for p in pubs):
            raise ApiError(ONTOLOGY_NOT_PUBLISHED, "无 enabled 且未过期的应用发布登记", http_status=400)
        ver = self.db.execute(
            select(MetaOntologyVersion).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
                MetaOntologyVersion.version == on.current_version,
            )
        ).scalar_one_or_none()
        if ver is None:
            raise ApiError(ONTOLOGY_NOT_PUBLISHED, "当前发布版本快照缺失", http_status=400)

        scope = dict(clone_scope or {})
        scope["max_entities"] = min(int(scope.get("max_entities", _DEFAULT_MAX_ENTITIES)), _HARD_MAX_ENTITIES)
        scope["max_relations"] = min(int(scope.get("max_relations", _DEFAULT_MAX_RELATIONS)), _HARD_MAX_RELATIONS)

        scene = SandboxScene(
            tenant_id=self.tenant_id, ontology_id=ontology_id,
            ontology_version=on.current_version, name=name,
            clone_scope_json=scope, exec_mode=exec_mode,
            tick_max=tick_max, status="draft", creator_id=creator_id,
        )
        self.db.add(scene)
        self.db.flush()
        self.db.add(SandboxBranch(
            tenant_id=self.tenant_id, scene_id=scene.id, name="基线分支",
            color="#4aa3ff", tick_now=0, status="active",
        ))
        self.db.commit()

        # 后台克隆（真实运行路径触发；测试直接以 service 层同步调 clone_scene，见 conftest 说明）
        from app.services.sandbox.sandbox_clone_service import submit_clone
        submit_clone(scene.id, self.tenant_id)
        return {"scene_id": scene.id, "status": "draft"}

    # ------------------------------------------------------------- 查询 S2/S3

    def get_scene(self, scene_id: int) -> dict:
        scene = self._scene_or_404(scene_id)
        branches = self.db.execute(
            select(SandboxBranch).where(
                SandboxBranch.tenant_id == self.tenant_id,
                SandboxBranch.scene_id == scene.id,
            ).order_by(SandboxBranch.id)
        ).scalars().all()
        from app.models.sandbox.sandbox import SandboxCheckpoint
        cp_count = self.db.execute(
            select(SandboxCheckpoint.id).where(
                SandboxCheckpoint.tenant_id == self.tenant_id,
                SandboxCheckpoint.scene_id == scene.id,
            )
        ).all()
        return self._serialize(scene, branches, len(cp_count))

    def list_scenes(self, ontology_id: Optional[int] = None, status: Optional[str] = None) -> list[dict]:
        q = select(SandboxScene).where(SandboxScene.tenant_id == self.tenant_id)
        if ontology_id is not None:
            q = q.where(SandboxScene.ontology_id == ontology_id)
        if status is not None:
            q = q.where(SandboxScene.status == status)
        rows = self.db.execute(q.order_by(SandboxScene.id.desc())).scalars().all()
        return [self._serialize(s, [], 0) for s in rows]

    # ------------------------------------------------------------- 变更 S5

    def patch_scene(self, scene_id: int, *, name: Optional[str] = None, exec_mode: Optional[str] = None) -> dict:
        scene = self._scene_or_404(scene_id)
        if name is not None:
            scene.name = name
        if exec_mode is not None:  # 三档由模型 CHECK 兜底非法值
            scene.exec_mode = exec_mode
        self.db.commit()
        return self._serialize(scene, [], 0)

    def delete_scene(self, scene_id: int) -> None:
        scene = self._scene_or_404(scene_id)
        # FK ON DELETE CASCADE 回收 branch/checkpoint/entity/relation/element/action/observation
        self.db.delete(scene)
        self.db.commit()

    # ------------------------------------------------------------- 内部

    def _scene_or_404(self, scene_id: int) -> SandboxScene:
        scene = self.db.execute(
            select(SandboxScene).where(
                SandboxScene.tenant_id == self.tenant_id, SandboxScene.id == scene_id
            )
        ).scalar_one_or_none()
        if scene is None:
            raise ApiError(SCENE_NOT_FOUND, "推演场景不存在", http_status=404)
        return scene

    def _serialize(self, scene: SandboxScene, branches, cp_count: int) -> dict:
        return {
            "scene_id": scene.id, "ontology_id": scene.ontology_id,
            "ontology_version": scene.ontology_version, "name": scene.name,
            "clone_scope": scene.clone_scope_json, "exec_mode": scene.exec_mode,
            "tick_now": scene.tick_now, "tick_max": scene.tick_max, "status": scene.status,
            "clone_stats": scene.clone_stats_json, "error_detail": scene.error_detail,
            "branches": [{"id": b.id, "name": b.name, "tick_now": b.tick_now,
                          "color": b.color, "status": b.status,
                          "base_checkpoint_id": b.base_checkpoint_id} for b in branches],
            "checkpoint_count": cp_count,
        }
