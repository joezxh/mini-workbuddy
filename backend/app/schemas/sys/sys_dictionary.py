"""字典数据 Schema"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


class SysDictionaryItemBase(BaseModel):
    """字典项基础模型"""
    dict_code: str = Field(..., description="所属字典编码")
    item_code: str = Field(..., description="字典项编码")
    item_name: str = Field(..., description="字典项名称")
    item_value: Optional[str] = Field(None, description="字典项值")
    parent_code: Optional[str] = Field(None, description="父级编码")
    level: int = Field(1, description="层级")
    color: Optional[str] = Field(None, description="颜色标识")
    icon: Optional[str] = Field(None, description="图标")
    sort_order: int = Field(0, description="排序顺序")
    is_active: bool = Field(True, description="是否启用")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="扩展数据")
    remark: Optional[str] = Field(None, description="备注")


class SysDictionaryItemCreate(SysDictionaryItemBase):
    """创建字典项"""
    pass


class SysDictionaryItemUpdate(BaseModel):
    """更新字典项"""
    item_name: Optional[str] = None
    item_value: Optional[str] = None
    parent_code: Optional[str] = None
    level: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    extra_data: Optional[Dict[str, Any]] = None
    remark: Optional[str] = None


class SysDictionaryItemResponse(SysDictionaryItemBase):
    """字典项响应"""
    item_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SysDictionaryBase(BaseModel):
    """字典基础模型"""
    dict_code: str = Field(..., description="字典编码")
    dict_name: str = Field(..., description="字典名称")
    dict_type: str = Field(..., description="字典类型")
    description: Optional[str] = Field(None, description="字典描述")
    sort_order: int = Field(0, description="排序顺序")
    is_active: bool = Field(True, description="是否启用")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="扩展数据")


class SysDictionaryCreate(SysDictionaryBase):
    """创建字典"""
    pass


class SysDictionaryUpdate(BaseModel):
    """更新字典"""
    dict_name: Optional[str] = None
    dict_type: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    extra_data: Optional[Dict[str, Any]] = None


class SysDictionaryResponse(SysDictionaryBase):
    """字典响应"""
    dict_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SysDictionaryWithItemsResponse(SysDictionaryResponse):
    """字典及其项响应"""
    items: List[SysDictionaryItemResponse] = []


class SysDictionaryTreeNode(BaseModel):
    """字典树节点"""
    item_id: int
    dict_code: str
    item_code: str
    item_name: str
    item_value: Optional[str] = None
    parent_code: Optional[str] = None
    level: int
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int
    is_active: bool
    children: List['SysDictionaryTreeNode'] = []
    
    model_config = ConfigDict(from_attributes=True)


class RegionResponse(BaseModel):
    """地区响应（来自 sys_region 表）"""
    region_id: int
    region_code: str
    region_name: str
    parent_code: Optional[str] = None
    region_level: str
    full_path: Optional[str] = None
    sort_order: int = 0
    longitude: Optional[str] = None
    latitude: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RegionTreeNode(BaseModel):
    """地区树节点（来自 sys_region 表）"""
    region_id: int
    region_code: str
    region_name: str
    parent_code: Optional[str] = None
    region_level: str
    full_path: Optional[str] = None
    sort_order: int = 0
    longitude: Optional[str] = None
    latitude: Optional[str] = None
    children: List['RegionTreeNode'] = []

    model_config = ConfigDict(from_attributes=True)


# 预定义的字典类型常量
class DictType:
    """字典类型常量"""
    RISK_LEVEL = "risk_level"  # 风险等级
    DISPOSAL_STATUS = "disposal_status"  # 处置状态
    EVENT_TYPE = "event_type"  # 事件类型
    EVENT_PHASE = "event_phase"  # 事件阶段：brewing/outbreak/escalation/disposal/calm
    GROUP_EMOTION = "group_emotion"  # 群体情绪：calm/anxious/angry/extreme
    DISPOSAL_DIFFICULTY = "disposal_difficulty"  # 处置难度：easy/medium/hard/critical
    POLITICAL_SENSITIVITY = "political_sensitivity"  # 政治敏感度：normal/sensitive/highly_sensitive
    REGION = "region"  # 区域
    SOURCE_TYPE = "source_type"  # 来源类型
    DEPT_TYPE = "dept_type"  # 部门类型
    PERSON_TYPE = "person_type"  # 人员类型
    TAG = "tag"  # 标签
    PERSON_MANAGE_STATUS = "person_manage_status"  # 人员管控状态
    EVENT_SOURCE_TYPE = "event_source_department"  # 事件来源部门类型(矛调/平安法治/110非警务警情...)
    EVENT_SOURCE_TYPE = "event_source_type"  # 事件来源(人工录入/批量导入/接口对接/物联网感知)
    TASK_TYPE = "task_type"  # 定时任务类型
    ENTITY_TYPE = "entity_type"  # 企业实体类型
    LOCATION_TYPE = "location_type"  # 风险地点类型
    GOLD_SAYING_TYPE = "gold_saying_type"  # 调解金句话术类型
    REPORT_TYPE = "report_type"  # AI 报告类型（处置分析/风险评估/趋势预测等）
    CLUSTER_DIMENSION = "cluster_dimension"  # 事件聚合维度（关键字/实体/人员/区域）
    ONTOLOGY_REL_TYPE = "ontology_rel_type"  # 本体关系类型（继承/实现/关联/聚合/组合/依赖）

