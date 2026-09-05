"""AI API Key and Chat Model models (PostgreSQL).

参考 mediation-platform 的 ApiKeyDO 和 ModelDO 实现。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, JSON, TIMESTAMP, ForeignKey, Float
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class AiApiKey(Base, TenantMixin):
    """AI API 密钥表"""
    __tablename__ = "ai_api_key"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="密钥名称")
    api_key = Column(Text, nullable=False, comment="API Key")
    platform = Column(String(50), nullable=False, index=True, comment="平台: OpenAI/通义千问/智谱/讯飞等")
    url = Column(String(500), nullable=True, default="", comment="API 地址")
    app_id = Column(String(100), nullable=True, default="", comment="AppId")
    property = Column(JSON, nullable=True, default=dict, comment="配置属性")
    status = Column(Integer, nullable=False, server_default="1", comment="状态: 1=启用, 0=禁用")
    sort = Column(Integer, nullable=False, server_default="0", comment="排序")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=datetime.now)
    creator = Column(String(64), nullable=True, comment="创建人")
    updater = Column(String(64), nullable=True, comment="更新人")

    chat_models = relationship("AiChatModel", back_populates="api_key_obj", cascade="all, delete-orphan")


class AiChatModel(Base, TenantMixin):
    """AI 聊天模型表"""
    __tablename__ = "ai_chat_model"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=True, comment="模型编码")
    key_id = Column(Integer, ForeignKey("ai_api_key.id", ondelete="CASCADE"), nullable=False, index=True, comment="API 密钥编号")
    name = Column(String(100), nullable=False, comment="模型名称")
    model = Column(String(100), nullable=False, comment="模型标志/模型ID")
    platform = Column(String(50), nullable=True, comment="平台")
    sort = Column(Integer, nullable=False, server_default="0", comment="排序")
    status = Column(Integer, nullable=False, server_default="1", comment="状态: 1=启用, 0=禁用")
    type = Column(Integer, nullable=True, comment="类型")

    temperature = Column(Float, nullable=True, comment="温度参数")
    max_tokens = Column(Integer, nullable=True, comment="最大 Token 数")
    top_k = Column(Integer, nullable=True, comment="保留概率最高的 k 个单词")
    top_p = Column(Float, nullable=True, comment="累积概率阈值 p")
    seed = Column(Integer, nullable=True, comment="随机种子")
    max_contexts = Column(Integer, nullable=True, comment="上下文最大 Message 数")
    max_turns = Column(Integer, nullable=True, comment="最大轮次")
    dimensions = Column(Integer, nullable=True, comment="维度")
    retry = Column(Integer, nullable=True, comment="重试次数")
    timeout = Column(Integer, nullable=True, comment="超时时间(秒)")
    stream_timeout = Column(Integer, nullable=True, comment="流式超时(秒)")

    enable_thinking = Column(Boolean, nullable=True, default=False, comment="支持思考")
    enable_search = Column(Boolean, nullable=True, default=False, comment="支持搜索")
    is_default = Column(Boolean, nullable=True, default=False, comment="是否默认模型")

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=datetime.now)

    api_key_obj = relationship("AiApiKey", back_populates="chat_models")
