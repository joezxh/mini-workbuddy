"""SQL 占位符归一与参数校验（孪生编译链路专用，spec §4.1 第 5~6 步）。

为什么需要归一：sqlglot 按 postgres 方言渲染时会把命名参数写成 psycopg2 风格
``%(p_1)s``，而 SQLAlchemy ``text()`` 的绑定标记是 ``:p_1``（由它再转成驱动风格）。
实测 SqlGuard 对两种写法均判定为只读，故统一以 ``:name`` 落库存储。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

MAX_PARAMS = 20
"""单条查询绑定参数上限（超出即拒绝，防慢查询拼装）。"""

_DRIVER_STYLE = re.compile(r"%\((\w+)\)s")
_TYPE_CHECKS = {
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "str": lambda v: isinstance(v, str),
    "date": lambda v: isinstance(v, str) and len(v) == 10,
    "bool": lambda v: isinstance(v, bool),
}


def normalize_placeholders(sql: str) -> str:
    """把驱动风格 ``%(name)s`` 归一为 SQLAlchemy ``:name``。"""
    return _DRIVER_STYLE.sub(r":\1", sql)


def declared_names(params_json: List[Dict[str, Any]]) -> List[str]:
    return [str(p.get("name", "")).strip() for p in (params_json or []) if p.get("name")]


def validate_params(declared: List[Dict[str, Any]], values: Dict[str, Any]) -> Dict[str, Any]:
    """校验绑定参数：只允许声明过的名字、个数受上限、类型必须匹配。

    :raises ValueError: 未声明参数、参数越界或类型不符
    """
    names = declared_names(declared)
    if len(values) > MAX_PARAMS:
        raise ValueError(f"参数个数超过上限 {MAX_PARAMS}")
    out: Dict[str, Any] = {}
    for key, val in values.items():
        if key not in names:
            raise ValueError(f"未声明的参数: {key}")
        spec = next((p for p in declared if p.get("name") == key), {})
        expected = str(spec.get("type", "str"))
        check = _TYPE_CHECKS.get(expected)
        if check is None:
            raise ValueError(f"不支持的参数类型声明: {expected}")
        if not check(val):
            raise ValueError(f"参数 {key} 类型不符，期望 {expected}")
        out[key] = val
    return out
