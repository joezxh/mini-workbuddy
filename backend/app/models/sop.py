"""SOP 模板数据模型 —— 模板库持久化。

spec: docs/design/sop-assistant-mode-design.md §4.3

``definition`` 存 ``SOPDefinition`` 的序列化 JSON；``template_key`` 与代码侧
注册表（``app/ai/sop/templates``）的模板 id 一一对应，是种子服务的幂等依据。

⚠️ 新增 model 必须在 ``app/db/init_models.py`` 登记，否则不会建表。
"""
from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, Boolean, TIMESTAMP, JSON,
)
from sqlalchemy.sql import func

from app.db.database import Base


class SOPTemplate(Base):
    """SOP 模板：系统内置骨架 + 行业预设 + 用户自建。"""

    __tablename__ = "sop_templates"

    # Postgres 下渲染为 BIGSERIAL；sqlite 变体用于离线单测
    # （sqlite 的 BIGINT 主键不自增，会导致 NOT NULL 约束失败）
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        comment="主键",
    )
    template_key = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="模板稳定标识（对应代码注册表 id），种子幂等依据",
    )
    name = Column(String(200), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    tags = Column(JSON, nullable=True, comment="标签列表")
    definition = Column(JSON, nullable=False, comment="SOPDefinition 序列化 JSON")
    builtin = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="系统内置为 true（由系统拥有，种子可刷新）；用户/预设为 false",
    )
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="是否启用",
    )
    created_by = Column(String(100), nullable=True, comment="创建人")
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
