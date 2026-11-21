# -*- coding: utf-8 -*-
"""种子脚本 HTTP 层契约：payload 来自 trade.seed_data（纯数据断言，不触网）。"""
import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[4] / "scripts"


def load_script(filename: str):
    """scripts 非包：按路径加载模块。"""
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_payloads_consistency():
    from app.ai.team.trade.seed_data import AGENTS, TEAMS

    mod = load_script("seed_org_pattern_teams.py")
    agent_payloads, team_payloads = mod.build_payloads()
    assert len(agent_payloads) == len(AGENTS) == 34
    assert len(team_payloads) == 8
    for ap in agent_payloads:
        assert ap["agent_type"] == "CHAT"
        assert ap["strategy"]["execution_mode"] == "llm"
        assert ap["tools"] == {"tools": [], "skills": []}
    for tp, raw in zip(team_payloads, TEAMS):
        assert tp["team_code"] == raw["team_code"]
        assert tp["mode"] == raw["mode"]
        node_keys = {m["node_key"] for m in tp["members"]}
        assert len(node_keys) == len(raw["members"])
        for e in tp["edges"]:
            assert e["from_node_key"] in node_keys | {"__START__", "__END__"}
            assert e["to_node_key"] in node_keys | {"__START__", "__END__"}


def test_script_has_no_inline_data_drift():
    """种子数据单一事实源在 seed_data：脚本不得再内联 AGENTS/TEAMS 定义。"""
    mod = load_script("seed_org_pattern_teams.py")
    from app.ai.team.trade import seed_data

    assert mod.AGENTS is seed_data.AGENTS
    assert mod.TEAMS is seed_data.TEAMS