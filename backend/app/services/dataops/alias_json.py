"""``aliases_json`` 列的统一读写入口。

历史契约：该列是 ``list[str]``（别名，用于匹配物理表名/注释）。
前端多处直接 ``(record.aliases || []).join(', ')``，绑定匹配也按列表遍历，
因此对外的 ``aliases`` 必须是数组——直接塞对象会让渲染函数抛
``join is not a function``，进而把 Vue 的 patch 打断成
``Cannot set properties of null``。

本体导入需要在同一列携带 icon / color / objectType / DataSource / Metric
等富元数据（对象标准没有第二个 JSONB 列可用，且不新增字段），故以
``{"_opl": {...}, "list": [...]}`` 的富结构存储。本模块保证：

- :func:`aliases_list` 对外永远返回 ``list[str]``；
- :func:`opl_meta` 单独取扩展元数据；
- :func:`with_aliases` 写回别名时保留 ``_opl``，不静默丢元数据。

新增读取 ``aliases_json`` 的代码一律走这里，不要再直接 ``or []``。
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional

OPL_KEY = "_opl"
LIST_KEY = "list"

# 可直接转成别名字符串的标量（排除 bool：它是 int 的子类，语义上不是别名）
_SCALARS = (str, int, float)


def aliases_list(value: Any) -> List[str]:
    """从 ``aliases_json`` 取出别名列表。

    兼容三种既有形态：``None``、纯数组（历史数据）、富结构 ``{"list": [...]}``。
    """
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, _SCALARS) and not isinstance(v, bool)]
    if isinstance(value, dict):
        inner = value.get(LIST_KEY)
        if isinstance(inner, list):
            return [str(v) for v in inner if isinstance(v, _SCALARS) and not isinstance(v, bool)]
    return []


def opl_meta(value: Any) -> Optional[dict]:
    """取出本体扩展元数据（``_opl``）；非富结构返回 ``None``。"""
    if isinstance(value, dict):
        meta = value.get(OPL_KEY)
        if isinstance(meta, dict):
            return meta
    return None


def build(aliases: Optional[Iterable[str]] = None, opl: Optional[dict] = None) -> Any:
    """构造写入值：无 ``_opl`` 时保持纯数组（最广兼容），有则用富结构。"""
    items = [str(a) for a in (aliases or [])]
    if not opl:
        return items
    return {LIST_KEY: items, OPL_KEY: opl}


def with_aliases(value: Any, aliases: Optional[Iterable[str]]) -> Any:
    """替换别名但保留已有 ``_opl``（对象编辑保存时用）。"""
    return build(aliases, opl_meta(value))
