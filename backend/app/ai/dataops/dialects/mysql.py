"""MySQL / Doris 方言适配器（P2 Task 4）。

MySQL 与 Doris 在 **查询协议层兼容**（Doris 走 9030 端口的 MySQL 协议），故
``DorisAdapter`` 直接复用 MySQL 实现，仅微调系统库过滤。

约定：
- ``database`` 参数对 MySQL 解释为 **schema/库名**（与 PG 的 schema 语义等价）；
  表/列注释在 MySQL 的 ``information_schema`` 中**原生存在**（COLUMN_COMMENT /
  TABLE_COMMENT），比 PG 简单，无需走 pg_catalog；
- 标识符一律 ``identifier_preparer.quote()``（MySQL → 反引号）；
- 归一化类型对齐 PG（integer/varchar/timestamp…），便于规则引擎复用。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy import text as _text

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)

#: MySQL information_schema 原生类型 → 归一化类型
_NORMALIZE_TYPES = {
    "tinyint": "integer",
    "smallint": "smallint",
    "mediumint": "integer",
    "int": "integer",
    "integer": "integer",
    "bigint": "bigint",
    "tinytext": "text",
    "mediumtext": "text",
    "longtext": "text",
    "text": "text",
    "datetime": "datetime",
    "timestamp": "timestamp",
    "double": "double precision",
    "real": "double precision",
    "float": "real",
    "bool": "boolean",
    "boolean": "boolean",
}

_NUMERIC_TYPES = {
    "tinyint", "smallint", "mediumint", "int", "integer", "bigint",
    "decimal", "numeric", "float", "double", "double precision", "real", "boolean",
}
_TEMPORAL_TYPES = {
    "date", "datetime", "timestamp", "time", "year",
}

#: 画像/overlap 的默认采样上限（与 PG 适配器一致）
DEFAULT_SAMPLE_ROWS = 1000
_MIN_SAMPLE_ROWS = 100
_MAX_SAMPLE_ROWS = 50000

#: 系统库（扫描时排除）
_MYSQL_SYSTEM_DBS = {"information_schema", "mysql", "performance_schema", "sys"}
_DORIS_SYSTEM_DBS = {"information_schema", "mysql", "sys", "performance_schema"}

_TYPE_PATTERNS = (
    ("update", re.compile(r"^\s*UPDATE\b", re.IGNORECASE)),
    ("delete", re.compile(r"^\s*DELETE\b", re.IGNORECASE)),
    ("insert", re.compile(r"^\s*INSERT\b", re.IGNORECASE)),
    ("ddl", re.compile(r"^\s*(CREATE|ALTER|DROP|TRUNCATE)\b", re.IGNORECASE)),
)


def _quote(conn, ident: str) -> str:
    """标识符引用：优先 SQLAlchemy dialect.identifier_preparer.quote。"""
    if not isinstance(ident, str) or not ident:
        raise ValueError(f"非法标识符: {ident!r}")
    engine = getattr(conn, "engine", None)
    dialect = getattr(engine, "dialect", None)
    preparer = getattr(dialect, "identifier_preparer", None)
    if preparer is not None:
        return preparer.quote(ident)
    return "`" + ident.replace("`", "``") + "`"


def _clamp_sample_rows(sample_rows: Optional[int]) -> int:
    if not sample_rows:
        return DEFAULT_SAMPLE_ROWS
    return max(_MIN_SAMPLE_ROWS, min(int(sample_rows), _MAX_SAMPLE_ROWS))


def _normalize_type(data_type: str) -> str:
    return _NORMALIZE_TYPES.get((data_type or "").lower(), data_type or "")


def _build_column_type(data_type: str, char_len, num_prec, num_scale, dt_prec) -> str:
    base = _normalize_type(data_type)
    if char_len:
        return f"{base}({char_len})"
    if num_prec is not None and (data_type or "").lower() in ("decimal", "numeric"):
        if num_scale:
            return f"{base}({num_prec},{num_scale})"
        return f"{base}({num_prec})"
    if dt_prec is not None and (data_type or "").lower() in ("datetime", "timestamp", "time"):
        return f"{base}({dt_prec})"
    return base


class MysqlAdapter:
    """MySQL 方言适配器（实现 DialectAdapter 协议）。"""

    name = "mysql"

    # ------------------------------------------------------------------
    def list_databases(self, conn) -> List[str]:
        rows = conn.exec_driver_sql("SHOW DATABASES").fetchall()
        names = [r[0] for r in rows]
        return [n for n in names if n.lower() not in _MYSQL_SYSTEM_DBS]

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        rows = conn.execute(
            _text(
                """
                SELECT TABLE_NAME, TABLE_TYPE, TABLE_COMMENT, TABLE_ROWS, ENGINE
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = :db
                ORDER BY TABLE_NAME
                """
            ),
            {"db": database},
        ).fetchall()
        tables: List[TableMeta] = []
        for name, table_type, comment, table_rows, engine in rows:
            tables.append(
                TableMeta(
                    name=name,
                    table_type="VIEW" if (table_type or "").upper() == "VIEW" else "BASE TABLE",
                    comment=comment or None,
                    row_count=int(table_rows) if table_rows is not None else None,
                    engine=engine or None,
                )
            )
        return tables

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            cols: List[ColumnMeta] = []
            for (name, ordinal, data_type, char_len, num_prec, num_scale, dt_prec,
                 is_nullable, default, col_key, extra, comment) in conn.execute(
                _text(
                    """
                    SELECT COLUMN_NAME, ORDINAL_POSITION, DATA_TYPE,
                           CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE,
                           DATETIME_PRECISION, IS_NULLABLE, COLUMN_DEFAULT,
                           COLUMN_KEY, EXTRA, COLUMN_COMMENT
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :table
                    ORDER BY ORDINAL_POSITION
                    """
                ),
                {"db": database, "table": table},
            ).fetchall():
                column_key = col_key if col_key in ("PRI", "UNI", "MUL") else None
                cols.append(
                    ColumnMeta(
                        name=name,
                        ordinal=int(ordinal),
                        data_type=_normalize_type(data_type),
                        column_type=_build_column_type(
                            data_type, char_len, num_prec, num_scale, dt_prec
                        ),
                        nullable=str(is_nullable).upper() == "YES",
                        column_key=column_key,
                        column_default=default,
                        extra=extra or None,
                        comment=comment or None,
                    )
                )
            result[table] = cols
        return result

    # ------------------------------------------------------------------
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        sample_rows = _clamp_sample_rows(sample_rows)
        qc = _quote(conn, column)
        qualified = f"{_quote(conn, database)}.{_quote(conn, table)}"

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

        data_type = self._column_data_type(conn, database, table, column)
        if data_type in _NUMERIC_TYPES or data_type in _TEMPORAL_TYPES:
            row = conn.execute(
                _text(f"SELECT min({qc}), max({qc}) FROM {qualified}")
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

    def _column_data_type(self, conn, database: str, table: str, column: str) -> str:
        row = conn.execute(
            _text(
                "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = :s AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"s": database, "t": table, "c": column},
        ).first()
        return _normalize_type(row[0]) if row else ""

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        """左列去重采样值命中右列的比例；异常一律 0.0（不抛出）。"""
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

    # ------------------------------------------------------------------
    def dry_run(self, conn, sql: str) -> WriteImpact:
        stmt_type = "unknown"
        for name, pattern in _TYPE_PATTERNS:
            if pattern.match(sql or ""):
                stmt_type = name
                break
        try:
            result = conn.exec_driver_sql(f"EXPLAIN {sql}")
            row = result.fetchone()
            estimated = None
            if row is not None:
                mapping = getattr(row, "_mapping", None) or dict(row)
                raw = mapping.get("rows") if isinstance(mapping, dict) else getattr(mapping, "get", lambda *_: None)("rows")
                if raw is not None:
                    estimated = int(raw)
            return WriteImpact(statement_type=stmt_type, estimated_rows=estimated, detail="EXPLAIN OK")
        except Exception as exc:  # noqa: BLE001 - EXPLAIN 失败（DDL/权限）不中断申请链
            return WriteImpact(statement_type=stmt_type, estimated_rows=None, detail=str(exc).split(chr(10))[0][:200])


class DorisAdapter(MysqlAdapter):
    """Doris 适配器（复用 MySQL 协议实现，仅微调系统库过滤）。

    Doris 经 MySQL 协议（默认 9030 端口）通信，information_schema 兼容 MySQL；
    写操作 EXPLAIN 语法略有差异，估算失败时按 None 处理（不致命）。
    """

    name = "doris"

    def list_databases(self, conn) -> List[str]:
        rows = conn.exec_driver_sql("SHOW DATABASES").fetchall()
        names = [r[0] for r in rows]
        return [n for n in names if n.lower() not in _DORIS_SYSTEM_DBS]
