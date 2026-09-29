"""金融 / 交易 / 投资研究类 SOP 模板。

参照工程：
- TradingAgents-CN（多 Agent 交易框架：分析师 → 多空辩论 → 研究经理 → 交易 → 风控）
- buffett-skills（巴菲特价值投资：生意质量 / 护城河 / 管理层 / 所有者收益 / 安全边际）
- UZI-Skill（游资短线：情绪周期 / 题材 / 龙头 / 买卖点 / 仓位风控）
- FinceptTerminal（金融终端：行情、财报、宏观数据取数与解读）

设计约定：``description`` 只写**终点交付物**（可验收），不写实现路线。
涉及真金白银与重大判断的步骤默认 ``verifier_type="human"`` 交人工拍板。
"""
from __future__ import annotations

from ..schemas import SOPDefinition, SOPStepDef
from .spec import SOPTemplateSpec

# ── 1. 股票多 Agent 综合分析 ────────────────────────────────────────────────

STOCK_MULTI_AGENT_ANALYSIS = SOPTemplateSpec(
    id="stock_multi_agent_analysis",
    name="股票多Agent综合分析",
    description="技术/基本面/情绪/消息四维分析 → 多空辩论 → 研究经理裁决 → 风控审查",
    tags=["金融", "股票", "交易", "多Agent", "投研"],
    builtin=False,
    definition=SOPDefinition(
        name="股票多Agent综合分析",
        description="给出含多空双方论证、经风控审查的个股交易结论",
        source="template",
        steps=[
            SOPStepDef(
                subject="行情与技术面分析",
                description="给出趋势、关键价位、量能与常用技术指标的技术面结论",
                executor_agent="market_analyst",
                verifier_type="ai",
                group_id="analyst",
            ),
            SOPStepDef(
                subject="基本面分析",
                description="给出盈利能力、成长性、财务质量与估值水平的基本面结论",
                executor_agent="fundamentals_analyst",
                verifier_type="ai",
                group_id="analyst",
            ),
            SOPStepDef(
                subject="情绪面分析",
                description="给出资金流向、换手、市场情绪与拥挤度的情绪面结论",
                executor_agent="sentiment_analyst",
                verifier_type="ai",
                group_id="analyst",
            ),
            SOPStepDef(
                subject="消息面分析",
                description="给出近期公告、新闻与政策事件的梳理及其影响判断",
                executor_agent="news_analyst",
                verifier_type="ai",
                group_id="analyst",
            ),
            SOPStepDef(
                subject="多空辩论",
                description="产出多头与空方各自最有力的论证及互相反驳，形成交锋记录",
                executor_agent="bull_bear_debater",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="研究经理裁决",
                description="基于四维分析与辩论给出明确的方向判断与置信度",
                executor_agent="research_manager",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="交易决策",
                description="给出具体的买卖方向、价位区间、仓位与时间框架",
                executor_agent="trader",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="风控审查",
                description="给出该交易的风险点、最大回撤预估与否决/放行结论",
                executor_agent="risk_manager",
                verifier_type="human",
                max_attempts=2,
            ),
            SOPStepDef(
                subject="组合与仓位建议",
                description="给出在现有组合约束下的最终仓位建议与执行计划",
                executor_agent="portfolio_manager",
                verifier_type="none",
                artifact_key="tradeDecision",
            ),
        ],
    ),
)

# ── 2. 巴菲特价值投资分析 ───────────────────────────────────────────────────

BUFFETT_VALUE_INVESTING = SOPTemplateSpec(
    id="buffett_value_investing",
    name="巴菲特价值投资分析",
    description="生意质量 → 护城河 → 管理层 → 所有者收益 → 安全边际估值的价值投资框架",
    tags=["金融", "价值投资", "巴菲特", "基本面", "长期"],
    builtin=False,
    definition=SOPDefinition(
        name="巴菲特价值投资分析",
        description="给出是否符合价值投资标准、以及是否值得长期持有的明确结论",
        source="template",
        steps=[
            SOPStepDef(
                subject="生意质量与能力圈",
                description="说清公司靠什么赚钱、生意是否简单可理解、是否落在能力圈内",
                executor_agent="business_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="经济护城河",
                description="判定护城河来源与强弱，并给出可持续性的证据",
                executor_agent="moat_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="管理层与资本配置",
                description="给出管理层诚信、经营能力与历史资本配置成绩的评价",
                executor_agent="management_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="财务与所有者收益",
                description="给出 ROE、利润率、自由现金流与所有者收益的量化结论",
                executor_agent="financial_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="估值与安全边际",
                description="给出内在价值区间、当前价格对应的安全边际与买入价阈值",
                executor_agent="valuation_analyst",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=4,
            ),
            SOPStepDef(
                subject="投资决策",
                description="给出买入/观望/回避的明确决定、理由与跟踪指标",
                executor_agent="investment_committee",
                verifier_type="human",
                max_attempts=2,
                artifact_key="investmentMemo",
            ),
        ],
    ),
)

# ── 3. A股游资龙头战法 ──────────────────────────────────────────────────────

UZI_DRAGON_HEAD = SOPTemplateSpec(
    id="uzi_dragon_head",
    name="A股游资龙头战法",
    description="情绪周期 → 题材识别 → 龙头筛选 → 买卖点 → 仓位风控的短线打法",
    tags=["金融", "A股", "游资", "短线", "龙头", "打板"],
    builtin=False,
    definition=SOPDefinition(
        name="A股游资龙头战法",
        description="给出当前情绪周期下的龙头标的与可执行的买卖点、仓位方案",
        source="template",
        steps=[
            SOPStepDef(
                subject="情绪周期判定",
                description="判定当前处于冰点/修复/发酵/高潮/退潮哪个阶段及依据",
                executor_agent="emotion_cycle_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="题材与热点识别",
                description="列出当前主流题材、持续性判断与题材梯队结构",
                executor_agent="theme_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="龙头标的筛选",
                description="给出龙头/中军/补涨的候选标的及各自辨识理由",
                executor_agent="dragon_picker",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="买卖点与打板策略",
                description="给出具体的介入条件、买点价位、卖点与止损位",
                executor_agent="timing_strategist",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="仓位与风控",
                description="给出分仓方案、单笔最大亏损与强制离场纪律",
                executor_agent="risk_manager",
                verifier_type="human",
                max_attempts=2,
                artifact_key="tradePlan",
            ),
        ],
    ),
)

# ── 4. 对冲基金日级交易流程 ─────────────────────────────────────────────────

HEDGE_FUND_DAILY = SOPTemplateSpec(
    id="hedge_fund_daily",
    name="对冲基金日级交易流程",
    description="盘前宏观 → 敞口盘点 → 信号生成 → 组合对冲 → 执行 → 盘后归因",
    tags=["金融", "对冲基金", "交易", "组合", "风控"],
    builtin=False,
    definition=SOPDefinition(
        name="对冲基金日级交易流程",
        description="产出当日可执行交易指令与盘后归因报告",
        source="template",
        steps=[
            SOPStepDef(
                subject="盘前宏观与隔夜",
                description="给出隔夜外盘、重要数据与事件对当日交易的含义",
                executor_agent="macro_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="持仓风险敞口盘点",
                description="给出当前组合的行业/因子敞口、集中度与风险限额使用情况",
                executor_agent="risk_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="交易信号生成",
                description="给出当日候选信号清单，含方向、强度与失效条件",
                executor_agent="signal_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="组合构建与对冲",
                description="给出目标权重、对冲工具与预期组合风险",
                executor_agent="portfolio_manager",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="执行与成交",
                description="给出分拆算法、限价区间与执行完毕的成交汇总",
                executor_agent="execution_trader",
                verifier_type="human",
                max_attempts=2,
            ),
            SOPStepDef(
                subject="盘后复盘与归因",
                description="给出当日盈亏归因、信号有效性评价与次日关注点",
                executor_agent="performance_analyst",
                verifier_type="none",
                artifact_key="dailyReview",
            ),
        ],
    ),
)

# ── 5. 个股深度分析 ────────────────────────────────────────────────────────

STOCK_DEEP_DIVE = SOPTemplateSpec(
    id="stock_deep_dive",
    name="个股深度分析",
    description="业务拆解 → 行业竞争 → 财务质量 → 估值 → 风险清单 → 结论",
    tags=["金融", "个股", "深度研究", "基本面"],
    builtin=False,
    definition=SOPDefinition(
        name="个股深度分析",
        description="产出一份可据以决策的个股深度分析报告",
        source="template",
        steps=[
            SOPStepDef(
                subject="公司与业务拆解",
                description="给出公司业务构成、收入结构与核心驱动因素",
                executor_agent="business_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="行业与竞争格局",
                description="给出行业空间、增速、竞争格局与公司所处位置",
                executor_agent="industry_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="财务质量",
                description="给出成长性、盈利质量、现金流与资产负债健康状况结论",
                executor_agent="financial_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="估值分析",
                description="给出多种估值方法下的合理价值区间与当前位置",
                executor_agent="valuation_analyst",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="风险清单",
                description="列出最关键的风险项、触发信号与影响程度",
                executor_agent="risk_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="分析结论",
                description="给出明确的投资结论、关键跟踪指标与复核时点",
                executor_agent="research_manager",
                verifier_type="human",
                max_attempts=2,
                artifact_key="deepDiveReport",
            ),
        ],
    ),
)

# ── 6. 财报解读 ────────────────────────────────────────────────────────────

EARNINGS_REPORT_ANALYSIS = SOPTemplateSpec(
    id="earnings_report_analysis",
    name="财报解读",
    description="关键数据提取 → 预期差 → 业务驱动拆解 → 质量风险扫描 → 投资含义",
    tags=["金融", "财报", "基本面", "业绩"],
    builtin=False,
    definition=SOPDefinition(
        name="财报解读",
        description="产出一份说清业绩成色与预期差的财报解读",
        source="template",
        steps=[
            SOPStepDef(
                subject="关键数据提取",
                description="提取营收、利润、毛利率、费用率、现金流等核心数据",
                executor_agent="data_extractor",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="同比环比与预期差",
                description="给出同比/环比变化以及相对市场预期是超预期还是低于预期",
                executor_agent="financial_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="业务驱动拆解",
                description="说清业绩变化来自量、价、结构还是一次性因素",
                executor_agent="business_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="质量与风险扫描",
                description="指出应收、存货、商誉、减值等需要警惕的会计质量信号",
                executor_agent="quality_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="投资含义",
                description="给出财报对后续业绩预期与投资判断的具体影响",
                executor_agent="research_manager",
                verifier_type="human",
                max_attempts=2,
                artifact_key="earningsNote",
            ),
        ],
    ),
)

# ── 7. 宏观与市场策略 ──────────────────────────────────────────────────────

MACRO_MARKET_STRATEGY = SOPTemplateSpec(
    id="macro_market_strategy",
    name="宏观与市场策略",
    description="宏观指标 → 政策流动性 → 大类资产联动 → 情景假设 → 配置建议",
    tags=["金融", "宏观", "策略", "资产配置"],
    builtin=False,
    definition=SOPDefinition(
        name="宏观与市场策略",
        description="产出当前宏观环境下的大类资产配置建议",
        source="template",
        steps=[
            SOPStepDef(
                subject="宏观指标梳理",
                description="给出增长、通胀、就业、信用等核心指标的当前读数与趋势",
                executor_agent="macro_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="政策与流动性",
                description="给出货币、财政与监管取向及流动性环境的判断",
                executor_agent="policy_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="大类资产联动",
                description="给出股债商品汇率之间的联动关系与当前主导变量",
                executor_agent="cross_asset_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="情景与假设",
                description="给出基准/乐观/悲观三档情景、触发条件与概率估计",
                executor_agent="strategy_analyst",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="配置建议",
                description="给出各大类资产的目标比例与调整动作建议",
                executor_agent="allocation_committee",
                verifier_type="human",
                max_attempts=2,
                artifact_key="allocationPlan",
            ),
        ],
    ),
)

FINANCE_TEMPLATES = [
    STOCK_MULTI_AGENT_ANALYSIS,
    BUFFETT_VALUE_INVESTING,
    UZI_DRAGON_HEAD,
    HEDGE_FUND_DAILY,
    STOCK_DEEP_DIVE,
    EARNINGS_REPORT_ANALYSIS,
    MACRO_MARKET_STRATEGY,
]
