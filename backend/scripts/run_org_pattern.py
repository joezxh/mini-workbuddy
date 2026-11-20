# -*- coding: utf-8 -*-
"""跨境电商组织模式统一 CLI（收敛自 examples/org_patterns 各脚本的 __main__）。

按 PATTERNS 注册表分派到 app/ai/team/org_patterns/<pattern>.py 的 run 入口，
打印 final 与 trace 摘要；--mock 离线确定性运行，真实模型走 --model-id
（factory_ext DB 配置）或 OPENAI/DASHSCOPE 环境变量兜底。

用法（backend 目录下）：
  python scripts/run_org_pattern.py listing_launch --mock
  python scripts/run_org_pattern.py market_expansion --mock --timeout-team xborder-eu-team
  python scripts/run_org_pattern.py inquiry_pipeline --mock --inject-bad-rate
  python scripts/run_org_pattern.py ad_review_debate --mock --judge-always-continue
  python scripts/run_org_pattern.py budget_parallel --mock --fail-channel xborder-roi-meta
  python scripts/run_org_pattern.py supply_chain_federation --mock --probe-boundary
  python scripts/run_org_pattern.py listing_launch --model-id 1
  python scripts/run_org_pattern.py --list
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 沿用 scripts/apply_ddl.py 惯例：挂 backend 以 import app

from app.ai.team.org_patterns import PATTERNS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="跨境电商组织模式运行入口（--mock 离线运行）")
    parser.add_argument("pattern", nargs="?", choices=sorted(PATTERNS), help="模式 key（业务模块名）")
    parser.add_argument("--list", action="store_true", help="列出全部模式与示例输入")
    parser.add_argument("--mock", action="store_true", help="使用脚本化离线模型，不触网")
    parser.add_argument("--model-id", type=int, default=None, help="DB 模型配置 id（factory_ext 构建）")
    parser.add_argument("--timeout-team", default=None, help="market_expansion：注入子团队超时")
    parser.add_argument("--inject-bad-rate", action="store_true", help="inquiry_pipeline：注入错误汇率")
    parser.add_argument("--judge-always-continue", action="store_true", help="ad_review_debate：裁判恒 continue")
    parser.add_argument("--fail-channel", default=None, help="budget_parallel：注入渠道测算失败")
    parser.add_argument("--probe-boundary", action="store_true", help="supply_chain_federation：越界字段探测")
    args = parser.parse_args()

    if args.list or not args.pattern:
        for key, meta in PATTERNS.items():
            print(f"{key:26s} {meta['team_code']:30s} {meta['name']}（mode={meta['mode']}）")
            print(f"{'':26s} 示例输入：{meta['sample_input']}")
        if not args.pattern:
            parser.exit(0 if args.list else 1)
        return

    meta = PATTERNS[args.pattern]
    flags = {}
    if args.timeout_team:
        flags["timeout_team"] = args.timeout_team
    if args.inject_bad_rate:
        flags["inject_bad_rate"] = True
    if args.judge_always_continue:
        flags["judge_always_continue"] = True
    if args.fail_channel:
        flags["fail_channel"] = args.fail_channel
    if args.probe_boundary:
        flags["probe_boundary"] = True

    out = asyncio.run(meta["run"](mock=args.mock, model_id=args.model_id, **flags))
    print(f"\n== {meta['name']}（{meta['team_code']}）final ==")
    print(out["final"])
    print(f"\n== trace：{len(out['trace'].items)} 条 ==")
    for it in out["trace"].items:
        print(it)


if __name__ == "__main__":
    main()