# -*- coding: utf-8 -*-
"""跨境电商 8 组织模式团队幂等种子脚本（方案 A 双轨制的 API 挂载轨）。

只走 HTTP API（POST /api/v1/agent-config、GET/POST /api/v1/ai-team），
不做 DB 迁移；范式照 seed_domain_content.py（按 code 查重跳过、缺成员跳过整团队）。
真实模式语义由 backend/examples/org_patterns/ 独立脚本演示（--mock 离线）；
挂载 mode 仅记录来源模板 + 前端展示（运行时统一 llm_orchestrated，不读 mode）。

用法（需先启动后端 uvicorn）：
  python scripts/seed_org_pattern_teams.py --dry-run
  python scripts/seed_org_pattern_teams.py [--base-url http://127.0.0.1:8000] [--username admin] [--password xxx]
"""
from __future__ import annotations

import argparse

import requests

BASE = "http://127.0.0.1:8000"
TOKEN = ""
TIMEOUT = 120
CATEGORY = "跨境电商"


def api(method: str, path: str, ok_codes=(200, 201), **kw):
    headers = kw.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = requests.request(method, BASE + path, headers=headers, timeout=TIMEOUT, **kw)
    if r.status_code not in ok_codes:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else None


def as_items(res):
    """兼容 list / {data:[]} / {items:[]} 多种返回。"""
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("data", "items", "list", "records"):
            v = res.get(k)
            if isinstance(v, list):
                return v
    return []


# ── Agent 定义（无技能纯 LLM：agent_type=CHAT，execution_mode=llm）──────────
def _agent(suffix: str, name: str, description: str, system_prompt: str) -> dict:
    return {
        "agent_code": f"xborder-{suffix}",
        "name": name,
        "category": CATEGORY,
        "description": description,
        "strategy": {"execution_mode": "llm", "system_prompt": system_prompt},
        "tools": {"tools": [], "skills": []},
    }


AGENTS = [
    # 01 Supervisor-Worker：4 worker（leader 由运行时自动生成，与 orchestrator 一致）
    _agent("product-picker", "选品分析师", "范例01 选品 Worker：市场热度与竞争度分析",
           "你是跨境选品分析师，基于市场扫描数据评估品类热度、竞争度与关键词趋势，输出选品建议。"),
    _agent("listing-writer", "多语种 Listing 撰写", "范例01 Listing Worker：多语种标题/卖点/描述",
           "你是跨境 Listing 撰写专家，按目标市场语言输出标题、五点卖点与商品描述，突出差异化。"),
    _agent("compliance-checker", "合规审查员", "范例01 合规 Worker：目标市场认证与备案核查",
           "你是跨境合规审查员，核查目标市场准入认证与备案要求，输出合规结论与缺口清单。"),
    _agent("pricing-analyst", "定价分析师", "范例01 定价 Worker：成本/汇率/平台费核算定价",
           "你是跨境定价分析师，按成本结构、汇率与平台费率核算建议售价与毛利区间。"),
    # 02 层级式：6 角色平铺（表结构无层级字段，层级写进描述；真实语义由脚本保证）
    _agent("region-director", "区域拓展总监", "范例02 总监层：只面对渠道 Leader，不直派 Worker",
           "你是海外市场拓展总监，只向渠道 Leader（sea_leader/eu_leader）下达团队级任务，汇总两区域结论产出拓展方案；不得直接指挥 Worker。"),
    _agent("sea-leader", "东南亚渠道 Leader", "范例02 Leader 层：东南亚子团队负责人",
           "你是东南亚渠道负责人，把总监任务拆给 sea_researcher/sea_writer，汇总子团队结论上报总监。"),
    _agent("eu-leader", "欧洲渠道 Leader", "范例02 Leader 层：欧洲子团队负责人",
           "你是欧洲渠道负责人，把总监任务拆给 eu_researcher，汇总子团队结论上报总监。"),
    _agent("sea-researcher", "东南亚市场调研", "范例02 Worker 层：东南亚平台与消费调研",
           "你是东南亚市场调研员，输出目标国平台格局、消费偏好与准入要点。"),
    _agent("sea-writer", "东南亚本地化文案", "范例02 Worker 层：东南亚本地化卖点文案",
           "你是东南亚本地化文案专员，按调研结论输出本地语言卖点与渠道话术。"),
    _agent("eu-researcher", "欧洲市场调研", "范例02 Worker 层：欧洲合规与渠道调研",
           "你是欧洲市场调研员，输出欧盟合规要求（CE/GDPR 等）与渠道进入策略。"),
    # 03 流水线：询盘→报价→合同→跟单
    _agent("inquiry-parser", "询盘解析员", "范例03 步骤1：提取询盘关键要素",
           "你是外贸询盘解析员，从询盘原文提取买家、数量、目的港、贸易条款与诉求。"),
    _agent("quotation-maker", "报价员", "范例03 步骤2：成本+汇率核算报价（带验收重试）",
           "你是外贸报价员，按真实汇率与成本结构核算单价/总价/交期，输出可执行报价。"),
    _agent("contract-drafter", "合同起草员", "范例03 步骤3：关键合同条款",
           "你是外贸合同起草员，基于报价输出付款、质保、不可抗力等关键条款。"),
    _agent("followup-clerk", "跟单催单员", "范例03 步骤4：跟单与催单时间表",
           "你是外贸跟单员，输出付款确认、验货、发运、清关提醒的催单时间表。"),
    # 04 交接式：跨语种客服（交接语义由脚本演示）
    _agent("presale-es", "西语售前客服", "范例04 首接专家：西语售前，越界诉求交接",
           "你是西语售前客服，负责新品咨询；物流/退款诉求用 transfer_to 交接，摘要含订单号/诉求/已承诺事项，禁复述整段对话。"),
    _agent("logistics-en", "英语物流专员", "范例04 中转专家：查件与承运商对接",
           "你是英文物流专员，负责查件与承运商对接；退款诉求用 transfer_to 交接，只传摘要。"),
    _agent("returns-zh", "中文退换货专员", "范例04 终接专家：退款流程与客户挽留",
           "你是中文退货退款专员，负责退款流程与客户挽留，直接给出终答。"),
    # 05 对等网状：4 平台运营（无中心节点）
    _agent("amazon-ops", "亚马逊运营", "范例05 对等节点：亚马逊库存/价格联动",
           "你是亚马逊运营，关注共享消息板上的库存/价格变动并回应，每轮最多 1 条发言，目标是多平台策略一致。"),
    _agent("shopee-ops", "Shopee 运营", "范例05 对等节点：Shopee 库存/价格联动",
           "你是 Shopee 运营，关注共享消息板上的库存/价格变动并回应，每轮最多 1 条发言，目标是多平台策略一致。"),
    _agent("tiktok-ops", "TikTok 运营", "范例05 对等节点：TikTok 闪购与价格联动",
           "你是 TikTok Shop 运营，发起或响应闪购降价等变动，每轮最多 1 条发言，目标是多平台策略一致。"),
    _agent("indie-ops", "独立站运营", "范例05 对等节点：独立站价格与库存联动",
           "你是独立站运营，关注共享消息板上的库存/价格变动并回应，每轮最多 1 条发言，避免与平台价冲突。"),
    # 06 辩论/群聊：正方/反方/裁判
    _agent("pro-creative", "激进投放辩手", "范例06 正方：激进创意+高预算押注",
           "你是广告评审正方，主张激进创意与高预算集中押注（如 TikTok），用数据与案例论证，并回应反方质疑。"),
    _agent("con-creative", "稳健投放辩手", "范例06 反方：保守合规+小步测试",
           "你是广告评审反方，主张合规优先与小步 A/B 测试（如 Google 稳健投放），指出激进方案风险并回应正方。"),
    _agent("ad-judge", "评审裁判", "范例06 裁判：每轮结构化裁决 continue/final",
           "你是广告策略评审裁判，每轮末输出结构化裁决 {verdict: continue|final, reason, final_plan}；第 3 轮必须 final 并给出终审投放方案。"),
    # 07 并行聚合：3 渠道测算 + 聚合
    _agent("roi-google", "Google 渠道测算", "范例07 并行 Worker：Google Ads ROI 测算",
           "你是 Google Ads 投放分析师，按预算测算 ROI 与转化预期，输出渠道结论。"),
    _agent("roi-meta", "Meta 渠道测算", "范例07 并行 Worker：Meta Ads ROI 测算",
           "你是 Meta Ads 投放分析师，按预算测算 ROI 与转化预期，输出渠道结论。"),
    _agent("roi-tiktok", "TikTok 渠道测算", "范例07 并行 Worker：TikTok Ads ROI 测算",
           "你是 TikTok Ads 投放分析师，按预算测算 ROI 与转化预期，输出渠道结论。"),
    _agent("budget-aggregator", "预算聚合师", "范例07 聚合者：三渠道结果汇总分配",
           "你是预算聚合师，汇总三渠道 ROI 测算（含失败占位说明），输出预算分配方案与调优建议。"),
    # 08 联邦式：协调者 + 3 信任域（白名单网关边界由脚本演示）
    _agent("brand-coordinator", "品牌协调者", "范例08 协调者：只经白名单网关取最小必要字段",
           "你是品牌方供应链协调者，只经各域白名单网关获取最小必要字段（产能/交期、报价/时效、预算消耗），产出大促联动方案；不得索取域内私有数据（如成本价）。"),
    _agent("factory-erp-agent", "工厂 ERP 代理", "范例08 工厂域：只暴露产能/交期",
           "你是工厂 ERP 域代理，数据主权独立，只对外暴露产能与交期，拒绝成本价等越界字段请求。"),
    _agent("logistics-agent-federation", "物流域代理", "范例08 物流域：只暴露报价/时效",
           "你是物流域代理，数据主权独立，只对外暴露报价与时效，拒绝越界字段请求。"),
    _agent("ads-platform-agent", "广告平台域代理", "范例08 广告域：只暴露预算消耗",
           "你是广告平台域代理，数据主权独立，只对外暴露预算消耗，拒绝越界字段请求。"),
]


# ── 团队定义（edges 端点用 agent_code 原文；build_payloads 统一转 node_key）──
def _chain(members: list) -> list:
    """链式 edges：__START__ → m1 → … → mn → __END__。"""
    keys = ["__START__", *members, "__END__"]
    return [{"from_node_key": a, "to_node_key": b} for a, b in zip(keys, keys[1:])]


def _fanout(center: str, leaves: list) -> list:
    """扇出+汇聚：__START__ → center → 各 leaf → __END__。"""
    return [
        {"from_node_key": "__START__", "to_node_key": center},
        *[{"from_node_key": center, "to_node_key": lf} for lf in leaves],
        *[{"from_node_key": lf, "to_node_key": "__END__"} for lf in leaves],
    ]


def _parallel_fanin(workers: list, aggregator: str) -> list:
    """并行扇出+汇聚：__START__ → 各 worker → aggregator → __END__。"""
    return [
        *[{"from_node_key": "__START__", "to_node_key": w} for w in workers],
        *[{"from_node_key": w, "to_node_key": aggregator} for w in workers],
        {"from_node_key": aggregator, "to_node_key": "__END__"},
    ]


TEAMS = [
    {
        "team_code": "xborder-supervisor-listing",
        "name": "新品上架统筹团队",
        "description": "范例01 Supervisor-Worker：Leader 运行时自动生成并派活汇总，4 worker 独立上下文；模式语义见 examples/org_patterns/01_supervisor_worker.py",
        "category": CATEGORY,
        "mode": "supervisor",
        "members": ["xborder-product-picker", "xborder-listing-writer",
                     "xborder-compliance-checker", "xborder-pricing-analyst"],
        "roles": {"xborder-product-picker": "选品分析师", "xborder-listing-writer": "Listing 撰写",
                   "xborder-compliance-checker": "合规审查员", "xborder-pricing-analyst": "定价分析师"},
        "edges": [],
        "sample_input": "评估『便携咖啡机』上架日本亚马逊，给出 GO/NO-GO 与售价",
    },
    {
        "team_code": "xborder-hierarchy-expansion",
        "name": "海外市场拓展团队",
        "description": "范例02 层级式：总监→渠道 Leader→Worker 两层（表结构无层级字段，6 角色平铺，层级见角色描述）；真实层级语义由 02_hierarchy_expansion.py 保证",
        "category": CATEGORY,
        "mode": "supervisor",
        "members": ["xborder-region-director", "xborder-sea-leader", "xborder-eu-leader",
                     "xborder-sea-researcher", "xborder-sea-writer", "xborder-eu-researcher"],
        "roles": {"xborder-region-director": "区域拓展总监", "xborder-sea-leader": "东南亚 Leader",
                   "xborder-eu-leader": "欧洲 Leader", "xborder-sea-researcher": "东南亚调研",
                   "xborder-sea-writer": "东南亚文案", "xborder-eu-researcher": "欧洲调研"},
        "edges": [],
        "sample_input": "为便携咖啡机制定东南亚与欧洲市场渠道拓展方案",
    },
    {
        "team_code": "xborder-pipeline-inquiry",
        "name": "外贸询盘 SOP 团队",
        "description": "范例03 流水线：询盘解析→报价（带验收重试≤3）→合同条款→跟单催单；模式语义见 03_pipeline_inquiry.py（原生 agentscope.sop）",
        "category": CATEGORY,
        "mode": "sequential",
        "members": ["xborder-inquiry-parser", "xborder-quotation-maker",
                     "xborder-contract-drafter", "xborder-followup-clerk"],
        "roles": {"xborder-inquiry-parser": "询盘解析员", "xborder-quotation-maker": "报价员",
                   "xborder-contract-drafter": "合同起草员", "xborder-followup-clerk": "跟单催单员"},
        "edges": _chain(["xborder-inquiry-parser", "xborder-quotation-maker",
                          "xborder-contract-drafter", "xborder-followup-clerk"]),
        "sample_input": "Dear seller, we are interested in your portable coffee maker. Please quote 500 units to Tokyo, CIF, with lead time. — Tanaka Trading",
    },
    {
        "team_code": "xborder-handoff-support",
        "name": "跨语种客服交接团队",
        "description": "范例04 交接式：控制权一次性交出，只传 <handover>摘要</handover> 不传全量对话，max_hops=3；交接语义由 04_handoff_support.py 演示",
        "category": CATEGORY,
        "mode": "sequential",
        "members": ["xborder-presale-es", "xborder-logistics-en", "xborder-returns-zh"],
        "roles": {"xborder-presale-es": "西语售前", "xborder-logistics-en": "英语物流",
                   "xborder-returns-zh": "中文退换货"},
        "edges": _chain(["xborder-presale-es", "xborder-logistics-en", "xborder-returns-zh"]),
        "sample_input": "Hola, mi pedido ORD-2026-1120 lleva 10 días sin actualización de envío, quiero un reembolso.",
    },
    {
        "team_code": "xborder-mesh-multiplatform",
        "name": "多平台运营互通团队",
        "description": "范例05 对等网状：无中心节点，共享消息板全员可见，轮转发言预算 16 条/max_rounds=4；语义见 05_mesh_multiplatform.py",
        "category": CATEGORY,
        "mode": "msghub",
        "members": ["xborder-amazon-ops", "xborder-shopee-ops", "xborder-tiktok-ops", "xborder-indie-ops"],
        "roles": {"xborder-amazon-ops": "亚马逊运营", "xborder-shopee-ops": "Shopee 运营",
                   "xborder-tiktok-ops": "TikTok 运营", "xborder-indie-ops": "独立站运营"},
        "edges": [],
        "sample_input": "TikTok 闪购降价 15%，各平台同步应对",
    },
    {
        "team_code": "xborder-debate-adreview",
        "name": "广告策略评审辩论团队",
        "description": "范例06 辩论/群聊：正反方互见全量辩论记录，裁判每轮结构化裁决，max_rounds=3 硬终局；语义见 06_debate_adreview.py",
        "category": CATEGORY,
        "mode": "msghub",
        "members": ["xborder-pro-creative", "xborder-con-creative", "xborder-ad-judge"],
        "roles": {"xborder-pro-creative": "激进投放辩手", "xborder-con-creative": "稳健投放辩手",
                   "xborder-ad-judge": "评审裁判"},
        "edges": [],
        "sample_input": "黑五网一：$5000 预算押注 TikTok 激进投放 vs Google 稳健投放",
    },
    {
        "team_code": "xborder-parallel-budget",
        "name": "多渠道预算测算团队",
        "description": "范例07 并行聚合：三渠道无依赖真并发（asyncio.gather+wait_for），单路失败占位继续，聚合师汇总；语义见 07_parallel_budget.py",
        "category": CATEGORY,
        "mode": "parallel",
        "members": ["xborder-roi-google", "xborder-roi-meta", "xborder-roi-tiktok", "xborder-budget-aggregator"],
        "roles": {"xborder-roi-google": "Google 测算", "xborder-roi-meta": "Meta 测算",
                   "xborder-roi-tiktok": "TikTok 测算", "xborder-budget-aggregator": "预算聚合师"},
        "edges": _parallel_fanin(["xborder-roi-google", "xborder-roi-meta", "xborder-roi-tiktok"],
                                  "xborder-budget-aggregator"),
        "sample_input": "黑五 $10000 预算，三渠道 ROI 测算与分配",
    },
    {
        "team_code": "xborder-federated-supplychain",
        "name": "跨组织供应链协同团队",
        "description": "范例08 联邦式：协调者经白名单网关扇出 3 信任域（工厂/物流/广告），越界字段拒绝，只交换最小必要结果；语义见 08_federated_supplychain.py",
        "category": CATEGORY,
        "mode": "dag",
        "members": ["xborder-brand-coordinator", "xborder-factory-erp-agent",
                     "xborder-logistics-agent-federation", "xborder-ads-platform-agent"],
        "roles": {"xborder-brand-coordinator": "品牌协调者", "xborder-factory-erp-agent": "工厂 ERP 代理",
                   "xborder-logistics-agent-federation": "物流域代理", "xborder-ads-platform-agent": "广告平台代理"},
        "edges": _fanout("xborder-brand-coordinator",
                          ["xborder-factory-erp-agent", "xborder-logistics-agent-federation",
                           "xborder-ads-platform-agent"]),
        "sample_input": "圣诞季：确认工厂产能、锁物流舱位、联动广告预算",
    },
]


def build_payloads() -> tuple:
    """纯函数：AGENTS/TEAMS → (agent_payloads, team_payloads)，不触网。

    node_key 统一 code.replace('-', '_')（与 seed_domain_content 一致）；
    agent_config_id 由 main() 运行时解析填充。
    """
    agent_payloads = [dict(a, agent_type="CHAT") for a in AGENTS]
    team_payloads = []
    for t in TEAMS:
        members = [
            {"node_key": code.replace("-", "_"), "agent_code": code, "role_name": t["roles"][code]}
            for code in t["members"]
        ]
        edges = [
            {"from_node_key": e["from_node_key"].replace("-", "_"),
             "to_node_key": e["to_node_key"].replace("-", "_")}
            for e in t["edges"]
        ]
        team_payloads.append({
            "team_code": t["team_code"], "name": t["name"], "description": t["description"],
            "category": t["category"], "mode": t["mode"],
            "members": members, "edges": edges, "sample_input": t["sample_input"],
        })
    return agent_payloads, team_payloads


# ── 运行时步骤（幂等：按 code 查重跳过、缺成员跳过整团队）──────────────────
def login(username: str, password: str):
    global TOKEN
    data = api("POST", "/api/v1/auth/login", json={"username": username, "password": password},
               ok_codes=(200, 401, 422))
    if isinstance(data, dict):
        TOKEN = data.get("token") or data.get("access_token") or ""
        if TOKEN:
            print("✔ 登录成功")
            return
    raise SystemExit("登录失败：请用 --username/--password 提供管理员账号")


def step_create_agents(agent_payloads: list):
    created = skipped = 0
    for ap in agent_payloads:
        res = api("GET", f"/api/v1/agent-config?page=1&page_size=100&keyword={ap['agent_code']}")
        if any(it.get("agent_code") == ap["agent_code"] for it in as_items(res)):
            skipped += 1
            continue
        api("POST", "/api/v1/agent-config", json=ap)
        print(f"✔ 创建 Agent {ap['name']}（{ap['agent_code']}）")
        created += 1
    print(f"✔ Agent：新建 {created} / 已存在 {skipped}")


def step_create_teams(team_payloads: list):
    created = skipped = 0
    for tp in team_payloads:
        res = api("GET", "/api/v1/ai-team?page=1&page_size=100")
        if any(it.get("team_code") == tp["team_code"] for it in as_items(res)):
            skipped += 1
            continue
        members = []
        for m in tp["members"]:
            r = api("GET", f"/api/v1/agent-config?page=1&page_size=50&keyword={m['agent_code']}")
            found = next((it for it in as_items(r) if it.get("agent_code") == m["agent_code"]), None)
            if not found:
                print(f"  ✗ 团队 {tp['team_code']} 缺成员 {m['agent_code']}，跳过团队")
                members = []
                break
            members.append({"node_key": m["node_key"], "agent_config_id": found["id"],
                            "role_name": m["role_name"]})
        if not members:
            continue
        api("POST", "/api/v1/ai-team", json={
            "name": tp["name"], "team_code": tp["team_code"], "description": tp["description"],
            "category": tp["category"], "mode": tp["mode"],
            "members": members, "edges": tp["edges"],
        })
        print(f"✔ 创建团队 {tp['name']}（{tp['team_code']}，mode={tp['mode']}，"
              f"{len(members)} 成员 {len(tp['edges'])} 边）")
        created += 1
    print(f"✔ Team：新建 {created} / 已存在 {skipped}")


def main():
    global BASE
    ap = argparse.ArgumentParser(description="跨境电商 xborder-* 8 团队幂等种子")
    ap.add_argument("--dry-run", action="store_true", help="只打印预览，不触网")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    args = ap.parse_args()
    BASE = args.base_url.rstrip("/")

    agent_payloads, team_payloads = build_payloads()
    if args.dry_run:
        print(f"== dry-run 预览：{len(agent_payloads)} Agent / {len(team_payloads)} 团队（不触网）==")
        for tp in team_payloads:
            print(f"[dry] {tp['team_code']}  mode={tp['mode']}  成员={len(tp['members'])}  边={len(tp['edges'])}")
            print(f"      示例输入：{tp['sample_input']}")
        return

    print(f"== 跨境电商组织模式种子（base={BASE}）==")
    login(args.username, args.password)
    step_create_agents(agent_payloads)
    step_create_teams(team_payloads)
    print("== 完成 ==")


if __name__ == "__main__":
    main()