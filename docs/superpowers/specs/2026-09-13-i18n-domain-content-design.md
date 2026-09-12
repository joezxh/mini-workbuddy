# 多语言国际化 + 三领域内容初始化（技能/Agent/团队/MCP）设计

> 日期：2026-09-13
> 状态：已获用户批准（i18n=全部管理页分批；技能=全量安装；MCP=模板+预装示例；Seed=幂等脚本）

## 1. 背景与目标

五项需求，拆解为五个可独立交付的子项目：

| 子项目 | 内容 | 依赖 |
|---|---|---|
| P1 | 前端 i18n 覆盖**全部管理页**（zh-CN/zh-TW/en-US/ja-JP），分批 | 无 |
| P2 | 官方技能批量安装（金融证券/科研/市场营销三域，全量） | 无 |
| P3 | Agent Management 三域范例（共 9 个），绑定官方技能 | P2 |
| P4 | AgentTeam 三域团队范例（共 3 个） | P3 |
| P5 | MCP 广场三域模板（12~15 个）+ 每域预装 1 个 | 无 |

## 2. 决策记录

| 决策点 | 结论 |
|---|---|
| i18n 范围 | 全部管理页（非仅四模块），分 5 批 |
| i18n 策略 | 方案 A：语义 key + 模块命名空间，沿用现有 `t()` 风格 |
| 技能安装 | 全量安装，走 SkillHub git 适配器官方链路（本地路径作 repo URL） |
| MCP 广场 | 模板 12~15 个 + 每域预装 1 个接入态 |
| Seed 交付 | 幂等脚本 `backend/scripts/seed_domain_content.py`，调官方 API，支持 `--dry-run`/`--domain`/`--skip-skills` |
| 飞书连接器 app_secret | 不动（OAuth2 协议必需，与搜索密钥无关） |

## 3. P1 i18n 设计

### 3.1 现状

- vue-i18n `legacy:false`，四语言包 `frontend/src/i18n/locales/{zh-CN,zh-TW,en-US,ja-JP}.ts`
- 语言切换入口已有（`AppHeader.vue` 顶栏 + 登录页），偏好存 `localStorage['app-locale']`，`dayjs.locale` 已同步
- 新增工作 = 文案提取，无需动基建

### 3.2 key 命名规范

按模块建命名空间，成员用 camelCase，与现有 `skillHub.*` 风格一致：

`webSearch.*` / `toolMgmt.*` / `mcpSquare.*` / `apiKeyMgmt.*` / `skillMgmt.*` / `agentMgmt.*` / `teamMgmt.*` / `dashboard.*` / `sysMgmt.*` / `kbMgmt.*` / `wikiMgmt.*` / `login.*`

### 3.3 分批计划（每批独立可验证、独立提交）

1. **批1**：`views/admin/ai/`（websearch/tool/mcp/apikey/skill 及其 components）
2. **批2**：`views/admin/agent/` + `views/admin/agent-team/`
3. **批3**：`Dashboard.vue` + `views/admin/system/`（用户/角色/菜单/租户/审计/字典/区域）
4. **批4**：`views/admin/knowledge/` + `views/admin/llm-wiki/` + `views/kms/wiki/`
5. **批5**：全局骨架（登录/顶栏/侧栏）key 校验补齐；运行 key 对齐检查脚本保证四语言包 key 集合一致

### 3.4 约束

- 动态内容（后端返回的名称/状态等）不在 i18n 范围；字典驱动的文案继续走字典表
- 每批完成后运行 `npm run build`（vue-tsc）+ 四语言包 key 集合 diff 检查
- 插值用 vue-i18n 具名插值 `{name}` 语法

## 4. P2 官方技能批量安装

### 4.1 仓库注册（三域 → 三仓库）

| 领域 | 仓库本地路径 | hub 名称 |
|---|---|---|
| 金融证券分析 | `d:/projects/miniworkbuddy-skills/ai-berkshire` | 官方·金融证券技能库 |
| 科研研究 | `d:/projects/miniworkbuddy-skills/scientific-agent-skills` | 官方·科研技能库 |
| 市场营销 | `d:/projects/miniworkbuddy-skills/marketingskills` | 官方·市场营销技能库 |

git 适配器（`git_hub.py`）支持本地路径直接 clone（副本入 `data/hub_cache/<repo_id>/`）；仓库表 `ai_skill_hub_repo` 的 `url` 有 unique 约束。

### 4.2 安装流程

`POST /api/v1/ai-system/skill-hub/repos`（注册）→ `POST /repos/{id}/refresh` → `GET /repos/{id}/skills` 分页枚举 → 逐个 `POST /repos/{id}/skills/{skill_id}/install`（走 `AiSkillAdminService.import_zip` 官方链路：落盘 `backend/data/skills/<package_id>/` + 落库 `ai_skill_package`）。

失败技能记录清单继续安装，不中断；结束输出汇总（成功/失败/跳过）。

## 5. P3 Agent 范例（9 个）

`agent_type=SKILL`、`execution_mode='skill'`、`skills=["<package_id>"]`，system_prompt 按领域定制，幂等键 `agent_code`：

| 域 | agent_code | 名称 | 绑定技能 |
|---|---|---|---|
| 金融 | fin-value-analyst | 价值分析专家 | ai-berkshire 对应技能 |
| 金融 | fin-risk-portfolio | 组合风控专家 | 同上 |
| 金融 | fin-market-news | 行情资讯解读 | 同上 |
| 科研 | res-literature-review | 文献综述助手 | scientific 对应技能 |
| 科研 | res-experiment-design | 实验设计助手 | 同上 |
| 科研 | res-data-analysis | 数据分析助手 | 同上 |
| 营销 | mkt-content-creator | 内容创作专家 | marketingskills 对应技能 |
| 营销 | mkt-competitor-watch | 竞品监测专家 | 同上 |
| 营销 | mkt-campaign-optimizer | 投放优化专家 | 同上 |

具体绑定的 package_id 在 P2 安装后按实际安装结果选取（脚本内按技能名匹配规则选取，匹配不到时输出告警并跳过该绑定）。

## 6. P4 AgentTeam 范例（3 个）

幂等键 `team_code`；成员引用 `agent_config.id`（node_key + role_name），edges 定义协作拓扑：

| team_code | 名称 | 拓扑（mode=sequential） |
|---|---|---|
| fin-research-team | 投研报告团队 | 行情解读 → 价值分析 → 组合风控 → 汇总 |
| res-review-team | 文献综述团队 | 文献检索/综述 → 实验设计 → 数据分析 |
| mkt-campaign-team | 营销活动团队 | 内容创作 → 竞品监测 → 投放优化 |

成员技能通过 P3 Agent 自带 `skills` 继承（不额外 override），保证"引用+覆盖"模型示例清晰。

## 7. P5 MCP 广场模板

- 联网调研核实后录入 **12~15 个**真实 MCP 模板（每域 4~5 个），候选方向：
  - 金融：Polygon.io / Alpha Vantage / Financial Modeling Prep 等行情与基本面数据 MCP
  - 科研：arXiv / Semantic Scholar / PubMed 等论文检索 MCP
  - 营销：浏览器自动化（Playwright）/ 网页抓取（Firecrawl/Exa）/ 邮件营销类 MCP
- 字段：`name`（幂等键）、`category`（finance/research/marketing）、`service_type`（http/sse）、`service_url`、`capabilities`、`default_client_config`、`icon`、`description`
- 每域预装 1 个：走官方 `POST /api/v1/admin/ai/mcp-square/install`（生成 `AiMcpApiKey` + `AiMcpClient` 接入态），其余保持"可接入"

## 8. Seed 脚本设计

`backend/scripts/seed_domain_content.py`：

```
用法：
  python scripts/seed_domain_content.py --domain all [--dry-run] [--skip-skills] [--base-url http://127.0.0.1:8000]
```

- 参数：`--domain finance|research|marketing|all`、`--dry-run`（只打印计划不写库）、`--skip-skills`（跳过耗时的全量技能安装）、`--base-url`
- 前置：要求 uvicorn 已启动（脚本走 HTTP API，与官方链路 100% 一致）
- 幂等策略：技能按 `package_id`、Agent 按 `agent_code`、Team 按 `team_code`、MCP 模板按 `name` 查重，已存在即跳过并报告
- 步骤：注册 hub 仓库 → 刷新+枚举技能 → 逐个安装 → 创建 Agent → 创建 Team（内联 members/edges）→ 创建 MCP 模板 → 预装
- 输出：每步骤结果清单 + 最终汇总表

## 9. 验证闭环

| 项 | 验证 |
|---|---|
| P1 每批 | `npm run build`（vue-tsc）+ 四语言包 key 集合 diff（自写检查脚本，缺 key 即失败）+ 抽查页面切换语言目检 |
| P2 | 脚本输出安装汇总；`/api/v1/ai-assistant/skills` 列表核对；技能详情可打开 |
| P3/P4 | Agent Management / 团队列表页面可见；团队编排页拓扑正确；`POST /{team_id}/validate` 通过 |
| P5 | MCP 广场页面浏览/检索正常；预装项显示"已接入"；`POST /test/{id}` 探测可执行 |
| 回归 | 全局关键词无回归；后端编译 + OpenAPI 冒烟 |

## 10. 风险与边界

- 技能全量安装数量取决于仓库实际 SKILL.md 结构（预计数十至上百），`--skip-skills` 可跳过重跑 Agent/Team 部分
- MCP 模板的 `service_url` 以官方公开文档为准，个别需用户自配 API Key 才真正可用（预装示例也会因密钥缺失而 health=unknown，属预期）
- i18n 分批期间允许存在未提取的硬编码文案（后续批次覆盖），但每批结束四语言包 key 必须对齐
