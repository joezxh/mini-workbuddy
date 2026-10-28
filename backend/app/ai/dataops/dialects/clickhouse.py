"""ClickHouse 方言适配器（类型体系扩展，元数据 SQL 移植自 SQLBot db_sql.py ck 分支）。

约定：
- ``database`` 即 ClickHouse 的 database（连接级库名 == 扫描边界，无 schema 层）；
- 元数据来自 ``system.databases / system.tables / system.columns``；
- 版本 < 22 无 ``comment`` 列：先取 ``version()`` 主版本号再分支（SQLBot 同款）；
- 探活 ``SELECT 1``；驱动为 clickhouse-sqlalchemy（clickhouse+http），懒加载；
- 写操作在分析库场景中极少，dry-run 首期仅语句分类。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy import text as _text

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)
from app.ai.dataops.dialects._sqlalchemy_base import SQLAlchemyProbeMixin

DEFAULT_SAMPLE_ROWS = 1000
_MIN_SAMPLE_ROWS = 100
_MAX_SAMPLE_ROWS = 50000

#: CK 类型判定前缀（画像 min/max 与归一化用）
_NUMERIC_PREFIXES = ("int", "uint", "float", "decimal", "bool", "nullable(int", "nullable(float", "nullable(decimal", "nullable(uint", "nullable(bool")
_TEMPORAL_PREFIXES = ("date", "datetime")


def _quote(conn, ident: str) -> str:
    """标识符引用：优先 SQLAlchemy dialect.identifier_preparer（CK → 反引号）。"""
    if not isinstance(ident, str) or not ident:
        raise ValueError(f"非法标识符: {ident!r}")
    engine = getattr(conn, "engine", None)
    preparer = getattr(getattr(engine, "dialect", None), "identifier_preparer", None)
    if preparer is not None:
        return preparer.quote(ident)
    return "`" + ident.replace("`", "``") + "`"


def _clamp_sample_rows(sample_rows: Any) -> int:
    if not sample_rows:
        return DEFAULT_SAMPLE_ROWS
    return max(_MIN_SAMPLE_ROWS, min(int(sample_rows), _MAX_SAMPLE_ROWS))


def _base_type(data_type: str) -> str:
    """去掉 Nullable(...) 包装，便于类型族判定。"""
    dt = (data_type or "").strip()
    if dt.lower().startswith("nullable(") and dt.endswith(")"):
        dt = dt[len("nullable("):-1]
    return dt


class ClickhouseAdapter(SQLAlchemyProbeMixin):
    """ClickHouse 适配器（clickhouse+http）。"""

    name = "clickhouse"
    probe_sql = "SELECT 1"

    # ------------------------------------------------------------------
    def _major_version(self, conn) -> Optional[int]:
        """服务端主版本号；取不到返回 None（保守按新版本处理）。"""
        try:
            raw = conn.execute(_text("SELECT version()")).fetchone()[0]
            return int(str(raw).split(".")[0])
        except Exception:  # noqa: BLE001
            return None

    def list_databases(self, conn) -> List[str]:
        rows = conn.execute(_text(
            "SELECT name FROM system.databases ORDER BY name"
        )).fetchall()
        return [r[0] for r in rows]

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        has_comment = (self._major_version(conn) or 99) >= 22
        sql = (
            "SELECT name, engine, comment" if has_comment
            else "SELECT name, engine, '' as comment"
        )
        rows = conn.execute(
            _text(sql + " FROM system.tables WHERE database = :db AND engine NOT IN ('Dictionary') ORDER BY name"),
            {"db": database},
        ).fetchall()
        return [
            TableMeta(
                name=name,
                table_type="VIEW" if "View" in (engine or "") else "BASE TABLE",
                comment=comment or None,
                engine=engine or None,
            )
            for name, engine, comment in rows
        ]

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        has_comment = (self._major_version(conn) or 99) >= 22
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            cols: List[ColumnMeta] = []
            sql = (
                "SELECT name, type, position, comment" if has_comment
                else "SELECT name, type, position, '' as comment"
            )
            for (name, data_type, position, comment) in conn.execute(
                _text(sql + " FROM system.columns WHERE database = :db AND table = :table ORDER BY position"),
                {"db": database, "table": table},
            ).fetchall():
                cols.append(
                    ColumnMeta(
                        name=name,
                        ordinal=int(position),
                        data_type=_base_type(data_type),
                        column_type=data_type,
                        nullable=(data_type or "").lower().startswith("nullable("),
                        comment=comment or None,
                    )
                )
            result[table] = cols
        return result

    # ------------------------------------------------------------------
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        sample_rows = _clamp_sample_rows(sample_rows)
        qualified = f"{_quote(conn, database)}.{_quote(conn, table)}"
        qc = _quote(conn, column)
        total, non_null = conn.execute(
            _text(f"SELECT COUNT(*), COUNT({qc}) FROM {qualified} LIMIT {sample_rows}")
        ).fetchone()
        total, non_null = int(total), int(non_null)
        distinct = int(conn.execute(
            _text(f"SELECT uniqExact({qc}) FROM {qualified} LIMIT {sample_rows}")
        ).fetchone()[0])
        profile = ColumnProfile(
            total=total, non_null=non_null, distinct_count=distinct,
            null_rate=round((total - non_null) / total, 6) if total else 0.0,
            distinct_ratio=round(distinct / non_null, 6) if non_null else 0.0,
        )
        base = _base_type(self._column_data_type(conn, database, table, column)).lower()
        if base.startswith(_NUMERIC_PREFIXES) or base.startswith(_TEMPORAL_PREFIXES):
            row = conn.execute(
                _text(f"SELECT toString(min({qc})), toString(max({qc})) FROM {qualified}")
            ).fetchone()
            profile.min_value, profile.max_value = row[0] or None, row[1] or None
        else:
            top = conn.execute(
                _text(
                    f"SELECT toString({qc}) AS value, count(*) AS cnt FROM {qualified} "
                    f"WHERE {qc} IS NOT NULL GROUP BY {qc} ORDER BY cnt DESC, value LIMIT 10"
                )
            ).fetchall()
            profile.top_values = [{"value": v, "count": int(c)} for v, c in top]
        return profile

    def _column_data_type(self, conn, database: str, table: str, column: str) -> str:
        row = conn.execute(
            _text("SELECT type FROM system.columns WHERE database = :db AND table = :t AND name = :c"),
            {"db": database, "t": table, "c": column},
        ).first()
        return row[0] if row else ""

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        try:
            ql = f"{_quote(conn, database)}.{_quote(conn, left.table)}"
            qr = f"{_quote(conn, database)}.{_quote(conn, right.table)}"
            qc_l, qc_r = _quote(conn, left.column), _quote(conn, right.column)
            matched = conn.execute(
                _text(
                    f"SELECT COUNT(*) FROM (SELECT DISTINCT {qc_l} AS v FROM {ql} LIMIT {DEFAULT_SAMPLE_ROWS}) s "
                    f"WHERE EXISTS (SELECT 1 FROM {qr} r WHERE r.{qc_r} = s.v)"
                )
            ).fetchone()
            total = conn.execute(
                _text(f"SELECT COUNT(*) FROM (SELECT DISTINCT {qc_l} FROM {ql} LIMIT {DEFAULT_SAMPLE_ROWS}) s")
            ).fetchone()
            n = int(total[0]) if total else 0
            return round(int(matched[0]) / n, 6) if n else 0.0
        except Exception:  # noqa: BLE001 - 类型不可比等估算失败置 0
            return 0.0

    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult:
        limit = max(1, min(int(limit), 50))
        result = conn.execute(_text(
            f"SELECT * FROM {_quote(conn, database)}.{_quote(conn, table)} LIMIT {limit + 1}"
        ))
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchmany(limit + 1)]
        truncated = len(rows) > limit
        return QueryResult(columns=columns, rows=rows[:limit], row_count=len(rows[:limit]),
                           truncated=truncated)

    # ------------------------------------------------------------------
    _TYPE_PATTERNS = (
        ("update", re.compile(r"^\s*(ALTER\s+UPDATE|UPDATE)\b", re.IGNORECASE)),
        ("delete", re.compile(r"^\s*(ALTER\s+DELETE|DELETE)\b", re.IGNORECASE)),
        ("insert", re.compile(r"^\s*INSERT\b", re.IGNORECASE)),
        ("ddl", re.compile(r"^\s*(CREATE|ALTER\s+(?:TABLE|DATABASE)|DROP|TRUNCATE|RENAME)\b", re.IGNORECASE)),
    )

    def dry_run(self, conn, sql: str) -> WriteImpact:
        stmt_type = "unknown"
        for name, pattern in self._TYPE_PATTERNS:
            if pattern.match(sql or ""):
                stmt_type = name
                break
        # CK 的 EXPLAIN 面向查询计划，mutation 无行数预估语法，首期不做
        return WriteImpact(statement_type=stmt_type, estimated_rows=None,
                           detail="ClickHouse dry-run 暂不支持行数预估")
