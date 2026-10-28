"""ElasticSearch 方言适配器（类型体系扩展，elasticsearch-py 原生客户端族）。

约定：
- 不走 SQLAlchemy：``open`` 经 ``connection.open_connection("es", ...)`` 返回
  Elasticsearch 客户端（懒加载，未安装时探活返回安装指引）；
- ES 无「库/schema」层级：``list_databases`` 返回单元素伪作用域 ``["_cluster"]``，
  让「作用域 → 索引 → 字段」三层树与其他类型保持同构（``list_tables`` 忽略该参数）；
- 表 == 索引（``_cat/indices``，过滤 ``.`` 前缀系统索引），注释取 mapping
  ``_meta.description``；列 == mapping properties（语义对齐 SQLBot es_engine.py）；
- 画像基于聚合（cardinality / min / max / terms），不可比字段静默降级；
  overlap 与 dry-run 首期不做（估算信号恒 0 / 仅分类）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.ai.dataops.dialect_base import (
    ColRef, ColumnMeta, ColumnProfile, QueryResult, TableMeta, WriteImpact,
)

#: 伪作用域常量：ES 集群级无 database 概念，占位保持三层树同构
PSEUDO_SCOPE = "_cluster"

#: ES mapping type → 归一化类型（对齐 mysql/pg 适配器语义）
_NORMALIZE_TYPES = {
    "keyword": "varchar", "keywordcaseinsensitive": "varchar", "wildcard": "varchar",
    "text": "text", "match_only_text": "text",
    "integer": "integer", "integer_range": "integer",
    "long": "bigint", "long_range": "bigint",
    "short": "smallint", "byte": "smallint",
    "double": "double precision", "float": "real", "half_float": "real",
    "scaled_float": "numeric", "double_range": "double precision",
    "boolean": "boolean", "date": "timestamp", "date_nanos": "timestamp",
    "date_range": "timestamp", "ip": "inet", "ip_range": "inet",
    "nested": "nested", "object": "object", "flattened": "jsonb", "join": "keyword",
}
_NUMERIC_PREFIXES = ("integer", "long", "short", "byte", "double", "float", "half_float", "scaled_float")


def _normalize(es_type: str) -> str:
    return _NORMALIZE_TYPES.get((es_type or "").lower(), es_type or "")


def _is_numeric(es_type: str) -> bool:
    return (es_type or "").lower().startswith(_NUMERIC_PREFIXES)


class EsAdapter:
    """ElasticSearch 适配器（elasticsearch-py 客户端，非 SQLAlchemy 族）。"""

    name = "es"

    # ------------------------------------------------------------------
    def open(self, ds, connect_database: Optional[str] = None) -> Tuple[object, callable]:
        """打开 ES 客户端：返回 (client, cleanup)。connect_database 仅签名对齐，ES 忽略。"""
        from app.ai.dataops.connection import open_connection

        client = open_connection(
            "es", ds.host, ds.port, ds.username,
            getattr(ds, "_password_plain", None), ds.database,
            config=getattr(ds, "config_json", None) or {},
        )

        def _cleanup() -> None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - 老版本客户端无 close()
                pass

        return client, _cleanup

    def test_connect(self, ds) -> Tuple[bool, Optional[str]]:
        try:
            client, cleanup = self.open(ds)
            try:
                if not client.ping():
                    return False, "Elasticsearch ping 未通过（地址/凭据/集群健康检查）"
                return True, None
            finally:
                cleanup()
        except Exception as exc:  # noqa: BLE001 - 探活失败原因（含驱动指引）原样回传
            return False, f"{type(exc).__name__}: {exc}"[:500]

    # ------------------------------------------------------------------
    def list_databases(self, conn) -> List[str]:
        return [PSEUDO_SCOPE]

    def list_tables(self, conn, database: str) -> List[TableMeta]:
        indices = conn.cat.indices(format="json") or []
        tables: List[TableMeta] = []
        for idx in indices:
            name = idx.get("index")
            if not name or name.startswith("."):  # 过滤 .kibana/.security 等系统索引
                continue
            comment = None
            try:
                mapping = conn.indices.get_mapping(index=name)
                meta = (mapping.get(name) or {}).get("mappings", {}).get("_meta") or {}
                comment = meta.get("description") or None
            except Exception:  # noqa: BLE001 - 单索引 mapping 读取失败不阻断列表
                pass
            tables.append(TableMeta(name=name, table_type="INDEX", comment=comment,
                                    row_count=int(idx["docs_count"]) if idx.get("docs_count") else None))
        tables.sort(key=lambda t: t.name)
        return tables

    def list_columns(self, conn, database: str, tables: List[str]) -> Dict[str, List[ColumnMeta]]:
        result: Dict[str, List[ColumnMeta]] = {}
        for table in tables:
            cols: List[ColumnMeta] = []
            try:
                mapping = conn.indices.get_mapping(index=table)
                entry = mapping.get(table) or next(iter(mapping.values()), {})
                properties = entry.get("mappings", {}).get("properties") or {}
            except Exception:  # noqa: BLE001 - 索引无 mapping/已删除，返回空列
                properties = {}
            for field, config in properties.items():
                config = config or {}
                es_type = config.get("type") or ",".join(config.keys()) or "object"
                meta = config.get("_meta") or {}
                cols.append(
                    ColumnMeta(
                        name=field,
                        ordinal=len(cols) + 1,
                        data_type=_normalize(config.get("type") or es_type),
                        column_type=es_type,
                        nullable=True,
                        comment=meta.get("description") or None,
                    )
                )
            result[table] = cols
        return result

    # ------------------------------------------------------------------
    def profile_column(self, conn, database: str, table: str, column: str, sample_rows: int) -> ColumnProfile:
        total = int(conn.count(index=table).get("count", 0))
        non_null = int(conn.count(index=table, body={
            "query": {"bool": {"filter": [{"exists": {"field": column}}]}}
        }).get("count", 0))
        profile = ColumnProfile(
            total=total, non_null=non_null,
            null_rate=round((total - non_null) / total, 6) if total else 0.0,
        )
        es_type = self._column_type(conn, table, column)
        agg_field = column if (".keyword" in column or es_type not in ("text", "match_only_text")) else f"{column}.keyword"
        try:
            distinct = conn.search(index=table, size=0, body={
                "aggs": {"d": {"cardinality": {"field": agg_field}}}
            }).get("aggregations", {}).get("d", {}).get("value")
            profile.distinct_count = int(distinct or 0)
            profile.distinct_ratio = round(profile.distinct_count / non_null, 6) if non_null else 0.0
        except Exception:  # noqa: BLE001 - cardinality 不可用（字段缺失/映射异常）保持 0
            pass
        try:
            if _is_numeric(es_type) or es_type in ("date", "date_nanos"):
                bounds = conn.search(index=table, size=0, body={"aggs": {
                    "mn": {"min": {"field": column}}, "mx": {"max": {"field": column}}
                }}).get("aggregations", {})
                profile.min_value = _num_to_str((bounds.get("mn") or {}).get("value"))
                profile.max_value = _num_to_str((bounds.get("mx") or {}).get("value"))
            else:
                buckets = conn.search(index=table, size=0, body={"aggs": {
                    "t": {"terms": {"field": agg_field, "size": 10}}
                }}).get("aggregations", {}).get("t", {}).get("buckets", [])
                profile.top_values = [{"value": b.get("key"), "count": int(b.get("doc_count", 0))}
                                      for b in buckets]
        except Exception:  # noqa: BLE001 - 聚合失败静默降级，不影响其余统计
            pass
        return profile

    @staticmethod
    def _column_type(conn, table: str, column: str) -> str:
        try:
            mapping = conn.indices.get_mapping(index=table)
            entry = mapping.get(table) or next(iter(mapping.values()), {})
            node: Any = entry.get("mappings", {}).get("properties") or {}
            for part in column.split("."):
                node = (node.get(part) or {}) if isinstance(node, dict) else {}
                if "properties" in node:
                    node = node["properties"]
            return str(node.get("type") or "")
        except Exception:  # noqa: BLE001
            return ""

    def overlap_ratio(self, conn, database: str, left: ColRef, right: ColRef) -> float:
        """ES 跨索引值域比对成本高，首期恒返回 0（估算信号，不抛出）。"""
        return 0.0

    def sample_rows(self, conn, database: str, table: str, limit: int) -> QueryResult:
        limit = max(1, min(int(limit), 50))
        resp = conn.search(index=table, size=limit + 1, body={"sort": []})
        hits = resp.get("hits", {}).get("hits", [])
        rows: List[List[Any]] = []
        columns: List[str] = []
        seen = set()
        for hit in hits[:limit + 1]:
            source = hit.get("_source") or {}
            for key in source:
                if key not in seen:
                    seen.add(key)
                    columns.append(key)
            rows.append([_jsonable(source.get(c)) for c in columns])
        truncated = len(hits) > limit
        rows = rows[:limit]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)

    # ------------------------------------------------------------------
    def dry_run(self, conn, sql: str) -> WriteImpact:
        """ES 无 SQL 写语法（本客户端族），dry-run 仅标记不支持。"""
        return WriteImpact(statement_type="unknown", estimated_rows=None,
                           detail="ElasticSearch 不支持 SQL dry-run")


def _num_to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _jsonable(value: Any) -> Any:
    """样本值直接进 JSON 响应：标量透传，复杂结构转字符串摘要。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_jsonable(v) if isinstance(v, (bool, int, float, str)) else str(v) for v in value]
    return str(value)
