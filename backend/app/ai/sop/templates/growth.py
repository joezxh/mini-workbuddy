"""市场营销 / 自媒体运营类 SOP 模板。

参照工程：
- marketingskills（市场分析：市场规模、受众、竞品、定位、渠道、度量）
- Easel（自媒体运营：定位、选题、内容创作、发布分发、数据复盘迭代）

设计约定：``description`` 只写**终点交付物**，不写实现路线。
内容创作类步骤天然是"写→审→改"，统一声明 ``loop="goal"`` 走微循环。
"""
from __future__ import annotations

from ..schemas import SOPDefinition, SOPStepDef
from .spec import SOPTemplateSpec

# ── 8. 市场营销分析 ─────────────────────────────────────────────────────────

MARKETING_ANALYSIS = SOPTemplateSpec(
    id="marketing_analysis",
    name="市场营销分析",
    description="市场规模 → 受众画像 → 竞品差异化 → 定位 → 渠道 → 度量的完整营销分析",
    tags=["营销", "市场分析", "增长", "marketing"],
    builtin=False,
    definition=SOPDefinition(
        name="市场营销分析",
        description="产出一份含定位、渠道与度量指标的市场营销方案",
        source="template",
        steps=[
            SOPStepDef(
                subject="市场与规模",
                description="给出目标市场的规模、增速与主要细分结构",
                executor_agent="marketing_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="目标受众与画像",
                description="给出核心受众画像、决策链与关键触达场景",
                executor_agent="audience_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="竞品与差异化",
                description="给出主要竞品对比与自身可立足的差异化空间",
                executor_agent="competitor_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="定位与信息屋",
                description="给出定位陈述与分层信息屋（核心主张/支撑点/证明）",
                executor_agent="positioning_strategist",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="渠道与触达",
                description="给出渠道优先级、各渠道打法与预算分配建议",
                executor_agent="channel_planner",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="度量与KPI",
                description="给出可追踪的 KPI 体系、目标值与复盘节奏",
                executor_agent="growth_analyst",
                verifier_type="none",
                artifact_key="marketingPlan",
            ),
        ],
    ),
)

# ── 9. 竞品分析 ────────────────────────────────────────────────────────────

COMPETITOR_ANALYSIS = SOPTemplateSpec(
    id="competitor_analysis",
    name="竞品分析",
    description="竞品识别分层 → 功能对标 → 定价商业模式 → 营销渠道 → 机会点",
    tags=["营销", "竞品", "竞争分析"],
    builtin=False,
    definition=SOPDefinition(
        name="竞品分析",
        description="产出一份可直接用于决策的竞品分析报告",
        source="template",
        steps=[
            SOPStepDef(
                subject="竞品识别与分层",
                description="给出直接、间接、替代三类竞品清单与分层优先级",
                executor_agent="competitor_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="产品功能对标",
                description="给出功能矩阵对比与各自短板、独有能力",
                executor_agent="product_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="定价与商业模式",
                description="给出各家定价结构、商业模式与目标客群差异",
                executor_agent="pricing_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="营销与渠道",
                description="给出竞品的内容打法、渠道布局与获客方式",
                executor_agent="channel_planner",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="优劣势与机会点",
                description="给出我方相对优劣势结论与可切入的机会点排序",
                executor_agent="strategy_analyst",
                verifier_type="none",
                artifact_key="competitorReport",
            ),
        ],
    ),
)

# ── 10. ICP与品牌定位 ──────────────────────────────────────────────────────

ICP_POSITIONING = SOPTemplateSpec(
    id="icp_positioning",
    name="ICP与品牌定位",
    description="客户拆解 → 痛点JTBD → ICP定义与优先级 → 定位陈述与差异化",
    tags=["营销", "定位", "ICP", "品牌"],
    builtin=False,
    definition=SOPDefinition(
        name="ICP与品牌定位",
        description="产出明确的 ICP 定义与可对外使用的定位陈述",
        source="template",
        steps=[
            SOPStepDef(
                subject="现有客户拆解",
                description="给出成交客户的行业、规模、角色分布与共性特征",
                executor_agent="audience_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="痛点与Jobs-to-be-done",
                description="给出客户正在「雇佣」产品完成的任务与未被满足的痛点",
                executor_agent="research_analyst",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="ICP定义与优先级",
                description="给出可量化的 ICP 定义、分层与优先攻占顺序",
                executor_agent="positioning_strategist",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=3,
            ),
            SOPStepDef(
                subject="定位陈述与差异化",
                description="给出定位陈述、差异化主张与目标客群选择",
                executor_agent="positioning_strategist",
                verifier_type="none",
                artifact_key="positioningStatement",
            ),
        ],
    ),
)

# ── 11. 自媒体内容运营 ─────────────────────────────────────────────────────

SELFMEDIA_CONTENT_OPS = SOPTemplateSpec(
    id="selfmedia_content_ops",
    name="自媒体内容运营",
    description="账号定位 → 选题库 → 内容日历 → 创作 → 发布分发 → 数据复盘",
    tags=["自媒体", "运营", "内容", "增长"],
    builtin=False,
    definition=SOPDefinition(
        name="自媒体内容运营",
        description="产出可执行的内容日历与首批成稿内容",
        source="template",
        steps=[
            SOPStepDef(
                subject="账号定位与人设",
                description="给出账号定位、人设标签与内容边界",
                executor_agent="content_strategist",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="选题库搭建",
                description="给出不少于 15 个选题及各自目标与受众价值",
                executor_agent="topic_researcher",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="内容日历排期",
                description="给出按周排布的内容日历，含频次、形式与平台",
                executor_agent="content_strategist",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="内容创作",
                description="产出达到可发布质量的完整内容（标题/正文或脚本/封面文案）",
                executor_agent="script_writer",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=4,
            ),
            SOPStepDef(
                subject="发布与分发",
                description="给出发布时间、平台适配版本与冷启动分发动作",
                executor_agent="distribution_specialist",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="数据复盘与迭代",
                description="给出核心指标复盘结论与下一轮内容调整建议",
                executor_agent="data_analyst",
                verifier_type="none",
                artifact_key="contentCalendar",
            ),
        ],
    ),
)

# ── 12. 爆款选题与脚本策划 ─────────────────────────────────────────────────

SELFMEDIA_TOPIC_PLANNING = SOPTemplateSpec(
    id="selfmedia_topic_planning",
    name="爆款选题与脚本策划",
    description="热点洞察 → 选题评分 → 标题钩子打磨 → 脚本大纲 → 发布建议",
    tags=["自媒体", "选题", "脚本", "爆款"],
    builtin=False,
    definition=SOPDefinition(
        name="爆款选题与脚本策划",
        description="产出高潜力选题及可直接拍摄/发布的分镜脚本",
        source="template",
        steps=[
            SOPStepDef(
                subject="热点与需求洞察",
                description="给出当前热点、搜索需求与受众情绪的洞察清单",
                executor_agent="topic_researcher",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="选题筛选与评分",
                description="给出候选选题按潜力/差异化/可执行性的评分与排序",
                executor_agent="content_strategist",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="标题与钩子设计",
                description="给出多组标题与前 3 秒钩子，并说明推荐理由",
                executor_agent="copywriter",
                verifier_type="ai",
                loop="goal",
                goal_max_iters=4,
            ),
            SOPStepDef(
                subject="脚本与大纲产出",
                description="给出完整分镜脚本或内容大纲，含节奏与转场设计",
                executor_agent="script_writer",
                verifier_type="ai",
            ),
            SOPStepDef(
                subject="发布建议",
                description="给出平台选择、发布时机与配套话题/标签建议",
                executor_agent="distribution_specialist",
                verifier_type="none",
                artifact_key="topicPlan",
            ),
        ],
    ),
)

GROWTH_TEMPLATES = [
    MARKETING_ANALYSIS,
    COMPETITOR_ANALYSIS,
    ICP_POSITIONING,
    SELFMEDIA_CONTENT_OPS,
    SELFMEDIA_TOPIC_PLANNING,
]
