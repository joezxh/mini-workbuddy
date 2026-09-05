"""Skill 版本管理 - 同步 SQLAlchemy。"""
from __future__ import annotations
from typing import List

from sqlalchemy import desc

from app.models.ai.ai_skill_version import AiSkillVersion


class SkillVersionManager:
    """AiSkillVersion 的版本号生成与回滚。"""

    def __init__(self, db) -> None:
        self.db = db

    def get_next_version(self, skill_id: str) -> int:
        row = (
            self.db.query(AiSkillVersion.version_number)
            .filter(AiSkillVersion.skill_id == skill_id)
            .order_by(desc(AiSkillVersion.version_number))
            .first()
        )
        return int(row[0]) + 1 if row else 1

    def list_versions(self, skill_id: str) -> List[AiSkillVersion]:
        return list(
            self.db.query(AiSkillVersion)
            .filter(AiSkillVersion.skill_id == skill_id)
            .order_by(desc(AiSkillVersion.version_number))
            .all()
        )

    def get_version(self, skill_id: str, version_number: int) -> AiSkillVersion | None:
        return (
            self.db.query(AiSkillVersion)
            .filter(
                AiSkillVersion.skill_id == skill_id,
                AiSkillVersion.version_number == version_number,
            )
            .first()
        )

    def rollback(self, skill_id: str, target_version: int) -> None:
        """回滚: 把当前所有 is_stable=false, 目标版本 is_stable=true。"""
        rows = (
            self.db.query(AiSkillVersion)
            .filter(AiSkillVersion.skill_id == skill_id)
            .all()
        )
        if not rows:
            raise ValueError(f"no versions found for skill_id={skill_id!r}")
        if target_version not in {r.version_number for r in rows}:
            raise ValueError(f"version {target_version} not found")
        for r in rows:
            r.is_stable = (r.version_number == target_version)
        self.db.commit()
