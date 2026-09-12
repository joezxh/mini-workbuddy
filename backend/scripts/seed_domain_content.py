"""三领域内容种子脚本（幂等）：技能全量安装 + Agent 范例 + AgentTeam 范例 + MCP 广场模板。

用法（需先启动后端 uvicorn）：
  python scripts/seed_domain_content.py --domain all [--dry-run] [--skip-skills] [--base-url http://127.0.0.1:8000] [--username admin] [--password xxx]
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

import requests

BASE = "http://127.0.0.1:8000"
TOKEN = ""
TIMEOUT = 120


def api(method: str, path: str, ok_codes=(200,), **kw):
    headers = kw.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = requests.request(method, BASE + path, headers=headers, timeout=TIMEOUT, **kw)
    if r.status_code not in ok_codes:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else None


# ── 领域定义 ────────────────────────────────────────────────────────────────
SKILL_REPOS = {
    "finance": ("官方·金融证券技能库", r"d:\projects\miniworkbuddy-skills\ai-berkshire"),
    "research": ("官方·科研技能库", r"d:\projects\miniworkbuddy-skills\scientific-agent-skills"),
    "marketing": ("官方·市场营销技能库", r"d:\projects\miniworkbuddy-skills\marketingskills"),
}

DOMAIN_LABEL = {"finance": "金融证券", "research": "科研", "marketing": "市场营销"}


@dataclass
class AgentSpec:
    agent_code: str
    name: str
    domain: str
    skill_keywords: list  # 按序匹配安装后的技能 package_id/name
    system_prompt: str
    description: str


AGENTS = [
    AgentSpec("fin-value-analyst", "价值分析专家", "finance", ["value", "intrinsic", "moat", "buffett", "valuation"],
              "你是一名价值投资分析师，擅长基本面分析、护城河评估与内在价值估算。基于给定的技能方法论与上下文，输出结构化的投资研究结论，并明确列出假设与风险。",
              "绑定金融证券技能的价值分析 Agent 范例"),
    AgentSpec("fin-risk-portfolio", "组合风控专家", "finance", ["risk", "portfolio", "allocation", "position"],
              "你是一名组合风控专家，擅长仓位管理、回撤控制与风险因子识别。基于给定上下文输出风险评估与调仓建议，风格保守严谨。",
              "绑定金融证券技能的组合风控 Agent 范例"),
    AgentSpec("fin-market-news", "行情资讯解读", "finance", ["news", "market", "macro", "sentiment"],
              "你是一名市场资讯解读分析师，擅长把行情动态与宏观新闻转化为可操作的投资要点。输出要点清单与影响评估。",
              "绑定金融证券技能的行情解读 Agent 范例"),
    AgentSpec("res-literature-review", "文献综述助手", "research", ["review", "survey", "paper", "literature", "search"],
              "你是一名科研文献综述助手，擅长检索、筛选与归纳学术文献，输出带引用的综述报告。",
              "绑定科研技能的文献综述 Agent 范例"),
    AgentSpec("res-experiment-design", "实验设计助手", "research", ["experiment", "design", "method", "protocol"],
              "你是一名实验设计助手，擅长设计可复现的实验方案与对照分析，输出实验步骤、变量与预期指标。",
              "绑定科研技能的实验设计 Agent 范例"),
    AgentSpec("res-data-analysis", "数据分析助手", "research", ["data", "analysis", "statistic", "plot"],
              "你是一名科研数据分析助手，擅长统计检验、数据清洗与可视化建议，输出分析结论与图表建议。",
              "绑定科研技能的数据分析 Agent 范例"),
    AgentSpec("mkt-content-creator", "内容创作专家", "marketing", ["content", "copy", "writing", "social"],
              "你是一名营销内容创作专家，擅长面向目标人群撰写多平台文案。输出标题、正文与发布建议。",
              "绑定市场营销技能的内容创作 Agent 范例"),
    AgentSpec("mkt-competitor-watch", "竞品监测专家", "marketing", ["competitor", "market", "research", "analysis"],
              "你是一名竞品监测专家，擅长收集竞品动态并输出竞争格局分析。",
              "绑定市场营销技能的竞品监测 Agent 范例"),
    AgentSpec("mkt-campaign-optimizer", "投放优化专家", "marketing", ["campaign", "ads", "growth", "optimize"],
              "你是一名投放优化专家，擅长渠道策略与投放效果优化，输出可执行的投放方案。",
              "绑定市场营销技能的投放优化 Agent 范例"),
]

TEAMS = [
    {
        "team_code": "fin-research-team",
        "name": "投研报告团队",
        "domain": "finance",
        "description": "金融证券多 Agent 协作范例：行情解读 → 价值分析 → 组合风控，产出完整投研结论",
        "category": "金融证券",
        "members": ["fin-market-news", "fin-value-analyst", "fin-risk-portfolio"],
        "roles": {"fin-market-news": "行情资讯员", "fin-value-analyst": "价值分析师", "fin-risk-portfolio": "风控审核员"},
    },
    {
        "team_code": "res-review-team",
        "name": "文献综述团队",
        "domain": "research",
        "description": "科研多 Agent 协作范例：文献综述 → 实验设计 → 数据分析",
        "category": "科研",
        "members": ["res-literature-review", "res-experiment-design", "res-data-analysis"],
        "roles": {"res-literature-review": "文献调研员", "res-experiment-design": "方案设计师", "res-data-analysis": "数据分析员"},
    },
    {
        "team_code": "mkt-campaign-team",
        "name": "营销活动团队",
        "domain": "marketing",
        "description": "市场营销多 Agent 协作范例：内容创作 → 竞品监测 → 投放优化",
        "category": "市场营销",
        "members": ["mkt-content-creator", "mkt-competitor-watch", "mkt-campaign-optimizer"],
        "roles": {"mkt-content-creator": "内容策划", "mkt-competitor-watch": "竞品分析师", "mkt-campaign-optimizer": "投放优化师"},
    },
]

# MCP 广场模板（category 与服务类型以真实公开项目为准；service_url 可被接入时覆盖）
MCP_TEMPLATES = [
    # ── 金融证券 finance ──
    dict(name="Polygon.io 行情数据", category="finance", service_type="http", platform="polygon",
         description="美股行情、K 线与公司基本面数据（Polygon.io 官方 MCP Server）",
         service_url="https://mcp.polygon.io/sse", capabilities=["quotes", "aggregates", "ticker-news"],
         icon="chart-line"),
    dict(name="Alpha Vantage 市场数据", category="finance", service_type="http", platform="alphavantage",
         description="股票/外汇/加密货币历史与实时数据（Alpha Vantage MCP）",
         service_url="https://mcp.alphavantage.co/mcp", capabilities=["time-series", "fundamentals", "fx"],
         icon="chart-area"),
    dict(name="Financial Modeling Prep 基本面", category="finance", service_type="http", platform="fmp",
         description="财报、估值与财务报表数据（FMP MCP Server）",
         service_url="https://mcp.financialmodelingprep.com/mcp", capabilities=["income-statement", "balance-sheet", "ratios"],
         icon="file-invoice-dollar"),
    dict(name="CoinGecko 加密行情", category="finance", service_type="http", platform="coingecko",
         description="加密货币价格与市场数据（CoinGecko 公共 MCP，无需密钥即可查询）",
         service_url="https://mcp.api.coingecko.com/mcp", capabilities=["price", "market-chart", "trending"],
         icon="bitcoin"),
    # ── 科研研究 research ──
    dict(name="arXiv 论文检索", category="research", service_type="http", platform="arxiv",
         description="arXiv 预印本检索与摘要获取（社区 arXiv MCP Server）",
         service_url="https://mcp.arxiv.org/mcp", capabilities=["search-papers", "get-abstract"],
         icon="book"),
    dict(name="Semantic Scholar 学术搜索", category="research", service_type="http", platform="semanticscholar",
         description="学术论文语义检索与引用图谱（Semantic Scholar MCP）",
         service_url="https://mcp.semanticscholar.org/mcp", capabilities=["paper-search", "citations", "recommendations"],
         icon="graduation-cap"),
    dict(name="PubMed 医学文献", category="research", service_type="http", platform="pubmed",
         description="生物医学文献检索（PubMed/NCBI MCP Server）",
         service_url="https://mcp.ncbi.nlm.nih.gov/mcp", capabilities=["pubmed-search", "abstract"],
         icon="stethoscope"),
    dict(name="Hugging Face 模型广场", category="research", service_type="http", platform="huggingface",
         description="模型/数据集检索与模型卡信息（HF MCP Server）",
         service_url="https://huggingface.co/mcp", capabilities=["model-search", "dataset-search"],
         icon="robot"),
    # ── 市场营销 marketing ──
    dict(name="Playwright 浏览器自动化", category="marketing", service_type="http", platform="playwright",
         description="网页浏览、截图与自动化操作（Microsoft Playwright MCP，适合营销素材采集）",
         service_url="https://cdn.jsdelivr.net/npm/@playwright/mcp@latest/sse", capabilities=["browse", "screenshot", "fill-form"],
         icon="chrome"),
    dict(name="Exa AI 搜索", category="marketing", service_type="http", platform="exa",
         description="面向营销调研的语义网页搜索（Exa MCP Server）",
         service_url="https://mcp.exa.ai/mcp", capabilities=["web-search", "crawling", "similar-pages"],
         icon="search"),
    dict(name="Firecrawl 网页抓取", category="marketing", service_type="http", platform="firecrawl",
         description="站点抓取与结构化提取（Firecrawl MCP，适合内容营销素材收集）",
         service_url="https://mcp.firecrawl.dev/mcp", capabilities=["scrape", "crawl", "extract"],
         icon="fire"),
    dict(name="Mailchimp 邮件营销", category="marketing", service_type="http", platform="mailchimp",
         description="邮件列表与营销活动管理（Mailchimp MCP Server）",
         service_url="https://mcp.mailchimp.com/mcp", capabilities=["audience", "campaigns", "reports"],
         icon="mail-bulk"),
]
PREINSTALL = {  # 每域预装 1 个（模板名 → 接入态示例）
    "finance": "CoinGecko 加密行情",
    "research": "arXiv 论文检索",
    "marketing": "Exa AI 搜索",
}


# ── 步骤实现 ────────────────────────────────────────────────────────────────
def login(username: str, password: str):
    global TOKEN
    data = api("POST", "/api/v1/auth/login", json={"username": username, "password": password}, ok_codes=(200, 401, 422))
    if isinstance(data, dict):
        TOKEN = data.get("token") or data.get("access_token") or ""
        if TOKEN:
            print("✔ 登录成功")
            return
    raise SystemExit("登录失败：请用 --username/--password 提供管理员账号（或后端为免认证模式）")


def as_items(res):
    """兼容 list / {data:[]} / {items:[]} / {packages:[]} 多种返回。"""
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("data", "items", "packages", "list", "records"):
            v = res.get(k)
            if isinstance(v, list):
                return v
    return []


def existing_package_ids() -> set:
    try:
        res = api("GET", "/api/v1/ai-assistant/skills?page=1&page_size=100")
        return {it.get("package_id") for it in as_items(res) if it.get("package_id")}
    except Exception:
        return set()


def step_install_skills(domains: list, dry: bool) -> dict:
    summary = {}
    installed_ids = set()
    domain_ids: dict = {d: set() for d in domains}
    for domain in domains:
        name, url = SKILL_REPOS[domain]
        repos = api("GET", "/api/v1/ai-system/skill-hub/repos")
        lst = as_items(repos)
        repo = next((r for r in lst if r.get("url") == url), None)
        if not repo:
            if dry:
                print(f"[dry] 注册仓库 {name} ({url})")
                summary[domain] = ("dry", 0)
                continue
            repo = api("POST", "/api/v1/ai-system/skill-hub/repos",
                       json={"name": name, "url": url, "branch": "main"})
            print(f"✔ 注册仓库 {name} -> id={repo.get('id')}")
        repo_id = repo.get("id")
        if not dry:
            api("POST", f"/api/v1/ai-system/skill-hub/repos/{repo_id}/refresh")
        # 枚举技能
        skills, page = [], 1
        while True:
            res = api("GET", f"/api/v1/ai-system/skill-hub/repos/{repo_id}/skills?page={page}&page_size=50")
            batch = res.get("skills") or res.get("items") or res.get("data") or [] if isinstance(res, dict) else res
            skills.extend(batch or [])
            total = res.get("total", 0) if isinstance(res, dict) else 0
            if len(skills) >= total or not batch:
                break
            page += 1
        have = existing_package_ids()
        ok = fail = skip = 0
        for s in skills:
            sid = s.get("skill_id") or s.get("id") or s.get("name")
            pkg_id = s.get("package_id") or sid
            if pkg_id in have:
                skip += 1
                continue
            if dry:
                print(f"[dry] 安装 {domain}/{sid}")
                ok += 1
                continue
            try:
                api("POST", f"/api/v1/ai-system/skill-hub/repos/{repo_id}/skills/{sid}/install")
                ok += 1
                installed_ids.add(pkg_id)
                domain_ids.setdefault(domain, set()).add(pkg_id)
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"  ✗ 安装失败 {sid}: {e}")
        summary[domain] = ("installed", ok, skip, fail)
        print(f"✔ {DOMAIN_LABEL[domain]} 技能安装：成功 {ok} / 跳过 {skip} / 失败 {fail}")
    return {"summary": summary, "installed_ids": installed_ids, "domain_ids": domain_ids}


def pick_skill_id(domain: str, spec: AgentSpec, domain_ids: dict) -> str | None:
    kws = [k.lower() for k in spec.skill_keywords]
    have = existing_package_ids()
    # 1) 本次安装的、该域仓库下、按关键词匹配
    for pkg in sorted(domain_ids.get(domain, set())):
        if any(k in pkg.lower() for k in kws):
            return pkg
    # 2) 该域本次安装的任意技能
    d = domain_ids.get(domain, set())
    if d:
        return sorted(d)[0]
    # 3) 全库按关键词匹配
    for pkg in sorted(have):
        if any(k in pkg.lower() for k in kws):
            return pkg
    # 4) 兜底
    return sorted(have)[0] if have else None


def step_create_agents(domains: list, dry: bool, domain_ids: dict):
    created = skipped = 0
    for spec in AGENTS:
        if spec.domain not in domains:
            continue
        res = api("GET", f"/api/v1/agent-config?page=1&page_size=100&keyword={spec.agent_code}")
        items = as_items(res)
        if any((it.get("agent_code") == spec.agent_code) for it in items):
            skipped += 1
            continue
        skill_id = pick_skill_id(spec.domain, spec, domain_ids)
        if not skill_id:
            print(f"  ✗ {spec.agent_code}: 无可用技能，跳过")
            continue
        if dry:
            print(f"[dry] 创建 Agent {spec.agent_code}（技能 {skill_id}）")
            created += 1
            continue
        api("POST", "/api/v1/agent-config", json={
            "agent_code": spec.agent_code,
            "name": spec.name,
            "agent_type": "SKILL",
            "category": DOMAIN_LABEL[spec.domain],
            "execution_mode": "skill",
            "description": spec.description,
            "system_prompt": spec.system_prompt,
            "tools": {"skills": [skill_id]},
        })
        print(f"✔ 创建 Agent {spec.name}（{spec.agent_code}，技能 {skill_id}）")
        created += 1
    print(f"✔ Agent 范例：新建 {created} / 已存在 {skipped}")


def step_create_teams(domains: list, dry: bool):
    created = skipped = 0
    for team in TEAMS:
        if team["domain"] not in domains:
            continue
        res = api("GET", "/api/v1/ai-team?page=1&page_size=100")
        items = as_items(res)
        if any((it.get("team_code") == team["team_code"]) for it in items):
            skipped += 1
            continue
        # 解析成员 agent_config_id
        members, node_keys = [], []
        for code in team["members"]:
            r = api("GET", f"/api/v1/agent-config?page=1&page_size=50&keyword={code}")
            lst = r.get("data") or r.get("items") or []
            found = next((it for it in lst if it.get("agent_code") == code), None)
            if not found:
                print(f"  ✗ 团队 {team['team_code']} 缺成员 {code}，跳过团队")
                members = []
                break
            node_key = code.replace("-", "_")
            node_keys.append(node_key)
            members.append({
                "node_key": node_key,
                "agent_config_id": found["id"],
                "role_name": team["roles"][code],
            })
        if not members:
            continue
        edges = [
            {"from_node_key": "__START__", "to_node_key": node_keys[0]},
            *[{"from_node_key": node_keys[i], "to_node_key": node_keys[i + 1]} for i in range(len(node_keys) - 1)],
            {"from_node_key": node_keys[-1], "to_node_key": "__END__"},
        ]
        if dry:
            print(f"[dry] 创建团队 {team['name']}（{len(members)} 成员）")
            created += 1
            continue
        api("POST", "/api/v1/ai-team", json={
            "name": team["name"],
            "team_code": team["team_code"],
            "description": team["description"],
            "category": team["category"],
            "mode": "sequential",
            "members": members,
            "edges": edges,
        })
        print(f"✔ 创建团队 {team['name']}（{team['team_code']}，{len(members)} 成员 {len(edges)} 边）")
        created += 1
    print(f"✔ Team 范例：新建 {created} / 已存在 {skipped}")


def step_mcp_square(domains: list, dry: bool):
    created = installed = skipped = 0
    for tpl in MCP_TEMPLATES:
        domain = {"finance": "finance", "research": "research", "marketing": "marketing"}[tpl["category"]]
        if domain not in domains and tpl["category"] not in domains:
            continue
        res = api("GET", f"/api/v1/admin/ai/mcp-square/page?name={tpl['name']}&page=1&page_size=10")
        items = as_items(res)
        found = next((it for it in items if it.get("name") == tpl["name"]), None)
        if found:
            skipped += 1
            template_id = found["id"]
        else:
            if dry:
                print(f"[dry] 创建 MCP 模板 {tpl['name']}")
                created += 1
                continue
            r = api("POST", "/api/v1/admin/ai/mcp-square/create", json={
                "name": tpl["name"], "icon": tpl.get("icon", "plug"), "category": tpl["category"],
                "platform": tpl["platform"], "description": tpl["description"],
                "service_type": tpl["service_type"], "service_url": tpl["service_url"],
                "capabilities": tpl["capabilities"], "status": 1,
                "default_client_config": {"client_type": "http", "mcp_type": "tool"},
            })
            template_id = r.get("id")
            print(f"✔ 创建 MCP 模板 {tpl['name']} -> id={template_id}")
            created += 1
        # 预装
        if tpl["name"] == PREINSTALL.get(tpl["category"]) and not dry:
            try:
                api("POST", "/api/v1/admin/ai/mcp-square/install", json={"template_id": template_id})
                print(f"  ✔ 预装接入态：{tpl['name']}")
                installed += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ 预装失败 {tpl['name']}: {e}")
    print(f"✔ MCP 广场：新建模板 {created} / 已存在 {skipped} / 预装 {installed}")


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="all", choices=["finance", "research", "marketing", "all"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-skills", action="store_true")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    args = ap.parse_args()
    BASE = args.base_url.rstrip("/")
    domains = ["finance", "research", "marketing"] if args.domain == "all" else [args.domain]

    print(f"== 三领域内容种子（domain={args.domain} dry={args.dry_run}）==")
    try:
        login(args.username, args.password)
    except SystemExit as e:
        print(e)
        print("提示：若后端为免认证模式，可忽略登录失败重跑（接口会返回 401 时脚本会中止）")
        raise

    if not args.skip_skills:
        res = step_install_skills(domains, args.dry_run)
        domain_ids = res["domain_ids"]
    else:
        print("-- 跳过技能安装")
        domain_ids = {}
    step_create_agents(domains, args.dry_run, domain_ids)
    step_create_teams(domains, args.dry_run)
    step_mcp_square(domains, args.dry_run)
    print("== 完成 ==")


if __name__ == "__main__":
    main()
