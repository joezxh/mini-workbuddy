"""SOP 模板服务 —— 模板库 CRUD 与内置模板播种。

spec: docs/design/sop-assistant-mode-design.md §4.3

代码侧注册表（``app.ai.sop.templates``）是模板定义的权威来源，本服务负责
把注册表同步进 ``sop_templates`` 表，并提供列表/检索/增删改供 API 层调用。

事务约定：只做 ``flush`` + ``commit``，不自行 ``begin()``（项目统一约束）。
"""
from __future__ import annotations

from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.sop.templates import ALL_TEMPLATES
from app.models.sop import SOPTemplate


class SOPTemplateService:
    """SOP 模板库服务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 查询 ────────────────────────────────────────────────────────────────

    def list_templates(
        self, keyword: str = "", include_disabled: bool = False
    ) -> List[SOPTemplate]:
        """列表；keyword 按 template_key/名称/描述/标签子串过滤。"""
        query = self.db.query(SOPTemplate)
        if not include_disabled:
            query = query.filter(SOPTemplate.enabled.is_(True))
        rows = query.order_by(SOPTemplate.builtin.desc(), SOPTemplate.id.asc()).all()

        kw = (keyword or "").strip().lower()
        if not kw:
            return rows
        return [r for r in rows if kw in self._keywords(r)]

    def get(self, template_id: int) -> Optional[SOPTemplate]:
        return (
            self.db.query(SOPTemplate)
            .filter(SOPTemplate.id == template_id)
            .first()
        )

    def get_by_key(self, template_key: str) -> Optional[SOPTemplate]:
        return (
            self.db.query(SOPTemplate)
            .filter(SOPTemplate.template_key == template_key)
            .first()
        )

    # ── 写入 ────────────────────────────────────────────────────────────────

    def create(self, payload: dict) -> SOPTemplate:
        row = SOPTemplate(**payload)
        self.db.add(row)
        self.db.flush()
        self.db.commit()
        return row

    def update(self, row: SOPTemplate, payload: dict) -> SOPTemplate:
        for key, value in payload.items():
            setattr(row, key, value)
        self.db.flush()
        self.db.commit()
        return row

    def delete(self, row: SOPTemplate) -> None:
        self.db.delete(row)
        self.db.flush()
        self.db.commit()

    # ── 播种 ────────────────────────────────────────────────────────────────

    def seed(self) -> dict:
        """按代码注册表播种模板（按 template_key 幂等）。

        - 内置模板（builtin=True）由系统拥有，每次播种刷新定义；
        - 其余预设与用户自建仅在缺失时插入，避免覆盖用户改动。
        """
        created = updated = skipped = 0
        for spec in ALL_TEMPLATES:
            row = self.get_by_key(spec.id)
            if row is None:
                self.db.add(
                    SOPTemplate(
                        template_key=spec.id,
                        name=spec.name,
                        description=spec.description,
                        tags=spec.tags,
                        definition=spec.definition.model_dump(mode="json"),
                        builtin=spec.builtin,
                        enabled=True,
                        created_by="system",
                    )
                )
                created += 1
                continue
            if row.builtin and spec.builtin:
                row.name = spec.name
                row.description = spec.description
                row.tags = spec.tags
                row.definition = spec.definition.model_dump(mode="json")
                updated += 1
            else:
                skipped += 1

        self.db.flush()
        self.db.commit()
        logger.info(
            f"[SOP] 模板播种完成: 新建 {created}, 刷新 {updated}, 跳过 {skipped}"
        )
        return {"created": created, "updated": updated, "skipped": skipped}

    # ── 辅助 ────────────────────────────────────────────────────────────────

    @staticmethod
    def _keywords(row: SOPTemplate) -> str:
        tags = [str(t) for t in (row.tags or [])]
        return " ".join(
            [row.template_key, row.name, row.description or "", *tags]
        ).lower()
