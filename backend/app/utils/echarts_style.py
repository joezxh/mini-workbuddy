"""ECharts 图谱转换常量与样式映射。

将 ``routers/graph.py`` 中散布的 ECharts 节点/边样式常量集中到此处，
保持纯数据、零逻辑，便于复用与统一维护。
"""

from typing import Any, Dict

# 节点分类（category index 必须与前端图例对齐）
CATEGORIES = [
    {"name": "风险事件"},   # 0
    {"name": "相关人员"},   # 1
    {"name": "相关机构"},   # 2
    {"name": "相关地点"},   # 3
    {"name": "纠纷类型"},   # 4
]

TYPE_TO_CATEGORY: Dict[str, int] = {
    "RiskEvent": 0,
    "Person": 1, "RiskPerson": 1,
    "Organization": 2, "RiskEntity": 2,
    "Location": 3,
    "DisputeCategory": 4, "Other": 4,
}

CATEGORY_STYLES: Dict[int, Dict[str, Any]] = {
    0: {"color": "#1557a0", "borderColor": "#5aaaf0", "borderWidth": 4,
        "shadowBlur": 20, "shadowColor": "rgba(13,63,122,.55)"},
    1: {"color": "#1d6fc2", "borderColor": "#80c0f0", "borderWidth": 2,
        "shadowBlur": 8,  "shadowColor": "rgba(29,111,194,.4)"},
    2: {"color": "#145e38", "borderColor": "#3abf7a", "borderWidth": 2,
        "shadowBlur": 8,  "shadowColor": "rgba(20,94,56,.4)"},
    3: {"color": "#c06820", "borderColor": "#e8a060", "borderWidth": 2,
        "shadowBlur": 6,  "shadowColor": "rgba(180,100,20,.35)"},
    4: {"color": "#c0282a", "borderColor": "#ff7070", "borderWidth": 2,
        "shadowBlur": 8,  "shadowColor": "rgba(200,40,40,.4)"},
}

# 节点 symbol 形状按 category
CATEGORY_SYMBOL: Dict[int, str] = {
    0: "circle", 1: "circle", 2: "roundRect", 3: "roundRect", 4: "diamond",
}

# 节点基础 symbolSize 按 category
CATEGORY_SIZE: Dict[int, int] = {
    0: 80, 1: 52, 2: 56, 3: 44, 4: 44,
}

# 边关系类型 → 中文（仅当 role 为空时的兜底）
EDGE_LABEL_ZH: Dict[str, str] = {
    "PARTICIPATED_IN": "参与",
    "INVOLVED_IN": "涉及",
    "ASSOCIATED_WITH_LOCATION": "关联地点",
    "CLASSIFIED_AS": "归类",
    "INVOLVES_ENTITY": "涉及机构",
    "SUBTYPE_OF": "子类型",
    "KNOWS": "认识",
    "FAMILY": "家庭关系",
    "COLLEAGUE": "同事",
    "INCITES": "煽动",
    "ORGANIZES": "组织",
    "FOLLOWS": "追随",
    "OPPOSES": "对抗",
}

# 边线条样式（颜色/宽度/虚实）
EDGE_STYLE: Dict[str, Dict[str, Any]] = {
    "PARTICIPATED_IN":          {"color": "#1d6fc2", "width": 1.8},
    "INVOLVED_IN":              {"color": "#1d6fc2", "width": 1.8},
    "ASSOCIATED_WITH_LOCATION": {"color": "#c06820", "width": 1.4, "type": "dashed"},
    "CLASSIFIED_AS":            {"color": "#c0282a", "width": 1.6},
    "INVOLVES_ENTITY":          {"color": "#1a7a4a", "width": 1.6},
    "SUBTYPE_OF":               {"color": "#6a8090", "width": 1.0, "type": "dashed"},
    "KNOWS":                    {"color": "#7030a0", "width": 1.2},
    "FAMILY":                   {"color": "#7030a0", "width": 1.4},
    "COLLEAGUE":                {"color": "#546070", "width": 1.2, "type": "dashed"},
    "INCITES":                  {"color": "#c0282a", "width": 1.4},
    "ORGANIZES":                {"color": "#c0282a", "width": 1.4},
    "FOLLOWS":                  {"color": "#7030a0", "width": 1.2, "type": "dashed"},
    "OPPOSES":                  {"color": "#c0282a", "width": 1.4, "type": "dashed"},
}

# 边 label 基础样式（前端 ECharts edgeLabel 使用）
EDGE_LABEL_STYLE_BASE: Dict[str, Any] = {
    "show": True,
    "fontSize": 10,
    "fontFamily": "Microsoft YaHei, PingFang SC, sans-serif",
    "backgroundColor": "rgba(255,255,255,.88)",
    "padding": [2, 6],
    "borderRadius": 3,
    "borderWidth": 1,
    "borderColor": "rgba(0,0,0,.08)",
}

# tooltip 中要跳过的内部/冗余字段
SKIP_TOOLTIP_KEYS = frozenset({
    "updated_at", "synced_at", "normalized_name",
    "source_system", "pipeline", "source",
})
