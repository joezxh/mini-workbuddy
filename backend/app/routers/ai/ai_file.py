"""AI 文件访问路由：/api/v1/ai/files/{file_id}（修复前端 404 契约）。

返回统一文件存储中的原始字节，供会话附件预览/下载使用。
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.file import file_config_service, file_service

router = APIRouter(prefix="/ai/files", tags=["AI 文件"])


@router.get("/{file_id}")
def get_ai_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    download: bool = Query(False, description="是否强制下载"),
):
    record = file_service.get_file(db, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")
    client = file_config_service.get_client_by_config_id(db, record.config_id)
    content = client.get_content(record.path, db)
    if content is None:
        raise HTTPException(status_code=404, detail="文件内容不存在")
    name = record.name or record.path.split("/")[-1]
    headers = {}
    if download:
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
    return Response(content=content, media_type=record.type or "application/octet-stream", headers=headers)
