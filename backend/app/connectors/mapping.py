"""字段映射（P3 Task 2~5 共享能力）。

把外部系统的响应字段映射到内部目标字段，并做轻量类型/格式转换。
转换器用**白名单函数表**实现，**严禁 eval / 任意表达式**，避免注入。
与连接器抽象同构，纯函数便于单测。
"""
from __future__ import annotations

import datetime
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class FieldMapItem(BaseModel):
    """一条字段映射：从 ``source``（dotted 路径）取值，写入 ``target``。"""

    target: str
    source: str                       # dotted 路径，如 "data.user.name"
    transform: Optional[str] = None   # 转换器名，见 TRANSFORMS
    default: Optional[Any] = None     # 取值为空/缺失时的默认值


def extract_path(obj: Any, path: Optional[str]) -> Any:
    """按 dotted 路径从 dict 取值；路径为空直接返回 obj。"""
    if not path:
        return obj
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _to_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y", "t")
    return bool(value)


_DATE_FORMATS = (
    "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d", "%Y-%m-%dT%H:%M:%SZ",
)


def _to_date_iso(value: Any) -> Any:
    if value is None or value == "":
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, str):
        s = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.datetime.strptime(s, fmt).isoformat()
            except ValueError:
                continue
    return value  # 解析失败原样返回，交由下游决定


# 转换器白名单：名称 → 函数。只允许这些，杜绝任意表达式执行。
TRANSFORMS: Dict[str, Callable[[Any], Any]] = {
    "int": lambda v: int(v) if v not in (None, "") else v,
    "float": lambda v: float(v) if v not in (None, "") else v,
    "bool": _to_bool,
    "str": lambda v: None if v is None else str(v),
    "lower": lambda v: v.lower() if isinstance(v, str) else v,
    "upper": lambda v: v.upper() if isinstance(v, str) else v,
    "title": lambda v: v.title() if isinstance(v, str) else v,
    "trim": lambda v: v.strip() if isinstance(v, str) else v,
    "date_iso": _to_date_iso,
}


def _apply_transform(value: Any, name: Optional[str]) -> Any:
    if not name:
        return value
    fn = TRANSFORMS.get(name)
    if fn is None:
        raise ValueError(f"未知字段转换器: {name!r}（可用: {', '.join(sorted(TRANSFORMS))}）")
    try:
        return fn(value)
    except (ValueError, TypeError):
        # 转换失败（如 int("abc")）回退为 None，不中断整批拉取
        return None


def apply_field_map(records: List[Dict[str, Any]], field_map: Optional[List[FieldMapItem]]) -> List[Dict[str, Any]]:
    """把原始记录列表按 ``field_map`` 映射为目标字段 dict 列表。

    - ``field_map`` 为空/None → 原样返回（透传）。
    - 缺失源字段或取值为空 → 使用 ``default``；仍缺则目标字段不出现。
    - 转换器仅在 ``transform`` 指定时应用。
    """
    if not field_map:
        return records
    out: List[Dict[str, Any]] = []
    for rec in records:
        mapped: Dict[str, Any] = {}
        for item in field_map:
            raw = extract_path(rec, item.source)
            if raw is None or raw == "":
                if item.default is not None:
                    mapped[item.target] = _apply_transform(item.default, item.transform)
                # default 为 None 且源缺失 → 不写入目标字段
                continue
            mapped[item.target] = _apply_transform(raw, item.transform)
        out.append(mapped)
    return out
