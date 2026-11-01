"""平台内置行动模板库（spec §3.9；平台级种子，P2 才评估租户化）。

无 TenantMixin：模板是平台资产，场景只能引用 enabled 模板，不能自定义（V3）。
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, String, Text, TIMESTAMP,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class SandboxActionTemplate(Base):
    """内置行动模板（supply_cut|delay|price_up|reroute 起步）。"""

    __tablename__ = "onto_action_template"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(64), nullable=False, comment="supply_cut|delay|price_up|reroute")
    name = Column(String(200), nullable=False, comment="展示名")
    description = Column(Text, nullable=True, comment="说明")
    domain_hint = Column(String(64), nullable=True, comment="适用域提示（如 supply_chain）")
    param_schema_json = Column(JSONB, nullable=False, comment="F7 表单参数 schema")
    effect_spec_json = Column(JSONB, nullable=False,
                              comment='{"fire_delay_tick":1,"writes":[{"entity":"<target>","prop":"...","expr":{...}}]}')
    status = Column(String(16), nullable=False, server_default="enabled", comment="enabled|disabled")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("code", name="uq_action_template_code"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_action_template_status"),
    )
