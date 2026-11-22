"""统一文件管理路由（对齐 Java /system/file 端点，适配本工程 /api/v1 前缀）。"""
from __future__ import annotations

from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user
from app.models.sys.sys_user import SysUser
from app.services.file import archive_extract_service, file_service

router = APIRouter(prefix="/system/file", tags=["文件管理"])


def _ok(data=None, message="success"):
    return {"code": 0, "message": message, "data": data}


def _tenant_id(user: SysUser | None) -> int | None:
    return getattr(user, "tenant_id", None) if user else None


def _creator(user: SysUser | None) -> str | None:
    return getattr(user, "username", None) if user else None


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    directory: str = Form(""),
    code: str = Form(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """模式一：后端上传。指定 code 用对应存储，否则用 master。"""
    content = file.file.read()
    try:
        record = file_service.create_file(
            db, content, file.filename or "unnamed", directory=directory,
            code=code or None, mime=file.content_type, creator=_creator(current_user),
            tenant_id=_tenant_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok({"id": record.id, "url": record.url, "path": record.path,
                "name": record.name, "size": record.size, "type": record.type})


@router.post("/upload-archive")
def upload_archive(
    file: UploadFile = File(...),
    directory: str = Form(""),
    code: str = Form(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """上传 zip/7z 并创建异步解压任务，立即返回 taskId。"""
    content = file.file.read()
    try:
        task = archive_extract_service.create_archive_task(
            db, content, file.filename or "archive.zip", directory=directory, code=code or None,
            user_id=getattr(current_user, "user_id", None),
            tenant_id=_tenant_id(current_user), creator=_creator(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(task)


@router.get("/upload-archive/{task_id}")
def get_archive_progress(task_id: str):
    task = archive_extract_service.get_archive_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return _ok(task)


@router.delete("/upload-archive/{task_id}")
def cancel_archive(task_id: str):
    return _ok(archive_extract_service.cancel_archive_task(task_id))


@router.get("/presigned-url")
def get_presigned_url(
    name: str = Query(...),
    directory: str = Query(""),
    code: str = Query(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """模式二：获取上传预签名 URL（LOCAL/DB 不支持，返回 400）。"""
    try:
        return _ok(file_service.presign_put_url(db, name, directory, code or None))
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/create")
def create_file(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """模式二：前端直传完成后登记文件。"""
    try:
        record = file_service.create_file_declared(db, payload, _tenant_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ok(record.id)


@router.delete("/delete")
def delete_file(id: int = Query(...), db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    return _ok(file_service.delete_file(db, id, _tenant_id(current_user)))


@router.delete("/delete-list")
def delete_file_list(ids: str = Query(...), db: Session = Depends(get_db),
                     current_user: SysUser = Depends(get_current_user)):
    try:
        id_list = [int(i) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids 格式错误")
    return _ok(file_service.delete_file_list(db, id_list, _tenant_id(current_user)))


@router.get("/{file_id}/download")
def download_file_by_id(file_id: int, db: Session = Depends(get_db)):
    """按文件 ID 下载（业务模块如图片资产统一使用此端点）。"""
    from urllib.parse import quote
    from app.services.file import file_config_service

    record = file_service.get_file(db, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")
    client = file_config_service.get_client_by_config_id(db, record.config_id)
    content = client.get_content(record.path, db)
    if content is None:
        raise HTTPException(status_code=404, detail="文件内容不存在")
    name = record.name or record.path.split("/")[-1]
    return Response(
        content=content, media_type=record.type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


@router.get("/{config_id}/get/{path:path}")
def get_file_content(
    config_id: int, path: str, db: Session = Depends(get_db),
    download: bool = Query(False, description="true=强制下载(attachment)；默认 inline 供预览"),
):
    """文件内容端点：默认 inline + 正确 MIME（预览用）；download=1 时 attachment 下载。

    仅放行 DB 有精确记录的路径，防路径穿越。
    """
    from sqlalchemy import select
    from app.models.sys.sys_infra_file import SysInfraFile

    path = unquote(path)
    record = db.execute(
        select(SysInfraFile).where(
            SysInfraFile.config_id == config_id,
            SysInfraFile.path == path,
            SysInfraFile.deleted == "0",
        ).limit(1)
    ).scalars().first()
    if record is None:
        return Response(status_code=404)
    content = file_service.get_file_content(db, config_id, path)
    if content is None:
        return Response(status_code=404)
    file_name = record.name or path.split("/")[-1]
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type=record.type or "application/octet-stream",
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(file_name)}"},
    )


@router.get("/page")
def get_file_page(
    page: int = Query(1, ge=1), pageSize: int = Query(15, ge=1, le=100),
    configId: int | None = Query(None), path: str = Query(""), type: str = Query(""),
    db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user),
):
    return _ok(file_service.get_file_page(
        db, page, pageSize, configId, path or None, type or None,
        tenant_id=_tenant_id(current_user),
    ))


@router.get("/directories")
def get_directories(db: Session = Depends(get_db),
                    current_user: SysUser = Depends(get_current_user)):
    return _ok(file_service.get_directories(db, tenant_id=_tenant_id(current_user)))


@router.get("/statistics")
def get_statistics(db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    return _ok(file_service.get_statistics(db, tenant_id=_tenant_id(current_user)))
