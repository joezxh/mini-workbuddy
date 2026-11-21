# -*- coding: utf-8 -*-
"""跨语种客服交接（交接式）：只传摘要不传全量对话 + 交接跳数上限。"""
import asyncio

from app.ai.team.trade import support_handoff


def test_handoff_summary_only_and_hops():
    out = asyncio.run(support_handoff.run(mock=True))
    hops = out["trace"].kinds("handoff")
    assert [h["to"] for h in hops] == ["xborder-logistics-en", "xborder-returns-zh"]
    for fm in out["trace"].kinds("expert_first_msg"):
        assert fm["content"].startswith("<handover>")
        assert "西语客户完整对话" not in fm["content"]  # 前专家全量对话标记串不得出现
    assert len(hops) <= 3