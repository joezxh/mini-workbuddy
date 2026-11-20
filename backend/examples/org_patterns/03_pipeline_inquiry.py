# -*- coding: utf-8 -*-
"""范例03 流水线 —— 外贸询盘→报价→合同→跟单（agentscope 2.0.12 原生 agentscope.sop）。

模式语义：步骤写代码时固定，逐步接力；每步只拿到前一步的 handover（看不到其对话/工具输出）；
报价步带 verifier，验收失败重试 ≤ max_attempts=3。

运行：python 03_pipeline_inquiry.py --mock
"""
from __future__ import annotations

from agentscope.event import CustomEvent
from agentscope.message import Msg, TextBlock
from agentscope.sop import SOP, SOPEngine, SOPStep
from agentscope.tool import FunctionTool

from _common import Trace, make_agent, make_model, mock_cost_table, mock_fx_rate, run_cli

SAMPLE_INPUT = (
    "Dear seller, we are interested in your portable coffee maker. "
    "Please quote 500 units to Tokyo, CIF, with lead time. — Tanaka Trading"
)

# 结构化输出经内置 GenerateStructuredOutput 工具完成（SOPStep 约定：
# executor 交 _Handover{handover}，verifier 交 _Verdict{passed, message}）
_GSO = "GenerateStructuredOutput"


def _handover(text: str) -> dict:
    return {"tool_calls": [{"name": _GSO, "input": {"handover": text}}]}


def _verdict(passed: bool, message: str = "") -> dict:
    return {"tool_calls": [{"name": _GSO, "input": {"passed": passed, "message": message}}]}


async def run_demo(mock: bool, inject_bad_rate: bool = False) -> dict:
    trace = Trace()

    # 注入错误汇率：mock_fx_rate 首次返回错误值（verifier 据此判 fail 触发重试）
    fx_calls = {"n": 0}

    def fx_tool(pair: str) -> dict:
        """查询汇率（演示注入：首次可能返回错误汇率）。

        Args:
            pair (str): 货币对，如 "USD/JPY"。
        """
        fx_calls["n"] += 1
        if inject_bad_rate and fx_calls["n"] == 1:
            return {"pair": pair, "rate": 999.0}
        return mock_fx_rate(pair)

    if mock:
        parser_model = make_model([_handover(
            "询盘解析：Tanaka Trading 求购便携咖啡机 500 台，目的港东京，CIF 条款，需报价与交期。")],
            name="inquiry_parser")
        quote_script = [
            {"tool_calls": [{"name": "fx_tool", "input": {"pair": "USD/JPY"}}]},
            _handover("报价：500 台便携咖啡机 CIF 东京，单价 4980 日元，总价 249 万日元，交期 14 天。"),
        ]
        if inject_bad_rate:
            # 第 1 次尝试用了错误汇率 → verifier 判 fail；第 2 次修正
            quote_script = [
                {"tool_calls": [{"name": "fx_tool", "input": {"pair": "USD/JPY"}}]},
                _handover("报价：按汇率 999 折算，单价 32000 日元（汇率异常）。"),
                {"tool_calls": [{"name": "fx_tool", "input": {"pair": "USD/JPY"}}]},
                _handover("报价（修正）：按 USD/JPY=155 折算，单价 4980 日元，总价 249 万日元，交期 14 天。"),
            ]
        quote_model = make_model(quote_script, name="quotation_maker")
        verifier_script = [_verdict(False, "汇率 999 明显偏离市场价，请改用真实汇率重算。"), _verdict(True)] \
            if inject_bad_rate else [_verdict(True)]
        verifier_model = make_model(verifier_script, name="rate_verifier")
        contract_model = make_model([_handover(
            "合同条款：CIF 东京，付款 30% 预付 + 70% 见提单副本，质保 12 个月，不可抗力免责。")],
            name="contract_drafter")
        followup_model = make_model([_handover(
            "跟单催单包：D+3 确认预付款，D+10 验货拍照，D+14 订舱发运，到港前 3 天提醒清关。")],
            name="followup_clerk")
    else:
        parser_model = quote_model = verifier_model = contract_model = followup_model = None

    steps = [
        SOPStep("解析询盘", "从询盘原文提取买家、数量、目的港、贸易条款与诉求。",
                make_agent("inquiry_parser", "你是外贸询盘解析员，提取询盘关键要素。", model=parser_model)),
        SOPStep("报价", "核算成本并按真实汇率报价（单价/总价/交期）。",
                make_agent("quotation_maker", "你是报价员，用 fx_tool 查汇率、mock_cost_table 核成本后报价。",
                           tools=[FunctionTool(fx_tool), FunctionTool(mock_cost_table)], model=quote_model),
                verifier=make_agent("rate_verifier", "你是报价审核员，核对汇率是否真实、算式是否正确。",
                                    model=verifier_model),
                max_attempts=3),
        SOPStep("合同条款", "基于报价起草关键合同条款。",
                make_agent("contract_drafter", "你是外贸合同起草员，输出付款/质保/免责等关键条款。", model=contract_model)),
        SOPStep("跟单催单", "输出跟单与催单时间表。",
                make_agent("followup_clerk", "你是跟单员，输出付款/验货/发运/清关的催单时间表。", model=followup_model)),
    ]
    engine = SOPEngine(SOP(name="外贸询盘 SOP", steps=steps))

    from agentscope.console import ConsoleRenderer
    renderer = ConsoleRenderer()
    task = Msg(name="user", role="user", content=[TextBlock(type="text", text=SAMPLE_INPUT)])
    async for evt in engine.reply_stream(task):
        if isinstance(evt, CustomEvent):
            if evt.name == "SOP_STEP_STARTED":
                subject, attempt = evt.value["step"], evt.value["attempt"]
                trace.record("step_start", subject=subject)
                if attempt > 1:
                    trace.record("step_retry", subject=subject, attempt=attempt)
            elif evt.name == "SOP_STEP_ENDED" and evt.value["phase"] == "completed":
                trace.record("step_done", subject=evt.value["step"])
        if not isinstance(evt, Msg):
            renderer.render(evt)

    submission = engine.state.steps[-1].submission or []
    final = "\n".join(b.text for b in submission if getattr(b, "type", "") == "text")
    trace.record("final", text=final)
    return {"final": final, "trace": trace}


if __name__ == "__main__":
    run_cli(run_demo)