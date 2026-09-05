"""结果格式化：字段裁剪、重命名、排序、精度控制与行数截断。

输出稳定结构 ``{records, total, truncated, columns}``，便于 Agent 与前端消费。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.ai.tool_manager.sqlbot_tool_config import ResultFormatConfig

logger = logging.getLogger(__name__)

__all__ = ["format_results", "normalize_cell"]


def normalize_cell(value: Any, precision: Optional[int] = None) -> Any:
    """归一化单元格值，保证 JSON 可序列化。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        if precision is not None:
            return round(value, precision)
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [normalize_cell(v, precision) for v in value]
    if isinstance(value, dict):
        return {str(k): normalize_cell(v, precision) for k, v in value.items()}
    return str(value)


def _sort_key(row: Dict[str, Any], field: str):
    value = row.get(field)
    if value is None:
        return (1, 0, "")
    if isinstance(value, bool):
        return (0, int(value), "")
    if isinstance(value, (int, float, Decimal)):
        return (0, float(value), "")
    return (0, 0, str(value))


def format_results(
    rows: List[Dict[str, Any]], fmt: ResultFormatConfig
) -> Dict[str, Any]:
    """按配置格式化结果集。

    :return: ``{"records": [...], "total": n, "truncated": bool, "columns": [...]}``
    """
    rows = [r for r in rows if isinstance(r, dict)]
    raw_total = len(rows)

    # 1. 排序（多字段，后声明的先排以保证前置字段优先级更高）
    for item in reversed(fmt.order_by or []):
        try:
            rows = sorted(rows, key=lambda r: _sort_key(r, item.field), reverse=item.desc)
        except TypeError as exc:  # noqa: PERF203
            logger.warning("排序字段 %s 类型不可比较，已跳过: %s", item.field, exc)

    # 2. 行数截断
    max_rows = fmt.max_rows
    truncated = raw_total > max_rows
    if truncated:
        rows = rows[:max_rows]

    # 3. 字段裁剪 + 重命名 + 精度
    include = fmt.include_fields
    exclude = set(fmt.exclude_fields or [])
    alias = fmt.field_alias or {}
    precision = fmt.number_precision

    records: List[Dict[str, Any]] = []
    columns: List[str] = []
    seen_cols: set[str] = set()

    for row in rows:
        new_row: Dict[str, Any] = {}
        keys = include if include else list(row.keys())
        for key in keys:
            if key in exclude:
                continue
            if include and key not in row:
                continue
            out_key = alias.get(key, key)
            new_row[out_key] = normalize_cell(row.get(key), precision)
            if out_key not in seen_cols:
                seen_cols.add(out_key)
                columns.append(out_key)
        records.append(new_row)

    return {
        "records": records,
        "total": len(records),
        "rawTotal": raw_total,
        "truncated": truncated,
        "columns": columns,
    }
