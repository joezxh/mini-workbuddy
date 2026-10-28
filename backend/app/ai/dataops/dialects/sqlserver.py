"""SQL Server 方言适配器（类型体系扩展，元数据 SQL 移植自 SQLBot db_sql.py sqlServer 分支）。

约定：
- 连接级库名在 ``DataSource.database``；``list_databases`` 返回 **schema**
  （与 SQLBot get_schema 的 ``sys.schemas`` 一致），``database`` 参数解释为
  schema，空值兜底 ``dbo``；
- 表/列注释来自 ``sys.extended_properties``（MS_Description），
  information_schema 本身无注释列；
- 标识符引用走 mssql dialect 的 identifier_preparer（``[ ]``）；
- dry-run 首期仅语句分类（SQLBot 亦不做行数预估）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from sqlalchemy import text as _text

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)
from app.ai.dataops.dialects._sqlalchemy_base import SQLAlchemyProbeMixin

#: 归一化类型（对齐 mysql/pg 适配器语义）
_NORMALIZE_TYPES = {
    "int": "integer", "bigint": "bigint", "smallint": "smallint", "tinyint": "smallint",
    "bit": "boolean", "numeric": "numeric", "decimal": "decimal",
    "float": "double precision", "real": "real", "money": "numeric",
    "varchar": "varchar", "nvarchar": "nvarchar", "char": "char", "nchar": "nchar",
    "text": "text", "ntext": "text",
    "datetime": "datetime", "datetime2": "datetime", "smalldatetime": "datetime",
    "date": "date", "time": "time", "datetimeoffset": "timestamptz",
}

_NUMERIC_TYPES = {
    "int", "bigint", "smallint", "tinyint", "bit", "numeric", "decimal",
    "float", "real", "money", "smallmoney",
}
_TEMPORAL_TYPES = {"date", "time", "datetime", "datetime2", "smalldatetime", "datetimeoffset"}

DEFAULT_SAMPLE_ROWS = 1000
_MIN_SAMPLE_ROWS = 100
_MAX_SAMPLE_ROWS = 50000


def _quote(conn, ident: str) -> str:
    """标识符引用：优先 SQLAlchemy mssql dialect（``[ ]``）。"""
    if not isinstance(ident, str) or not ident:
        raise ValueError(f"非法标识符: {ident!r}")
    engine = getattr(conn, "engine", None)
    preparer = getattr(getattr(engine, "dialect", None), "identifier_preparer", None)
    if preparer is not None:
        return preparer.quote(ident)
    return "[" + ident.replace("]", "]]") + "]"


def _clamp_sample_rows(sample_rows: Any) -> int:
    if not sample_rows:
        return DEFAULT_SAMPLE_ROWS
    return max(_MIN_SAMPLE_ROWS, min(int(sample_rows), _MAX_SAMPLE_ROWS))


def _normalize(data_type: str) -> str:
    return _NORMALIZE_TYPES.get((data_type or "").lower(), data_type or "")


class SqlserverAdapter(SQLAlchemyProbeMixin):
    """SQL Server 适配器（mssql+pymssql，探活 SELECT 1）。"""

    name = "sqlserver"
    probe_sql = "SELECT 1"

    @staticmethod
    def _schema(database: str) -> str:
        """database 参数按 schema 解释，空值兜底 dbo（对齐 SQLBot 默认）。"""
        return (database or "").strip() or "dbo"

    # ------------------------------------------------------------------
    def list_databases(self, conn) -> List[str]:
        rows = conn.execute(_text(
            "SELECT name FROM sys.schemas ORDER BY name"
        )).fetchall()
        return [r[0] for r in rows]

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        rows = conn.execute(
            _text(
                """
                SELECT t.TABLE_NAME, t.TABLE_TYPE, ISNULL(ep.value, '')
                FROM INFORMATION_SCHEMA.TABLES t
                LEFT JOIN sys.extended_properties ep
                  ON ep.major_id = OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME)
                 AND ep.minor_id = 0 AND ep.name = 'MS_Description'
                WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                  AND t.TABLE_SCHEMA = :schema
                ORDER BY t.TABLE_NAME
                """
            ),
            {"schema": self._schema(database)},
        ).fetchall()
        return [
            TableMeta(
                name=name,
                table_type="VIEW" if (table_type or "").upper() == "VIEW" else "BASE TABLE",
                comment=comment or None,
            )
            for name, table_type, comment in rows
        ]

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        schema = self._schema(database)
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            cols: List[ColumnMeta] = []
            for (name, data_type, char_len, num_prec, num_scale,
                 is_nullable, default, comment) in conn.execute(
                _text(
                    """
                    SELECT C.COLUMN_NAME, C.DATA_TYPE, C.CHARACTER_MAXIMUM_LENGTH,
                           C.NUMERIC_PRECISION, C.NUMERIC_SCALE,
                           C.IS_NULLABLE, C.COLUMN_DEFAULT, ISNULL(EP.value, '')
                    FROM INFORMATION_SCHEMA.COLUMNS C
                    LEFT JOIN sys.extended_properties EP
                      ON EP.major_id = OBJECT_ID(C.TABLE_SCHEMA + '.' + C.TABLE_NAME)
                     AND EP.minor_id = C.ORDINAL_POSITION AND EP.name = 'MS_Description'
                    WHERE C.TABLE_SCHEMA = :schema AND C.TABLE_NAME = :table
                    ORDER BY C.ORDINAL_POSITION
                    """
                ),
                {"schema": schema, "table": table},
            ).fetchall():
                column_type = _normalize(data_type)
                if char_len:
                    column_type = f"{column_type}({char_len})"
                elif num_prec:
                    column_type = (
                        f"{column_type}({num_prec},{num_scale})" if num_scale
                        else f"{column_type}({num_prec})"
                    )
                cols.append(
                    ColumnMeta(
                        name=name,
                        ordinal=len(cols) + 1,
                        data_type=_normalize(data_type),
                        column_type=column_type,
                        nullable=str(is_nullable).upper() == "YES",
                        column_default=(str(default) if default is not None else None),
                        comment=comment or None,
                    )
                )
            result[table] = cols
        return result

    # ------------------------------------------------------------------
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        schema = self._schema(database)
        qc = _quote(conn, column)
        qualified = f"{_quote(conn, schema)}.{_quote(conn, table)}"
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
            _text(f"SELECT MIN(CONVERT(nvarchar(512), {qc})), MAX(CONVERT(nvarchar(512), {qc})) FROM {qualified}")
        ).fetchone()
        profile.min_value, profile.max_value = (str(row[0]) if row[0] is not None else None,
                                                str(row[1]) if row[1] is not None else None)
        return profile

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        try:
            schema = self._schema(database)
            ql, qr = _quote(conn, schema) + "." + _quote(conn, left.table), _quote(conn, schema) + "." + _quote(conn, right.table)
            qc_l, qc_r = _quote(conn, left.column), _quote(conn, right.column)
            matched = conn.execute(
                _text(
                    f"SELECT COUNT(*) FROM (SELECT DISTINCT TOP {DEFAULT_SAMPLE_ROWS} {qc_l} AS v FROM {ql}) s "
                    f"WHERE EXISTS (SELECT 1 FROM {qr} r WHERE r.{qc_r} = s.v)"
                )
            ).fetchone()
            total = conn.execute(
                _text(f"SELECT COUNT(*) FROM (SELECT DISTINCT TOP {DEFAULT_SAMPLE_ROWS} {qc_l} FROM {ql}) s")
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
        schema = self._schema(database)
        result = conn.execute(_text(
            f"SELECT TOP {limit + 1} * FROM {_quote(conn, schema)}.{_quote(conn, table)}"
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
        # SHOWPLAN_XML 成本高且需会话级开关，首期不做行数预估（对齐 SQLBot 行为）
        return WriteImpact(statement_type=stmt_type, estimated_rows=None,
                           detail="SQL Server dry-run 暂不支持行数预估")
