# -*- coding: utf-8 -*-
"""广告策略评审（辩论/群聊）：≤3 轮收敛 + 双方互见 + 裁判恒 continue 时代码兜底终局。"""
import asyncio

from app.ai.team.org_patterns import ad_review_debate


def test_debate_converges_within_3_rounds():
    out = asyncio.run(ad_review_debate.run(mock=True))
    rounds = out["trace"].kinds("round")
    assert 1 <= len(rounds) <= 3
    assert out["trace"].kinds("verdict")[-1]["verdict"] == "final"
    assert out["final"]  # 终审方案非空
    assert len(rounds) == 2  # mock 裁判第 1 轮 continue、第 2 轮 final → 提前收敛


def test_both_sides_see_opponent():
    out = asyncio.run(ad_review_debate.run(mock=True))
    for s in out["trace"].kinds("speech"):
        if s["role"] == "xborder-con-creative":
            assert "xborder-pro-creative" in s["sees"]


def test_judge_stubborn_forced_final_at_round3():
    out = asyncio.run(ad_review_debate.run(mock=True, judge_always_continue=True))
    assert len(out["trace"].kinds("round")) == 3  # max_rounds=3 代码兜底
    assert out["trace"].kinds("verdict")[-1]["verdict"] == "final"
    assert out["final"]