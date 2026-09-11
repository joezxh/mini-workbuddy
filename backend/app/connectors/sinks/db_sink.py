"""DB 落库 Sink（P3 Task 7）。

把连接器拉取并映射后的记录持久化到 ``connector_ingest``（按租户+类型+外部 ID 幂等
upsert），并把增量游标写回 ``connector_sync_state``。实现 ``ConnectorSink`` 协议，
可在 ``BaseConnector.sync(sink)`` 中替换内存 Sink。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.connectors.base import ConnectorSink, SinkResult
from app.models.connectors.connector_record import ConnectorIngest, ConnectorSyncState


def _external_id_for(record: Dict[str, Any], id_field: str) -> str:
    """确定记录的外部 ID：优先取 id_field，否则对 payload 做稳定哈希。"""
    if id_field in record and record[id_field] is not None:
        return str(record[id_field])
    blob = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class DBSink:
    """基于 SQLAlchemy Session 的落库 Sink（tenant_id + connector_type 隔离）。"""

    def __init__(
        self,
        db,
        tenant_id: Optional[int],
        connector_type: str,
        id_field: str = "id",
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.connector_type = connector_type
        self.id_field = id_field

    async def write(self, records: List[Dict[str, Any]], meta: Dict[str, Any]) -> SinkResult:
        incremental_field = meta.get("incremental_field")
        last_cursor = meta.get("last_cursor")
        written = 0
        skipped = 0

        for rec in records:
            ext_id = _external_id_for(rec, self.id_field)
            cursor_val = str(rec[incremental_field]) if (incremental_field and rec.get(incremental_field) is not None) else None
            stmt = pg_insert(ConnectorIngest).values(
                tenant_id=self.tenant_id,
                connector_type=self.connector_type,
                external_id=ext_id,
                payload=rec,
                cursor_value=cursor_val,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["tenant_id", "connector_type", "external_id"],
                set_={"payload": rec, "cursor_value": cursor_val},
            )
            self.db.execute(stmt)
            written += 1

        if last_cursor:
            self._update_sync_state(last_cursor)

        self.db.commit()
        return SinkResult(
            written=written,
            skipped=skipped,
            detail=f"db:{self.connector_type}:tenant={self.tenant_id}:written={written}",
        )

    def _update_sync_state(self, last_cursor: str) -> None:
        """upsert 增量游标（postgresql ON CONFLICT）。"""
        stmt = pg_insert(ConnectorSyncState).values(
            tenant_id=self.tenant_id,
            connector_type=self.connector_type,
            last_cursor=last_cursor,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "connector_type"],
            set_={"last_cursor": last_cursor},
        )
        self.db.execute(stmt)

    def get_last_cursor(self) -> Optional[str]:
        """读取本「租户+类型」的最近增量游标，供下一轮同步的 ``since``。"""
        row = self.db.execute(
            select(ConnectorSyncState.last_cursor).where(
                ConnectorSyncState.tenant_id == self.tenant_id,
                ConnectorSyncState.connector_type == self.connector_type,
            )
        ).scalar_one_or_none()
        return row


# 协议兼容性：DBSink 实现 ConnectorSink 的 write 签名（异步）
ConnectorSink.register(DBSink)
