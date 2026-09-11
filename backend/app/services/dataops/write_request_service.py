"""数据写操作申请单服务（P2 Task 10：申请 → 批准 → 一次性令牌执行）。

安全主线（spec §7.3）：
- 申请时经 ``SqlGuard`` 校验**必须是写语句**（只读查询拒绝申请）；
- ``sql_sha256`` 是审批与执行一致性的锚点：执行前重新计算并与存储值比对，
  中途被篡改则拒绝（fail-closed）；
- 批准后发放**一次性令牌**，执行需携带且不可重放（``token_consumed``）；
- 过期申请不可执行；执行后再经 ``SqlGuard`` 复核（纵深防御）。
"""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.dataops.connection import build_engine
from app.models.dataops.data_source import DataSource
from app.models.dataops.write_request import DataWriteRequest
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.sql_guard import SqlGuard

from sqlalchemy import func


def _dialect_of(source_type: str) -> Optional[str]:
    t = (source_type or "").lower()
    if t == "postgresql":
        return "postgres"
    if t in ("mysql", "doris"):
        return "mysql"
    return None


def _detect_write_type(sql: str, dialect: Optional[str]) -> Optional[str]:
    """识别写语句类型；只读/无法识别返回 None。"""
    import sqlglot
    from sqlglot import expressions as exp

    try:
        nodes = sqlglot.parse(sql, dialect=dialect)
    except Exception:  # noqa: BLE001
        return None
    statements = [n for n in nodes if n is not None]
    if len(statements) != 1:
        return None
    node = statements[0]
    if isinstance(node, exp.Command):  # EXPLAIN 等命令不算写
        return None
    mapping = {
        "insert": "insert",
        "update": "update",
        "delete": "delete",
        "create": "ddl",
        "drop": "ddl",
        "alter": "ddl",
        "truncate": "ddl",
    }
    return mapping.get(type(node).__name__.lower())


def _sha256(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()


class DataWriteRequestService:
    """写申请单 CRUD + 审批 + 一次性令牌执行（按 tenant_id 隔离）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("DataWriteRequestService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._ds = DataSourceService(db, tenant_id)
        self._guard = SqlGuard()

    def get_or_404(self, request_id: int) -> DataWriteRequest:
        obj = self.db.execute(
            select(DataWriteRequest).where(
                DataWriteRequest.tenant_id == self.tenant_id,
                DataWriteRequest.id == request_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            raise KeyError(request_id)
        return obj

    def list_requests(self, source_id: Optional[int] = None) -> List[DataWriteRequest]:
        stmt = select(DataWriteRequest).where(DataWriteRequest.tenant_id == self.tenant_id)
        if source_id is not None:
            stmt = stmt.where(DataWriteRequest.source_id == source_id)
        return list(self.db.execute(stmt.order_by(DataWriteRequest.id)).scalars().all())

    def create_request(
        self,
        source_id: int,
        sql_text: str,
        database: Optional[str] = None,
        applicant_id: Optional[int] = None,
        expires_at=None,
    ) -> DataWriteRequest:
        ds = self._ds.get_or_404(source_id)  # 租户隔离校验
        dialect = _dialect_of(ds.source_type)
        if self._guard.is_readonly(sql_text, dialect):
            raise ValueError("写申请不能是只读查询")
        stmt_type = _detect_write_type(sql_text, dialect)
        if stmt_type is None:
            raise ValueError("无法识别的写语句（仅支持 INSERT/UPDATE/DELETE/DDL）")

        obj = DataWriteRequest(
            tenant_id=self.tenant_id,
            source_id=source_id,
            database=database,
            sql_text=sql_text,
            sql_sha256=_sha256(sql_text),
            statement_type=stmt_type,
            status="pending",
            applicant_id=applicant_id,
            expires_at=expires_at,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def approve(self, request_id: int, approver_id: Optional[int] = None) -> DataWriteRequest:
        obj = self.get_or_404(request_id)
        if obj.status != "pending":
            raise ValueError(f"仅 pending 申请可批准，当前状态 {obj.status}")
        obj.status = "approved"
        obj.approver_id = approver_id
        obj.token = secrets.token_hex(32)  # 一次性令牌
        self.db.flush()
        return obj

    def reject(self, request_id: int, approver_id: Optional[int] = None) -> DataWriteRequest:
        obj = self.get_or_404(request_id)
        if obj.status != "pending":
            raise ValueError(f"仅 pending 申请可驳回，当前状态 {obj.status}")
        obj.status = "rejected"
        obj.approver_id = approver_id
        self.db.flush()
        return obj

    def execute(self, request_id: int, token: str, executor_id: Optional[int] = None) -> DataWriteRequest:
        obj = self.get_or_404(request_id)
        # 一次性令牌校验（防重放）
        if not obj.token or obj.token != token:
            raise ValueError("令牌无效")
        if obj.token_consumed:
            raise ValueError("令牌已消费，不可重放")
        if obj.status != "approved":
            raise ValueError(f"仅 approved 申请可执行，当前状态 {obj.status}")
        if obj.expires_at is not None and obj.expires_at < func.now():
            obj.status = "expired"
            self.db.flush()
            raise ValueError("申请已过期")

        # 一致性锚点：重新计算 sha256 比对，防执行前 SQL 被篡改
        if _sha256(obj.sql_text) != obj.sql_sha256:
            raise ValueError("SQL 摘要校验失败，可能存在篡改")

        ds = self._ds.get_or_404(obj.source_id)
        dialect = _dialect_of(ds.source_type)
        if self._guard.is_readonly(obj.sql_text, dialect):
            raise ValueError("执行校验失败：非写语句")

        password = self._ds.reveal_password(ds.id)
        engine = build_engine(
            ds.source_type, ds.host, ds.port, ds.username, password, ds.database
        )
        started = time.perf_counter()
        try:
            with engine.begin() as conn:
                result = conn.execute(text(obj.sql_text))
                affected = int(result.rowcount)
        finally:
            engine.dispose()

        obj.status = "executed"
        obj.token_consumed = True
        obj.executed_at = func.now()
        obj.result_json = {
            "affected_rows": affected,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
        self.db.flush()
        return obj

    def delete(self, request_id: int) -> bool:
        obj = self.db.execute(
            select(DataWriteRequest).where(
                DataWriteRequest.tenant_id == self.tenant_id,
                DataWriteRequest.id == request_id,
            )
        ).scalar_one_or_none()
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True
