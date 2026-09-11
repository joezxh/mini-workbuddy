"""只读 SQL 执行（P2 Task 9）。

安全主线（spec §7.2）：
- 经 ``SqlGuard`` 单一事实来源校验，仅允许单条只读查询，否则拒绝；
- 行数上限 + 截断标记，防止大结果集打爆内存；
- 凭据经 ``DataSourceService.reveal_password`` 解密建连，API 出口绝不出现明文。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.dataops.connection import build_engine
from app.models.dataops.data_source import DataSource
from app.services.dataops.data_source_service import DataSourceService
from app.services.dataops.sql_guard import SqlGuard


def _dialect_of(source_type: str) -> Optional[str]:
    t = (source_type or "").lower()
    if t == "postgresql":
        return "postgres"
    if t in ("mysql", "doris"):
        return "mysql"
    return None


class ReadonlyQueryService:
    """只读查询执行（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("ReadonlyQueryService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._ds = DataSourceService(db, tenant_id)
        self._guard = SqlGuard()

    def run(self, source_id: int, sql: str, limit: int = 100) -> dict:
        """执行只读查询，返回列/行/截断标记。"""
        if limit < 1:
            limit = 1
        elif limit > 5000:
            limit = 5000

        ds = self._ds.get_or_404(source_id)  # 租户隔离校验
        dialect = _dialect_of(ds.source_type)
        if not self._guard.is_readonly(sql, dialect):
            raise ValueError("仅允许单条只读查询（SELECT/CTE/UNION/EXPLAIN 查询），且不含注释与危险函数")

        password = self._ds.reveal_password(ds.id)
        engine = build_engine(
            ds.source_type, ds.host, ds.port, ds.username, password, ds.database
        )
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = [list(r) for r in result.fetchmany(limit + 1)]
        finally:
            engine.dispose()

        truncated = len(rows) > limit
        rows = rows[:limit]
        # 敏感字段兜底：结果字典不含凭据
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
