# -*- coding: utf-8 -*-
"""trade 注册表契约：模式 → 实现映射与种子数据一致。"""
import inspect

from app.ai.team.trade import PATTERNS
from app.ai.team.trade.seed_data import TEAMS


def test_registry_covers_eight_teams():
    assert len(PATTERNS) == 8
    assert {meta["team_code"] for meta in PATTERNS.values()} == {t["team_code"] for t in TEAMS}


def test_registry_entries_runnable_and_documented():
    for key, meta in PATTERNS.items():
        assert inspect.iscoroutinefunction(meta["run"]), key
        assert meta["name"] and meta["mode"] and meta["sample_input"], key
        assert meta["mode"] in {"sequential", "parallel", "msghub", "supervisor", "dag"}


def test_registry_sample_input_matches_seed():
    by_code = {t["team_code"]: t for t in TEAMS}
    for meta in PATTERNS.values():
        assert meta["sample_input"] == by_code[meta["team_code"]]["sample_input"]