"""AI 工具管理 Router。

实现 docs/ai-scene.md 测试场景 1-11 的「工具管理」接口，以及「工具分组」管理接口。
路由前缀: /api/v1/admin/ai/tool
"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.sys.sys_user import SysUser
from app.models.ai.ai_tool_definition import AiToolDefinition
from app.models.ai.ai_tool_group import AiToolGroup, AiToolGroupMember
from app.schemas.ai.ai_tool import (
    AiToolCreate, AiToolUpdate, AiToolGroupCreate, AiToolGroupUpdate, AiToolGroupMemberAdd, AiToolTestRequest,
)
from app.ai.tool_manager import get_tool_manager, ToolExecutor
from app.ai.tool_manager.sqlbot_tool_config import validate_config
from app.ai.tool_manager.sqlbot_tool_factory import SQLBOT_TEMPLATE_CLASS_PATH
from app.ai.tool_manager.tool_context import bind_tool_user, build_user_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/tool", tags=["AI 工具管理"])

# 默认分类（与场景 2 保持一致，作为兜底）
DEFAULT_CATEGORIES = [
    "信息查询", "数据处理", "AI增强",
    # AgentScope 内置工具分类
    "文件系统", "任务管理", "Shell执行",
    # 项目自定义开发工具分类
    "文档处理", "自动化", "消息通知", "数据分析",
]

SYSTEM_DELETE_CODE = "TOOL_SYSTEM_CANNOT_DELETE"


def _apply_sqlbot_defaults(data: Any, *, is_create: bool) -> None:
    """当 ``type=sqlbot`` 时，自动注入通用实现类与方法，并对 config_value 做声明式校验。

    直接在 Pydantic 模型上原地修改，避免多次赋值。
    """
    if getattr(data, "type", None) != "sqlbot":
        return
    if is_create or data.className is None:
        data.className = SQLBOT_TEMPLATE_CLASS_PATH
    if is_create or data.methodName is None:
        data.methodName = "call"
    if data.configValue:
        cfg, errors, warnings = validate_config(data.configValue)
        if errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "SQLBot 工具配置校验失败", "errors": errors},
            )


# ===========================================================================
# 工具 CRUD
# ===========================================================================

def _to_dict(m: AiToolDefinition) -> dict:
    return {
        "id": m.id,
        "toolKey": m.tool_key,
        "displayName": m.display_name,
        "category": m.category,
        "type": m.tool_type,
        "className": m.class_name,
        "methodName": m.method_name,
        "description": m.description,
        "configSchema": m.config_schema,
        "configValue": m.config_value,
        "inputSchema": m.input_schema,
        "outputSchema": m.output_schema,
        "status": m.status,
        "isSystem": m.is_system,
        "sort": m.sort,
        "creator": m.creator,
        "updater": m.updater,
        "createdAt": m.created_at.isoformat() if m.created_at else None,
        "updatedAt": m.updated_at.isoformat() if m.updated_at else None,
    }


@router.get("/page")
def tool_page(
    toolKey: Optional[str] = Query(None, description="按 toolKey 模糊搜索"),
    displayName: Optional[str] = Query(None, description="按 displayName 模糊搜索"),
    category: Optional[str] = Query(None, description="分类筛选"),
    type: Optional[str] = Query(None, description="类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选 enabled/disabled"),
    isSystem: Optional[bool] = Query(None, description="是否系统内置"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """工具列表分页（测试场景 1/2/11）"""
    query = db.query(AiToolDefinition)
    if toolKey:
        query = query.filter(AiToolDefinition.tool_key.contains(toolKey))
    if displayName:
        query = query.filter(AiToolDefinition.display_name.contains(displayName))
    if category:
        query = query.filter(AiToolDefinition.category == category)
    if type:
        query = query.filter(AiToolDefinition.tool_type == type)
    if status:
        query = query.filter(AiToolDefinition.status == status)
    if isSystem is not None:
        query = query.filter(AiToolDefinition.is_system == isSystem)

    total = query.count()
    items = (
        query.order_by(AiToolDefinition.sort.desc(), AiToolDefinition.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return {
        "data": [_to_dict(i) for i in items],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.get("/simple-list")
def tool_simple_list(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """工具简易列表（测试场景 10，下拉选择用）。返回全部工具，确保前端可加载并展示系统中全部工具。"""
    query = db.query(AiToolDefinition)
    if category:
        query = query.filter(AiToolDefinition.category == category)
    items = query.order_by(AiToolDefinition.sort.desc(), AiToolDefinition.id.desc()).all()
    return [
        {"id": i.id, "toolKey": i.tool_key, "displayName": i.display_name, "category": i.category}
        for i in items
    ]


@router.get("/get")
def tool_get(
    id: int = Query(..., description="工具 ID"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """工具详情（测试场景 4 回填来源）"""
    item = db.query(AiToolDefinition).filter(AiToolDefinition.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="工具不存在")
    return _to_dict(item)


@router.post("/create")
def tool_create(
    data: AiToolCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建工具（测试场景 3）"""
    _apply_sqlbot_defaults(data, is_create=True)

    exists = db.query(AiToolDefinition).filter(
        AiToolDefinition.tool_key == data.toolKey
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"toolKey 已存在: {data.toolKey}")

    item = AiToolDefinition(
        tool_key=data.toolKey,
        display_name=data.displayName,
        category=data.category,
        tool_type=data.type,
        class_name=data.className,
        method_name=data.methodName,
        description=data.description,
        config_schema=data.configSchema,
        config_value=data.configValue,
        input_schema=data.inputSchema,
        output_schema=data.outputSchema,
        status=data.status,
        is_system=data.isSystem,
        sort=data.sort,
        creator=current_user.username if current_user else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # 写入缓存
    get_tool_manager().cache_model(item)
    return {"id": item.id, "message": "创建成功"}


@router.post("/update")
def tool_update(
    data: AiToolUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """更新工具（测试场景 4/6）"""
    item = db.query(AiToolDefinition).filter(AiToolDefinition.id == data.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="工具不存在")

    _apply_sqlbot_defaults(data, is_create=False)

    if data.toolKey is not None and data.toolKey != item.tool_key:
        clash = db.query(AiToolDefinition).filter(
            AiToolDefinition.tool_key == data.toolKey
        ).first()
        if clash:
            raise HTTPException(status_code=400, detail=f"toolKey 已存在: {data.toolKey}")
        # 同步缓存 key
        get_tool_manager().evict(item.tool_key)
        item.tool_key = data.toolKey

    if data.displayName is not None:
        item.display_name = data.displayName
    if data.category is not None:
        item.category = data.category
    if data.type is not None:
        item.tool_type = data.type
    if data.className is not None:
        item.class_name = data.className
    if data.methodName is not None:
        item.method_name = data.methodName
    if data.description is not None:
        item.description = data.description
    if data.configSchema is not None:
        item.config_schema = data.configSchema
    if data.configValue is not None:
        item.config_value = data.configValue
    if data.inputSchema is not None:
        item.input_schema = data.inputSchema
    if data.outputSchema is not None:
        item.output_schema = data.outputSchema
    if data.status is not None:
        item.status = data.status
    if data.isSystem is not None:
        item.is_system = data.isSystem
    if data.sort is not None:
        item.sort = data.sort
    item.updater = current_user.username if current_user else None

    db.commit()
    db.refresh(item)
    get_tool_manager().cache_model(item)
    return {"id": item.id, "message": "更新成功"}


@router.delete("/delete")
def tool_delete(
    id: int = Query(..., description="工具 ID"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """删除工具（测试场景 7/8）"""
    item = db.query(AiToolDefinition).filter(AiToolDefinition.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="工具不存在")
    if item.is_system:
        raise HTTPException(
            status_code=400,
            detail={"code": SYSTEM_DELETE_CODE, "message": "系统内置工具不允许删除"},
        )
    db.delete(item)  # 关联成员由 FK ondelete CASCADE 清理
    db.commit()
    get_tool_manager().evict(item.tool_key)
    return {"message": "删除成功"}


@router.delete("/delete-list")
def tool_delete_list(
    ids: str = Query(..., description="逗号分隔的 ID 列表"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """批量删除工具（跳过系统内置，遇系统内置直接拒绝）"""
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids 格式错误")

    items = db.query(AiToolDefinition).filter(AiToolDefinition.id.in_(id_list)).all()
    if not items:
        raise HTTPException(status_code=404, detail="未找到工具")
    for it in items:
        if it.is_system:
            raise HTTPException(
                status_code=400,
                detail={"code": SYSTEM_DELETE_CODE, "message": f"系统内置工具不允许删除: {it.tool_key}"},
            )
    for it in items:
        db.delete(it)
    db.commit()
    for it in items:
        get_tool_manager().evict(it.tool_key)
    return {"message": f"已删除 {len(items)} 个工具"}


@router.post("/enable")
def tool_enable(
    id: int = Query(..., description="工具 ID"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """启用工具（自定义工具生命周期：启用/禁用）。"""
    item = db.query(AiToolDefinition).filter(AiToolDefinition.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="工具不存在")
    item.status = "enabled"
    db.commit()
    get_tool_manager().cache_model(item)
    return {"id": item.id, "status": item.status, "message": "已启用"}


@router.post("/disable")
def tool_disable(
    id: int = Query(..., description="工具 ID"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """禁用工具（自定义工具生命周期：启用/禁用）。"""
    item = db.query(AiToolDefinition).filter(AiToolDefinition.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="工具不存在")
    item.status = "disabled"
    db.commit()
    get_tool_manager().evict(item.tool_key)
    return {"id": item.id, "status": item.status, "message": "已禁用"}


@router.post("/test")
async def tool_test(
    payload: AiToolTestRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """测试工具执行（测试场景 5）

    对配置化工具（``config_value`` 非空）额外注入 config 与当前用户上下文，
    使行级数据权限与列级脱敏在试跑时同样生效。
    """
    executor = ToolExecutor()

    # 解析目标工具
    if payload.toolKey:
        item = db.query(AiToolDefinition).filter(
            AiToolDefinition.tool_key == payload.toolKey
        ).first()
    elif payload.id:
        item = db.query(AiToolDefinition).filter(
            AiToolDefinition.id == payload.id
        ).first()
    else:
        item = None

    class_name = payload.className
    method_name = payload.methodName
    config_value = None
    if item is not None:
        class_name = class_name or item.class_name
        method_name = method_name or item.method_name
        if isinstance(item.config_value, dict) and item.config_value:
            config_value = item.config_value

    # 构造并绑定当前用户上下文（供配置化工具的权限与脱敏使用）
    user_ctx = build_user_context(db, current_user)

    with bind_tool_user(user_ctx):
        result = await executor.execute(
            class_name=class_name,
            method_name=method_name,
            inputs=payload.inputs,
            config=config_value,
            context=user_ctx,
        )
    return result


@router.post("/refresh-cache")
def tool_refresh_cache(
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """刷新工具缓存（测试场景 9）"""
    mgr = get_tool_manager()
    count = mgr.reload(db)
    return {"message": "缓存刷新成功", "count": count}


@router.get("/categories")
def tool_categories(
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """获取分类列表（测试场景 2 下拉）"""
    rows = db.query(AiToolDefinition.category).filter(
        AiToolDefinition.category.isnot(None)
    ).distinct().all()
    cats = [r[0] for r in rows if r[0]]
    for c in DEFAULT_CATEGORIES:
        if c not in cats:
            cats.append(c)
    return cats


# ===========================================================================
# 工具分组管理
# ===========================================================================

def _group_to_dict(g: AiToolGroup, tool_count: int = 0) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "displayName": g.display_name,
        "description": g.description,
        "instructions": g.instructions,
        "isActive": g.is_active,
        "sort": g.sort,
        "toolCount": tool_count,
        "createdAt": g.created_at.isoformat() if g.created_at else None,
        "updatedAt": g.updated_at.isoformat() if g.updated_at else None,
    }


@router.get("/group/page")
def group_page(
    name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """分组列表分页"""
    query = db.query(AiToolGroup)
    if name:
        query = query.filter(AiToolGroup.name.contains(name))
    total = query.count()
    items = (
        query.order_by(AiToolGroup.sort.desc(), AiToolGroup.id.desc())
        .offset((page - 1) * pageSize).limit(pageSize).all()
    )
    result = []
    for g in items:
        cnt = db.query(AiToolGroupMember).filter(AiToolGroupMember.group_id == g.id).count()
        result.append(_group_to_dict(g, cnt))
    return {"data": result, "total": total, "page": page, "pageSize": pageSize}


@router.post("/group/create")
def group_create(
    data: AiToolGroupCreate,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """创建分组"""
    if db.query(AiToolGroup).filter(AiToolGroup.name == data.name).first():
        raise HTTPException(status_code=400, detail=f"分组名已存在: {data.name}")
    g = AiToolGroup(
        name=data.name,
        display_name=data.displayName,
        description=data.description,
        instructions=data.instructions,
        is_active=data.isActive,
        sort=data.sort,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"id": g.id, "message": "创建成功"}


@router.post("/group/update")
def group_update(
    data: AiToolGroupUpdate,
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """更新分组"""
    g = db.query(AiToolGroup).filter(AiToolGroup.name == data.name).first()
    if not g:
        raise HTTPException(status_code=404, detail="分组不存在")
    if data.displayName is not None:
        g.display_name = data.displayName
    if data.description is not None:
        g.description = data.description
    if data.instructions is not None:
        g.instructions = data.instructions
    if data.isActive is not None:
        g.is_active = data.isActive
    if data.sort is not None:
        g.sort = data.sort
    db.commit()
    db.refresh(g)
    return {"id": g.id, "message": "更新成功"}


@router.delete("/group/delete")
def group_delete(
    id: int = Query(..., description="分组 ID"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """删除分组"""
    g = db.query(AiToolGroup).filter(AiToolGroup.id == id).first()
    if not g:
        raise HTTPException(status_code=404, detail="分组不存在")
    db.delete(g)  # 成员由 FK ondelete CASCADE 清理
    db.commit()
    return {"message": "删除成功"}


@router.post("/group/members/add")
def group_members_add(
    group_id: int = Query(..., description="分组 ID"),
    data: AiToolGroupMemberAdd = Body(...),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """向分组添加工具成员"""
    g = db.query(AiToolGroup).filter(AiToolGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="分组不存在")
    added = 0
    for tk in data.toolKeys:
        tool = db.query(AiToolDefinition).filter(
            AiToolDefinition.tool_key == tk
        ).first()
        if not tool:
            continue
        exists = db.query(AiToolGroupMember).filter(
            AiToolGroupMember.group_id == group_id,
            AiToolGroupMember.tool_key == tk,
        ).first()
        if exists:
            continue
        db.add(AiToolGroupMember(group_id=group_id, tool_key=tk, sort_order=tool.sort))
        added += 1
    db.commit()
    return {"message": f"已添加 {added} 个成员"}


@router.post("/group/members/remove")
def group_members_remove(
    group_id: int = Query(..., description="分组 ID"),
    toolKey: str = Query(..., description="toolKey"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """从分组移除工具成员"""
    m = db.query(AiToolGroupMember).filter(
        AiToolGroupMember.group_id == group_id,
        AiToolGroupMember.tool_key == toolKey,
    ).first()
    if m:
        db.delete(m)
        db.commit()
    return {"message": "移除成功"}


@router.get("/group/members")
def group_members(
    group_id: int = Query(..., description="分组 ID"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """获取分组成员工具列表"""
    members = db.query(AiToolGroupMember).filter(
        AiToolGroupMember.group_id == group_id
    ).order_by(AiToolGroupMember.sort_order.desc()).all()
    result = []
    for m in members:
        tool = db.query(AiToolDefinition).filter(
            AiToolDefinition.tool_key == m.tool_key
        ).first()
        if tool:
            d = _to_dict(tool)
            d["groupSortOrder"] = m.sort_order
            result.append(d)
    return result
