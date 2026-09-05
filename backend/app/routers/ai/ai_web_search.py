"""AI 联网搜索供应商路由。"""
import logging
import time
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.ai.ai_web_search import AiWebSearch, AiWebSearchLog
from app.schemas.ai.ai_web_search import (
    AiWebSearchCreate,
    WebSearchUpdate,
    WebSearchTestRequest,
    WebSearchQuotaItem,
    WebSearchHealthItem,
    WebSearchLogResp,
)
from app.ai.web_search.factory import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/web-search", tags=["AI 联网搜索"])


# ============= CRUD =============

@router.get("/page")
def get_web_search_page(
    name: Optional[str] = Query(None, description="名称搜索"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    status: Optional[int] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """分页获取搜索供应商列表"""
    query = db.query(AiWebSearch)

    if name:
        query = query.filter(AiWebSearch.name.contains(name))
    if platform:
        query = query.filter(AiWebSearch.platform == platform)
    if status is not None:
        query = query.filter(AiWebSearch.status == status)

    total = query.count()
    items = (
        query.order_by(AiWebSearch.sort.desc(), AiWebSearch.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    return {
        "data": [_to_resp(item) for item in items],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.get("/simple-list")
def get_web_search_simple_list(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """简易列表（仅启用状态）"""
    items = (
        db.query(AiWebSearch)
        .filter(AiWebSearch.status == 1)
        .order_by(AiWebSearch.sort.desc(), AiWebSearch.id.desc())
        .all()
    )
    return [{"id": i.id, "name": i.name, "platform": i.platform} for i in items]


@router.post("/create")
def create_web_search(
    data: AiWebSearchCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建搜索供应商"""
    item = AiWebSearch(
        name=data.name,
        api_key=data.api_key,
        platform=data.platform,
        url=data.url or "",
        app_id=data.app_id or "",
        property=data.property or {},
        timeout=data.timeout,
        max_results=data.max_results,
        daily_quota=data.daily_quota,
        priority=data.priority,
        status=data.status,
        sort=data.sort,
        creator=current_user.username if current_user else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": "创建成功"}


@router.post("/update")
def update_web_search(
    data: WebSearchUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新搜索供应商"""
    item = db.query(AiWebSearch).filter(AiWebSearch.id == data.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="搜索供应商不存在")

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if k == "id":
            continue
        setattr(item, k, v)

    item.updater = current_user.username if current_user else None
    item.updated_at = datetime.now()
    db.commit()
    return {"id": item.id, "message": "更新成功"}


@router.delete("/delete")
def delete_web_search(
    id: int = Query(..., description="搜索供应商 ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除搜索供应商"""
    item = db.query(AiWebSearch).filter(AiWebSearch.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="搜索供应商不存在")

    db.delete(item)
    db.commit()
    return {"message": "删除成功"}


# ============= 搜索测试 =============

@router.post("/test")
async def test_web_search(
    req: WebSearchTestRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """测试搜索功能"""
    item = db.query(AiWebSearch).filter(AiWebSearch.id == req.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="搜索供应商不存在")
    if item.status != 1:
        raise HTTPException(status_code=400, detail="搜索供应商已禁用")

    provider = get_provider(item.platform)
    start = time.perf_counter()
    try:
        result = await provider.search(
            query=req.query,
            api_key=item.api_key,
            url=item.url or "",
            config=item.property,
        )
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    # 记录调用日志 + 递增当日使用量
    ok = not result.raw.get("error")
    log = AiWebSearchLog(
        web_search_id=item.id,
        service_name=item.name,
        platform=item.platform,
        query=req.query,
        response_time=elapsed_ms,
        results_count=result.total,
        success=ok,
        error=result.raw.get("error", "") if not ok else "",
    )
    db.add(log)
    item.used_count = (item.used_count or 0) + 1
    item.quota_date = datetime.now().date()
    db.commit()

    return result.to_dict()


# ============= Helper =============

def _to_resp(item: AiWebSearch) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "api_key": item.api_key,
        "platform": item.platform,
        "url": item.url or "",
        "app_id": item.app_id or "",
        "property": item.property or {},
        "timeout": item.timeout,
        "max_results": item.max_results,
        "daily_quota": item.daily_quota,
        "used_count": item.used_count or 0,
        "priority": item.priority,
        "status": item.status,
        "sort": item.sort,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "creator": item.creator,
        "updater": item.updater,
    }


# ============= 配额 / 健康 / 日志 =============

@router.get("/quota", response_model=list[WebSearchQuotaItem])
def get_web_search_quota(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """配额与用量统计（用于进度条可视化）"""
    from datetime import date

    today = date.today()
    items = db.query(AiWebSearch).order_by(AiWebSearch.sort.desc()).all()
    result: list[WebSearchQuotaItem] = []
    for it in items:
        quota = it.daily_quota or 0
        # 仅统计当天的用量（跨天后 used_count 尚未被搜索触发重置时，进度条也归零）
        used = (it.used_count or 0) if it.quota_date == today else 0
        remaining = max(quota - used, 0) if quota > 0 else -1  # -1 表示不限
        percent = round(used / quota * 100, 1) if quota > 0 else 0.0
        result.append(
            WebSearchQuotaItem(
                id=it.id,
                name=it.name,
                platform=it.platform,
                daily_quota=quota,
                used_count=used,
                remaining=remaining,
                usage_percent=percent,
            )
        )
    return result


@router.get("/health", response_model=list[WebSearchHealthItem])
async def get_web_search_health(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """健康检查（正常/警告/异常）"""
    items = db.query(AiWebSearch).order_by(AiWebSearch.sort.desc()).all()
    result: list[WebSearchHealthItem] = []
    for it in items:
        if it.status != 1:
            result.append(
                WebSearchHealthItem(
                    id=it.id, name=it.name, platform=it.platform,
                    status="warning", message="供应商已禁用",
                )
            )
            continue
        provider = get_provider(it.platform)
        ok, msg, elapsed = await provider.health_check(
            api_key=it.api_key, url=it.url or "", config=it.property,
            timeout=it.timeout or 30,
        )
        result.append(
            WebSearchHealthItem(
                id=it.id, name=it.name, platform=it.platform,
                status="normal" if ok else "error",
                message=msg, response_time=elapsed,
            )
        )
    return result


@router.get("/logs", response_model=list[WebSearchLogResp])
def get_web_search_logs(
    web_search_id: Optional[int] = Query(None, description="按供应商筛选"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """搜索调用日志列表"""
    query = db.query(AiWebSearchLog)
    if web_search_id is not None:
        query = query.filter(AiWebSearchLog.web_search_id == web_search_id)
    items = (
        query.order_by(AiWebSearchLog.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return [_log_to_resp(i) for i in items]


def _log_to_resp(log: AiWebSearchLog) -> dict:
    return {
        "id": log.id,
        "web_search_id": log.web_search_id,
        "service_name": log.service_name,
        "platform": log.platform,
        "query": log.query,
        "response_time": log.response_time,
        "results_count": log.results_count,
        "success": log.success,
        "error": log.error or "",
        "created_at": log.created_at,
    }


@router.get("/{web_search_id}")
def get_web_search(
    web_search_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取搜索供应商详情"""
    item = db.query(AiWebSearch).filter(AiWebSearch.id == web_search_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="搜索供应商不存在")
    return _to_resp(item)
