"""字典数据模型"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, TIMESTAMP, Text, JSON
from sqlalchemy.sql import func
from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class SysDictionary(Base, TenantMixin):
    """字典表 - 存储系统字典数据"""
    __tablename__ = 'sys_dictionary'
    
    dict_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='字典ID')
    dict_code = Column(String(50), unique=True, nullable=False, comment='字典编码')
    dict_name = Column(String(100), nullable=False, comment='字典名称')
    dict_type = Column(String(50), nullable=False, comment='字典类型')
    description = Column(Text, comment='字典描述')
    
    # 排序和状态
    sort_order = Column(Integer, default=0, comment='排序顺序')
    is_active = Column(Boolean, nullable=False, default=True, comment='是否启用')
    
    # 扩展字段
    extra_data = Column(JSON, comment='扩展数据')
    
    # 系统字段
    created_by = Column(BigInteger, comment='创建人ID')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    def __repr__(self):
        return f"<SysDictionary {self.dict_name}>"


class SysDictionaryItem(Base, TenantMixin):
    """字典项表 - 存储字典的具体项"""
    __tablename__ = 'sys_dictionary_item'
    
    item_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='字典项ID')
    dict_code = Column(String(50), nullable=False, comment='所属字典编码')
    
    # 字典项信息
    item_code = Column(String(50), nullable=False, comment='字典项编码')
    item_name = Column(String(100), nullable=False, comment='字典项名称')
    item_value = Column(String(200), comment='字典项值')
    
    # 层级关系
    parent_code = Column(String(50), comment='父级编码')
    level = Column(Integer, default=1, comment='层级')
    
    # 样式配置
    color = Column(String(20), comment='颜色标识')
    icon = Column(String(50), comment='图标')
    
    # 排序和状态
    sort_order = Column(Integer, default=0, comment='排序顺序')
    is_active = Column(Boolean, nullable=False, default=True, comment='是否启用')
    
    # 扩展字段
    extra_data = Column(JSON, comment='扩展数据')
    remark = Column(Text, comment='备注')
    
    # 系统字段
    created_by = Column(BigInteger, comment='创建人ID')
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    def __repr__(self):
        return f"<SysDictionaryItem {self.item_name}>"

