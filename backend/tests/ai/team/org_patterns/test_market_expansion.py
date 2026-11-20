# -*- coding: utf-8 -*-
"""海外市场拓展（层级式）：总监不越权直派 Worker + 子团队超时不中断总监。"""
import asyncio

from app.ai.team.org_patterns import market_expansion


def test_no_skip_level():
    out = asyncio.run(market_expansion.run(mock=True))
    director_tasks = [t["task"] for t in out["trace"].kinds("assign_team")]
    worker_names = {"xborder-sea-researcher", "xborder-sea-writer", "xborder-eu-researcher"}
    assert all(not any(w in t for w in worker_names) for t in director_tasks)  # 总监不直派 Worker
    assert {t["team"] for t in out["trace"].kinds("assign_team")} == {"xborder-sea-team", "xborder-eu-team"}
    # worker_call 只出现在 leader 层
    assert {(w["leader"], w["worker"]) for w in out["trace"].kinds("worker_call")} == {
        ("xborder-sea-leader", "xborder-sea-researcher"),
        ("xborder-sea-leader", "xborder-sea-writer"),
        ("xborder-eu-leader", "xborder-eu-researcher")}
    assert {t["team"] for t in out["trace"].kinds("team_done")} == {"xborder-sea-team", "xborder-eu-team"}
    assert out["final"]


def test_subteam_timeout_does_not_abort_director():
    out = asyncio.run(market_expansion.run(mock=True, timeout_team="xborder-eu-team"))
    assert out["final"]  # 总监仍产出（含 eu 失败说明）
    assert "eu" in out["final"]
    assert out["trace"].kinds("team_failed")
    assert {t["team"] for t in out["trace"].kinds("team_done")} == {"xborder-sea-team"}