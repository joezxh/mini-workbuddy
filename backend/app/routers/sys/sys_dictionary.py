"""字典数据路由"""
from app.middleware.audit_logger import AuditLogRoute
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.models.sys.sys_dictionary import SysDictionary, SysDictionaryItem
from app.schemas.sys.sys_dictionary import (
    SysDictionaryCreate, SysDictionaryUpdate, SysDictionaryResponse, SysDictionaryWithItemsResponse,
    SysDictionaryItemCreate, SysDictionaryItemUpdate, SysDictionaryItemResponse,
    SysDictionaryTreeNode, DictType, RegionResponse, RegionTreeNode
)
from app.services.sys.sys_dictionary_service import clear_dict_cache

router = APIRouter(route_class=AuditLogRoute)


# ==================== 字典管理 ====================

@router.get("/dictionaries")
def get_dictionaries(
    dict_type: Optional[str] = Query(None, description="字典类型"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(15, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取字典列表（分页）"""
    query = db.query(SysDictionary).filter(SysDictionary.is_deleted == False)
    
    if dict_type:
        query = query.filter(SysDictionary.dict_type == dict_type)
    if is_active is not None:
        query = query.filter(SysDictionary.is_active == is_active)
    
    total = query.count()
    dictionaries = (
        query.order_by(SysDictionary.sort_order, SysDictionary.dict_id)
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return {
        "data": dictionaries,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.get("/dictionaries/{dict_code}", response_model=SysDictionaryWithItemsResponse)
def get_dictionary(
    dict_code: str,
    include_inactive: bool = Query(False, description="是否包含未启用的项"),
    db: Session = Depends(get_db)
):
    """获取字典详情（包含字典项）"""
    dictionary = db.query(SysDictionary).filter(
        SysDictionary.dict_code == dict_code,
        SysDictionary.is_deleted == False
    ).first()
    
    if not dictionary:
        raise HTTPException(status_code=404, detail="字典不存在")
    
    # 查询字典项
    items_query = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code,
        SysDictionaryItem.is_deleted == False
    )
    
    if not include_inactive:
        items_query = items_query.filter(SysDictionaryItem.is_active == True)
    
    items = items_query.order_by(SysDictionaryItem.sort_order, SysDictionaryItem.item_id).all()
    
    # 构造响应
    result = SysDictionaryWithItemsResponse(
        dict_id=dictionary.dict_id,
        dict_code=dictionary.dict_code,
        dict_name=dictionary.dict_name,
        dict_type=dictionary.dict_type,
        description=dictionary.description,
        sort_order=dictionary.sort_order,
        is_active=dictionary.is_active,
        extra_data=dictionary.extra_data,
        created_at=dictionary.created_at,
        updated_at=dictionary.updated_at,
        items=items
    )
    
    return result


@router.post("/dictionaries", response_model=SysDictionaryResponse)
def create_dictionary(
    dictionary: SysDictionaryCreate,
    db: Session = Depends(get_db)
):
    """创建字典"""
    # 检查编码是否已存在
    existing = db.query(SysDictionary).filter(
        SysDictionary.dict_code == dictionary.dict_code,
        SysDictionary.is_deleted == False
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="字典编码已存在")
    
    db_dictionary = SysDictionary(**dictionary.model_dump())
    db.add(db_dictionary)
    db.commit()
    db.refresh(db_dictionary)
    
    return db_dictionary


@router.put("/dictionaries/{dict_code}", response_model=SysDictionaryResponse)
def update_dictionary(
    dict_code: str,
    dictionary: SysDictionaryUpdate,
    db: Session = Depends(get_db)
):
    """更新字典"""
    db_dictionary = db.query(SysDictionary).filter(
        SysDictionary.dict_code == dict_code,
        SysDictionary.is_deleted == False
    ).first()
    
    if not db_dictionary:
        raise HTTPException(status_code=404, detail="字典不存在")
    
    # 更新字段
    update_data = dictionary.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_dictionary, field, value)
    
    db.commit()
    db.refresh(db_dictionary)
    # 清除缓存
    clear_dict_cache(dict_code)
    return db_dictionary


@router.delete("/dictionaries/{dict_code}")
def delete_dictionary(
    dict_code: str,
    db: Session = Depends(get_db)
):
    """删除字典（软删除）"""
    db_dictionary = db.query(SysDictionary).filter(
        SysDictionary.dict_code == dict_code,
        SysDictionary.is_deleted == False
    ).first()
    
    if not db_dictionary:
        raise HTTPException(status_code=404, detail="字典不存在")
    
    # 软删除字典及其所有项
    db_dictionary.is_deleted = True
    db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code
    ).update({"is_deleted": True})
    
    db.commit()
    # 清除缓存
    clear_dict_cache(dict_code)

    return {"message": "删除成功"}


# ==================== 字典项管理 ====================

@router.get("/dictionaries/{dict_code}/items", response_model=List[SysDictionaryItemResponse])
def get_dictionary_items(
    dict_code: str,
    parent_code: Optional[str] = Query(None, description="父级编码"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db)
):
    """获取字典项列表"""
    query = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code,
        SysDictionaryItem.is_deleted == False
    )
    
    if parent_code is not None:
        query = query.filter(SysDictionaryItem.parent_code == parent_code)
    if is_active is not None:
        query = query.filter(SysDictionaryItem.is_active == is_active)
    
    items = query.order_by(SysDictionaryItem.sort_order, SysDictionaryItem.item_id).all()
    return items


@router.get("/dictionaries/{dict_code}/tree", response_model=List[SysDictionaryTreeNode])
def get_dictionary_tree(
    dict_code: str,
    include_inactive: bool = Query(False, description="是否包含未启用的项"),
    db: Session = Depends(get_db)
):
    """获取字典树形结构"""
    query = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code,
        SysDictionaryItem.is_deleted == False
    )
    
    if not include_inactive:
        query = query.filter(SysDictionaryItem.is_active == True)
    
    items = query.order_by(SysDictionaryItem.sort_order, SysDictionaryItem.item_id).all()
    
    # 构建树形结构
    def build_tree(parent_code: Optional[str] = None) -> List[SysDictionaryTreeNode]:
        nodes = []
        for item in items:
            if item.parent_code == parent_code:
                node = SysDictionaryTreeNode(
                    item_id=item.item_id,
                    dict_code=item.dict_code,
                    item_code=item.item_code,
                    item_name=item.item_name,
                    item_value=item.item_value,
                    parent_code=item.parent_code,
                    level=item.level,
                    color=item.color,
                    icon=item.icon,
                    sort_order=item.sort_order,
                    is_active=item.is_active,
                    children=build_tree(item.item_code)
                )
                nodes.append(node)
        return nodes
    
    return build_tree()


@router.post("/dictionaries/{dict_code}/items", response_model=SysDictionaryItemResponse)
def create_dictionary_item(
    dict_code: str,
    item: SysDictionaryItemCreate,
    db: Session = Depends(get_db)
):
    """创建字典项"""
    # 检查字典是否存在
    dictionary = db.query(SysDictionary).filter(
        SysDictionary.dict_code == dict_code,
        SysDictionary.is_deleted == False
    ).first()
    
    if not dictionary:
        raise HTTPException(status_code=404, detail="字典不存在")
    
    # 检查编码是否已存在
    existing = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code,
        SysDictionaryItem.item_code == item.item_code,
        SysDictionaryItem.is_deleted == False
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="字典项编码已存在")
    
    db_item = SysDictionaryItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    # 清除缓存
    clear_dict_cache(dict_code)
    return db_item


@router.put("/dictionaries/{dict_code}/items/{item_code}", response_model=SysDictionaryItemResponse)
def update_dictionary_item(
    dict_code: str,
    item_code: str,
    item: SysDictionaryItemUpdate,
    db: Session = Depends(get_db)
):
    """更新字典项"""
    db_item = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code,
        SysDictionaryItem.item_code == item_code,
        SysDictionaryItem.is_deleted == False
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    
    # 更新字段
    update_data = item.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)
    
    db.commit()
    db.refresh(db_item)
    # 清除缓存
    clear_dict_cache(dict_code)
    return db_item


@router.delete("/dictionaries/{dict_code}/items/{item_code}")
def delete_dictionary_item(
    dict_code: str,
    item_code: str,
    db: Session = Depends(get_db)
):
    """删除字典项（软删除）"""
    db_item = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == dict_code,
        SysDictionaryItem.item_code == item_code,
        SysDictionaryItem.is_deleted == False
    ).first()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    
    db_item.is_deleted = True
    db.commit()
    # 清除缓存
    clear_dict_cache(dict_code)
    return {"message": "删除成功"}


# ==================== 快捷查询接口 ====================

@router.get("/dict/risk-levels", response_model=List[SysDictionaryItemResponse])
def get_risk_levels(db: Session = Depends(get_db)):
    """获取风险等级字典"""
    return db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == DictType.RISK_LEVEL,
        SysDictionaryItem.is_active == True,
        SysDictionaryItem.is_deleted == False
    ).order_by(SysDictionaryItem.sort_order).all()


@router.get("/dict/disposal-status", response_model=List[SysDictionaryItemResponse])
def get_disposal_status(db: Session = Depends(get_db)):
    """获取处置状态字典"""
    return db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == DictType.DISPOSAL_STATUS,
        SysDictionaryItem.is_active == True,
        SysDictionaryItem.is_deleted == False
    ).order_by(SysDictionaryItem.sort_order).all()


@router.get("/dict/event-types", response_model=List[SysDictionaryItemResponse])
def get_event_types(db: Session = Depends(get_db)):
    """获取事件类型字典"""
    return db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == DictType.EVENT_TYPE,
        SysDictionaryItem.is_active == True,
        SysDictionaryItem.is_deleted == False
    ).order_by(SysDictionaryItem.sort_order).all()


@router.get("/dict/regions/stats")
def get_region_stats_count(
    db: Session = Depends(get_db)
):
    """获取各级别区域数量统计"""
    from sqlalchemy import func
    from app.models.sys.sys_user import SysRegion
    results = db.query(
        SysRegion.region_level,
        func.count(SysRegion.region_id).label('count')
    ).filter(SysRegion.status == 'active').group_by(SysRegion.region_level).all()
    return {r.region_level: r.count for r in results}


@router.get("/dict/regions", response_model=List[RegionResponse])
def get_regions(
    parent_code: Optional[str] = Query(None, description="父级区域编码"),
    db: Session = Depends(get_db)
):
    """获取行政区域列表（从 sys_region 表查询，支持层级查询）"""
    from app.services.sys.region_service import RegionService
    region_service = RegionService(db)
    return region_service.get_regions(parent_code=parent_code)


@router.get("/dict/regions/tree", response_model=List[RegionTreeNode])
def get_regions_tree(
    parent_code: Optional[str] = Query(None, description="父级区域编码，不传则返回完整树"),
    db: Session = Depends(get_db)
):
    """获取行政区域树形结构（从 sys_region 表查询）"""
    from app.services.sys.region_service import RegionService
    region_service = RegionService(db)
    return region_service.get_region_tree(parent_code=parent_code)


@router.get("/dict/source-types", response_model=List[SysDictionaryItemResponse])
def get_source_types(db: Session = Depends(get_db)):
    """获取来源类型字典"""
    return db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == DictType.SOURCE_TYPE,
        SysDictionaryItem.is_active == True,
        SysDictionaryItem.is_deleted == False
    ).order_by(SysDictionaryItem.sort_order).all()


@router.get("/dict/person-manage-status", response_model=List[SysDictionaryItemResponse])
def get_person_manage_status(db: Session = Depends(get_db)):
    """获取人员管控状态字典"""
    return db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code == DictType.PERSON_MANAGE_STATUS,
        SysDictionaryItem.is_active == True,
        SysDictionaryItem.is_deleted == False
    ).order_by(SysDictionaryItem.sort_order).all()


@router.post("/dict/batch")
def get_batch_dictionaries(
    dict_codes: List[str],
    include_inactive: bool = Query(False, description="是否包含未启用的项"),
    db: Session = Depends(get_db)
):
    """
    批量获取多个字典的枚举值
    请求体：["code1", "code2", ...]
    返回：{"code1": [...items], "code2": [...items]}
    """
    if not dict_codes:
        return {}

    query = db.query(SysDictionaryItem).filter(
        SysDictionaryItem.dict_code.in_(dict_codes),
        SysDictionaryItem.is_deleted == False
    )
    if not include_inactive:
        query = query.filter(SysDictionaryItem.is_active == True)

    items = query.order_by(SysDictionaryItem.dict_code, SysDictionaryItem.sort_order, SysDictionaryItem.item_id).all()

    # 按 dict_code 分组，保持传入的顺序
    result: dict = {code: [] for code in dict_codes}
    for item in items:
        if item.dict_code in result:
            result[item.dict_code].append({
                "item_id":    item.item_id,
                "dict_code":  item.dict_code,
                "item_code":  item.item_code,
                "item_name":  item.item_name,
                "item_value": item.item_value,
                "parent_code":item.parent_code,
                "color":      item.color,
                "icon":       item.icon,
                "sort_order": item.sort_order,
                "is_active":  item.is_active,
            })
    return result


# ==================== 行政区域 CRUD ====================

@router.post("/regions", response_model=RegionResponse)
def create_region(
    data: dict,
    db: Session = Depends(get_db)
):
    """新增行政区域"""
    from app.models.sys.sys_user import SysRegion
    from app.services.sys.region_service import clear_region_cache
    # 检查编码唯一性
    if db.query(SysRegion).filter(SysRegion.region_code == data.get('region_code')).first():
        raise HTTPException(status_code=400, detail="区域编码已存在")
    region = SysRegion(**{k: v for k, v in data.items() if hasattr(SysRegion, k)})
    db.add(region)
    db.commit()
    db.refresh(region)
    clear_region_cache()
    return region


@router.put("/regions/{region_code}", response_model=RegionResponse)
def update_region(
    region_code: str,
    data: dict,
    db: Session = Depends(get_db)
):
    """更新行政区域"""
    from app.models.sys.sys_user import SysRegion
    from app.services.sys.region_service import clear_region_cache
    region = db.query(SysRegion).filter(SysRegion.region_code == region_code).first()
    if not region:
        raise HTTPException(status_code=404, detail="区域不存在")
    allowed = {'region_name', 'parent_code', 'region_level', 'full_path', 'sort_order', 'longitude', 'latitude', 'status'}
    for k, v in data.items():
        if k in allowed:
            setattr(region, k, v)
    db.commit()
    db.refresh(region)
    clear_region_cache()
    return region


@router.delete("/regions/{region_code}")
def delete_region(
    region_code: str,
    db: Session = Depends(get_db)
):
    """删除行政区域（同时删除所有子区域）"""
    from app.services.sys.region_service import clear_region_cache
    from sqlalchemy import text
    # 递归删除子区域（用递归 CTE）
    db.execute(text("""
        WITH RECURSIVE children AS (
            SELECT region_code FROM sys_region WHERE region_code = :code
            UNION ALL
            SELECT r.region_code FROM sys_region r
            INNER JOIN children c ON r.parent_code = c.region_code
        )
        DELETE FROM sys_region WHERE region_code IN (SELECT region_code FROM children)
    """), {"code": region_code})
    db.commit()
    clear_region_cache()
    return {"message": "删除成功"}
