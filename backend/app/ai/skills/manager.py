"""Skill 管理器 - 统一技能管理服务（元数据层）。

提供技能包/脚本的 DB 查询与 AgentScope Workspace 兼容接口。
执行能力已迁移至 SkillExecutionService（app/ai/skills/execution.py）。

调用方：
  - SkillHandler（AI 助手聊天流程）→ SkillExecutionService
  - SkillExecutor（Pipeline 引擎）→ SkillExecutionService
  - SkillDirectEngine（技能直调引擎）→ SkillExecutionService
  - ai_skill router（REST API）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── DB 模型（延迟导入友好） ──────────────────────────────────────────────────
from app.models.ai.ai_skill_package import AiSkillPackage
from app.models.ai.ai_skill_script import AiSkillScript


class SkillManager:
    """统一技能管理器（元数据层）。

    提供：
    1. DB 注册表查询（get_packages / get_script）
    2. SKILL.md 读取（get_skill_markdown）
    3. AgentScope Workspace 兼容（list_skills / get_skill）
    """

    def __init__(
        self,
        db: Session | None = None,
        **kwargs: Any,
    ) -> None:
        self.db = db

    @property
    def skills_base_path(self) -> Path:
        """技能包根目录（backend/data/skills/）"""
        return Path(__file__).resolve().parent.parent.parent.parent / "data" / "skills"

    # ─────────────────────────────────────────────────────────────────────
    # 1. DB 注册表查询
    # ─────────────────────────────────────────────────────────────────────

    def get_packages(self, db: Session | None = None) -> List[Dict[str, Any]]:
        """获取所有已启用且目录存在的技能包。"""
        _db = db or self.db
        if not _db:
            return []

        rows = _db.scalars(
            select(AiSkillPackage)
            .where(AiSkillPackage.enabled == True)  # noqa: E712
            .order_by(AiSkillPackage.category, AiSkillPackage.id)
        ).all()

        result = []
        for pkg in rows:
            pkg_dir = self.skills_base_path / pkg.package_id
            if not pkg_dir.exists():
                logger.warning("技能包目录不存在，跳过: %s", pkg_dir)
                continue

            scripts = _db.scalars(
                select(AiSkillScript)
                .where(
                    AiSkillScript.package_id == pkg.package_id,
                    AiSkillScript.enabled == True,  # noqa: E712
                )
                .order_by(AiSkillScript.sort_order, AiSkillScript.id)
            ).all()

            result.append({
                "id": pkg.package_id,
                "name": pkg.name,
                "description": pkg.description or "",
                "icon": pkg.icon or "tool",
                "category": pkg.category or "other",
                "version": pkg.version or "1.0.0",
                "scripts": [
                    {
                        "id": s.script_id,
                        "name": s.name,
                        "description": s.description or "",
                        "command": s.command,
                        "params": s.params or [],
                    }
                    for s in scripts
                ],
            })
        return result

    def get_script(
        self, package_id: str, script_id: str, db: Session | None = None,
    ) -> Dict[str, Any] | None:
        """获取指定脚本配置。"""
        _db = db or self.db
        if not _db:
            return None

        script = _db.scalars(
            select(AiSkillScript).where(
                AiSkillScript.package_id == package_id,
                AiSkillScript.script_id == script_id,
            )
        ).first()

        if not script:
            return None
        return {
            "id": script.script_id,
            "name": script.name,
            "description": script.description or "",
            "command": script.command,
            "params": script.params or [],
        }

    # ─────────────────────────────────────────────────────────────────────
    # 2. 辅助
    # ─────────────────────────────────────────────────────────────────────

    def get_skill_markdown(self, package_id: str, db: Session | None = None) -> str | None:
        """读取技能包 SKILL.md 内容（数据库 skill_markdown 优先，fallback 文件系统）。

        Returns:
            SKILL.md 文本内容；若数据库与文件系统均无则返回 None。
        """
        _db = db or self.db
        # 优先使用数据库中保存的 skill_markdown
        if _db is not None:
            try:
                pkg = _db.scalars(
                    select(AiSkillPackage).where(
                        AiSkillPackage.package_id == package_id,
                    )
                ).first()
                if pkg is not None and pkg.skill_markdown:
                    return pkg.skill_markdown
            except Exception as e:  # noqa: BLE001
                logger.debug("从数据库读取 skill_markdown 失败: %s", e)

        # fallback：文件系统
        md_path = self.skills_base_path / package_id / "SKILL.md"
        if not md_path.exists():
            return None
        try:
            return md_path.read_text(encoding="utf-8")
        except OSError:
            return None

    # ─────────────────────────────────────────────────────────────────────
    # 4. AgentScope Workspace 兼容层
    # ─────────────────────────────────────────────────────────────────────

    async def list_skills(self) -> list[dict[str, Any]]:
        """列出所有 Skill（workspace + DB 合并）。"""
        db_skills = self.get_packages()
        result = []
        for pkg in db_skills:
            result.append({
                "name": pkg["id"],
                "description": pkg.get("description", ""),
                "skill_code": pkg["id"],
                "status": "active",
                "version": pkg.get("version", "1.0.0"),
                "dir": str(self.skills_base_path / pkg["id"]),
            })
        return result

    async def get_skill(self, name: str) -> dict[str, Any] | None:
        """按名称获取单个 Skill 详情。"""
        packages = self.get_packages()
        pkg = next((p for p in packages if p["id"] == name), None)
        if not pkg:
            return None
        return {
            "name": pkg["id"],
            "description": pkg.get("description", ""),
            "scripts": pkg.get("scripts", []),
        }


# ─── 全局单例 ──────────────────────────────────────────────────────────

_skill_manager: SkillManager | None = None


def get_skill_manager(db: Session | None = None) -> SkillManager:
    """获取全局 SkillManager 单例。

    Args:
        db: 数据库 session（仅首次创建时生效；后续调用可传入新 session 用于执行）

    Returns:
        SkillManager 实例
    """
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager(db=db)
    elif db is not None and _skill_manager.db is None:
        # 允许后续补充 db session
        _skill_manager.db = db
    return _skill_manager
