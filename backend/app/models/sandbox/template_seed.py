"""内置行动模板种子数据（迁移 0011 与测试 conftest 共用同一真源）。

数值在 props/AST 中一律字符串（Decimal 纪律）；``<target>`` 占位由行动目标解析。
effect_spec 的 AST 节点形状以 app/services/sandbox/ast_eval.py 文法为准（spec §4.1）。
"""

# (code, name, domain_hint, param_schema_json, effect_spec_json)
ACTION_TEMPLATE_SEEDS = [
    ("supply_cut", "断供", "supply_chain",
     {"type": "object", "properties": {"ratio": {"type": "number", "default": 100}}, "required": ["ratio"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "supply_cut", "expr": {"op": "num", "v": "1"}},
         {"entity": "<target>", "prop": "risk_score", "expr": {"op": "num", "v": "0.9"}}]}),
    ("delay", "延迟交付", "supply_chain",
     {"type": "object", "properties": {"days": {"type": "number", "default": 5}}, "required": ["days"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "delay_days", "expr": {"op": "param", "key": "days"}}]}),
    ("price_up", "提价", "supply_chain",
     {"type": "object", "properties": {"pct": {"type": "number", "default": 10}}, "required": ["pct"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "price_up_pct", "expr": {"op": "param", "key": "pct"}}]}),
    ("reroute", "切换供应商", "supply_chain",
     {"type": "object", "properties": {"alt_entity": {"type": "string"}}, "required": ["alt_entity"]},
     {"fire_delay_tick": 1, "writes": [
         {"entity": "<target>", "prop": "rerouted_to", "expr": {"op": "param", "key": "alt_entity"}},
         {"entity": "<target>", "prop": "risk_score",
          "expr": {"op": "sub", "a": {"op": "prop", "entity": "<target>", "key": "risk_score"},
                   "b": {"op": "num", "v": "0.3"}}}]}),
]
