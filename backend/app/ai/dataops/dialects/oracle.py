"""Oracle 方言适配器（类型体系扩展，元数据 SQL 移植自 SQLBot db_sql.py oracle 分支）。

约定：
- ``database`` 参数对 Oracle 解释为 **schema（OWNER，大写）**——与 PG 的 schema
  语义等价；连接级 service_name/SID 在 ``DataSource.database`` 列；
- 字典视图取 ``ALL_TABLES / ALL_VIEWS / ALL_MVIEWS / ALL_TAB_COMMENTS /
  ALL_TAB_COLUMNS / ALL_COL_COMMENTS``（与登录用户可见范围一致，SQLBot 同款）；
- OWNER 统一.upper()（Oracle 数据字典大小写敏感）；
- 探活 ``SELECT 1 FROM DUAL``；dry-run 不支持（Oracle 无 EXPLAIN 便捷语法）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from sqlalchemy import text as _text

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)
from app.ai.dataops.dialects._sqlalchemy_base import SQLAlchemyProbeMixin

probe_sql = "SELECT 1 FROM DUAL"

#: Oracle 类型 → 归一化类型（对齐 mysql/pg 适配器语义）
_NORMALIZE_TYPES = {
    "varchar2": "varchar", "nvarchar2": "varchar", "char": "char", "nchar": "char",
    "number": "numeric", "float": "double precision", "binary_float": "real",
    "binary_double": "double precision", "date": "timestamp",
    "clob": "text", "nclob": "text", "blob": "bytea",
    "timestamp": "timestamp",
}
_NUMERIC_PREFIXES = ("number", "float", "binary_float", "binary_double", "int")


def _normalize(data_type: str) -> str:
    dt = (data_type or "").lower()
    for key, val in _NORMALIZE_TYPES.items():
        if dt.startswith(key):
            return val
    return data_type or ""


class OracleAdapter(SQLAlchemyProbeMixin):
    """Oracle 方言适配器（oracle+oracledb thin mode）。"""

    name = "oracle"
    probe_sql = "SELECT 1 FROM DUAL"

    def list_databases(self, conn) -> List[str]:
        rows = conn.execute(_text(
            "SELECT username FROM ALL_USERS ORDER BY username"
        )).fetchall()
        return [r[0] for r in rows]

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        owner = (database or "").upper()
        rows = conn.execute(
            _text(
                """
                SELECT DISTINCT t.TABLE_NAME, t.OBJECT_TYPE, NVL(c.COMMENTS, '')
                FROM (
                    SELECT TABLE_NAME, 'TABLE' AS OBJECT_TYPE FROM ALL_TABLES WHERE OWNER = :owner
                    UNION ALL
                    SELECT VIEW_NAME, 'VIEW' FROM ALL_VIEWS WHERE OWNER = :owner
                    UNION ALL
                    SELECT MVIEW_NAME, 'MATERIALIZED VIEW' FROM ALL_MVIEWS WHERE OWNER = :owner
                ) t
                LEFT JOIN ALL_TAB_COMMENTS c
                  ON c.TABLE_NAME = t.TABLE_NAME AND c.OWNER = :owner
                ORDER BY t.TABLE_NAME
                """
            ),
            {"owner": owner},
        ).fetchall()
        return [
            TableMeta(
                name=name,
                table_type="VIEW" if obj_type == "VIEW" else "BASE TABLE",
                comment=comment or None,
            )
            for name, obj_type, comment in rows
        ]

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        owner = (database or "").upper()
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            cols: List[ColumnMeta] = []
            for (name, data_type, nullable, default, comment) in conn.execute(
                _text(
                    """
                    SELECT col.COLUMN_NAME,
                           col.DATA_TYPE,
                           col.NULLABLE,
                           col.DATA_DEFAULT,
                           NVL(com.COMMENTS, '')
                    FROM ALL_TAB_COLUMNS col
                    LEFT JOIN ALL_COL_COMMENTS com
                      ON com.OWNER = col.OWNER AND com.TABLE_NAME = col.TABLE_NAME
                     AND com.COLUMN_NAME = col.COLUMN_NAME
                    WHERE col.OWNER = :owner AND col.TABLE_NAME = :table
                    ORDER BY col.COLUMN_ID
                    """
                ),
                {"owner": owner, "table": (table or "").upper()},
            ).fetchall():
                cols.append(
                    ColumnMeta(
                        name=name,
                        ordinal=len(cols) + 1,
                        data_type=_normalize(data_type),
                        column_type=data_type,
                        nullable=str(nullable).upper() == "Y",
                        column_default=(str(default).strip() if default else None),
                        comment=comment or None,
                    )
                )
            result[table] = cols
        return result

    # ------------------------------------------------------------------
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        qualified = f'"{(database or "").upper()}"."{table.upper()}"'
        qc = f'"{column.upper()}"'
        total, non_null, distinct = conn.execute(
            _text(
                f"SELECT COUNT(*), COUNT({qc}), COUNT(DISTINCT {qc}) FROM {qualified}"
            )
        ).fetchone()
        total, non_null, distinct = int(total), int(non_null), int(distinct)
        profile = ColumnProfile(
            total=total, non_null=non_null, distinct_count=distinct,
            null_rate=round((total - non_null) / total, 6) if total else 0.0,
            distinct_ratio=round(distinct / non_null, 6) if non_null else 0.0,
        )
        row = conn.execute(
            _text(f"SELECT MIN({qc}), MAX({qc}) FROM {qualified}")
        ).fetchone()
        profile.min_value, profile.max_value = (str(row[0]) if row[0] is not None else None,
                                                str(row[1]) if row[1] is not None else None)
        return profile

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        try:
            owner = (database or "").upper()
            matched = conn.execute(
                _text(
                    f'SELECT COUNT(*) FROM (SELECT DISTINCT "{left.column.upper()}" V FROM '
                    f'"{owner}"."{left.table.upper()}" WHERE ROWNUM <= 1000) s '
                    f'WHERE EXISTS (SELECT 1 FROM "{owner}"."{right.table.upper()}" r '
                    f'WHERE r."{right.column.upper()}" = s.V)'
                )
            ).fetchone()
            total = conn.execute(
                _text(
                    f'SELECT COUNT(*) FROM (SELECT DISTINCT "{left.column.upper()}" FROM '
                    f'"{owner}"."{left.table.upper()}" WHERE ROWNUM <= 1000)'
                )
            ).fetchone()
            n = int(total[0]) if total else 0
            return round(int(matched[0]) / n, 6) if n else 0.0
        except Exception:  # noqa: BLE001 - 估算信号失败置 0，不抛出
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return 0.0

    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult:
        limit = max(1, min(int(limit), 50))
        owner = (database or "").upper()
        result = conn.execute(_text(
            f'SELECT * FROM "{owner}"."{table.upper()}" WHERE ROWNUM <= {limit + 1}'
        ))
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchmany(limit + 1)]
        truncated = len(rows) > limit
        return QueryResult(columns=columns, rows=rows[:limit], row_count=len(rows[:limit]),
                           truncated=truncated)

    # ------------------------------------------------------------------
    _TYPE_PATTERNS = (
        ("update", re.compile(r"^\s*UPDATE\b", re.IGNORECASE)),
        ("delete", re.compile(r"^\s*DELETE\b", re.IGNORECASE)),
        ("insert", re.compile(r"^\s*INSERT\b", re.IGNORECASE)),
        ("ddl", re.compile(r"^\s*(CREATE|ALTER|DROP|TRUNCATE)\b", re.IGNORECASE)),
    )

    def dry_run(self, conn, sql: str) -> WriteImpact:
        stmt_type = "unknown"
        for name, pattern in self._TYPE_PATTERNS:
            if pattern.match(sql or ""):
                stmt_type = name
                break
        # Oracle EXPLAIN PLAN 需建表 + 读取，首期不做行数预估（不中断申请链）
        return WriteImpact(statement_type=stmt_type, estimated_rows=None,
                           detail="Oracle dry-run 暂不支持行数预估")
