"""AI Web Search 供应商模型（PostgreSQL）。

参考 mediation-platform 的 WebSearchDO 实现。
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, JSON, TIMESTAMP, Float, Boolean, Date, Index
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiWebSearch(Base, TenantMixin):
    """AI 联网搜索供应商配置表"""
    __tablename__ = "ai_web_search"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(100), nullable=False, comment="配置名称")
    api_key = Column(Text, nullable=False, comment="平台 API Key")
    platform = Column(String(50), nullable=False, index=True, comment="平台: bocha/anspire/google/bing/custom")
    url = Column(String(500), nullable=True, default="", comment="API 地址")
    app_id = Column(String(100), nullable=True, default="", comment="AppId")
    property = Column(JSON, nullable=True, default=dict, comment="扩展配置(含 api_secret 等敏感项)")
    timeout = Column(Integer, nullable=False, server_default="30", comment="请求超时(秒)")
    max_results = Column(Integer, nullable=False, server_default="10", comment="单次最大结果数")
    daily_quota = Column(Integer, nullable=False, server_default="0", comment="每日配额(0=不限)")
    used_count = Column(Integer, nullable=False, server_default="0", comment="已使用次数(当日)")
    quota_date = Column(Date, nullable=True, default=None, comment="used_count 所属日期(用于每日配额重置)")
    priority = Column(Integer, nullable=False, server_default="50", comment="优先级(越大越优先)")
    status = Column(Integer, nullable=False, server_default="1", comment="状态: 1=启用, 0=禁用")
    sort = Column(Integer, nullable=False, server_default="0", comment="排序")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=datetime.now)
    creator = Column(String(64), nullable=True, comment="创建人")
    updater = Column(String(64), nullable=True, comment="更新人")

    def __repr__(self) -> str:
        return f"<AiWebSearch {self.name} [{self.platform}]>"


class AiWebSearchLog(Base, TenantMixin):
    """联网搜索供应商调用日志（管理页日志列表数据源）。"""
    __tablename__ = "ai_web_search_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    web_search_id = Column(Integer, nullable=False, index=True, comment="供应商ID")
    service_name = Column(String(64), nullable=False, default="", comment="供应商名称(冗余)")
    platform = Column(String(32), nullable=False, default="", comment="平台")
    query = Column(String(512), nullable=False, default="", comment="搜索关键词")
    response_time = Column(Float, nullable=False, server_default="0", comment="响应耗时(ms)")
    results_count = Column(Integer, nullable=False, server_default="0", comment="结果条数")
    success = Column(Boolean, nullable=False, server_default="1", comment="是否成功")
    error = Column(Text, nullable=True, default="", comment="错误信息")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<AiWebSearchLog {self.platform} [{self.query}]>"
