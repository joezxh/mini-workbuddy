# -*- coding: utf-8 -*-
"""范例02 层级式：总监不越权直派 Worker + 子团队超时不中断总监。"""
import asyncio

from .conftest import load_example


def test_no_skip_level():
    out = asyncio.run(load_example("02_hierarchy_expansion.py").run_demo(mock=True))
    director_tasks = [t["task"] for t in out["trace"].kinds("assign_team")]
    worker_names = {"sea_researcher", "sea_writer", "eu_researcher"}
    assert all(not any(w in t for w in worker_names) for t in director_tasks)  # 总监不直派 Worker
    assert {t["team"] for t in out["trace"].kinds("assign_team")} == {"sea_team", "eu_team"}
    # worker_call 只出现在 leader 层
    assert {(w["leader"], w["worker"]) for w in out["trace"].kinds("worker_call")} == {
        ("sea_leader", "sea_researcher"), ("sea_leader", "sea_writer"), ("eu_leader", "eu_researcher")}
    assert {t["team"] for t in out["trace"].kinds("team_done")} == {"sea_team", "eu_team"}
    assert out["final"]


def test_subteam_timeout_does_not_abort_director():
    out = asyncio.run(load_example("02_hierarchy_expansion.py").run_demo(mock=True, timeout_team="eu_team"))
    assert out["final"]  # 总监仍产出（含 eu 失败说明）
    assert "eu" in out["final"]
    assert out["trace"].kinds("team_failed")
    assert {t["team"] for t in out["trace"].kinds("team_done")} == {"sea_team"}