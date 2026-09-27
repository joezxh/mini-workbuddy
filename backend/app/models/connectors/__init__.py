"""连接器域 ORM 模型。"""
from app.models.connectors.connector_record import ConnectorIngest, ConnectorSyncState
from app.models.connectors.connector_record import ConnectorInstance, ConnectorSyncLog
from app.models.connectors.external_kb_endpoint import ExternalKbEndpoint

__all__ = [
    "ConnectorIngest",
    "ConnectorSyncState",
    "ConnectorInstance",
    "ConnectorSyncLog",
    "ExternalKbEndpoint",
]
