"""MCP 服务管理路由 - API Key / Client / Square。"""
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.ai.ai_mcp_api_key import AiMcpApiKey
from app.models.ai.ai_mcp_client import AiMcpClient
from app.models.ai.ai_mcp_square_template import AiMcpSquareTemplate
from app.schemas.ai.ai_mcp import (
    AiMcpApiKeyCreate, AiMcpApiKeyUpdate, AiMcpApiKeyPageResp,
    AiMcpApiKeyDetailResp, AiMcpApiKeySimpleResp,
    AiMcpClientCreate, AiMcpClientUpdate, AiMcpClientPageResp,
    McpSquareInstallReq, McpSquareCreate, McpSquareUpdate, McpSquarePageResp,
)

logger = logging.getLogger(__name__)

# protocol_type 自动推导映射
PROTOCOL_TYPE_MAP = {
    "nacos2": "Nacos Registry",
    "nacos3": "Nacos Registry",
    "http": "Streamable HTTP",
    "sse": "SSE",
}

# ============= API Key Router =============
router = APIRouter(prefix="/ai/mcp-api-key", tags=["MCP API Key"])


@router.get("/page")
def get_mcp_api_key_page(
    name: Optional[str] = Query(None, description="密钥名称搜索"),
    service_type: Optional[str] = Query(None, description="服务类型筛选"),
    status: Optional[int] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """分页获取 MCP API Key 列表"""
    query = db.query(AiMcpApiKey)
    if name:
        query = query.filter(AiMcpApiKey.name.contains(name))
    if service_type:
        query = query.filter(AiMcpApiKey.service_type == service_type)
    if status is not None:
        query = query.filter(AiMcpApiKey.status == status)
    total = query.count()
    items = query.order_by(AiMcpApiKey.sort.desc(), AiMcpApiKey.id.desc())\
        .offset((page - 1) * pageSize).limit(pageSize).all()
    return {
        "data": [AiMcpApiKeyPageResp.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.get("/get")
def get_mcp_api_key(
    id: int = Query(..., description="ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 MCP API Key 详情"""
    item = db.query(AiMcpApiKey).filter(AiMcpApiKey.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="API Key not found")
    return AiMcpApiKeyDetailResp.model_validate(item)


@router.post("/create")
def create_mcp_api_key(
    data: AiMcpApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建 MCP API Key"""
    obj = AiMcpApiKey(**data.model_dump(exclude_unset=True))
    obj.protocol_type = PROTOCOL_TYPE_MAP.get(data.service_type, "")
    obj.creator = current_user.username if current_user else "system"
    obj.updater = obj.creator
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "message": "创建成功"}


@router.post("/update")
def update_mcp_api_key(
    data: AiMcpApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新 MCP API Key"""
    obj = db.query(AiMcpApiKey).filter(AiMcpApiKey.id == data.id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="API Key not found")
    for k, v in data.model_dump(exclude_unset=True, exclude={"id"}).items():
        setattr(obj, k, v)
    if data.service_type:
        obj.protocol_type = PROTOCOL_TYPE_MAP.get(data.service_type, obj.protocol_type)
    obj.updater = current_user.username if current_user else "system"
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "message": "更新成功"}


@router.delete("/delete")
def delete_mcp_api_key(
    id: int = Query(..., description="ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除 MCP API Key（级联删除关联 Client）"""
    obj = db.query(AiMcpApiKey).filter(AiMcpApiKey.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="API Key not found")
    # 级联删除关联 Client
    db.query(AiMcpClient).filter(AiMcpClient.api_key_id == id).delete()
    db.delete(obj)
    db.commit()
    return {"message": "删除成功"}


@router.get("/simple-list")
def get_mcp_api_key_simple_list(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 MCP API Key 简易列表（启用状态）"""
    items = db.query(AiMcpApiKey).filter(AiMcpApiKey.status == 1)\
        .order_by(AiMcpApiKey.sort.desc()).all()
    return [AiMcpApiKeySimpleResp.model_validate(i) for i in items]


@router.get("/simple-select")
def get_mcp_server_select(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """MCP 服务下拉选择（合并数据源）。

    同时返回两类，供 Agent 绑定 MCP 服务时选择：
    1. 已安装的 MCP 服务（AiMcpApiKey，status=1）
    2. 系统内置提供的 MCP 服务（AiMcpSquareTemplate，status=1，且尚未安装）
    内置服务以 template_id 通过 't' 前缀标识，前端选中后由保存逻辑自动安装。
    """
    # 1. 已安装的 MCP 服务
    installed = (
        db.query(AiMcpApiKey)
        .filter(AiMcpApiKey.status == 1)
        .order_by(AiMcpApiKey.sort.desc())
        .all()
    )
    installed_template_ids = {i.template_id for i in installed if i.template_id}
    result = [
        {
            "value": i.id,
            "label": i.name,
            "service_type": i.service_type,
            "source": "installed",
            "template_id": i.template_id,
        }
        for i in installed
    ]

    # 2. 系统内置且尚未安装的 MCP 模板
    templates = (
        db.query(AiMcpSquareTemplate)
        .filter(AiMcpSquareTemplate.status == 1)
        .order_by(AiMcpSquareTemplate.sort.desc())
        .all()
    )
    for t in templates:
        if t.id in installed_template_ids:
            continue  # 已安装的不重复展示
        result.append(
            {
                "value": f"t{t.id}",
                "label": t.name,
                "service_type": t.service_type,
                "source": "builtin",
                "template_id": t.id,
            }
        )
    return result


# ============= Client Router =============
client_router = APIRouter(prefix="/ai/mcp-client", tags=["MCP Client"])


@client_router.get("/page")
def get_mcp_client_page(
    api_key_id: int = Query(..., description="关联API Key ID"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """分页获取 MCP Client 列表"""
    query = db.query(AiMcpClient).filter(AiMcpClient.api_key_id == api_key_id)
    total = query.count()
    items = query.order_by(AiMcpClient.id.desc())\
        .offset((page - 1) * pageSize).limit(pageSize).all()
    return {
        "data": [AiMcpClientPageResp.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@client_router.get("/get")
def get_mcp_client(
    id: int = Query(..., description="ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 MCP Client 详情"""
    item = db.query(AiMcpClient).filter(AiMcpClient.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Client not found")
    return AiMcpClientPageResp.model_validate(item)


@client_router.post("/create")
def create_mcp_client(
    data: AiMcpClientCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建 MCP Client"""
    # 验证 API Key 存在
    api_key = db.query(AiMcpApiKey).filter(AiMcpApiKey.id == data.api_key_id).first()
    if not api_key:
        raise HTTPException(status_code=400, detail="关联的 API Key 不存在")
    obj = AiMcpClient(**data.model_dump(exclude_unset=True))
    obj.creator = current_user.username if current_user else "system"
    obj.updater = obj.creator
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "message": "创建成功"}


@client_router.post("/update")
def update_mcp_client(
    data: AiMcpClientUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新 MCP Client"""
    obj = db.query(AiMcpClient).filter(AiMcpClient.id == data.id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Client not found")
    for k, v in data.model_dump(exclude_unset=True, exclude={"id"}).items():
        setattr(obj, k, v)
    obj.updater = current_user.username if current_user else "system"
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "message": "更新成功"}


@client_router.delete("/delete")
def delete_mcp_client(
    id: int = Query(..., description="ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除 MCP Client"""
    obj = db.query(AiMcpClient).filter(AiMcpClient.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(obj)
    db.commit()
    return {"message": "删除成功"}


# ============= Square Router =============
square_router = APIRouter(prefix="/ai/mcp-square", tags=["MCP Square"])


@square_router.get("/page")
def get_mcp_square_page(
    name: Optional[str] = Query(None, description="模板名称搜索"),
    category: Optional[str] = Query(None, description="分类筛选"),
    status: Optional[int] = Query(None, description="状态筛选 (None=全部, 1=启用, 0=禁用)"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """分页获取 MCP 广场模板列表"""
    query = db.query(AiMcpSquareTemplate)
    if name:
        query = query.filter(AiMcpSquareTemplate.name.contains(name))
    if category:
        query = query.filter(AiMcpSquareTemplate.category == category)
    if status is not None:
        query = query.filter(AiMcpSquareTemplate.status == status)
    total = query.count()
    items = query.order_by(AiMcpSquareTemplate.sort.desc(), AiMcpSquareTemplate.id.desc())\
        .offset((page - 1) * pageSize).limit(pageSize).all()

    # 查询已安装的模板ID集合
    installed_ids = set(
        r[0] for r in db.query(AiMcpApiKey.template_id)
        .filter(AiMcpApiKey.template_id > 0).all()
    )
    result = []
    for item in items:
        resp = McpSquarePageResp.model_validate(item)
        resp.is_installed = item.id in installed_ids
        result.append(resp)
    return {
        "data": result,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@square_router.get("/get")
def get_mcp_square_detail(
    id: int = Query(..., description="模板ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """获取 MCP 广场模板详情"""
    item = db.query(AiMcpSquareTemplate).filter(AiMcpSquareTemplate.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    # 标记是否已安装
    installed = db.query(AiMcpApiKey).filter(
        AiMcpApiKey.template_id == id
    ).first() is not None
    resp = McpSquarePageResp.model_validate(item)
    resp.is_installed = installed
    return resp


@square_router.post("/create")
def create_mcp_square(
    data: McpSquareCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建 MCP 广场模板"""
    # 检查名称唯一性
    exists = db.query(AiMcpSquareTemplate).filter(AiMcpSquareTemplate.name == data.name).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"模板名称已存在: {data.name}")
    obj = AiMcpSquareTemplate(**data.model_dump(exclude_unset=True))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "message": "创建成功"}


@square_router.post("/update")
def update_mcp_square(
    data: McpSquareUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新 MCP 广场模板"""
    obj = db.query(AiMcpSquareTemplate).filter(AiMcpSquareTemplate.id == data.id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="模板不存在")
    # 如果改名，检查唯一性
    if data.name and data.name != obj.name:
        exists = db.query(AiMcpSquareTemplate).filter(
            AiMcpSquareTemplate.name == data.name,
            AiMcpSquareTemplate.id != data.id,
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail=f"模板名称已存在: {data.name}")
    for k, v in data.model_dump(exclude_unset=True, exclude={"id"}).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "message": "更新成功"}


@square_router.delete("/delete")
def delete_mcp_square(
    id: int = Query(..., description="模板ID"),
    force: bool = Query(False, description="是否强制删除（级联删除已安装的 API Key）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删除 MCP 广场模板。
    默认：如果模板已被安装（有关联的 API Key），拒绝删除。
    force=True：级联删除所有关联 API Key 及其 Client。
    """
    obj = db.query(AiMcpSquareTemplate).filter(AiMcpSquareTemplate.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="模板不存在")
    installed_keys = db.query(AiMcpApiKey).filter(AiMcpApiKey.template_id == id).all()
    if installed_keys and not force:
        raise HTTPException(
            status_code=400,
            detail=f"模板已被安装（{len(installed_keys)} 个 API Key），请先卸载后再删除，或使用强制删除",
        )
    if force:
        # 级联删除关联 Client + API Key
        for key in installed_keys:
            db.query(AiMcpClient).filter(AiMcpClient.api_key_id == key.id).delete()
            db.delete(key)
    db.delete(obj)
    db.commit()
    return {"message": "删除成功"}


@square_router.post("/install")
def install_mcp_square(
    data: McpSquareInstallReq,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """安装 MCP 广场模板 - 支持用户自定义 URL/API Key 等参数"""
    template = db.query(AiMcpSquareTemplate).filter(
        AiMcpSquareTemplate.id == data.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    username = current_user.username if current_user else "system"

    # 用户自定义参数优先，回退到模板默认值
    svc_url = data.service_url or template.service_url
    access_path = data.access_path or template.access_path
    api_key_val = data.api_key
    svc_name = data.service_name
    ns = data.namespace
    grp = data.group_key

    # 创建 API Key
    api_key_obj = AiMcpApiKey(
        name=data.name or f"{template.name}",
        service_type=template.service_type,
        platform=template.platform,
        version=template.version,
        description=template.description,
        service_url=svc_url,
        access_path=access_path,
        api_key=api_key_val,
        service_name=svc_name,
        namespace=ns,
        group_key=grp,
        capabilities=template.capabilities,
        template_id=template.id,
        health_status="unknown",
        creator=username,
        updater=username,
    )
    api_key_obj.protocol_type = PROTOCOL_TYPE_MAP.get(template.service_type, "")
    db.add(api_key_obj)
    db.flush()

    # 根据 default_client_config 创建 Client
    client_cfg = template.default_client_config or {}
    client_obj = AiMcpClient(
        name=f"{template.name} Client",
        api_key_id=api_key_obj.id,
        client_type=client_cfg.get("client_type", "http"),
        mcp_type=client_cfg.get("mcp_type", "tool"),
        version=template.version,
        tools_config=client_cfg.get("tools_config"),
        creator=username,
        updater=username,
    )
    db.add(client_obj)
    db.commit()
    return {"id": api_key_obj.id, "message": "安装成功"}


@square_router.post("/test/{id}")
async def test_mcp_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """测试 MCP 服务连接是否可用。

    策略：
    1. 配置完整性检查（必须有 service_url 或 service_name）
    2. 真实探测：HTTP/SSE 发 GET 请求，Nacos 检查服务名存在性
    3. 结果持久化到 health_status + last_check_at
    """
    obj = db.query(AiMcpApiKey).filter(AiMcpApiKey.id == id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="API Key not found")

    status = "unknown"
    detail = ""

    try:
        if obj.service_type in ("http", "sse"):
            # HTTP/SSE 探测
            url = obj.service_url or ""
            if obj.access_path:
                url = url.rstrip("/") + obj.access_path
            if not url:
                status = "unhealthy"
                detail = "缺少服务地址"
            else:
                headers = {}
                if obj.api_key:
                    headers["Authorization"] = f"Bearer {obj.api_key}"
                async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code < 500:
                        status = "healthy"
                        detail = f"HTTP {resp.status_code}"
                    else:
                        status = "unhealthy"
                        detail = f"HTTP {resp.status_code}"

        elif obj.service_type in ("nacos2", "nacos3"):
            # Nacos 探测：检查服务名是否注册
            if not obj.service_name:
                status = "unhealthy"
                detail = "缺少 Nacos 服务名"
            else:
                nacos_url = obj.service_url or ""
                if not nacos_url:
                    status = "unhealthy"
                    detail = "缺少 Nacos 服务地址"
                else:
                    api_path = f"/nacos/v1/ns/instance/list?serviceName={obj.service_name}"
                    if obj.namespace:
                        api_path += f"&namespaceId={obj.namespace}"
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(nacos_url.rstrip("/") + api_path)
                        if resp.status_code == 200:
                            status = "healthy"
                            detail = "Nacos 服务已注册"
                        else:
                            status = "unhealthy"
                            detail = f"Nacos HTTP {resp.status_code}"
        else:
            status = "unknown"
            detail = f"未知服务类型: {obj.service_type}"

    except httpx.TimeoutException:
        status = "unhealthy"
        detail = "连接超时（5s）"
    except httpx.ConnectError:
        status = "unhealthy"
        detail = "连接失败，请检查地址是否正确"
    except Exception as e:
        status = "unhealthy"
        detail = str(e)[:200]

    # 持久化健康状态
    obj.health_status = status
    obj.last_check_at = datetime.now()
    db.commit()

    return {
        "id": obj.id,
        "health_status": status,
        "detail": detail,
        "checked_at": obj.last_check_at.isoformat(),
    }


@square_router.delete("/uninstall")
def uninstall_mcp_square(
    api_key_id: int = Query(..., description="API Key ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """卸载已安装的 MCP 广场模板"""
    obj = db.query(AiMcpApiKey).filter(AiMcpApiKey.id == api_key_id).first()
    if not obj or obj.template_id == 0:
        raise HTTPException(status_code=404, detail="未找到已安装的模板")
    # 级联删除关联 Client
    db.query(AiMcpClient).filter(AiMcpClient.api_key_id == api_key_id).delete()
    db.delete(obj)
    db.commit()
    return {"message": "卸载成功"}


# ============= MCP Tools (已注册知识工具) Router =============
mcp_tools_router = APIRouter(prefix="/ai/mcp-tools", tags=["MCP 已注册工具"])

# 工具名称 → 分类映射（MinWorkBuddy: 已移除域特定工具）
_TOOL_CATEGORY_MAP = {
    "knowledge_base_search": "知识库",
    "semantic_query": "语义查询",
    # 推理工具
    "reasoning_rule_lookup": "推理分析",
    "event_aggregation_compute": "推理分析",
    "social_relation_confidence_compute": "推理分析",
}


def _get_tool_category(tool_name: str) -> str:
    """根据工具名称返回分类。"""
    return _TOOL_CATEGORY_MAP.get(tool_name, "其他")


@mcp_tools_router.get("/list")
def list_mcp_tools(
    name: Optional[str] = Query(None, description="工具名称搜索"),
    category: Optional[str] = Query(None, description="分类筛选"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
):
    """列出已注册的 MCP 知识库工具（从内存缓存读取，无需数据库）。"""
    from app.ai.mcp.server import get_knowledge_tools

    all_tools = get_knowledge_tools()
    items = []
    for t in all_tools:
        cat = _get_tool_category(t.name)
        entry = {
            "name": t.name,
            "description": t.description,
            "category": cat,
            "input_schema": t.input_schema if hasattr(t, "input_schema") else {},
        }
        # 过滤
        if name and name.lower() not in t.name.lower():
            continue
        if category and cat != category:
            continue
        items.append(entry)

    total = len(items)
    start = (page - 1) * pageSize
    page_items = items[start: start + pageSize]
    return {
        "data": page_items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }
