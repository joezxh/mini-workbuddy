"""达梦（DM8）方言适配器（类型体系扩展，dmPython 原生驱动族）。

约定：
- 不走 SQLAlchemy：``open`` 经 ``connection.open_connection("dm", ...)`` 返回
  dmPython 原生连接（懒加载，未安装时探活返回安装指引）；
- 数据字典为 Oracle 风格（``all_tab_comments / ALL_TAB_COLS / ALL_COL_COMMENTS``，
  元数据 SQL 移植自 SQLBot db_sql.py dm 分支）；``database`` 参数解释为
  **模式名（OWNER，大写）**；
- dmPython 命名参数风格与 SQLBot 一致：``cursor.execute(sql, {"param": v})``；
- 探活 ``SELECT 1``（SQLBot 同款，DM 支持无 FROM 写法）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)

#: 达梦类型 → 归一化类型（与 oracle 适配器语义对齐）
_NORMALIZE_TYPES = {
    "varchar": "varchar", "varchar2": "varchar", "character": "char",
    "numeric": "numeric", "decimal": "numeric", "int": "integer",
    "integer": "integer", "bigint": "bigint", "smallint": "smallint",
    "tinyint": "smallint", "float": "double precision", "double": "double precision",
    "date": "timestamp", "timestamp": "timestamp", "clob": "text", "blob": "bytea",
}
_DEFAULT_SAMPLE_ROWS = 1000


def _normalize(data_type: str) -> str:
    dt = (data_type or "").lower()
    for key, val in _NORMALIZE_TYPES.items():
        if dt == key or dt.startswith(key):
            return val
    return data_type or ""


def _quote_ident(ident: str) -> str:
    return '"' + str(ident).replace('"', '""') + '"'


def _fetch(conn, sql: str, params: Optional[Dict[str, Any]] = None) -> List[tuple]:
    """执行查询并取回全部行（dmPython 原生 cursor，with 语境自动归还）。"""
    with conn.cursor() as cursor:
        cursor.execute(sql, params or {})
        return cursor.fetchall()


class DmAdapter:
    """达梦适配器（dmPython 原生连接，非 SQLAlchemy 族）。"""

    name = "dm"

    # ------------------------------------------------------------------
    def open(self, ds, connect_database: Optional[str] = None) -> Tuple[object, callable]:
        """打开 dmPython 连接：返回 (raw_conn, cleanup)。connect_database 仅签名对齐，达梦忽略。"""
        from app.ai.dataops.connection import open_connection

        conn = open_connection(
            "dm", ds.host, ds.port, ds.username,
            getattr(ds, "_password_plain", None), ds.database,
            config=getattr(ds, "config_json", None) or {},
        )
        return conn, (lambda: conn.close())

    def test_connect(self, ds) -> Tuple[bool, Optional[str]]:
        try:
            conn, cleanup = self.open(ds)
            try:
                _fetch(conn, "SELECT 1")
            finally:
                cleanup()
            return True, None
        except Exception as exc:  # noqa: BLE001 - 探活失败原因（含驱动指引）原样回传
            return False, f"{type(exc).__name__}: {exc}"[:500]

    # ------------------------------------------------------------------
    def list_databases(self, conn) -> List[str]:
        """达梦的扫描边界是模式（schema）；DBA 视图优先，权限不足退 ALL_OBJECTS。"""
        for sql in (
            "SELECT OBJECT_NAME FROM DBA_OBJECTS WHERE OBJECT_TYPE = 'SCH' ORDER BY OBJECT_NAME",
            "SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OBJECT_TYPE = 'SCH' ORDER BY OBJECT_NAME",
        ):
            try:
                return [r[0] for r in _fetch(conn, sql)]
            except Exception:  # noqa: BLE001 - 视图不可用尝试下一个
                continue
        return []

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        rows = _fetch(
            conn,
            """
            SELECT TABLE_NAME, TABLE_TYPE, COMMENTS
            FROM ALL_TAB_COMMENTS
            WHERE OWNER = :owner AND TABLE_TYPE IN ('TABLE', 'VIEW')
            ORDER BY TABLE_NAME
            """,
            {"owner": (database or "").upper()},
        )
        return [
            TableMeta(
                name=name,
                table_type="VIEW" if (table_type or "").upper() == "VIEW" else "BASE TABLE",
                comment=comment or None,
            )
            for name, table_type, comment in rows
        ]

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        owner = (database or "").upper()
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            cols: List[ColumnMeta] = []
            for (name, data_type, nullable, comment) in _fetch(
                conn,
                """
                SELECT c.COLUMN_NAME, c.DATA_TYPE, c.NULLABLE, COALESCE(com.COMMENTS, '')
                FROM ALL_TAB_COLS c
                LEFT JOIN ALL_COL_COMMENTS com
                  ON c.OWNER = com.OWNER AND c.TABLE_NAME = com.TABLE_NAME
                 AND c.COLUMN_NAME = com.COLUMN_NAME
                WHERE c.OWNER = :owner AND c.TABLE_NAME = :table
                ORDER BY c.COLUMN_ID
                """,
                {"owner": owner, "table": (table or "").upper()},
            ):
                cols.append(
                    ColumnMeta(
                        name=name,
                        ordinal=len(cols) + 1,
                        data_type=_normalize(data_type),
                        column_type=data_type,
                        nullable=str(nullable).upper() == "Y",
                        comment=comment or None,
                    )
                )
            result[table] = cols
        return result

    # ------------------------------------------------------------------
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        qualified = f"{_quote_ident((database or '').upper())}.{_quote_ident(table.upper())}"
        qc = _quote_ident(column.upper())
        total, non_null, distinct = _fetch(
            conn, f"SELECT COUNT(*), COUNT({qc}), COUNT(DISTINCT {qc}) FROM {qualified}"
        )[0]
        total, non_null, distinct = int(total), int(non_null), int(distinct)
        profile = ColumnProfile(
            total=total, non_null=non_null, distinct_count=distinct,
            null_rate=round((total - non_null) / total, 6) if total else 0.0,
            distinct_ratio=round(distinct / non_null, 6) if non_null else 0.0,
        )
        row = _fetch(conn, f"SELECT MIN(TO_CHAR({qc})), MAX(TO_CHAR({qc})) FROM {qualified}")[0]
        profile.min_value, profile.max_value = row[0], row[1]
        return profile

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        try:
            owner = (database or "").upper()
            ql = f"{_quote_ident(owner)}.{_quote_ident(left.table.upper())}"
            qr = f"{_quote_ident(owner)}.{_quote_ident(right.table.upper())}"
            qc_l, qc_r = _quote_ident(left.column.upper()), _quote_ident(right.column.upper())
            matched = _fetch(
                conn,
                f"SELECT COUNT(*) FROM (SELECT DISTINCT {qc_l} AS v FROM {ql} WHERE ROWNUM <= {_DEFAULT_SAMPLE_ROWS}) s "
                f"WHERE EXISTS (SELECT 1 FROM {qr} r WHERE r.{qc_r} = s.v)",
            )[0][0]
            total = _fetch(
                conn,
                f"SELECT COUNT(*) FROM (SELECT DISTINCT {qc_l} FROM {ql} WHERE ROWNUM <= {_DEFAULT_SAMPLE_ROWS})",
            )[0][0]
            n = int(total)
            return round(int(matched) / n, 6) if n else 0.0
        except Exception:  # noqa: BLE001 - 估算信号失败置 0，不抛出
            return 0.0

    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult:
        limit = max(1, min(int(limit), 50))
        owner = (database or "").upper()
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {_quote_ident(owner)}.{_quote_ident(table.upper())} "
                f"WHERE ROWNUM <= {limit + 1}"
            )
            columns = [d[0] for d in cursor.description]
            rows = [list(r) for r in cursor.fetchall()]
        truncated = len(rows) > limit
        return QueryResult(columns=columns, rows=rows[:limit], row_count=len(rows[:limit]),
                           truncated=truncated)

    # ------------------------------------------------------------------
    def dry_run(self, conn, sql: str) -> WriteImpact:
        stmt = (sql or "").lstrip().upper()
        if stmt.startswith("UPDATE"):
            stmt_type = "update"
        elif stmt.startswith("DELETE"):
            stmt_type = "delete"
        elif stmt.startswith("INSERT"):
            stmt_type = "insert"
        elif any(stmt.startswith(k) for k in ("CREATE", "ALTER", "DROP", "TRUNCATE")):
            stmt_type = "ddl"
        else:
            stmt_type = "unknown"
        # 达梦 EXPLAIN 需 PLAN_TABLE 落表，首期不做行数预估
        return WriteImpact(statement_type=stmt_type, estimated_rows=None,
                           detail="达梦 dry-run 暂不支持行数预估")
