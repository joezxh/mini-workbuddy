"""地区服务 - 提供地区数据查询功能（含进程级内存缓存）"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.sys.sys_user import SysRegion

# ─── 进程级内存缓存 ────────────────────────────────────────────────────────────
# 地区数据变化极少，使用进程级 dict 缓存，避免每次请求都查 DB
# 为避免数据变更后缓存长期陈旧，增加 TTL：超过 REGION_CACHE_TTL 秒自动失效重载。
import time as _time
_REGION_CACHE_TTL = 300  # 5 分钟
_region_mapping_cache: Dict[str, str] = {}  # region_code -> region_name
_region_mapping_loaded: bool = False  # 标记全量映射是否已加载
_region_cache_ts: float = 0.0  # 最近一次加载时间戳（用于 TTL 判断）
_region_items_cache: Dict[str, List[dict]] = {}  # cache_key -> items list


def clear_region_cache(region_code: Optional[str] = None) -> None:
    """
    清除地区缓存
    
    Args:
        region_code: 指定清除某个地区的缓存，None 表示清除全部缓存
    """
    global _region_mapping_cache, _region_mapping_loaded, _region_items_cache, _region_cache_ts
    if region_code:
        _region_mapping_cache.pop(region_code, None)
        # 清除所有以 region_code 开头的缓存键（包括带 parent_code 的情况）
        keys_to_remove = [key for key in _region_items_cache.keys() 
                         if key.startswith(f"{region_code}:") or key == region_code]
        for key in keys_to_remove:
            _region_items_cache.pop(key, None)
    else:
        _region_mapping_cache.clear()
        _region_mapping_loaded = False
        _region_cache_ts = 0.0
        _region_items_cache.clear()


class RegionService:
    """地区服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_region_mapping(self) -> Dict[str, str]:
        """
        获取地区代码到名称的映射（带进程级缓存）
        
        Returns:
            地区代码到名称的映射字典
        """
        global _region_mapping_loaded, _region_cache_ts
        
        # 缓存命中且未过期，直接返回
        if _region_mapping_loaded and (_region_cache_ts > 0 and _time.time() - _region_cache_ts < _REGION_CACHE_TTL):
            return _region_mapping_cache
        
        # 缓存未命中或已过期，查询 DB 并写入缓存
        result = self.db.query(SysRegion).filter(
            SysRegion.status == 'active'
        ).all()
        
        _region_mapping_cache.update(
            {region.region_code: region.region_name for region in result}
        )
        _region_mapping_loaded = True
        _region_cache_ts = _time.time()
        return _region_mapping_cache
    
    def get_region_name(self, region_code: str) -> str:
        """
        获取地区名称
        
        Args:
            region_code: 地区编码
            
        Returns:
            地区名称，如果不存在则返回原始代码
        """
        mapping = self.get_region_mapping()
        return mapping.get(region_code, region_code)
    
    def get_regions(self, parent_code: Optional[str] = None) -> List[dict]:
        """
        获取地区列表（包含所有字段，带进程级缓存）
        
        Args:
            parent_code: 父级编码（可选，用于获取指定父级下的子地区）
            
        Returns:
            地区列表
        """
        # 生成缓存 key（考虑 parent_code）
        cache_key = f"parent:{parent_code}" if parent_code else "all"
        
        # 缓存命中，直接返回
        if cache_key in _region_items_cache:
            return _region_items_cache[cache_key]
        
        # 构建查询
        query = self.db.query(SysRegion).filter(SysRegion.status == 'active')
        
        # 如果指定了父级编码，添加过滤条件
        if parent_code:
            query = query.filter(SysRegion.parent_code == parent_code)
        
        query = query.order_by(SysRegion.sort_order, SysRegion.region_id)
        
        # 缓存未命中，查询 DB 并写入缓存
        regions = query.all()
        
        items = [
            {
                "region_id": region.region_id,
                "region_code": region.region_code,
                "region_name": region.region_name,
                "parent_code": region.parent_code,
                "region_level": region.region_level,
                "full_path": region.full_path,
                "sort_order": region.sort_order,
                "longitude": region.longitude,
                "latitude": region.latitude,
            }
            for region in regions
        ]
        _region_items_cache[cache_key] = items
        return items
    
    def get_region_tree(self, parent_code: Optional[str] = None) -> List[dict]:
        """
        获取地区树形结构
        
        Args:
            parent_code: 父级编码（可选）
            
        Returns:
            地区树形结构
        """
        # 获取所有地区
        all_regions = self.get_regions()
        
        # 构建树形结构
        def build_tree(parent: Optional[str] = None) -> List[dict]:
            nodes = []
            for region in all_regions:
                if region["parent_code"] == parent:
                    node = {
                        "region_id": region["region_id"],
                        "region_code": region["region_code"],
                        "region_name": region["region_name"],
                        "parent_code": region["parent_code"],
                        "region_level": region["region_level"],
                        "full_path": region["full_path"],
                        "sort_order": region["sort_order"],
                        "longitude": region["longitude"],
                        "latitude": region["latitude"],
                        "children": build_tree(region["region_code"])
                    }
                    nodes.append(node)
            return nodes
        
        return build_tree(parent_code)


def get_region_service(db: Session = None) -> RegionService:
    """获取地区服务实例"""
    if db is None:
        from app.db.database import get_db
        db = next(get_db())
    return RegionService(db)

