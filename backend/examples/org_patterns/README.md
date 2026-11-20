# 多智能体组织模式范例（跨境电商场景）

基于 **agentscope 2.0.12** 的 8 个可离线运行范例，演示 8 种多智能体组织模式的**真实语义**
（派活/交接/广播/裁决/并发/网关边界），配套 API 幂等种子脚本把 8 个 `xborder-*` 团队挂进平台。

设计依据：`docs/design/org-pattern-examples-zh.md`（方案 A 双轨制）；
范式参考：`docs/design/agent-architecture-patterns-zh.md`。

## 8 模式索引

| # | 模式 | 脚本 | 业务场景 | 原生程度 |
|---|------|------|----------|----------|
| 01 | Supervisor-Worker | `01_supervisor_worker.py` | 跨境新品上架统筹（GO/NO-GO） | ★★★ 原生 `TeamPipeline` |
| 02 | 层级式 | `02_hierarchy_expansion.py` | 海外市场拓展（总监→Leader→Worker） | ★☆ 薄编排层 + 子 `TeamPipeline` |
| 03 | 流水线 | `03_pipeline_inquiry.py` | 询盘→报价→合同→跟单（验收重试≤3） | ★★★ 原生 `agentscope.sop` |
| 04 | 交接式 | `04_handoff_support.py` | 跨语种客服专家交接（只传摘要） | ☆ 外部工具 + 自建驱动循环 |
| 05 | 对等网状 | `05_mesh_multiplatform.py` | 多平台运营互通（无中心节点） | ☆ 共享消息板 + 自建广播循环 |
| 06 | 辩论/群聊 | `06_debate_adreview.py` | 广告策略评审（结构化裁决收敛） | ☆ 自建轮次 + 原生结构化输出 |
| 07 | 并行聚合 | `07_parallel_budget.py` | 多渠道预算测算（时间戳证并发） | ★★ `asyncio.gather` + 聚合 Agent |
| 08 | 联邦式 | `08_federated_supplychain.py` | 跨组织供应链协同（白名单网关） | ★★ 原生通信 + 工程边界 |

共享脚手架 `_common.py`：`FakeChatModel`（脚本化离线模型）/ `make_model` / `make_agent`
（BYPASS 免交互）/ `Trace`（编排语义留痕）/ mock 业务工具 / 白名单网关 / `run_cli`。

## 运行

```powershell
cd backend

# 离线运行（无需任何 API Key，全 mock 确定性数据）
.venv\Scripts\python.exe examples\org_patterns\01_supervisor_worker.py --mock
# …02~08 同理

# 真实模型运行（二选一配置环境变量；皆无则抛清晰中文错误提示加 --mock）
$env:OPENAI_BASE_URL = "https://你的兼容端点"
$env:OPENAI_API_KEY  = "sk-xxx"
# 可选：$env:OPENAI_MODEL = "gpt-4o-mini"（默认）
# 或 DashScope：
$env:DASHSCOPE_API_KEY = "sk-xxx"
# 可选：$env:DASHSCOPE_MODEL = "qwen-plus"（默认）
.venv\Scripts\python.exe examples\org_patterns\01_supervisor_worker.py
```

语义验收全部走 `--mock`（确定性断言）；真实模型路径只做冒烟，不做语义断言。

## 测试

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/org_patterns -q
```

覆盖：脚手架契约（含 tool_call id 跨响应唯一性回归）、8 范例语义断言
（派活/交接摘要不泄漏/重试上限/并发时间戳/裁决收敛/广播预算/网关拒绝）、
种子数据契约（8 团队 `xborder-*` 前缀、mode、成员/边引用完整性）。

## 种子脚本（挂载到平台 UI）

```powershell
cd backend
# 只打印预览，不触网
.venv\Scripts\python.exe scripts\seed_org_pattern_teams.py --dry-run
# 幂等注册 32 Agent + 8 团队（需先启动后端；按 code 查重跳过、缺成员跳过整团队）
.venv\Scripts\python.exe scripts\seed_org_pattern_teams.py --base-url http://127.0.0.1:8000 --username admin --password xxx
```

## 与 UI 统一编排的关系（方案 A 权衡）

- 平台现有 orchestrator 运行时**不读 team.mode**：无论挂载 mode 是什么，UI 对话统一走
  「Leader + ask_xxx 派活」的 Supervisor-Worker 编排。挂载 mode 仅记录来源模板 + 前端展示。
- 因此**模式语义的权威演示在本目录脚本**（原生 API + 自建薄编排层）；种子挂载的
  `xborder-*` 团队提供可对话的专家组入口，层级/交接/联邦等语义在团队 description
  与角色描述中注明，由对应脚本保证。
- 让 UI 真正按 mode 分派编排策略属方案 B，另行立项（见 spec D2）。

## 硬上限与约束

- 每范例均有终止保障：`max_iters`（4~12）/ `max_hops=3` / `max_rounds=3~4` /
  发言预算 16 / `asyncio.wait_for(60)` / SOP `max_attempts=3`。
- Agent name 一律 ASCII（中文角色名入 system_prompt）；范例不 import `app.*`；
  种子脚本只走 HTTP API；不新增事件枚举、不做 DB 迁移。