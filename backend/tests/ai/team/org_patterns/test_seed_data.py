# -*- coding: utf-8 -*-
"""trade 种子数据契约：8 个 xborder-* 团队 + 34 Agent（纯数据断言，不触网）。"""
from app.ai.team.trade.seed_data import AGENTS, TEAMS


def test_seed_data_contract():
    codes = [t["team_code"] for t in TEAMS]
    assert len(codes) == 8 and len(set(codes)) == 8
    assert all(c.startswith("xborder-") for c in codes)
    assert all(t["category"] == "跨境电商" for t in TEAMS)
    assert all(t["mode"] in {"sequential", "parallel", "msghub", "supervisor", "dag"} for t in TEAMS)
    agent_codes = {a["agent_code"] for a in AGENTS}
    assert len(agent_codes) == len(AGENTS) == 34
    for t in TEAMS:
        assert set(t["members"]) <= agent_codes          # 无悬空成员
        assert set(t["roles"]) == set(t["members"])
        assert t["sample_input"]                          # 每团队带示例输入
    for a in AGENTS:
        assert a["strategy"]["execution_mode"] == "llm"  # 无技能纯 LLM Agent


def test_business_naming_no_demo_flavor():
    """正式收编后：标识全 ASCII、描述去『范例』演示味、团队名为业务名。"""
    for a in AGENTS:
        assert a["agent_code"].isascii() and a["agent_code"].startswith("xborder-")
        assert "范例" not in a["description"]
    for t in TEAMS:
        assert "范例" not in t["description"] and "团队" not in t["name"]
        assert t["name"]  # 中文业务名


def test_edges_reference_known_nodes():
    for t in TEAMS:
        known = set(t["members"]) | {"__START__", "__END__"}
        for e in t["edges"]:
            assert e["from_node_key"] in known, (t["team_code"], e)
            assert e["to_node_key"] in known, (t["team_code"], e)
        if t["mode"] in {"supervisor", "msghub"}:
            assert t["edges"] == []  # 动态模式无静态边