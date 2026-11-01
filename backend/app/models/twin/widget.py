"""画布组件实例（spec §3.4）。query_id 用 SET NULL：删定义不打碎画面，打回「待绑定」空态。"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer,
    String, TIMESTAMP, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin

WIDGET_KEYS = ("kpi", "trend", "bar", "donut", "alert_table", "graph", "scene2d", "scene3d")


class TwinWidget(Base, TenantMixin):
    __tablename__ = "twin_widget"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    page_id = Column(BigInteger, ForeignKey("twin_page.id", ondelete="CASCADE"), nullable=False, comment="所属页面")
    widget_key = Column(String(32), nullable=False, comment="模块类型（palette 项），非实例")
    title = Column(String(200), nullable=False, comment="组件标题")
    query_id = Column(
        BigInteger, ForeignKey("onto_ontology_query.id", ondelete="SET NULL"), nullable=True,
        comment="绑定的本体查询；NULL = 原型「待绑定」空态",
    )
    param_values_json = Column(JSONB, nullable=True, comment="参数实值 {name: value}")
    display_json = Column(JSONB, nullable=True, comment="{series_map, thresholds, columns, span}")
    grid_json = Column(JSONB, nullable=False, server_default='{"x":0,"y":0,"w":6,"h":4}', comment="12 列栅格位")
    refresh_json = Column(JSONB, nullable=True, comment="覆盖页面级刷新")
    sort_order = Column(Integer, nullable=False, server_default="0", comment="同 (y) 内次序")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        CheckConstraint(
            "widget_key IN ('kpi','trend','bar','donut','alert_table','graph','scene2d','scene3d')",
            name="ck_twin_widget_key",
        ),
        Index("idx_twin_widget_page", "page_id", "sort_order"),
        Index("idx_twin_widget_query", "query_id"),
    )
