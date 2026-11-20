# 跨境电商 AgentTeam 组织模式（正式能力）

基于 **agentscope 2.0.12** 的 8 个组织模式实现，已正式收编进后端 team 模块
（`backend/app/ai/team/org_patterns/`），不再是独立演示脚本：每个模式对外暴露统一
`async def run(mock: bool, model_id: Optional[int] = None, **flags) -> dict` 入口
（返回 `{"final": str, "trace": Trace}`），可被编排层/会话侧直接复用；配套 API 幂等
种子脚本把 8 个 `xborder-*` 团队挂进平台，供会话选用。

设计依据：`docs/design/org-pattern-examples-zh.md`（方案 A 双轨制，历史设计稿）；
范式参考：`docs/design/agent-architecture-patterns-zh.md`。

## 代码结构

```
backend/app/ai/team/org_patterns/
├── __init__.py                  # PATTERNS 注册表（模式 key → PATTERN 元数据）与导出
├── scaffolding.py               # 共享脚手架（原 examples/_common.py）
├── seed_data.py                 # 种子数据单一事实源（AGENTS 34 / TEAMS 8）
├── listing_launch.py            # 01 Supervisor-Worker
├── market_expansion.py          # 02 层级式
├── inquiry_pipeline.py          # 03 流水线
├── support_handoff.py           # 04 交接式
├── multiplatform_ops.py         # 05 对等网状
├── ad_review_debate.py          # 06 辩论/群聊
├── budget_parallel.py           # 07 并行聚合
└── supply_chain_federation.py   # 08 联邦式

backend/scripts/run_org_pattern.py        # 统一 CLI（收敛自原各脚本 __main__）
backend/scripts/seed_org_pattern_teams.py # HTTP API 幂等种子
backend/tests/ai/team/org_patterns/       # 离线语义断言测试（pytest，不依赖网络/DB）
```

共享脚手架 `scaffolding.py`：`FakeChatModel`（脚本化离线模型）/ `make_model` /
`make_agent`（BYPASS 免交互）/ `Trace`（编排语义留痕）/ mock 业务工具 / 白名单网关。
库模块无 argparse/CLI 副作用、无 sys.path hack，全部规范包内导入。

## 8 模式索引（业务命名）

| 模式 key | 团队标识 | 团队名 | mode | 业务场景 | 原生程度 |
|----------|----------|--------|------|----------|----------|
| `listing_launch` | xborder-supervisor-listing | 跨境新品上架统筹 | supervisor | 新品上架 GO/NO-GO | ★★★ 原生 `TeamPipeline` |
| `market_expansion` | xborder-hierarchy-expansion | 海外市场拓展 | supervisor | 总监→Leader→Worker | ★☆ 薄编排层 + 子 `TeamPipeline` |
| `inquiry_pipeline` | xborder-pipeline-inquiry | 外贸询盘报价 | sequential | 询盘→报价→合同→跟单（验收重试≤3） | ★★★ 原生 `agentscope.sop` |
| `support_handoff` | xborder-handoff-support | 跨语种客服交接 | sequential | 跨语种客服专家交接（只传摘要） | ☆ 外部工具 + 自建驱动循环 |
| `multiplatform_ops` | xborder-mesh-multiplatform | 多平台运营协同 | msghub | 多平台运营互通（无中心节点） | ☆ 共享消息板 + 自建广播循环 |
| `ad_review_debate` | xborder-debate-adreview | 广告策略评审 | msghub | 结构化裁决收敛 | ☆ 自建轮次 + 原生结构化输出 |
| `budget_parallel` | xborder-parallel-budget | 多渠道预算测算 | parallel | 时间戳证并发 | ★★ `asyncio.gather` + 聚合 Agent |
| `supply_chain_federation` | xborder-federated-supplychain | 跨组织供应链协同 | dag | 白名单网关边界 | ★★ 原生通信 + 工程边界 |

## 运行（统一 CLI）

```powershell
cd backend

# 列出全部模式与示例输入
.venv\Scripts\python.exe scripts\run_org_pattern.py --list

# 离线运行（无需任何 API Key，全 mock 确定性数据）
.venv\Scripts\python.exe scripts\run_org_pattern.py listing_launch --mock
# …其余 7 个模式 key 同理

# 失败注入开关（离线确定性验证边界行为）
.venv\Scripts\python.exe scripts\run_org_pattern.py market_expansion --mock --timeout-team xborder-eu-team
.venv\Scripts\python.exe scripts\run_org_pattern.py inquiry_pipeline --mock --inject-bad-rate
.venv\Scripts\python.exe scripts\run_org_pattern.py ad_review_debate --mock --judge-always-continue
.venv\Scripts\python.exe scripts\run_org_pattern.py budget_parallel --mock --fail-channel xborder-roi-meta
.venv\Scripts\python.exe scripts\run_org_pattern.py supply_chain_federation --mock --probe-boundary

# 真实模型运行（优先 DB 模型配置，走 factory_ext）
.venv\Scripts\python.exe scripts\run_org_pattern.py listing_launch --model-id 13
```

真实模型构建三级路径（`make_model`）：
1. `--mock` → `FakeChatModel`（离线确定性）；
2. `--model-id` → `app.ai.strategy.factory_ext` 的 `resolve_model_config + build_model`
   （DB 模型配置，系统既有能力，首选）；
3. 环境变量兜底：`OPENAI_BASE_URL + OPENAI_API_KEY`（可选 `OPENAI_MODEL`）或
   `DASHSCOPE_API_KEY`（可选 `DASHSCOPE_MODEL`）。保留兜底是为无 DB 场景（CI/裸机）
   仍可真实冒烟；皆无则抛含 `--mock` 提示的中文错误。

语义验收全部走 `--mock`（确定性断言）；真实模型路径只做冒烟，不做语义断言。

## 测试

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/ai/team/org_patterns -q
# 与 orchestrator 事件测试合跑
.venv\Scripts\python.exe -m pytest tests/ai/team/org_patterns tests/agent/test_team_orchestrator_events.py tests/agent/test_team_chat_sse.py -q
```

覆盖：脚手架契约（含 tool_call id 跨响应唯一性回归）、8 模式语义断言
（派活/交接摘要不泄漏/重试上限/并发时间戳/裁决收敛/广播预算/网关拒绝）、
种子数据契约（34 Agent / 8 团队 `xborder-*` 前缀、mode、成员/边引用完整性、
脚本与 seed_data 单一事实源一致性）。

## 种子注册（挂载到平台 UI）

```powershell
cd backend
# 只打印预览，不触网
.venv\Scripts\python.exe scripts\seed_org_pattern_teams.py --dry-run
# 幂等注册 34 Agent + 8 团队（需先启动后端；按 code 查重跳过、缺成员跳过整团队）
.venv\Scripts\python.exe scripts\seed_org_pattern_teams.py --base-url http://127.0.0.1:8000 --username admin --password xxx
```

种子数据单一事实源：`app/ai/team/org_patterns/seed_data.py`（AGENTS/TEAMS）；
脚本只走既有 HTTP API（POST /api/v1/agent-config、GET/POST /api/v1/ai-team），不做 DB 迁移。

## 会话中的使用方式

注册后在以下入口选用团队（category「跨境电商」）：
- 前端 `/admin/agent-team` 团队对话；
- `POST /api/v1/ai-team/{team_id}/run`（同步运行，落库运行记录，可带 `model_id`）；
- `POST /api/v1/ai-team/{team_id}/chat`（SSE 流式对话）。

每个团队的 `sample_input` 已随种子写入（见 `seed_data.py` 与各模块 `PATTERN["sample_input"]`），
例如「外贸询盘报价」：`Dear seller, we are interested in your portable coffee maker. Please quote 500 units to Tokyo, CIF, with lead time. — Tanaka Trading`。
预期输出为 Leader 汇总各成员结论后的最终答复（报价方案/上架决策/评审裁决等），
运行事件可在运行回放/时间线端点查看。

## UI 会话语义 vs 模式实现语义（方案 A 权衡）

- **UI 会话语义**：平台现有 orchestrator 运行时**不读 team.mode**——无论挂载 mode 是什么，
  UI 对话统一走「Leader + ask_xxx 派活」的 Supervisor-Worker 编排。挂载 mode 仅记录
  来源模板 + 前端展示。本次收编**未改动**该编排策略。
- **模式实现语义**：层级/流水线/交接/网状/辩论/并行/联邦的真实编排语义由
  `app/ai/team/org_patterns/` 各模块的 `run()` 保证（原生 API + 自建薄编排层），
  离线 mock 确定性可验；编排层/会话侧如需真实模式语义，直接调用对应 `run()`。
- 让 UI 真正按 mode 分派编排策略属方案 B，另行立项（见历史设计稿 D2）。

## 硬上限与约束

- 每模式均有终止保障：`max_iters`（4~12）/ `MAX_HOPS=3` / `MAX_ROUNDS=3~4` /
  发言预算 16 / `asyncio.wait_for(60)` / SOP `max_attempts=3`。
- Agent name 一律 ASCII（中文业务名入 system_prompt / 团队 name / 描述）；
  团队标识沿用 `xborder-` 前缀、mode ∈ {sequential, parallel, msghub, supervisor, dag}、
  category「跨境电商」；不新增事件枚举、不改 DB 模型、不做 alembic 迁移、不改前端。