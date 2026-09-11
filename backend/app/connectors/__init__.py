"""连接器包（P3 Task 1~7）：抽象 / HTTP 连接器 / 具体类型 / 字段映射 / DB 落库。"""
from app.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorSink,
    InMemorySink,
    PaginationConfig,
    SinkResult,
)
from app.connectors.http import HttpConnector
from app.connectors.mapping import FieldMapItem, apply_field_map
from app.connectors.registry import get_connector, register_connector
from app.connectors.runner import run_connector
from app.connectors.sinks.db_sink import DBSink
from app.connectors.types import (
    DingtalkConnector,
    FeishuConnector,
    OAuth2ApiConnector,
    WeComConnector,
)

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorSink",
    "InMemorySink",
    "PaginationConfig",
    "SinkResult",
    "HttpConnector",
    "FieldMapItem",
    "apply_field_map",
    "get_connector",
    "register_connector",
    "run_connector",
    "DBSink",
    "OAuth2ApiConnector",
    "DingtalkConnector",
    "FeishuConnector",
    "WeComConnector",
]
