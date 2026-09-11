"""技能分类常量定义

从数据库字典表动态加载技能分类，避免硬编码。

Usage:
    from app.ai.skills.categories import SkillCategory
    
    # 获取分类代码
    category = SkillCategory.LEGAL_REASONING
    
    # 验证分类是否有效
    if SkillCategory.is_valid('legal-reasoning'):
        print("分类有效")
    
    # 获取所有有效分类
    all_categories = SkillCategory.all_categories()
"""
from typing import Set, Optional
from sqlalchemy import select
from app.db.database import SessionLocal
from app.models.sys.sys_dictionary import SysDictionaryItem


class SkillCategory:
    """技能分类常量类
    
    从数据库字典表动态加载分类定义，提供类型安全的分类访问。
    
    Attributes:
        LEGAL_REASONING: 法律推理类技能
        DOCUMENT: 法律文书类技能
        RISK_ASSESSMENT: 风险评估类技能
        RETRIEVAL: 法律检索类技能
        ARGUMENTATION: 法律论证类技能
        DATA_ANALYSIS: 数据分析类技能
        OTHER: 其他类技能
    """
    
    # 缓存的分类数据（避免频繁查询数据库）
    _cache: Optional[Set[str]] = None
    _cache_timestamp: Optional[float] = None
    
    # 分类代码常量（从字典表加载后动态设置）
    LEGAL_REASONING = 'legal-reasoning'
    DOCUMENT = 'document'
    RISK_ASSESSMENT = 'risk-assessment'
    RETRIEVAL = 'retrieval'
    ARGUMENTATION = 'argumentation'
    DATA_ANALYSIS = 'data-analysis'
    OTHER = 'other'
    
    @classmethod
    def _default_categories(cls) -> Set[str]:
        """内置默认分类集合（数据库不可用 / 字典未启用时的兜底）。"""
        return {
            cls.LEGAL_REASONING,
            cls.DOCUMENT,
            cls.RISK_ASSESSMENT,
            cls.RETRIEVAL,
            cls.ARGUMENTATION,
            cls.DATA_ANALYSIS,
            cls.OTHER,
        }

    @classmethod
    def _load_from_database(cls) -> Set[str]:
        """从数据库字典表加载所有有效的技能分类。

        注意：查询**成功但结果为空**同样按「加载失败」处理并退回内置分类。
        否则字典表未启用（is_active=false）或尚未初始化时，all_categories()
        会返回空集合，导致任何技能都装不上（"无效的技能分类 'other'。有效分类："）。
        """
        db = SessionLocal()
        try:
            items = db.scalars(
                select(SysDictionaryItem.item_code).where(
                    SysDictionaryItem.dict_code == 'skill_category',
                    SysDictionaryItem.is_active == True,
                    SysDictionaryItem.is_deleted == False,
                )
            ).all()
            categories = set(items)
            if categories:
                return categories
            print("⚠️  数据库字典 skill_category 中没有启用状态下的分类项")
            print("   使用默认分类集合")
            return cls._default_categories()
        except Exception as e:
            # 如果数据库查询失败，返回默认分类（向后兼容）
            print(f"⚠️  无法从数据库加载技能分类：{e}")
            print("   使用默认分类集合")
            return cls._default_categories()
        finally:
            db.close()
    
    @classmethod
    def all_categories(cls) -> Set[str]:
        """获取所有有效的技能分类
        
        Returns:
            包含所有有效分类代码的集合
            
        Example:
            >>> categories = SkillCategory.all_categories()
            >>> 'legal-reasoning' in categories
            True
        """
        return cls._load_from_database()
    
    @classmethod
    def is_valid(cls, category: str) -> bool:
        """验证给定的分类代码是否有效
        
        Args:
            category: 要验证的分类代码
            
        Returns:
            如果分类有效返回 True，否则返回 False
            
        Example:
            >>> SkillCategory.is_valid('legal-reasoning')
            True
            >>> SkillCategory.is_valid('invalid-category')
            False
        """
        return category in cls.all_categories()
    
    @classmethod
    def validate(cls, category: str) -> str:
        """验证并返回分类代码
        
        Args:
            category: 要验证的分类代码
            
        Returns:
            如果分类有效，返回原始分类代码
            
        Raises:
            ValueError: 如果分类无效
            
        Example:
            >>> SkillCategory.validate('legal-reasoning')
            'legal-reasoning'
            >>> SkillCategory.validate('invalid')
            ValueError: 无效的技能分类...
        """
        if not cls.is_valid(category):
            valid = ', '.join(sorted(cls.all_categories()))
            raise ValueError(
                f"无效的技能分类 '{category}'。"
                f"有效分类：{valid}"
            )
        return category
    
    @classmethod
    def get_default(cls) -> str:
        """获取默认分类
        
        Returns:
            默认分类代码（'other'）
            
        Example:
            >>> SkillCategory.get_default()
            'other'
        """
        return cls.OTHER
    
    @classmethod
    def clear_cache(cls):
        """清除分类缓存（用于字典更新后强制刷新）"""
        cls._cache = None
        cls._cache_timestamp = None
    
    @classmethod
    def get_category_info(cls, category: str) -> dict:
        """获取分类的详细信息（名称、颜色、图标等）
        
        Args:
            category: 分类代码
            
        Returns:
            包含分类详细信息的字典
            
        Example:
            >>> info = SkillCategory.get_category_info('legal-reasoning')
            >>> info['item_name']
            '法律推理'
        """
        db = SessionLocal()
        try:
            item = db.scalar(
                select(SysDictionaryItem).where(
                    SysDictionaryItem.dict_code == 'skill_category',
                    SysDictionaryItem.item_code == category,
                    SysDictionaryItem.is_deleted == False,
                )
            )
            
            if item:
                return {
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'description': item.item_value,
                    'color': item.color,
                    'icon': item.icon,
                    'sort_order': item.sort_order,
                }
            else:
                return {
                    'item_code': category,
                    'item_name': category,
                    'description': '',
                    'color': '#8c8c8c',
                    'icon': 'appstore',
                    'sort_order': 99,
                }
        finally:
            db.close()


# 便捷函数
def get_valid_skill_categories() -> Set[str]:
    """获取所有有效的技能分类（兼容旧接口）
    
    Returns:
        包含所有有效分类代码的集合
    """
    return SkillCategory.all_categories()


def validate_category(category: str, valid_categories: Optional[Set[str]] = None) -> str:
    """验证技能分类是否有效（兼容旧接口）
    
    Args:
        category: 要验证的分类代码
        valid_categories: 可选的有效分类集合（如果不提供，会自动从数据库加载）
        
    Returns:
        如果分类有效，返回原始分类代码
        
    Raises:
        ValueError: 如果分类无效
    """
    if valid_categories is None:
        valid_categories = SkillCategory.all_categories()
    
    if category not in valid_categories:
        valid = ', '.join(sorted(valid_categories))
        raise ValueError(
            f"无效的技能分类 '{category}'。"
            f"有效分类：{valid}"
        )
    return category
