"""连接器同步编排（P3 Task 7 落库总入口）。

把「取连接器 → 读上次增量游标 → 拉取（带 since）→ DB 落库（幂等 upsert + 写回游标）」
串成一步，供 API / 定时任务直接调用。
"""
from __future__ import annotations

from typing import Optional

from app.connectors.base import ConnectorConfig, SinkResult
from app.connectors.registry import get_connector
from app.connectors.sinks.db_sink import DBSink


async def run_connector(
    connector_type: str,
    config: ConnectorConfig,
    db,
    tenant_id: Optional[int],
    id_field: str = "id",
) -> SinkResult:
    """执行一次连接器同步落库，返回落库结果（含写入条数与新游标）。"""
    connector = get_connector(connector_type, config)
    sink = DBSink(db, tenant_id, connector.connector_type, id_field)
    since = sink.get_last_cursor()
    return await connector.sync(sink, since=since)
