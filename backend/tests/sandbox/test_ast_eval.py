"""受控 AST 求值器单测（Task 2，A1 确定性内核；无 DB）。"""
from decimal import Decimal

import pytest

from app.services.sandbox.ast_eval import AstEvalError, eval_expr

WORLD = {"SUP006": {"risk_score": Decimal("0.64"), "supply_cut": Decimal("1")},
         "FAC007": {"capacity": Decimal("100")}}


def GP(e, k):
    if e in WORLD and k in WORLD[e]:
        return WORLD[e][k]
    raise AstEvalError("MISSING_PROP", f"{e}.{k}")


def GPARAM(k):
    return Decimal("5")


def test_arith_decimal_exact():
    n = {"op": "sub", "a": {"op": "prop", "entity": "FAC007", "key": "capacity"},
         "b": {"op": "mul", "a": {"op": "prop", "entity": "FAC007", "key": "capacity"},
               "b": {"op": "num", "v": "0.38"}}}
    assert eval_expr(n, GP, GPARAM) == Decimal("62.0000")


def test_cmp_logic_agg_clip_if_param():
    assert eval_expr({"op": "ge", "a": {"op": "prop", "entity": "SUP006", "key": "risk_score"},
                      "b": {"op": "num", "v": "0.6"}}, GP, GPARAM) is True
    assert eval_expr({"op": "and", "items": [
        {"op": "eq", "a": {"op": "prop", "entity": "SUP006", "key": "supply_cut"},
         "b": {"op": "num", "v": "1"}},
        {"op": "not", "a": {"op": "lt", "a": {"op": "num", "v": "2"}, "b": {"op": "num", "v": "1"}}}]},
        GP, GPARAM) is True
    assert eval_expr({"op": "max", "items": [{"op": "num", "v": "1"}, {"op": "num", "v": "3"}]},
                     GP, GPARAM) == Decimal("3")
    assert eval_expr({"op": "clip", "x": {"op": "num", "v": "1.8"},
                      "lo": {"op": "num", "v": "0"}, "hi": {"op": "num", "v": "1"}},
                     GP, GPARAM) == Decimal("1")
    assert eval_expr({"op": "if", "cond": {"op": "gt", "a": {"op": "num", "v": "2"},
                                           "b": {"op": "num", "v": "1"}},
                      "a": {"op": "num", "v": "9"}, "b": {"op": "num", "v": "0"}},
                     GP, GPARAM) == Decimal("9")
    assert eval_expr({"op": "param", "key": "days"}, GP, GPARAM) == Decimal("5")


def test_or_short_circuit_semantics():
    # or 有一真即真；全部求值（无短路要求，确定性优先）
    assert eval_expr({"op": "or", "items": [
        {"op": "lt", "a": {"op": "num", "v": "5"}, "b": {"op": "num", "v": "1"}},
        {"op": "ge", "a": {"op": "num", "v": "5"}, "b": {"op": "num", "v": "5"}}]}, GP, GPARAM) is True


def test_agg_sum_avg_count_min():
    items = [{"op": "num", "v": "1"}, {"op": "num", "v": "2"}, {"op": "num", "v": "3"}]
    assert eval_expr({"op": "sum", "items": items}, GP, GPARAM) == Decimal("6")
    assert eval_expr({"op": "avg", "items": items}, GP, GPARAM) == Decimal("2")
    assert eval_expr({"op": "count", "items": items}, GP, GPARAM) == Decimal("3")
    assert eval_expr({"op": "min", "items": items}, GP, GPARAM) == Decimal("1")


def test_div_zero_and_missing_prop_and_unknown_op():
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "div", "a": {"op": "num", "v": "1"}, "b": {"op": "num", "v": "0"}}, GP, GPARAM)
    assert e.value.code == "DIV_ZERO"
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "prop", "entity": "NOPE", "key": "x"}, GP, GPARAM)
    assert e.value.code == "MISSING_PROP"
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "system", "cmd": "rm"}, GP, GPARAM)
    assert e.value.code == "UNKNOWN_OP"


def test_bad_shape_nodes():
    for bad in (None, "str", {}, {"op": "num"}, {"op": "add", "a": {"op": "num", "v": "1"}}):
        with pytest.raises(AstEvalError) as e:
            eval_expr(bad, GP, GPARAM)
        assert e.value.code in {"BAD_SHAPE", "MISSING_PROP"}


def test_bool_not_numeric():
    # 比较节点返回 bool；bool 不允许作四则运算数
    with pytest.raises(AstEvalError) as e:
        eval_expr({"op": "add",
                   "a": {"op": "gt", "a": {"op": "num", "v": "2"}, "b": {"op": "num", "v": "1"}},
                   "b": {"op": "num", "v": "1"}}, GP, GPARAM)
    assert e.value.code == "BAD_SHAPE"


def test_quantize_four_places():
    r = eval_expr({"op": "div", "a": {"op": "num", "v": "2"}, "b": {"op": "num", "v": "3"}}, GP, GPARAM)
    assert r == Decimal("0.6667") and r.as_tuple().exponent == -4
