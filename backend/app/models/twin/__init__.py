"""孪生域模型（import 即注册到 Base.metadata，供 create_all 与迁移使用）。"""
from app.models.twin.access import TwinAccessRequest  # noqa: F401
from app.models.twin.card import TwinCard, TwinPage  # noqa: F401
from app.models.twin.publish import TwinCardShare, TwinPublish  # noqa: F401
from app.models.twin.widget import WIDGET_KEYS, TwinWidget  # noqa: F401

__all__ = [
    "TwinAccessRequest", "TwinCard", "TwinCardShare", "TwinPage",
    "TwinPublish", "TwinWidget", "WIDGET_KEYS",
]
