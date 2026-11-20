# -*- coding: utf-8 -*-
"""跨境电商 8 组织模式团队的种子数据（单一事实源）。

供 backend/scripts/seed_org_pattern_teams.py 经 HTTP API 幂等注册，
也供 org_patterns 注册表（PATTERNS）对齐 team_code / sample_input。

契约：
- agent_code / team_code 前缀 xborder-，全 ASCII；中文业务名入 name/描述/system_prompt；
- 纯 LLM Agent：agent_type=CHAT + strategy.execution_mode=llm，tools/skills 留空；
- mode ∈ {sequential, parallel, msghub, supervisor, dag}，category「跨境电商」；
- UI 会话运行时统一 Leader+ask_xxx 派活（不读 mode），模式实现语义在对应模式模块。
"""
from __future__ import annotations

CATEGORY = "跨境电商"


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
    # 跨境新品上架统筹（Supervisor-Worker）：4 worker（UI 会话 Leader 由运行时自动生成）
    _agent("listing-director", "上架统筹总监", "新品上架统筹 Leader：GO/NO-GO 决策与派活汇总（模式实现 listing_launch 的 Leader 角色）",
           "你是跨境电商上架总监，负责新品上架的 GO/NO-GO 决策：把选品、Listing、合规、定价子任务派给对应专家，收齐结论后输出最终决策与建议售价。"),
    _agent("product-picker", "选品分析师", "新品上架统筹成员：市场热度与竞争度分析",
           "你是跨境选品分析师，基于市场扫描数据评估品类热度、竞争度与关键词趋势，输出选品建议。"),
    _agent("listing-writer", "多语种 Listing 撰写", "新品上架统筹成员：多语种标题/卖点/描述",
           "你是跨境 Listing 撰写专家，按目标市场语言输出标题、五点卖点与商品描述，突出差异化。"),
    _agent("compliance-checker", "合规审查员", "新品上架统筹成员：目标市场认证与备案核查",
           "你是跨境合规审查员，核查目标市场准入认证与备案要求，输出合规结论与缺口清单。"),
    _agent("pricing-analyst", "定价分析师", "新品上架统筹成员：成本/汇率/平台费核算定价",
           "你是跨境定价分析师，按成本结构、汇率与平台费率核算建议售价与毛利区间。"),
    # 海外市场拓展（层级式）：6 角色平铺（表结构无层级字段，层级写进描述；真实语义由模式实现保证）
    _agent("region-director", "区域拓展总监", "海外市场拓展总监层：只面对渠道负责人，不直派 Worker",
           "你是海外市场拓展总监，只向渠道负责人（东南亚/欧洲）下达团队级任务，汇总两区域结论产出拓展方案；不得直接指挥 Worker。"),
    _agent("sea-leader", "东南亚渠道负责人", "海外市场拓展 Leader 层：东南亚子团队负责人",
           "你是东南亚渠道负责人，把总监任务拆给东南亚市场调研与本地化文案专员，汇总子团队结论上报总监。"),
    _agent("eu-leader", "欧洲渠道负责人", "海外市场拓展 Leader 层：欧洲子团队负责人",
           "你是欧洲渠道负责人，把总监任务拆给欧洲市场调研员，汇总子团队结论上报总监。"),
    _agent("sea-researcher", "东南亚市场调研", "海外市场拓展 Worker 层：东南亚平台与消费调研",
           "你是东南亚市场调研员，输出目标国平台格局、消费偏好与准入要点。"),
    _agent("sea-writer", "东南亚本地化文案", "海外市场拓展 Worker 层：东南亚本地化卖点文案",
           "你是东南亚本地化文案专员，按调研结论输出本地语言卖点与渠道话术。"),
    _agent("eu-researcher", "欧洲市场调研", "海外市场拓展 Worker 层：欧洲合规与渠道调研",
           "你是欧洲市场调研员，输出欧盟合规要求（CE/GDPR 等）与渠道进入策略。"),
    # 外贸询盘报价（流水线）：询盘→报价→合同→跟单
    _agent("inquiry-parser", "询盘解析员", "外贸询盘报价步骤1：提取询盘关键要素",
           "你是外贸询盘解析员，从询盘原文提取买家、数量、目的港、贸易条款与诉求。"),
    _agent("quotation-maker", "报价员", "外贸询盘报价步骤2：成本+汇率核算报价（带验收重试）",
           "你是外贸报价员，按真实汇率与成本结构核算单价/总价/交期，输出可执行报价。"),
    _agent("rate-verifier", "报价审核员", "外贸询盘报价验收者：核对汇率真实性与算式（模式实现 inquiry_pipeline 的 verifier 角色）",
           "你是报价审核员，核对报价所用汇率是否真实、算式是否正确，输出通过/驳回结论。"),
    _agent("contract-drafter", "合同起草员", "外贸询盘报价步骤3：关键合同条款",
           "你是外贸合同起草员，基于报价输出付款、质保、不可抗力等关键条款。"),
    _agent("followup-clerk", "跟单催单员", "外贸询盘报价步骤4：跟单与催单时间表",
           "你是外贸跟单员，输出付款确认、验货、发运、清关提醒的催单时间表。"),
    # 跨语种客服交接（交接式）：交接语义由模式实现 support_handoff 保证
    _agent("presale-es", "西语售前客服", "跨语种客服交接首接专家：西语售前，越界诉求交接",
           "你是西语售前客服，负责新品咨询；物流/退款诉求用 transfer_to 交接，摘要含订单号/诉求/已承诺事项，禁复述整段对话。"),
    _agent("logistics-en", "英语物流专员", "跨语种客服交接中转专家：查件与承运商对接",
           "你是英文物流专员，负责查件与承运商对接；退款诉求用 transfer_to 交接，只传摘要。"),
    _agent("returns-zh", "中文退换货专员", "跨语种客服交接终接专家：退款流程与客户挽留",
           "你是中文退货退款专员，负责退款流程与客户挽留，直接给出终答。"),
    # 多平台运营协同（对等网状）：4 平台运营（无中心节点）
    _agent("amazon-ops", "亚马逊运营", "多平台运营协同对等节点：亚马逊库存/价格联动",
           "你是亚马逊运营，关注共享消息板上的库存/价格变动并回应，每轮最多 1 条发言，目标是多平台策略一致。"),
    _agent("shopee-ops", "Shopee 运营", "多平台运营协同对等节点：Shopee 库存/价格联动",
           "你是 Shopee 运营，关注共享消息板上的库存/价格变动并回应，每轮最多 1 条发言，目标是多平台策略一致。"),
    _agent("tiktok-ops", "TikTok 运营", "多平台运营协同对等节点：TikTok 闪购与价格联动",
           "你是 TikTok Shop 运营，发起或响应闪购降价等变动，每轮最多 1 条发言，目标是多平台策略一致。"),
    _agent("indie-ops", "独立站运营", "多平台运营协同对等节点：独立站价格与库存联动",
           "你是独立站运营，关注共享消息板上的库存/价格变动并回应，每轮最多 1 条发言，避免与平台价冲突。"),
    # 广告策略评审（辩论/群聊）：正方/反方/裁判
    _agent("pro-creative", "激进投放辩手", "广告策略评审正方：激进创意+高预算押注",
           "你是广告评审正方，主张激进创意与高预算集中押注（如 TikTok），用数据与案例论证，并回应反方质疑。"),
    _agent("con-creative", "稳健投放辩手", "广告策略评审反方：保守合规+小步测试",
           "你是广告评审反方，主张合规优先与小步 A/B 测试（如 Google 稳健投放），指出激进方案风险并回应正方。"),
    _agent("ad-judge", "评审裁判", "广告策略评审裁判：每轮结构化裁决 continue/final",
           "你是广告策略评审裁判，每轮末输出结构化裁决 {verdict: continue|final, reason, final_plan}；第 3 轮必须 final 并给出终审投放方案。"),
    # 多渠道预算测算（并行聚合）：3 渠道测算 + 聚合
    _agent("roi-google", "Google 渠道测算", "多渠道预算测算并行 Worker：Google Ads ROI 测算",
           "你是 Google Ads 投放分析师，按预算测算 ROI 与转化预期，输出渠道结论。"),
    _agent("roi-meta", "Meta 渠道测算", "多渠道预算测算并行 Worker：Meta Ads ROI 测算",
           "你是 Meta Ads 投放分析师，按预算测算 ROI 与转化预期，输出渠道结论。"),
    _agent("roi-tiktok", "TikTok 渠道测算", "多渠道预算测算并行 Worker：TikTok Ads ROI 测算",
           "你是 TikTok Ads 投放分析师，按预算测算 ROI 与转化预期，输出渠道结论。"),
    _agent("budget-aggregator", "预算聚合师", "多渠道预算测算聚合者：三渠道结果汇总分配",
           "你是预算聚合师，汇总三渠道 ROI 测算（含失败占位说明），输出预算分配方案与调优建议。"),
    # 跨组织供应链协同（联邦式）：协调者 + 3 信任域（白名单网关边界由模式实现保证）
    _agent("brand-coordinator", "品牌协调者", "跨组织供应链协同协调者：只经白名单网关取最小必要字段",
           "你是品牌方供应链协调者，只经各域白名单网关获取最小必要字段（产能/交期、报价/时效、预算消耗），产出大促联动方案；不得索取域内私有数据（如成本价）。"),
    _agent("factory-erp-agent", "工厂 ERP 代理", "跨组织供应链协同工厂域：只暴露产能/交期",
           "你是工厂 ERP 域代理，数据主权独立，只对外暴露产能与交期，拒绝成本价等越界字段请求。"),
    _agent("logistics-agent-federation", "物流域代理", "跨组织供应链协同物流域：只暴露报价/时效",
           "你是物流域代理，数据主权独立，只对外暴露报价与时效，拒绝越界字段请求。"),
    _agent("ads-platform-agent", "广告平台域代理", "跨组织供应链协同广告域：只暴露预算消耗",
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
        "name": "跨境新品上架统筹",
        "description": "Supervisor-Worker：Leader 运行时自动生成并派活汇总，4 专家独立上下文。模式实现语义见 app/ai/team/org_patterns/listing_launch.py；UI 会话统一走 Leader 派活。",
        "category": CATEGORY,
        "mode": "supervisor",
        "members": ["xborder-product-picker", "xborder-listing-writer",
                     "xborder-compliance-checker", "xborder-pricing-analyst"],
        "roles": {"xborder-product-picker": "选品分析师", "xborder-listing-writer": "多语种 Listing 撰写",
                   "xborder-compliance-checker": "合规审查员", "xborder-pricing-analyst": "定价分析师"},
        "edges": [],
        "sample_input": "评估『便携咖啡机』上架日本亚马逊，给出 GO/NO-GO 与售价",
    },
    {
        "team_code": "xborder-hierarchy-expansion",
        "name": "海外市场拓展",
        "description": "层级式：总监→渠道负责人→Worker 两层（表结构无层级字段，6 角色平铺，层级见角色描述）。真实层级语义由 app/ai/team/org_patterns/market_expansion.py 保证。",
        "category": CATEGORY,
        "mode": "supervisor",
        "members": ["xborder-region-director", "xborder-sea-leader", "xborder-eu-leader",
                     "xborder-sea-researcher", "xborder-sea-writer", "xborder-eu-researcher"],
        "roles": {"xborder-region-director": "区域拓展总监", "xborder-sea-leader": "东南亚渠道负责人",
                   "xborder-eu-leader": "欧洲渠道负责人", "xborder-sea-researcher": "东南亚市场调研",
                   "xborder-sea-writer": "东南亚本地化文案", "xborder-eu-researcher": "欧洲市场调研"},
        "edges": [],
        "sample_input": "为便携咖啡机制定东南亚与欧洲市场渠道拓展方案",
    },
    {
        "team_code": "xborder-pipeline-inquiry",
        "name": "外贸询盘报价",
        "description": "流水线：询盘解析→报价（带验收重试≤3）→合同条款→跟单催单。模式实现语义见 app/ai/team/org_patterns/inquiry_pipeline.py（原生 agentscope.sop）。",
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
        "name": "跨语种客服交接",
        "description": "交接式：控制权一次性交出，只传 <handover>摘要</handover> 不传全量对话，max_hops=3。交接语义由 app/ai/team/org_patterns/support_handoff.py 保证。",
        "category": CATEGORY,
        "mode": "sequential",
        "members": ["xborder-presale-es", "xborder-logistics-en", "xborder-returns-zh"],
        "roles": {"xborder-presale-es": "西语售前客服", "xborder-logistics-en": "英语物流专员",
                   "xborder-returns-zh": "中文退换货专员"},
        "edges": _chain(["xborder-presale-es", "xborder-logistics-en", "xborder-returns-zh"]),
        "sample_input": "Hola, mi pedido ORD-2026-1120 lleva 10 días sin actualización de envío, quiero un reembolso.",
    },
    {
        "team_code": "xborder-mesh-multiplatform",
        "name": "多平台运营协同",
        "description": "对等网状：无中心节点，共享消息板全员可见，轮转发言预算 16 条/max_rounds=4。语义见 app/ai/team/org_patterns/multiplatform_ops.py。",
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
        "name": "广告策略评审",
        "description": "辩论/群聊：正反方互见全量辩论记录，裁判每轮结构化裁决，max_rounds=3 硬终局。语义见 app/ai/team/org_patterns/ad_review_debate.py。",
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
        "name": "多渠道预算测算",
        "description": "并行聚合：三渠道无依赖真并发（asyncio.gather+wait_for），单路失败占位继续，聚合师汇总。语义见 app/ai/team/org_patterns/budget_parallel.py。",
        "category": CATEGORY,
        "mode": "parallel",
        "members": ["xborder-roi-google", "xborder-roi-meta", "xborder-roi-tiktok", "xborder-budget-aggregator"],
        "roles": {"xborder-roi-google": "Google 渠道测算", "xborder-roi-meta": "Meta 渠道测算",
                   "xborder-roi-tiktok": "TikTok 渠道测算", "xborder-budget-aggregator": "预算聚合师"},
        "edges": _parallel_fanin(["xborder-roi-google", "xborder-roi-meta", "xborder-roi-tiktok"],
                                  "xborder-budget-aggregator"),
        "sample_input": "黑五 $10000 预算，三渠道 ROI 测算与分配",
    },
    {
        "team_code": "xborder-federated-supplychain",
        "name": "跨组织供应链协同",
        "description": "联邦式：协调者经白名单网关扇出 3 信任域（工厂/物流/广告），越界字段拒绝，只交换最小必要结果。语义见 app/ai/team/org_patterns/supply_chain_federation.py。",
        "category": CATEGORY,
        "mode": "dag",
        "members": ["xborder-brand-coordinator", "xborder-factory-erp-agent",
                     "xborder-logistics-agent-federation", "xborder-ads-platform-agent"],
        "roles": {"xborder-brand-coordinator": "品牌协调者", "xborder-factory-erp-agent": "工厂 ERP 代理",
                   "xborder-logistics-agent-federation": "物流域代理", "xborder-ads-platform-agent": "广告平台域代理"},
        "edges": _fanout("xborder-brand-coordinator",
                          ["xborder-factory-erp-agent", "xborder-logistics-agent-federation",
                           "xborder-ads-platform-agent"]),
        "sample_input": "圣诞季：确认工厂产能、锁物流舱位、联动广告预算",
    },
]