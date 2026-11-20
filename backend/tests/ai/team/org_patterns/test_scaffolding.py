# -*- coding: utf-8 -*-
"""org_patterns 脚手架离线单测（不依赖网络/DB/真实模型）。"""
import asyncio

import pytest

from agentscope.message import Msg, TextBlock
from agentscope.model import DashScopeChatModel, OpenAIChatModel

from app.ai.team.org_patterns.scaffolding import (
    FakeChatModel,
    Trace,
    erp_gateway,
    make_model,
    mock_fx_rate,
)


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


def test_make_model_model_id_uses_factory(monkeypatch):
    """真实模型优先复用 factory_ext：给定 model_id 时走 DB 配置 + build_model。"""
    from app.ai.strategy import factory_ext

    sentinel = object()
    seen = {}

    def fake_resolve(model_id):
        seen["model_id"] = model_id
        return {"provider": "openai", "model": "m", "api_key": "k"}

    def fake_build(cfg):
        seen["cfg"] = cfg
        return sentinel

    monkeypatch.setattr(factory_ext, "resolve_model_config", fake_resolve)
    monkeypatch.setattr(factory_ext, "build_model", fake_build)
    assert make_model(model_id=7) is sentinel
    assert seen["model_id"] == 7 and seen["cfg"]["provider"] == "openai"


def test_make_model_env_openai_fallback(monkeypatch):
    """无 model_id 时保留 ENV 兜底（离线 CLI 场景无 DB 依赖）。"""
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:9/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    assert isinstance(make_model(), OpenAIChatModel)


def test_make_model_env_dashscope_fallback(monkeypatch):
    for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    assert isinstance(make_model(), DashScopeChatModel)


def test_trace_filter():
    t = Trace()
    t.record("dispatch", member="a")
    t.record("done")
    assert t.kinds("dispatch") == [{"kind": "dispatch", "member": "a"}]


def test_gateway_whitelist():
    assert "denied" in erp_gateway(["cost_price"])  # mock 工具是普通函数，直接调用


def test_fx_rate_deterministic():
    assert mock_fx_rate("USD/JPY")["rate"] == 155.0


def test_fake_model_tool_call_ids_unique_across_calls():
    """回归：跨响应的 tool_call id 重复会被 Agent 误判为已完成而跳过执行。"""
    m = FakeChatModel([
        {"tool_calls": [{"name": "t1", "input": {}}]},
        {"tool_calls": [{"name": "t2", "input": {}}]},
    ], name="t")

    async def go():
        r1 = await m(_ask())
        r2 = await m(_ask())
        return r1.content[0].id, r2.content[0].id

    id1, id2 = asyncio.run(go())
    assert id1 != id2