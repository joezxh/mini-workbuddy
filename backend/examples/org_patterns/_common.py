# -*- coding: utf-8 -*-
"""org_patterns 范例共享脚手架（agentscope 2.0.12）。

设计约定（见 docs/design/org-pattern-examples-zh.md 附录 A）：
- FakeChatModel 继承 ChatModelBase，覆写 async _call_api；脚本项 str → 纯文本，
  dict → 支持 {"text": ...} 与 {"tool_calls": [{"name": ..., "input": {...}}]}。
- block 为 pydantic 模型（属性访问）；ToolCallBlock.input 是 JSON 字符串。
- mock 工具均为普通 Python 函数（确定性返回），范例内自行用 FunctionTool 包装。
- 本模块不 import app.*，独立可运行。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from typing import Callable, Coroutine, List, Optional

from agentscope.agent import Agent, ReActConfig
from agentscope.console import ConsoleRenderer
from agentscope.credential import DashScopeCredential, OpenAICredential
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg, TextBlock, ToolCallBlock
from agentscope.model import ChatModelBase, ChatResponse, DashScopeChatModel, OpenAIChatModel
from agentscope.permission import PermissionMode
from agentscope.tool import Toolkit


# ── 模型 ────────────────────────────────────────────────────
class FakeChatModel(ChatModelBase):
    """按脚本队列顺序应答的离线模型；耗尽抛含模型名的清晰错误。"""

    def __init__(self, script: list, name: str = "fake"):
        super().__init__(
            credential=OpenAICredential(api_key="sk-fake"),
            model=name,
            parameters=ChatModelBase.Parameters(),
            stream=False,
        )
        self.script = list(script)
        self.name = name
        self._call_seq = 0
        # Agent 运行时需要 model.formatter（真实模型自带，基类不设默认）
        self.formatter = OpenAIChatFormatter()

    async def _call_api(self, model_name, messages, tools=None, tool_choice=None, **kwargs):
        if not self.script:
            raise RuntimeError(f"FakeChatModel 脚本耗尽: {self.name}")
        item = self.script.pop(0)
        self._call_seq += 1
        blocks: list = []
        if isinstance(item, str):
            blocks.append(TextBlock(type="text", text=item))
        elif isinstance(item, dict):
            if item.get("text"):
                blocks.append(TextBlock(type="text", text=item["text"]))
            for i, tc in enumerate(item.get("tool_calls", [])):
                blocks.append(ToolCallBlock(
                    id=tc.get("id", f"call_{self.name}_{self._call_seq}_{i}"),
                    name=tc["name"],
                    input=json.dumps(tc.get("input", {}), ensure_ascii=False),
                ))
        else:
            raise TypeError(f"FakeChatModel 脚本项类型不支持: {type(item)}")
        return ChatResponse(content=blocks, is_last=True)


def make_model(script: Optional[list] = None, name: str = "fake") -> ChatModelBase:
    """script 非 None → FakeChatModel；否则按环境变量构建真实模型；皆无 → 清晰中文报错。"""
    if script is not None:
        return FakeChatModel(script, name=name)
    base_url = os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if base_url and api_key:
        return OpenAIChatModel(
            credential=OpenAICredential(api_key=api_key, base_url=base_url),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY")
    if dashscope_key:
        return DashScopeChatModel(
            credential=DashScopeCredential(api_key=dashscope_key),
            model=os.environ.get("DASHSCOPE_MODEL", "qwen-plus"),
        )
    raise RuntimeError(
        "未配置模型环境变量：请设置 OPENAI_BASE_URL/OPENAI_API_KEY 或 "
        "DASHSCOPE_API_KEY，或加 --mock 离线运行"
    )


def make_agent(
    name: str,
    system_prompt: str,
    tools: Optional[list] = None,
    max_iters: int = 8,
    model: Optional[ChatModelBase] = None,
) -> Agent:
    """构建免确认（BYPASS）Agent；name 一律 ASCII，中文角色名入 system_prompt。"""
    agent = Agent(
        name=name,
        system_prompt=system_prompt,
        model=model if model is not None else make_model(),
        toolkit=Toolkit(tools=tools or []),
        react_config=ReActConfig(max_iters=max_iters),
    )
    agent.state.permission_context.mode = PermissionMode.BYPASS
    return agent


async def render_stream(stream) -> Msg:
    """ConsoleRenderer 渲染事件流并返回最终消息。"""
    renderer = ConsoleRenderer()
    final: Optional[Msg] = None
    async for item in stream:
        if isinstance(item, Msg):
            final = item
        else:
            renderer.render(item)
    return final if final is not None else renderer.last_msg


# ── Trace ───────────────────────────────────────────────────
class Trace:
    """范例内编排语义留痕（不新增事件枚举，仅本地断言用）。"""

    def __init__(self):
        self.items: List[dict] = []

    def record(self, kind: str, **kw) -> None:
        self.items.append({"kind": kind, **kw})

    def kinds(self, kind: str) -> List[dict]:
        return [it for it in self.items if it["kind"] == kind]


# ── mock 业务工具（普通函数，确定性返回）────────────────────
def mock_market_scan(category: str) -> dict:
    """扫描目标品类的市场热度与竞争度（离线确定性数据）。

    Args:
        category (str): 品类名，如 "宠物用品"。
    """
    return {
        "category": category,
        "heat_score": 82,
        "competition": "medium",
        "top_keywords": ["便携", "环保", "智能"],
    }


def mock_fx_rate(pair: str) -> dict:
    """查询汇率（离线确定性数据，USD/JPY 固定 155.0）。

    Args:
        pair (str): 货币对，如 "USD/JPY"。
    """
    table = {"USD/JPY": 155.0, "USD/CNY": 7.2, "EUR/USD": 1.08}
    return {"pair": pair, "rate": table.get(pair, 1.0)}


def mock_compliance_check(product: str, market: str) -> dict:
    """目标市场合规检查（离线确定性数据）。

    Args:
        product (str): 产品名。
        market (str): 目标市场，如 "JP"。
    """
    return {
        "product": product,
        "market": market,
        "passed": True,
        "certificates": ["PSE", "METI 备案"],
    }


def mock_cost_table(product: str) -> dict:
    """产品成本结构表（离线确定性数据）。

    Args:
        product (str): 产品名。
    """
    return {
        "product": product,
        "unit_cost_cny": 45.0,
        "shipping_cny": 12.0,
        "platform_fee_rate": 0.15,
    }


async def mock_channel_roi(channel: str, budget: float) -> dict:
    """渠道 ROI 测算（模拟 1s 耗时，返回时间戳以证并发）。

    Args:
        channel (str): 投放渠道，如 "roi_google"。
        budget (float): 预算金额。
    """
    started_at = time.monotonic()
    await asyncio.sleep(1)
    finished_at = time.monotonic()
    return {
        "channel": channel,
        "budget": budget,
        "roi": 2.4,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def mock_platform_stock(platform: str) -> dict:
    """平台库存快照（离线确定性数据）。

    Args:
        platform (str): 平台名，如 "amazon"。
    """
    return {"platform": platform, "stock": 320, "replenish_eta_days": 7}


def mock_platform_price(platform: str) -> dict:
    """平台价格快照（离线确定性数据）。

    Args:
        platform (str): 平台名，如 "shopee"。
    """
    return {"platform": platform, "price_usd": 29.9, "promo": False}


# ── 联邦白名单网关（越界字段返回拒绝）──────────────────────
_GATEWAY_WHITELIST = {
    "erp": {"capacity", "lead_time"},
    "logistics": {"quote", "transit_time"},
    "ads": {"budget_spent"},
}
_GATEWAY_DATA = {
    "erp": {"capacity": 5000, "lead_time": 14, "cost_price": 45.0},
    "logistics": {"quote": 3.2, "transit_time": 9, "cost_price": 2.1},
    "ads": {"budget_spent": 1200.0, "cost_price": 0.0},
}


def _gateway(domain: str, fields: List[str]) -> dict:
    allowed = _GATEWAY_WHITELIST[domain]
    denied = [f for f in fields if f not in allowed]
    if denied:
        return {"error": "字段越界", "denied": denied}
    return {f: _GATEWAY_DATA[domain][f] for f in fields}


def erp_gateway(fields: List[str]) -> dict:
    """ERP 域网关：仅允许 capacity/lead_time，越界字段拒绝。

    Args:
        fields (list[str]): 请求字段列表。
    """
    return _gateway("erp", fields)


def logistics_gateway(fields: List[str]) -> dict:
    """物流域网关：仅允许 quote/transit_time，越界字段拒绝。

    Args:
        fields (list[str]): 请求字段列表。
    """
    return _gateway("logistics", fields)


def ads_gateway(fields: List[str]) -> dict:
    """广告域网关：仅允许 budget_spent，越界字段拒绝。

    Args:
        fields (list[str]): 请求字段列表。
    """
    return _gateway("ads", fields)


# ── CLI ─────────────────────────────────────────────────────
def run_cli(main_coro_fn: Callable[..., Coroutine]) -> None:
    """统一 CLI：--mock 离线运行；asyncio.run(main_coro_fn(mock=...))。"""
    parser = argparse.ArgumentParser(description="多智能体组织模式范例（--mock 离线运行）")
    parser.add_argument("--mock", action="store_true", help="使用脚本化离线模型，不触网")
    args = parser.parse_args()
    asyncio.run(main_coro_fn(mock=args.mock))