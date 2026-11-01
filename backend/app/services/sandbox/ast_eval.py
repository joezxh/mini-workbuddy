"""受控 AST 求值器（spec 2026-11-01 §4.1：仅字面量/属性引用/四则/比较/逻辑/聚合/clip/if）。

确定性纪律：数值一律 Decimal（入参字符串，结果量化 4 位）；禁止 eval/exec；
节点形状非法或引用缺失抛 AstEvalError —— 引擎侧按"配置期 warn"处理，不中断 Tick。
"""
from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Callable, Union

Value = Union[Decimal, bool]

_ARITH = {"add", "sub", "mul", "div", "mod"}
_CMP = {"gt", "ge", "lt", "le", "eq", "ne"}
_AGG = {"min", "max", "sum", "avg", "count"}
_Q = Decimal("0.0001")


class AstEvalError(Exception):
    """code ∈ {BAD_OP, UNKNOWN_OP, MISSING_PROP, DIV_ZERO, BAD_SHAPE}。"""

    def __init__(self, code: str, msg: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {msg}")


def _d(x) -> Decimal:
    if isinstance(x, bool):
        raise AstEvalError("BAD_SHAPE", "bool 不作数值")
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        raise AstEvalError("BAD_SHAPE", f"数值非法: {x!r}")


def _truthy(v: Value) -> bool:
    return bool(v) if isinstance(v, bool) else v != 0


def _binary(node: dict) -> tuple:
    """二元节点形状守卫：缺 a/b 键 → BAD_SHAPE（而非 KeyError）。"""
    try:
        return node["a"], node["b"]
    except KeyError:
        raise AstEvalError("BAD_SHAPE", f"二元节点缺操作数: {node!r}")


def eval_expr(node: dict, get_prop: Callable[[str, str], Decimal],
              get_param: Callable[[str], Decimal]) -> Value:
    if not isinstance(node, dict) or "op" not in node:
        raise AstEvalError("BAD_SHAPE", f"节点非法: {node!r}")
    op = node["op"]
    if op == "num":
        try:
            v = node["v"]
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"num 值缺失: {node!r}")
        try:
            return _d(v).quantize(_Q)
        except AstEvalError:
            raise AstEvalError("BAD_SHAPE", f"num 值非法: {node!r}")
    if op == "prop":
        try:
            return _d(get_prop(node["entity"], node["key"])).quantize(_Q)
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"prop 节点缺 entity/key: {node!r}")
    if op == "param":
        try:
            return _d(get_param(node["key"])).quantize(_Q)
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"param 节点缺 key: {node!r}")
    if op in _ARITH:
        an, bn = _binary(node)
        a, b = _d(eval_expr(an, get_prop, get_param)), _d(eval_expr(bn, get_prop, get_param))
        try:
            if op == "add":
                r = a + b
            elif op == "sub":
                r = a - b
            elif op == "mul":
                r = a * b
            elif op == "div":
                if b == 0:
                    raise AstEvalError("DIV_ZERO")
                r = a / b
            else:
                if b == 0:
                    raise AstEvalError("DIV_ZERO")
                r = a % b
        except (DivisionByZero, InvalidOperation):
            raise AstEvalError("DIV_ZERO")
        return r.quantize(_Q)
    if op in _CMP:
        an, bn = _binary(node)
        a, b = _d(eval_expr(an, get_prop, get_param)), _d(eval_expr(bn, get_prop, get_param))
        return {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b,
                "eq": a == b, "ne": a != b}[op]
    if op in ("and", "or"):
        try:
            items = node["items"]
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"逻辑节点缺 items: {node!r}")
        vals = [_truthy(eval_expr(x, get_prop, get_param)) for x in items]
        return all(vals) if op == "and" else any(vals)
    if op == "not":
        try:
            inner = node["a"]
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"not 节点缺 a: {node!r}")
        return not _truthy(eval_expr(inner, get_prop, get_param))
    if op in _AGG:
        try:
            items = [_d(eval_expr(x, get_prop, get_param)) for x in node["items"]]
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"聚合节点缺 items: {node!r}")
        if op == "count":
            return Decimal(len(items)).quantize(_Q)
        if not items:
            raise AstEvalError("BAD_SHAPE", "空聚合")
        if op == "min":
            return min(items)
        if op == "max":
            return max(items)
        if op == "sum":
            return sum(items, Decimal(0)).quantize(_Q)
        return (sum(items, Decimal(0)) / Decimal(len(items))).quantize(_Q)  # avg
    if op == "clip":
        try:
            x = _d(eval_expr(node["x"], get_prop, get_param))
            lo = _d(eval_expr(node["lo"], get_prop, get_param))
            hi = _d(eval_expr(node["hi"], get_prop, get_param))
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"clip 节点缺 x/lo/hi: {node!r}")
        return max(lo, min(hi, x))
    if op == "if":
        try:
            cond, ta, fb = node["cond"], node["a"], node["b"]
        except KeyError:
            raise AstEvalError("BAD_SHAPE", f"if 节点缺 cond/a/b: {node!r}")
        return eval_expr(ta if _truthy(eval_expr(cond, get_prop, get_param)) else fb,
                         get_prop, get_param)
    raise AstEvalError("UNKNOWN_OP", op)
