"""SOP 模板 API。

spec: docs/design/sop-assistant-mode-design.md §4.3

router 自带完整 prefix ``/api/v1/sop``，故路由注册表不再叠加前缀。

- ``GET    /api/v1/sop/templates``        列表 / 关键词检索
- ``POST   /api/v1/sop/templates``        新建自定义模板
- ``GET    /api/v1/sop/templates/{id}``   详情
- ``PUT    /api/v1/sop/templates/{id}``   更新
- ``DELETE /api/v1/sop/templates/{id}``   删除（系统内置模板禁止删除）
- ``POST   /api/v1/sop/seed``             按代码注册表播种模板
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.sop.schemas import SOPDefinition
from app.db.database import get_db
from app.services.sop_service import SOPTemplateService

router = APIRouter(prefix="/api/v1/sop", tags=["SOP 模板"])


class SOPTemplateIn(BaseModel):
    """新建模板入参。template_key 缺省时自动生成。"""

    template_key: Optional[str] = None
    name: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    definition: SOPDefinition
    created_by: Optional[str] = None


class SOPTemplateUpdate(BaseModel):
    """更新模板入参（全字段可选）。"""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    definition: Optional[SOPDefinition] = None
    enabled: Optional[bool] = None


def _dump(row) -> Dict[str, Any]:
    """ORM 行 → API 响应字典。"""
    return {
        "id": row.id,
        "template_key": row.template_key,
        "name": row.name,
        "description": row.description,
        "tags": row.tags or [],
        "definition": row.definition,
        "builtin": row.builtin,
        "enabled": row.enabled,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/templates")
def list_templates(
    keyword: str = Query("", description="关键词：匹配 key/名称/描述/标签"),
    include_disabled: bool = Query(False, description="是否包含已停用模板"),
    db: Session = Depends(get_db),
):
    """模板列表 / 检索，供前端模板选择器使用。"""
    service = SOPTemplateService(db)
    return [_dump(r) for r in service.list_templates(keyword, include_disabled)]


@router.post("/templates")
def create_template(payload: SOPTemplateIn, db: Session = Depends(get_db)):
    """新建模板（用户自建，builtin=False）。"""
    service = SOPTemplateService(db)
    template_key = payload.template_key or f"custom_{uuid.uuid4().hex[:8]}"
    if service.get_by_key(template_key):
        raise HTTPException(status_code=409, detail=f"模板标识已存在: {template_key}")

    row = service.create(
        {
            "template_key": template_key,
            "name": payload.name,
            "description": payload.description,
            "tags": payload.tags,
            "definition": payload.definition.model_dump(mode="json"),
            "builtin": False,
            "enabled": True,
            "created_by": payload.created_by,
        }
    )
    return _dump(row)


@router.get("/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    service = SOPTemplateService(db)
    row = service.get(template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _dump(row)


@router.put("/templates/{template_id}")
def update_template(
    template_id: int, payload: SOPTemplateUpdate, db: Session = Depends(get_db)
):
    service = SOPTemplateService(db)
    row = service.get(template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    data = payload.model_dump(exclude_unset=True)
    definition = data.pop("definition", None)
    if definition is not None:
        data["definition"] = definition.model_dump(mode="json")
    return _dump(service.update(row, data))


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """删除模板；系统内置模板（builtin=True）不允许删除。"""
    service = SOPTemplateService(db)
    row = service.get(template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    if row.builtin:
        raise HTTPException(status_code=400, detail="系统内置模板不可删除")
    service.delete(row)
    return {"deleted": True, "id": template_id}


@router.post("/seed")
def seed_templates(db: Session = Depends(get_db)):
    """按代码注册表播种模板（幂等，按 template_key）。"""
    return SOPTemplateService(db).seed()
