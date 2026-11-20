# -*- coding: utf-8 -*-
"""种子脚本数据契约：8 个 xborder-* 团队（纯数据断言，不触网）。"""
import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[2] / "scripts"


def load_script(filename: str):
    """scripts 非包：按路径加载模块（与 conftest.load_example 同法）。"""
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_data_contract():
    mod = load_script("seed_org_pattern_teams.py")
    codes = [t["team_code"] for t in mod.TEAMS]
    assert len(codes) == 8 and len(set(codes)) == 8
    assert all(c.startswith("xborder-") for c in codes)
    assert all(t["category"] == "跨境电商" for t in mod.TEAMS)
    assert all(t["mode"] in {"sequential", "parallel", "msghub", "supervisor", "dag"} for t in mod.TEAMS)
    agent_codes = {a["agent_code"] for a in mod.AGENTS}
    for t in mod.TEAMS:
        assert set(t["members"]) <= agent_codes          # 无悬空成员
        assert set(t["roles"]) == set(t["members"])
        assert t["sample_input"]                          # 每团队带示例输入
    for a in mod.AGENTS:
        assert a["strategy"]["execution_mode"] == "llm"  # builder 决策：无技能纯 LLM Agent


def test_edges_reference_known_nodes():
    mod = load_script("seed_org_pattern_teams.py")
    for t in mod.TEAMS:
        known = set(t["members"]) | {"__START__", "__END__"}
        for e in t["edges"]:
            assert e["from_node_key"] in known, (t["team_code"], e)
            assert e["to_node_key"] in known, (t["team_code"], e)
        if t["mode"] in {"supervisor", "msghub"}:
            assert t["edges"] == []  # 动态模式无静态边


def test_build_payloads_consistency():
    mod = load_script("seed_org_pattern_teams.py")
    agent_payloads, team_payloads = mod.build_payloads()
    assert len(agent_payloads) == len(mod.AGENTS)
    assert len(team_payloads) == 8
    for ap in agent_payloads:
        assert ap["agent_type"] == "CHAT"
        assert ap["strategy"]["execution_mode"] == "llm"
        assert ap["tools"] == {"tools": [], "skills": []}
    for tp, raw in zip(team_payloads, mod.TEAMS):
        assert tp["team_code"] == raw["team_code"]
        assert tp["mode"] == raw["mode"]
        node_keys = {m["node_key"] for m in tp["members"]}
        assert len(node_keys) == len(raw["members"])
        for e in tp["edges"]:
            assert e["from_node_key"] in node_keys | {"__START__", "__END__"}
            assert e["to_node_key"] in node_keys | {"__START__", "__END__"}