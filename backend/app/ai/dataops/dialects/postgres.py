"""PostgreSQL 方言适配器（P2 Task 3）。

约定：``database`` 参数对 PG 解释为 **schema（namespace）**——扫描以
「连接（库）+ schema」为边界；表/列注释从 pg_catalog 取（information_schema
无注释列）；标识符一律 identifier_preparer.quote()。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)

_NUMERIC_TYPES = {
    "smallint", "integer", "bigint", "decimal", "numeric", "real",
    "double precision", "money",
}
_TEMPORAL_TYPES = {
    "date", "timestamp without time zone", "timestamp with time zone",
    "time", "time without time zone", "time with time zone", "interval",
}
_ESTIMATED_ROWS_RE = re.compile(r'"Plan Rows"\s*:\s*([0-9]+)')

#: information_schema.data_type → 归一化类型名（对齐 MySQL 语义，便于规则引擎复用）
_NORMALIZE_TYPES = {
    "character varying": "varchar",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamptz",
    "time without time zone": "time",
    "time with time zone": "timetz",
}

#: 画像/overlap 的默认采样上限（spec 6.3：100~50000）
DEFAULT_SAMPLE_ROWS = 1000
_MIN_SAMPLE_ROWS = 100
_MAX_SAMPLE_ROWS = 50000


def _quote(conn, ident: str) -> str:
    """标识符引用：优先 SQLAlchemy dialect.identifier_preparer.quote。"""
    if not isinstance(ident, str) or not ident:
        raise ValueError(f"非法标识符: {ident!r}")
    engine = getattr(conn, "engine", None)
    dialect = getattr(engine, "dialect", None)
    preparer = getattr(dialect, "identifier_preparer", None)
    if preparer is not None:
        return preparer.quote(ident)
    return '"' + ident.replace('"', '""') + '"'


def _clamp_sample_rows(sample_rows: Optional[int]) -> int:
    if not sample_rows:
        return DEFAULT_SAMPLE_ROWS
    return max(_MIN_SAMPLE_ROWS, min(int(sample_rows), _MAX_SAMPLE_ROWS))


class _TablesMixin:
    """库/表级元数据。"""

    # ------------------------------------------------------------------
    def list_databases(self, conn) -> List[str]:
        rows = conn.exec_driver_sql(
            "SELECT datname FROM pg_database WHERE datistemplate = false AND datallowconn"
        ).fetchall()
        names = [r[0] for r in rows]
        # 模板库排除（评审用例：template0/template1 不可见）
        return [n for n in names if not n.startswith("template")]

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        schema = database
        rows = conn.execute(
            _text(
                """
                SELECT c.relname,
                       c.relkind,
                       obj_description(c.oid, 'pg_class') AS comment,
                       c.reltuples::bigint AS approx_rows
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema
                  AND c.relkind IN ('r', 'p', 'v', 'm')
                  AND c.relname NOT LIKE 'pg\\_%'
                ORDER BY c.relname
                """
            ),
            {"schema": schema},
        ).fetchall()
        tables: List[TableMeta] = []
        for name, kind, comment, approx_rows in rows:
            tables.append(
                TableMeta(
                    name=name,
                    table_type="VIEW" if kind in ("v", "m") else "BASE TABLE",
                    comment=comment,
                    row_count=int(approx_rows) if approx_rows and approx_rows >= 0 else None,
                    engine=None,
                )
            )
        return tables


from sqlalchemy import text as _text  # noqa: E402  (模块级工具，位置靠后仅为组织清晰)


class _ColumnsMixin:
    """列级元数据（list_columns）：information_schema + col_description。"""

    _LIST_COLUMNS_SQL = """
        SELECT c.column_name,
               c.ordinal_position,
               c.data_type,
               c.character_maximum_length,
               c.numeric_precision,
               c.is_nullable,
               c.column_default,
               col_description(
                   (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                   c.ordinal_position
               ) AS comment
        FROM information_schema.columns c
        WHERE c.table_schema = :schema AND c.table_name = :table
        ORDER BY c.ordinal_position
    """
    _PK_COLUMNS_SQL = """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a
          ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = (:qualified)::regclass AND i.indisprimary
    """

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        schema = database
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            pk = {
                r[0]
                for r in conn.execute(
                    _text(self._PK_COLUMNS_SQL), {"qualified": f"{schema}.{table}"}
                ).fetchall()
            }
            cols: List[ColumnMeta] = []
            for (name, ordinal, data_type, char_len, num_prec,
                 is_nullable, default, comment) in conn.execute(
                _text(self._LIST_COLUMNS_SQL), {"schema": schema, "table": table}
            ).fetchall():
                data_type = _NORMALIZE_TYPES.get(data_type, data_type)
                column_type = data_type
                if char_len:
                    column_type = f"{data_type}({char_len})"
                elif num_prec:
                    column_type = f"{data_type}({num_prec})"
                cols.append(
                    ColumnMeta(
                        name=name,
                        ordinal=int(ordinal),
                        data_type=data_type,
                        column_type=column_type,
                        nullable=str(is_nullable).upper() == "YES",
                        column_key="PRI" if name in pk else None,
                        column_default=default,
                        comment=comment,
                    )
                )
            result[table] = cols
        return result


class _ProfileMixin:
    """画像 / 重叠率 / 取样（spec 6.3）。"""

    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        schema = database
        sample_rows = _clamp_sample_rows(sample_rows)
        qc = _quote(conn, column)
        qualified = f"{_quote(conn, schema)}.{_quote(conn, table)}"

        stats = conn.execute(
            _text(
                f"SELECT count(*) AS total, count({qc}) AS non_null, "
                f"count(DISTINCT {qc}) AS distinct_count FROM {qualified}"
            )
        ).fetchone()
        total, non_null, distinct = int(stats[0]), int(stats[1]), int(stats[2])
        profile = ColumnProfile(
            total=total,
            non_null=non_null,
            distinct_count=distinct,
            null_rate=round((total - non_null) / total, 6) if total else 0.0,
            distinct_ratio=round(distinct / non_null, 6) if non_null else 0.0,
        )

        data_type = self._column_data_type(conn, schema, table, column)
        if data_type in _NUMERIC_TYPES or data_type in _TEMPORAL_TYPES:
            row = conn.execute(
                _text(f"SELECT min({qc}::text), max({qc}::text) FROM {qualified}")
            ).fetchone()
            profile.min_value, profile.max_value = row[0], row[1]
        else:
            top = conn.execute(
                _text(
                    f"SELECT {qc} AS value, count(*) AS cnt FROM {qualified} "
                    f"WHERE {qc} IS NOT NULL GROUP BY {qc} ORDER BY cnt DESC, value LIMIT 10"
                )
            ).fetchall()
            profile.top_values = [{"value": v, "count": int(c)} for v, c in top]
        return profile

    def _column_data_type(self, conn, schema: str, table: str, column: str) -> str:
        row = conn.execute(
            _text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t AND column_name = :c"
            ),
            {"s": schema, "t": table, "c": column},
        ).first()
        return row[0] if row else ""

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        """左列去重采样值命中右列的比例；估算值，异常一律 0.0（不抛出）。"""
        qualified_l = f"{_quote(conn, database)}.{_quote(conn, left.table)}"
        qualified_r = f"{_quote(conn, database)}.{_quote(conn, right.table)}"
        qc_l, qc_r = _quote(conn, left.column), _quote(conn, right.column)
        try:
            matched = conn.execute(
                _text(
                    f"SELECT count(*) FROM ("
                    f"  SELECT DISTINCT {qc_l} AS v FROM {qualified_l} LIMIT {DEFAULT_SAMPLE_ROWS}"
                    f") s WHERE EXISTS (SELECT 1 FROM {qualified_r} r WHERE r.{qc_r} = s.v)"
                )
            ).fetchone()
            distinct = conn.execute(
                _text(
                    f"SELECT count(*) FROM ("
                    f"  SELECT DISTINCT {qc_l} FROM {qualified_l} LIMIT {DEFAULT_SAMPLE_ROWS}"
                    f") s"
                )
            ).fetchone()
            total = int(distinct[0]) if distinct else 0
            return round(int(matched[0]) / total, 6) if total else 0.0
        except Exception:  # noqa: BLE001 - 类型不可比/权限不足等，估算信号失败置 0
            # 失败的语句会让当前事务进入 aborted态，必须回滚，
            # 否则同连接上的后续语句全部报 InFailedSqlTransaction
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return 0.0

    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult:
        limit = max(1, min(int(limit), 50))  # spec 9：取样上限 50
        qualified = f"{_quote(conn, database)}.{_quote(conn, table)}"
        result = conn.execute(_text(f"SELECT * FROM {qualified} LIMIT {limit + 1}"))
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchmany(limit + 1)]
        truncated = len(rows) > limit
        return QueryResult(columns=columns, rows=rows[:limit], row_count=len(rows[:limit]), truncated=truncated)


class _DryRunMixin:
    """写操作 dry-run：EXPLAIN 估算行数（spec 7.3）。"""

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
        try:
            rows = conn.exec_driver_sql(f"EXPLAIN (FORMAT JSON) {sql}").fetchall()
            estimated = None
            for r in rows:
                value = r[0]
                if isinstance(value, (list, dict)):
                    # psycopg2 对 json 列自动反序列化
                    plans = value if isinstance(value, list) else [value]
                    for plan in plans:
                        estimated = (plan.get("Plan") or {}).get("Plan Rows")
                        if isinstance(estimated, (int, float)):
                            estimated = int(estimated)
                            break
                else:
                    match = _ESTIMATED_ROWS_RE.search(str(value))
                    if match:
                        estimated = int(match.group(1))
                if estimated is not None:
                    break
            return WriteImpact(statement_type=stmt_type, estimated_rows=estimated, detail="EXPLAIN OK")
        except Exception as exc:  # noqa: BLE001 - EXPLAIN 失败（DDL/权限）不中断申请链
            return WriteImpact(statement_type=stmt_type, estimated_rows=None, detail=str(exc).split(chr(10))[0][:200])


class PostgresAdapter(_TablesMixin, _ColumnsMixin, _ProfileMixin, _DryRunMixin):
    """PostgreSQL 适配器（组合各能力 Mixin，见文件头约定）。"""

    name = "postgresql"
