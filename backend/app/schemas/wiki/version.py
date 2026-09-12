"""Wiki 版本相关 Pydantic schemas（G2）。"""
from typing import List, Optional

from pydantic import BaseModel


class VersionResponse(BaseModel):
    id: int
    article_id: int
    version: int
    title: str
    slug: Optional[str] = None
    change_note: Optional[str] = None
    editor_id: Optional[int] = None
    operation_type: str = "edit"
    created_at: Optional[str] = None


class DiffResult(BaseModel):
    article_id: int
    current_version: int
    target_version: int
    diff: str


class RollbackRequest(BaseModel):
    change_note: Optional[str] = None
