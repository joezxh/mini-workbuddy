"""AiWorkspaceService - 工作空间 CRUD + 业务逻辑。"""
import logging
import uuid
from typing import Optional, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.ai.ai_workspace import AiWorkspace
from app.schemas.ai.ai_workspace import AiWorkspaceCreate, AiWorkspaceUpdate

logger = logging.getLogger(__name__)

# 系统内置公共空间 ID，不可修改/删除
PUBLIC_WORKSPACE_ID = 1


class AiWorkspaceService:
    """工作空间 CRUD + 业务逻辑。"""

    def __init__(self, db: Session):
        self.db = db

    def create_workspace(self, data: AiWorkspaceCreate, user_id: int, username: str) -> AiWorkspace:
        """创建工作空间。"""
        workspace = AiWorkspace(
            workspace_id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            scope=data.scope,
            execution_mode=data.execution_mode,
            workspace_type=data.workspace_type,
            user_id=user_id if data.scope == "private" else None,
            config=data.config or {},
            mcp_ids=data.mcp_ids or [],
            skill_ids=data.skill_ids or [],
            is_default=False,
            status="active",
            created_by=username,
        )
        self.db.add(workspace)
        self.db.commit()
        self.db.refresh(workspace)
        logger.info("Workspace created: %s by %s", workspace.workspace_id, username)
        return workspace

    def update_workspace(self, workspace_id: int, data: AiWorkspaceUpdate) -> Optional[AiWorkspace]:
        """更新工作空间。"""
        if workspace_id == PUBLIC_WORKSPACE_ID:
            raise ValueError("公共空间不允许修改")
        ws = self._get_active(workspace_id)
        if not ws:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(ws, key, value)
        self.db.commit()
        self.db.refresh(ws)
        return ws

    def delete_workspace(self, workspace_id: int) -> bool:
        """软删除工作空间。"""
        if workspace_id == PUBLIC_WORKSPACE_ID:
            raise ValueError("公共空间不允许删除")
        ws = self._get_active(workspace_id)
        if not ws:
            return False
        ws.is_deleted = True
        self.db.commit()
        return True

    def get_workspace(self, workspace_id: int) -> Optional[AiWorkspace]:
        """获取单个工作空间。"""
        return self._get_active(workspace_id)

    def list_workspaces(
        self, user_id: int, scope: Optional[str] = None, keyword: Optional[str] = None
    ) -> List[AiWorkspace]:
        """列出用户可见的工作空间。

        规则：公共工作空间 + 用户自己的私有工作空间。
        """
        query = self.db.query(AiWorkspace).filter(
            AiWorkspace.is_deleted == False,  # noqa: E712
            AiWorkspace.status == "active",
        )
        if scope == "public":
            query = query.filter(AiWorkspace.scope == "public")
        elif scope == "private":
            query = query.filter(AiWorkspace.scope == "private", AiWorkspace.user_id == user_id)
        else:
            query = query.filter(
                or_(
                    AiWorkspace.scope == "public",
                    (AiWorkspace.scope == "private") & (AiWorkspace.user_id == user_id),
                )
            )
        if keyword:
            query = query.filter(AiWorkspace.name.contains(keyword))
        return query.order_by(AiWorkspace.is_default.desc(), AiWorkspace.id.desc()).all()

    def activate_workspace(self, workspace_id: int, user_id: int) -> bool:
        """设为用户默认工作空间。"""
        ws = self._get_active(workspace_id)
        if not ws:
            return False
        # 取消同用户其他默认
        self.db.query(AiWorkspace).filter(
            AiWorkspace.user_id == user_id,
            AiWorkspace.is_default == True,  # noqa: E712
            AiWorkspace.id != workspace_id,
        ).update({"is_default": False})
        ws.is_default = True
        self.db.commit()
        return True

    # ── 资源关联 ──

    def link_mcp(self, workspace_id: int, mcp_id: int) -> bool:
        """关联 MCP 服务。"""
        ws = self._get_active(workspace_id)
        if not ws:
            return False
        current = ws.mcp_ids or []
        if mcp_id not in current:
            current.append(mcp_id)
            ws.mcp_ids = current
            self.db.commit()
        return True

    def unlink_mcp(self, workspace_id: int, mcp_id: int) -> bool:
        """取消关联 MCP 服务。"""
        ws = self._get_active(workspace_id)
        if not ws:
            return False
        current = ws.mcp_ids or []
        if mcp_id in current:
            current.remove(mcp_id)
            ws.mcp_ids = current
            self.db.commit()
        return True

    def link_skill(self, workspace_id: int, skill_id: int) -> bool:
        """关联技能。"""
        ws = self._get_active(workspace_id)
        if not ws:
            return False
        current = ws.skill_ids or []
        if skill_id not in current:
            current.append(skill_id)
            ws.skill_ids = current
            self.db.commit()
        return True

    def unlink_skill(self, workspace_id: int, skill_id: int) -> bool:
        """取消关联技能。"""
        ws = self._get_active(workspace_id)
        if not ws:
            return False
        current = ws.skill_ids or []
        if skill_id in current:
            current.remove(skill_id)
            ws.skill_ids = current
            self.db.commit()
        return True

    # ── 资源解析 ──

    def resolve_effective_skill_ids(self, workspace_id: int) -> List[int]:
        """解析工作空间生效的技能 ID 列表。

        公共空间（id=1）返回所有已启用技能；其他空间返回关联的技能 ID。
        """
        if workspace_id == PUBLIC_WORKSPACE_ID:
            from app.models.ai.ai_skill_package import AiSkillPackage
            rows = self.db.query(AiSkillPackage.id).filter(
                AiSkillPackage.enabled == True,  # noqa: E712
            ).all()
            return [r.id for r in rows]
        ws = self._get_active(workspace_id)
        return list(ws.skill_ids) if ws else []

    def resolve_effective_mcp_ids(self, workspace_id: int) -> List[int]:
        """解析工作空间生效的 MCP 服务 ID 列表。

        公共空间（id=1）返回所有已启用 MCP；其他空间返回关联的 MCP ID。
        """
        if workspace_id == PUBLIC_WORKSPACE_ID:
            from app.models.ai.ai_mcp_api_key import AiMcpApiKey
            rows = self.db.query(AiMcpApiKey.id).filter(
                AiMcpApiKey.status == 1,
            ).all()
            return [r.id for r in rows]
        ws = self._get_active(workspace_id)
        return list(ws.mcp_ids) if ws else []

    # ── 内部方法 ──

    def _get_active(self, workspace_id: int) -> Optional[AiWorkspace]:
        """获取未删除的工作空间。"""
        return self.db.query(AiWorkspace).filter(
            AiWorkspace.id == workspace_id,
            AiWorkspace.is_deleted == False,  # noqa: E712
        ).first()
