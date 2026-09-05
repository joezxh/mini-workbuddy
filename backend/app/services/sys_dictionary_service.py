"""字典服务 - 提供字典数据转换功能（含进程级内存缓存）"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db

# ─── 进程级内存缓存 ────────────────────────────────────────────────────────────
# 字典数据变化极少，使用进程级 dict 缓存，避免每次请求都查 DB
# 为避免数据变更后缓存长期陈旧，增加 TTL：超过 _DICT_CACHE_TTL 秒自动失效重载。
import time as _time
_DICT_CACHE_TTL = 300  # 5 分钟
# key: dict_code, value: 查询结果
_dict_mapping_cache: Dict[str, Dict[str, str]] = {}
_dict_value_mapping_cache: Dict[str, Dict[str, str]] = {}
_dict_items_cache: Dict[str, List[dict]] = {}
_dict_cache_ts: Dict[str, float] = {}  # dict_code -> 最近加载时间戳（TTL 判断）


def clear_dict_cache(dict_code: Optional[str] = None) -> None:
    """
    清除字典缓存
    
    Args:
        dict_code: 指定清除某个字典的缓存，None 表示清除全部缓存
    """
    global _dict_mapping_cache, _dict_items_cache, _dict_cache_ts
    if dict_code:
        _dict_mapping_cache.pop(dict_code, None)
        _dict_cache_ts.pop(dict_code, None)
        # 清除所有以 dict_code 开头的缓存键（包括带 parent_code 的情况）
        keys_to_remove = [key for key in _dict_items_cache.keys() if key.startswith(f"{dict_code}:") or key == dict_code]
        for key in keys_to_remove:
            _dict_items_cache.pop(key, None)
    else:
        _dict_mapping_cache.clear()
        _dict_items_cache.clear()
        _dict_cache_ts.clear()


class SysDictionaryService:
    """字典服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_dict_mapping(self, dict_code: str) -> Dict[str, str]:
        """
        获取字典代码到名称的映射（带进程级缓存）
        
        Args:
            dict_code: 字典编码
            
        Returns:
            字典项代码到名称的映射字典
        """
        # 缓存命中且未过期，直接返回
        if dict_code in _dict_mapping_cache and _dict_cache_ts.get(dict_code, 0) > 0 \
                and _time.time() - _dict_cache_ts[dict_code] < _DICT_CACHE_TTL:
            return _dict_mapping_cache[dict_code]
        
        # 缓存未命中或已过期，查询 DB 并写入缓存
        result = self.db.execute(text("""
            SELECT item_code, item_name
            FROM sys_dictionary_item
            WHERE dict_code = :dict_code AND is_deleted = false AND is_active = true
            ORDER BY sort_order
        """), {"dict_code": dict_code})
        
        mapping = {row.item_code: row.item_name for row in result}
        _dict_mapping_cache[dict_code] = mapping
        _dict_cache_ts[dict_code] = _time.time()
        return mapping
    
    def get_dict_item_name(self, dict_code: str, item_code: str) -> str:
        """
        获取字典项名称
        
        Args:
            dict_code: 字典编码
            item_code: 字典项编码
            
        Returns:
            字典项名称，如果不存在则返回原始代码
        """
        mapping = self.get_dict_mapping(dict_code)
        return mapping.get(item_code, item_code)
    
    def translate_dict_codes(self, data: dict, field_mappings: Dict[str, str]) -> dict:
        """
        将数据中的字典代码转换为名称
        
        Args:
            data: 要转换的数据字典
            field_mappings: 字段到字典编码的映射，如 {"event_type": "event_type", "status": "event_status"}
            
        Returns:
            转换后的数据字典
        """
        result = data.copy()
        
        for field, dict_code in field_mappings.items():
            if field in result and result[field]:
                result[field] = self.get_dict_item_name(dict_code, result[field])
        
        return result
    
    def translate_dict_codes_list(self, data_list: List[dict], field_mappings: Dict[str, str]) -> List[dict]:
        """
        批量转换列表中的字典代码
        
        Args:
            data_list: 要转换的数据列表
            field_mappings: 字段到字典编码的映射
            
        Returns:
            转换后的数据列表
        """
        # 预加载所有需要的字典映射（全部走缓存）
        dict_mappings = {}
        for dict_code in set(field_mappings.values()):
            dict_mappings[dict_code] = self.get_dict_mapping(dict_code)
        
        # 批量转换
        result = []
        for item in data_list:
            new_item = item.copy()
            for field, dict_code in field_mappings.items():
                if field in new_item and new_item[field]:
                    mapping = dict_mappings[dict_code]
                    new_item[field] = mapping.get(new_item[field], new_item[field])
            result.append(new_item)
        
        return result
    
    def get_dict_items(self, dict_code: str, parent_code: Optional[str] = None) -> List[dict]:
        """
        获取字典项列表（包含所有字段，带进程级缓存）
        
        Args:
            dict_code: 字典编码
            parent_code: 父级编码（可选，用于获取指定父级下的子项）
            
        Returns:
            字典项列表
        """
        # 生成缓存 key（考虑 parent_code）
        cache_key = f"{dict_code}:{parent_code}" if parent_code else dict_code
        
        # 缓存命中，直接返回
        if cache_key in _dict_items_cache:
            return _dict_items_cache[cache_key]
        
        # 构建查询条件
        query = text("""
            SELECT item_code, item_name, item_value, color, icon, sort_order
            FROM sys_dictionary_item
            WHERE dict_code = :dict_code AND is_deleted = false AND is_active = true
        """)
        
        params = {"dict_code": dict_code}
        
        # 如果指定了父级编码，添加过滤条件
        if parent_code:
            query = text(str(query) + " AND parent_code = :parent_code")
            params["parent_code"] = parent_code
        
        query = text(str(query) + " ORDER BY sort_order")
        
        # 缓存未命中，查询 DB 并写入缓存
        result = self.db.execute(query, params)
        
        items = [
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "item_value": row.item_value,
                "color": row.color,
                "icon": row.icon,
                "sort_order": row.sort_order
            }
            for row in result
        ]
        _dict_items_cache[cache_key] = items
        return items
    
    def get_dict_items_with_colors(self, dict_code: str) -> List[dict]:
        """
        获取字典项列表（包含颜色等扩展信息，复用 get_dict_items 缓存）
        
        Args:
            dict_code: 字典编码
            
        Returns:
            字典项列表
        """
        # 直接复用带缓存的 get_dict_items
        all_items = self.get_dict_items(dict_code)
        return [
            {
                "code": item["item_code"],
                "name": item["item_name"],
                "color": item["color"],
                "icon": item["icon"],
                "sort_order": item["sort_order"]
            }
            for item in all_items
        ]


def get_dictionary_service(db: Session = None) -> SysDictionaryService:
    """获取字典服务实例"""
    if db is None:
        db = next(get_db())
    return SysDictionaryService(db)
