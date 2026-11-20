# -*- coding: utf-8 -*-
"""_common.py 脚手架离线单测（不依赖网络/DB/真实模型）。"""
import asyncio

import pytest

from _common import FakeChatModel, make_model, Trace, mock_fx_rate, erp_gateway
from agentscope.message import Msg, TextBlock


def _ask(text="问"):
    return [Msg(name="user", content=[TextBlock(type="text", text=text)], role="user")]


def test_fake_model_script_order():
    m = FakeChatModel(["第一答", "第二答"], name="t")

    async def go():
        r1 = await m(_ask())
        r2 = await m(_ask())
        return r1.content[0].text, r2.content[0].text

    assert asyncio.run(go()) == ("第一答", "第二答")


def test_fake_model_exhausted_raises():
    m = FakeChatModel([], name="t")
    with pytest.raises(RuntimeError, match="脚本耗尽"):
        asyncio.run(m(_ask()))


def test_make_model_no_env_raises(monkeypatch):
    for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="--mock"):
        make_model()


def test_trace_filter():
    t = Trace()
    t.record("dispatch", member="a")
    t.record("done")
    assert t.kinds("dispatch") == [{"kind": "dispatch", "member": "a"}]


def test_gateway_whitelist():
    assert "denied" in erp_gateway(["cost_price"])  # mock 工具是普通函数，直接调用


def test_fx_rate_deterministic():
    assert mock_fx_rate("USD/JPY")["rate"] == 155.0