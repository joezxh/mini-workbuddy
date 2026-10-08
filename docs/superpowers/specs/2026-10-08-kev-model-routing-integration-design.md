# kev 决策模型接入 AgentScope 设计（路由 / 决策工具 / 护栏 三子项目）

## 背景与问题

MinWorkBuddy 的会话 Agent 目前是**一个 Agent 绑一个 chat model**：`app/ai/strategy/factory_ext.py`
按 `ai_chat_model.id` 解析配置并构造一个 `ChatModelBase`，`app/ai/agent_factory.py` 把它装进
Agent 后，整个会话期间不再变化。由此产生三类问题：

1. **模型选择静态** —— 简单问答也走强推理模型（成本浪费），复杂输入又无法升级模型。
2. **业务判定要靠 LLM 自由生成** —— 意图分流、风险分级、是否转人工这类"是/否/选一项/打几分"
   的判定，现在靠 prompt 让对话模型输出，结果不稳定、没有概率、无法设阈值、也无法积累标注数据。
3. **回复质量没有自动闸门** —— 回复前后没有拦截、没有打分、没有基于打分的重试或降级。

而 kev（本地 `D:\projects\github\kev`）是一个**已经部署好的小决策模型服务**，API 与 TypeSafe
System One 完全兼容，一次请求可给出带校准概率的 `noul` / `choice` / `score` 判定。AgentScope 上游
（#2715 及其子项 #2717 / #2720，PR #2758）已为这类 Jev-like 模型提供 `agentscope.classifier` 抽象
与 `ModelRouterMiddleware`。也就是说：**框架侧的分类与路由能力现成，缺的是把自建 kev 接上去，
以及把它的判定接到业务动作上**。

### 关键现状事实

**kev 侧（已实测）**

| 事实 | 值 |
|---|---|
| 已部署服务 | 容器 `kev-server` 映射宿主机 `8008`；容器 `kev-playground` 映射 `3030`；编排层 `kev/console` 监听 `8790` |
| 服务状态 | `Up`，`healthy`，`device=cuda`，`backend=torch`，`dtype=bfloat16` |
| 加载的模型 | `jaredpalmer/kev-0.8b`，基座 `Qwen/Qwen3.5-0.8B-Base`，`lora=16`，`temperature=2.3510958125672174` |
| 上下文 | `max_state_tokens=65536`，`truncate_states=false`（超限默认 422，不静默截断） |
| 鉴权 | **当前 `KEV_API_KEY` 为空，即开放服务**，任何能访问 8008 的进程都能推理 |
| 协议 | `POST /v1/systemone`；`GET /v1/models`；`POST /v1/systemone/permute`；`POST /v1/systemone/separate` |
| 问题类型 | `noul`（是/否概率）、`choice`（选项 + `probabilities` + `confidence`）、`score`（等级 + `legend` + `probabilities`） |
| 准确率（0.8B，新源 dev/test） | 0.648 / 0.697；Brier 0.481 / 0.416 —— **家族最低档**（4B 为 0.817 / 0.838） |
| 部署约束 | 两个 compose 栈共用服务名 `kev-server` 与网络 `kev-net`，**同一时刻只能跑一个规格** |
| console 已有能力 | `scenario_domains` / `scenarios` / `scenario_spec_history` / `goldset` / `eval` / `jobs` / `lineage` —— 场景与金标沉淀已有落点 |
| 本机 GPU | RTX 5070 Ti Laptop，12227 MiB，已用约 2.6 GiB |

**AgentScope 侧（上游仓库 `agentscope-ai/agentscope`）**

| 事实 | 说明 |
|---|---|
| #2715 `feat(jev): support Jev model in agentscope` | Roadmap issue，**仍 open**；子项 #2717（Jev 基础模型）、#2720（路由中间件）已 closed 完成 |
| PR #2758（已合，2026-09-22） | 落地 `agentscope.classifier`：`ClassifierModelBase` / `JevClassifierModel` / `ClassifierQuestion` / `ChoiceAnswer` / `ClassifierResponse` / `ClassifierUsage`；以及 `agentscope.middleware.ModelRouterMiddleware` + `ChatModelCandidate` |
| `JevClassifierModel` | 内部构造 `AsyncTypeSafeClient(api_key=..., base_url=credential.base_url, model=..., timeout=..., retry=RetryPolicy(...))` —— **`base_url` 可改，正好指向自建 kev** |
| `TypeSafeCredential` | 字段 `type="typesafe_credential"`、`api_key: SecretStr`、`base_url: str 或 None`；`get_chat_model_class()` 故意抛 `NotImplementedError` |
| 版本 | PyPI **2.0.9**（2026-09-28）含 extra `classifier-jev`（`typesafe-sdk>=0.7`），即含 `classifier` 模块 |
| #2786 / #2788 | `TypeSafeCredential` 未注册进 `CredentialFactory`，走 AgentScope App 凭据存储会 500；issue `not_planned`、PR 未合 |
| #2792 / #2793 | 新 reply 会继承上一轮路由、并用上一轮模型裁决本轮输入媒体；**已修并合入 2.0.9** |
| #2846 | `agent.reply()` 无输入被判为"恢复"从而继承上一轮路由；**未修（not_planned）** |
| #2828 | `min_confidence` 阈值 PR，**未合** —— 上游无置信度闸门 |

**MinWorkBuddy 侧**

| 事实 | 说明 |
|---|---|
| venv 实际版本 | **`agentscope==2.0.8`，不含 `classifier` 模块**；`requirements.txt` 写的是 `2.0.9`，未落地。`typesafe_sdk` 未安装 |
| 模型工厂 | `app/ai/strategy/factory_ext.py`：`resolve_model_config(model_id)`（空 dict = 不可用）后 `build_model(cfg)`；provider 到 (Model, Credential) 的映射表 |
| Agent 装配 | `app/ai/agent_factory.py`；AgentScope 语义中间件在 `app/ai/middleware/`（`config_trace` / `graphiti_memory` / `skill_metrics` / `tools` / `config_registry`） |
| 工具装配 | `app/ai/tool_manager/manager.py` 的 `build_toolkit()`；自定义工具在同目录（`ToolBase` 子类） |
| 配置中心 | `app/config/__init__.py` 的 `Settings` 由领域 mixin 组合；新增外部服务仿 `app/config/_app.py` 的 `SQLBOT_*` 写法 |
| 路由注册 | `app/core/router_registry.py` 的 `ROUTER_SPECS` 显式清单（不自动扫描） |
| 建表 | **无 alembic**，`main.py` 的 `create_all`；新增 Model 必须在 `app/db/models/__init__.py` import 并加进 `__all__` |
| 横切 | `app/services/workflow/circuit_breaker.py`、`retry_policy.py`；外部 HTTP 统一 httpx（样板 `app/middleware/sqlbot_client.py`） |
| 测试 | `backend/tests/{unit,ai,agent,kb,workflow,connectors,dataops,duplex,ontology,integration}`；HTTP 依赖多用 monkeypatch 或自建 fake client |

---

## 目标 / 非目标

本设计覆盖**一个公共底座 + 三个子项目**：

| 编号 | 子项目 | 目标 |
|---|---|---|
| **P0** | 公共底座 | kev 客户端、场景（问题定义）管理、决策留痕；P1/P2/P3 共用 |
| **P1** | 模型路由 | 每轮回复按用户输入自动选最合适的 chat model；kev 不可用时零影响回落 |
| **P2** | 决策工具 | 把 kev 判定包装成 Agent 可调用的 Toolkit 工具，用于意图分流、风险分级、是否转人工 |
| **P3** | 护栏与质量 | 回复前拦截、回复后质量打分、基于打分的重试与降级 |

**非目标**

- 不做 kev 的训练 / 微调本身（但 P0 的决策留痕与 P2 的场景表要能**导出微调语料**，喂给 kev 侧
  `skills/kev-finetune` 与 `/console` 的训练流程 —— 这是跨仓库协作，不在本仓库实现）。
- 不把 kev playground（`3030`）与 console（`8790`）嵌入 MinWorkBuddy 导航或做 iframe。
- **不覆盖 `duplex/voice` 实时语音链路**：P1/P3 依赖 `Agent.reply` / `reply_stream` 事件流，
  `app/duplex/voice/providers/agentscope.py` 的 `RealtimeAgent` 不走该链路。

---

## 方案选型

### 公共决策（四选一，已定）

| 维度 | 方案 | 结论 |
|---|---|---|
| **接入实现** | A. 升 2.0.9 + 官方 `JevClassifierModel`，`base_url` 指向 kev<br>B. 自建 `ClassifierModelBase` 子类，httpx 直连<br>C. 双实现可切换 | **A**。改动最小、与上游 #2715/#2758 对齐，升级免费跟随。SDK 自带重试点与本项目 `retry_policy`/熔断重叠 —— 通过 `max_retries=0` + 短超时规避双重重试 |
| **服务端规格** | A. 沿用 0.8B + 开鉴权<br>B. 切 4B + 开鉴权<br>C. 完全不动 | **A**。12 GB 卡上 4B（bf16 需 10–12 GB）太紧；首期锁 0.8B，换规格时**只改配置不改代码** |
| **配置来源** | A. DB 驱动<br>B. `settings`/ENV<br>C. 代码常量 | **A**。沿用 `AiChatModel`/`AiApiKey` 体系 + `ConfigRegistry` 加载，运营可配 |
| **playground** | A. 不嵌入，仅加诊断页<br>B. iframe 挂 3030<br>C. 完全不接前端 | **A**。诊断页用于标定描述与阈值；playground / console 保持独立人工工作台 |

### P2 决策工具：暴露形态

| 方案 | 做法 | 结论 |
|---|---|---|
| A. **场景模板驱动**（推荐） | DB 的 `ai_kev_scenario` 存问题定义（instructions + criteria + 类型 + 阈值 + 低置信度动作），每个启用场景生成一个具名工具挂进 Toolkit | **采用**。问题定义可审计、可标定、可积累标注数据做微调；Agent 只需传 state |
| B. **通用 `kev_decide` 工具** | 暴露一个工具让 Agent 自己写 questions JSON | **不采用**。LLM 现场造问题定义 → 概率不可标定、无法积累语料、 prompt 注入面变大 |
| C. 硬编码三个业务工具 | 直接写 `kev_intent` / `kev_risk` / `kev_needs_human` | **不采用**。改问题定义要发版，与"运营可配"冲突 |

### P3 护栏：重试放在哪一层

| 方案 | 做法 | 结论 |
|---|---|---|
| A. **中间件只打分，重试在上层编排**（推荐） | `KevQualityMiddleware` 打分 + 写 `middle_context` + 落库 + 发事件；由会话编排层读到低分后决定是否重跑 | **采用**。避免在 async generator 里重放事件流；重试策略（换模型 / 补 RAG / 限次数）属业务策略 |
| B. 中间件内静默重跑 | `on_reply` 里跑两次 `next_handler`，只 yield 第二次 | **不采用**。会吞掉第一次的完整事件流，与 MinWorkBuddy 既有流式事件架构冲突风险高 |
| C. 不重试，只告警 | 只打分不动作 | **不采用**。达不到用户要求的"降级重试" |

### 分期

P0 是 P1/P2/P3 的前置，**P1 先做完并验收，再启 P2，再启 P3**。三个子项目各自独立验收，
任一子项目关闭开关时系统行为与今天完全一致。

---

## 系统架构

```
                    ┌───────────────── P0 公共底座 ─────────────────┐
                    │  app/ai/kev/classifier.py   JevClassifierModel │
                    │  app/ai/kev/scenario.py     场景 → 问题定义     │
                    │  app/ai/kev/audit.py        决策留痕落库        │
                    └───────────────┬───────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
   P1 模型路由                 P2 决策工具                  P3 护栏与质量
   router_factory.py          toolkit.py                   guardrail.py（前）
   confidence.py              → AgentScope Toolkit         quality.py（后）
   policy.py                  → build_toolkit 装配         retry.py（上层编排）
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ▼
                    HTTP POST /v1/systemone  Authorization: Bearer <KEV_API_KEY>
                                    ▼
                    kev-server:8008（docker，kev-0.8b，cuda/bf16）

旁挂不动：kev-playground:3030、kev/console:8790 —— 人工调试与微调工作台
```

---

## 详细设计

### 0. P0 公共底座

#### 0.1 模块总表（新增后端包 `app/ai/kev/`）

| 模块 | 期 | 职责 | 失败语义 |
|---|---|---|---|
| `config.py` | P0 | 读 `settings.KEV_*`，提供 `kev_enabled()` | 未配置 → `False` |
| `classifier.py` | P0 | `build_kev_classifier()` 返回 `JevClassifierModel`；**延迟 import**（避免 `typesafe_sdk` 缺失时整个 ai 包导入失败） | 缺依赖或未配置 → `None` 并 `logger.warning` |
| `scenario.py` | P0 | DB 场景 → `ClassifierQuestion` 树；`build_questions(scenario)` | 场景缺失或非法 → `None` |
| `audit.py` | P0 | 每次 kev 调用落 `ai_kev_decision_log`（stage / 场景 / 输入摘要 / 输出概率 / latency / 最终动作） | 落库失败只告警，不影响主链路 |
| `confidence.py` | P1 | `ThresholdedKevClassifier`：低置信度改写 `choice` | 见 P1 |
| `policy.py` | P1 | 路由策略加载（经 `ConfigRegistry`） | 查不到 → `None` |
| `router_factory.py` | P1 | 组装 `ModelRouterMiddleware` | 任一环节失败 → `None` |
| `toolkit.py` | P2 | 场景 → AgentScope 工具；`build_kev_tools()` | 无启用场景 → 空列表 |
| `guardrail.py` | P3 | `KevGuardrailMiddleware`（回复前） | kev 不可用 → 放行 |
| `quality.py` | P3 | `KevQualityMiddleware`（回复后打分） | kev 不可用 → 不打分 |
| `retry.py` | P3 | 上层编排的重试判定 `should_retry(score_result)` | 纯函数 |
| `preview.py` | P1 | 诊断接口：直接打 kev 返回概率分布 | 明确报错，不静默降级 |

#### 0.2 数据模型（`app/models/ai/`，并在 `app/db/models/__init__.py` 登记）

```
ai_kev_scenario                      -- 场景 = 一组问题定义（P0，P1/P2/P3 共用）
  id             BIGINT PK
  tenant_id      BIGINT       NULL
  code           VARCHAR(64)         -- 全局唯一，如 'support_triage'
  name           VARCHAR(128)
  stage          VARCHAR(16)         -- 'route' | 'tool' | 'guard' | 'quality'
  scope          VARCHAR(16)  DEFAULT 'global'   -- 'global' 或 'agent'
  scope_key      VARCHAR(128) NULL   -- scope='agent' 时存 agent 标识
  question_type  VARCHAR(16)         -- 'noul' | 'choice' | 'score'
  instructions   TEXT
  criteria       JSON                -- choice: {opt: desc}；score: [level]；noul: {true,false}
  min_confidence DECIMAL(5,4) NULL   -- NULL 表示不做闸门
  low_conf_action VARCHAR(32) NULL   -- 'fallback' | 'force_human' | 'block' | NULL
  status         TINYINT DEFAULT 1
  created_at / updated_at DATETIME
  唯一约束 (tenant_id, code)

ai_kev_decision_log                  -- 每次 kev 调用留痕（P0，审计 + 后续微调语料源）
  id            BIGINT PK
  tenant_id     BIGINT NULL
  session_id    VARCHAR(64) NULL
  reply_id      VARCHAR(64) NULL
  stage         VARCHAR(16)          -- 'route' | 'tool' | 'guard' | 'quality'
  scenario_code VARCHAR(64)
  state_digest  VARCHAR(64)          -- 输入文本的 sha256，不存原文（含敏感信息）
  state_tokens  INT      NULL
  answer_type   VARCHAR(16)
  answer_json   JSON                 -- choice / probabilities / confidence / score / noul
  latency_ms    INT
  action        VARCHAR(32)          -- 最终采取的动作
  created_at    DATETIME
  索引 (tenant_id, scenario_code, created_at)
```

P1 另需两张表（见 P1 第 2 节）：`ai_model_route_policy`、`ai_model_route_candidate`。
P3 另需一张表：`ai_kev_guardrail_policy`（见 P3）。

#### 0.3 配置（`app/config/_kev.py`，登记进 `app/config/__init__.py` 的 mixin 列表）

```
KEV_ENABLED        bool  = False  -- 总开关，默认关闭
KEV_BASE_URL       str   = "http://127.0.0.1:8008"
KEV_API_KEY        str   = ""     -- kev-server 设了 KEV_API_KEY 后必填
KEV_MODEL          str   = "kev-latest"
KEV_TIMEOUT        float = 0.5    -- 路由/护栏在主链路同步前置，宁可降级也不拖慢首字
KEV_TOOL_TIMEOUT   float = 2.0    -- 工具调用由 Agent 主动发起，可放宽
KEV_AUDIT_ENABLED  bool  = True
KEV_MIN_CONFIDENCE float = 0.0    -- 0 表示不做闸门；可被场景表的 min_confidence 覆盖
```

#### 0.4 客户端构造

```python
JevClassifierModel(
    credential=TypeSafeCredential(api_key=settings.KEV_API_KEY, base_url=settings.KEV_BASE_URL),
    model=settings.KEV_MODEL,
    timeout=...,            # 路由/护栏用 KEV_TIMEOUT，工具用 KEV_TOOL_TIMEOUT
    max_retries=0,          # 关掉 SDK 自带重试，避免与项目 retry_policy / 熔断叠加
    retry_delay=0.0,
)
```

---

### 1. P1 模型路由

#### 1.1 数据模型

```
ai_model_route_policy
  id                 BIGINT PK
  tenant_id          BIGINT       NULL   -- NULL 表示全局
  scope              VARCHAR(16)         -- 'global' 或 'agent'
  scope_key          VARCHAR(128) NULL   -- scope='agent' 时存 agent 标识
  enabled            TINYINT(1)   DEFAULT 0
  scenario_code      VARCHAR(64)  NULL   -- 关联 ai_kev_scenario(stage='route')；NULL 用默认提问
  fallback_model_id  BIGINT       NULL   -- 兜底模型；NULL 表示用 Agent 自己的模型
  status             TINYINT      DEFAULT 1
  created_at / updated_at  DATETIME

ai_model_route_candidate
  id           BIGINT PK
  policy_id    BIGINT FK -> ai_model_route_policy.id
  model_id     BIGINT FK -> ai_chat_model.id
  name         VARCHAR(64)    -- 分类器返回的稳定标识，同一 policy 内唯一
  description  VARCHAR(512)   -- 作为 choice 的 criteria，直接决定分类质量
  position     INT     DEFAULT 0
  status       TINYINT DEFAULT 1
  唯一约束 (policy_id, name)
```

唯一约束与上游 `ModelRouterMiddleware` 的「duplicate candidates 抛 `ValueError`」检查一致，
先在 DB 层挡住。

#### 1.2 装配（`app/ai/agent_factory.py`）

```python
router = build_model_router_middleware(policy=load_policy(db, tenant_id, agent_key))
if router is not None:
    middlewares.insert(0, router)   # 最外层：最先改 agent.model，最后还原
```

理由：上游 `on_reply` 在 `next_handler` **之前**替换 `agent.model`、在 `finally` 还原，放在最外层
可保证内层中间件（`config_trace` / `graphiti_memory` / `skill_metrics` / `tools`）读到的是路由后
的模型。**Stage 3 必须实测**：确认这些既有中间件中哪些会读 `agent.model`；若存在必须在路由前读取
Agent 原始模型的中间件，则把路由中间件移到其后，并把结论回写本节。

开关：`enabled = 0`（默认）时完全不装配，行为与今天完全一致。

#### 1.3 置信度闸门 `ThresholdedKevClassifier`

上游 #2828 未合，`ModelRouterMiddleware` **没有** `min_confidence`。不 patch 上游，改为包一层：

```python
class ThresholdedKevClassifier(ClassifierModelBase):
    """kev 分类器加置信度闸门：低置信度时走兜底。"""

    def __init__(self, inner, min_confidence, fallback_name=None,
                 sentinel="__kev_low_confidence__"): ...

    async def __call__(self, state, questions, **kwargs):
        res = await self.inner(state=state, questions=questions, **kwargs)
        # 只改写 ChoiceAnswer；BinaryAnswer / ScoreAnswer 原样透传
        return res
```

**兜底口径**（避免歧义）：若 policy 配了 `fallback_model_id`，`router_factory` 把它作为**一个真实
候选**加入 `candidates`（`name="__fallback__"`，description 写"以上都不明确时使用的兜底模型"），
低置信度时直接返回 `"__fallback__"`；未配时才用哨兵，由上游 `logger.warning("unknown candidate")`
后回落。代价是 `__fallback__` 也可能被 kev 正常选中 —— 可接受，因为它本就是兜底模型。

> **注意**：kev 的 `choice.confidence = (p_max - 1/K) / (1 - 1/K)`，衡量概率分布集中度，
> **不是准确率**。阈值必须在诊断页实测标定，禁止拍脑袋写死。

#### 1.4 kev 与 AgentScope 的交互契约

- **触发点**：每轮 `ReplyStartEvent` 一次；HITL 恢复（携带 `UserConfirmResultEvent`、
  `UserInterruptEvent`、`ExternalExecutionResultEvent`）沿用已存路由；`finally` 还原 `agent.model`。
- **请求**：`state` 为最新一条 user 消息的纯文本（上游 `_latest_user_text`，只取 `get_text_content()`）；
  `questions = {"chat_model": ChoiceQuestion(instructions=..., criteria={候选名: 候选描述})}`。
- **响应**：`ChoiceAnswer(choice, confidence, probabilities)`，据此替换 `agent.model`。
- **三条硬约束**：
  1. **路由只看一条纯文本** —— 不看历史、不看工具返回；多模态附件在路由阶段只剩文本。
  2. **候选模型构造失败即剔除该候选**，**不使用** `build_default_model_config()` 的 ENV 兜底 ——
     否则会静默路由到运营没配过的模型。
  3. **超时短、失败即降级**。路由是主链路同步前置，不能拖慢首字。

#### 1.5 管理接口与诊断页

- CRUD：`app/schemas/ai/kev_route.py`、`app/services/ai/model_route_service.py`、
  `app/routers/ai/model_route.py`，前缀 `/api/v1/admin/model-route`，登记进 `router_registry`
  的 `ROUTER_SPECS`。校验：候选 `name` 同 policy 内唯一；`model_id` 存在且 `status=1`；
  至少 1 个启用候选才允许启用 policy。
- 诊断接口：`POST /api/v1/ai/model-route/preview`，入参 `{text, policy_id}`，
  出参 `{candidates: [{name, probability, confidence}], selected, thresholded, latency_ms}`。
- 前端：`frontend/src/api/model-route.ts` + `frontend/src/views/admin/ai/model-route/` 诊断页
  （textarea 输入，展示概率条、置信度、阈值判定、最终选中），在
  `frontend/src/views/admin/componentMap.ts` 登记（与 `voice-demo` 等既有条目同法）。
- 路由策略经 `app/ai/middleware/config_registry.py` 的 `ConfigRegistry` 加载（新增
  `_load_model_routes()`，沿用其 300 秒刷新间隔），故改动 5 分钟内生效，无需重启。

#### 1.6 playground / console 接入点

- **不嵌入**。定位是「改候选 `description` 之前先在这里试问法」的人工工作台：
  - playground 的 kev tab：直接改 state 与 questions 看概率；
  - `POST /v1/systemone/permute`：验证**选项顺序稳定性**（kev 官方明示选项顺序会影响 choice），
    候选描述调整后先跑 6–8 次 permute，确认 `argmax_stable`；
  - `/console/eval` 与 `/console/goldset`：后续沉淀路由标注集做微调的落点（本次不做）。
- 与 MinWorkBuddy 的唯一耦合是诊断页，且只调 MinWorkBuddy 自己的 preview 接口，不跨源。

---

### 2. P2 决策工具（Agent 可调用）

把 `ai_kev_scenario` 里 `stage='tool'` 的启用场景，各生成一个 AgentScope 工具，挂进 Agent 的 Toolkit。
Agent 只需传入要判定的文本，问题定义与阈值由 DB 控制。

#### 2.1 工具契约

| 项 | 约定 |
|---|---|
| 工具名 | `kev_<code>`（code 转小写下划线） |
| 工具描述 | scenario 的 `name` + `instructions`，让 Agent 知道何时该调用 |
| 入参 | `state: str`（待判定文本）；可选 `context: str`（补充上下文，与 state 拼接） |
| 出参（choice） | `{type, choice, probability, probabilities, confidence, low_confidence, action}` |
| 出参（noul） | `{type, probability, thresholded, action}` |
| 出参（score） | `{type, score, level_label, probabilities, confidence, low_confidence, action}` |
| 失败 | 返回 `{type: "error", reason}` —— **不抛异常**，避免打断 Agent 的 ReAct 循环；同时落 audit |

`low_conf_action` 的语义（写进工具描述，让 Agent 能据此决策）：

- `force_human` → 结果带 `needs_human: true` 与建议话术，由 Agent 自行转人工；
- `fallback` → 结果带 `low_confidence: true`，提示 Agent 走保守路径；
- `block` → **护栏专用**（P3），工具阶段出现该值视为配置错误，拒绝加载该场景。

#### 2.2 装配

`app/ai/tool_manager/manager.py` 的 `build_toolkit()` 末尾追加：

```python
tools += build_kev_tools(db=db, tenant_id=tenant_id, agent_key=agent_key)
```

`build_kev_tools()` 读启用场景（`stage='tool'`，`status=1`），逐个构造工具；任一场景构造失败
只跳过该场景并告警。无启用场景时返回空列表。

**启用范围**：场景表沿用与 `ai_model_route_policy` 相同的 `scope` / `scope_key` 两列（全局或按
agent 生效），首期支持 `global`；按 agent 白名单裁剪若确有需要再加绑定表。

#### 2.3 与 kev console 的衔接

场景表与 kev console 的 `scenarios` / `scenario_spec_history` 同构（code + instructions + criteria），
因此：MinWorkBuddy 侧 `ai_kev_decision_log` 可按 `scenario_code` 导出标注语料，喂给 kev 侧的
`/console/eval`（回测）与 `skills/kev-finetune`（微调）。**导出脚本不在本仓库实现**，本次只保证
留痕表含足够字段（`scenario_code` / `state_digest` / `answer_json`）。

---

### 3. P3 护栏与质量（回复前拦截 / 回复后打分 / 重试降级）

#### 3.1 数据模型

```
ai_kev_guardrail_policy
  id               BIGINT PK
  tenant_id        BIGINT NULL
  scope            VARCHAR(16)        -- 'global' 或 'agent'
  scope_key        VARCHAR(128) NULL
  stage            VARCHAR(16)        -- 'pre' | 'post'
  scenario_code    VARCHAR(64)        -- 关联 ai_kev_scenario(stage='guard' 或 'quality')
  action           VARCHAR(32)        -- pre: 'block' | 'warn'；post: 'score' | 'retry'
  threshold        DECIMAL(5,4) NULL  -- noul: 概率阈值；score: 低分阈值（<= 该值触发）
  message_template TEXT       NULL    -- pre 拦截时的回复文案
  upgrade_model_id BIGINT     NULL    -- retry 时改用该模型；NULL 表示沿用当前模型
  max_retries      INT        DEFAULT 1
  enabled          TINYINT(1) DEFAULT 0
  status           TINYINT    DEFAULT 1
  created_at / updated_at DATETIME
```

#### 3.2 回复前：`KevGuardrailMiddleware`

`on_reply` 中、调用 `next_handler` **之前**执行：

1. 取最新一条 user 文本，打 `stage='guard'` 的场景；
2. 命中 `block` 条件（`noul` 概率 ≥ threshold，或 `choice` 命中禁止项）→ **不调用 `next_handler`**，
   直接 yield 一条系统回复（`message_template`）并结束该轮；
   （`block` 机制按此实现，但**首期不启用，只上 `warn`** —— 见「关键约束」第 16 条）；
3. 命中 `warn` → 写入 `agent.state.middle_context` 并按既有事件架构发一个告警事件，继续正常流程；
4. **kev 不可用或超时 → 放行**（护栏不得因决策服务故障而阻断业务）。

#### 3.3 回复后：`KevQualityMiddleware`

`on_reply` 中正常透传 `next_handler` 的全部事件，同时累积最终 assistant 文本；流结束后：

1. 构造 `state = {"user_input": ..., "assistant_reply": ...}`（kev 的 state 支持 object，会转成带标签文本）；
2. 打 `stage='quality'` 的 `score` 场景，得到质量等级与概率；
3. 结果写入 `middle_context`、落 `ai_kev_decision_log`、按既有事件架构发事件（供前端展示质量分）；
4. **不在中间件内重跑**（选型 A）；kev 不可用则不打分、不阻断。

#### 3.4 重试与降级：上层编排

`retry.py` 提供纯函数：

```python
def should_retry(score_result: dict | None, policy: GuardrailPolicy, attempt: int) -> bool:
    # score_result 为 None（kev 不可用）→ False
    # score <= policy.threshold 且 attempt < policy.max_retries → True
```

由**会话执行层**在读完 `middle_context` 的质量分后决定是否重跑一次（改用 `upgrade_model_id`，
或补充 RAG 后重跑）。这样避免在 async generator 内部重放事件流。

> 会话执行层的具体位置在实施时定位（候选：会话路由所调用的 agent runner），定位后把路径回写本节。

#### 3.5 中间件顺序（P1 + P3 合并后）

由外到内：`KevGuardrailMiddleware` → `ModelRouterMiddleware` → `KevQualityMiddleware` → 既有中间件。
理由：护栏要最先看到原始输入并可能直接终止；路由要在其它中间件读到 `agent.model` 前完成替换；
质量打分在最内层收集最终回复。**该顺序在 Stage 实测后回写**（与 P1 第 1.2 节同一次实测）。

---

## 依赖关系

| 依赖 | 现状 | 动作 |
|---|---|---|
| `agentscope` | venv 装的是 **2.0.8**（无 `classifier`） | **必须升级到 2.0.9**（`requirements.txt` 已是 2.0.9） |
| `typesafe-sdk>=0.7` | 未安装 | 安装 `agentscope[classifier-jev]`，并写进 `requirements.txt` |
| Python | 3.12（agentscope 要求 3.11+） | 满足 |
| kev-server | 运行中，无鉴权 | 部署脚本加 `-ApiKey <key>` 重启；同一 key 写入后端 `KEV_API_KEY` |
| GPU | RTX 5070 Ti Laptop 12 GB，已用约 2.6 GiB | 0.8B 无压力；4B 需先 down 0.8B 栈且仍紧张 |

---

## 关键约束与已知坑

**跨子项目**

| # | 事项 | 应对 |
|---|---|---|
| 1 | **#2786**：`TypeSafeCredential` 未注册 `CredentialFactory`，走 AgentScope App 凭据存储会 500 | kev 密钥走本项目 `app/config` + DB，**不进** AgentScope 凭据体系 |
| 2 | **#2846 未修**：`agent.reply()` 无输入被判为"恢复"，继承上一轮路由 | 排查 MinWorkBuddy 是否存在无输入调用路径；有则规避并加回归测试 |
| 3 | **#2792 / #2793 已修**（2.0.9 含）：新 reply 不再被上一轮路由污染 | 中间件顺序仍需实测 |
| 4 | **#2828 未合**：上游无 `min_confidence` | 自建置信度闸门，不 patch 上游 |
| 5 | `confidence` 是分布集中度，**不是准确率** | 阈值实测标定；先以 `NULL`（不启用）上线 |
| 6 | 0.8B 新源准确率仅 0.648 / 0.697（家族最低） | 首期仅链路验证；上生产前评估 4B（0.817 / 0.838） |
| 7 | 两个 kev compose 栈共用服务名，**同时只能跑一个规格** | 换规格必须先 `docker compose down` 另一个栈 |
| 8 | 选项顺序影响 choice | 候选与场景描述定稿前用 playground 的 `permute` 校验 `argmax_stable` |
| 9 | state 上限 65,536 token，**0.8B 验证上下文仅 8,192** | 路由与护栏输入只取单条 user 文本；诊断页显示 `state_tokens` |
| 10 | 租户隔离 | 策略、场景、护栏表均带 `tenant_id`，与 `TenantResolverMiddleware` 对齐 |
| 11 | kev 无鉴权时任何进程可推理 | 首期必须设 `KEV_API_KEY`；后端该值为空即视为未配置 |
| 12 | 无 alembic | 新表靠 `create_all`；同步维护 `schema.sql` 导出 |

**P2 专用**

| # | 事项 | 应对 |
|---|---|---|
| 13 | 工具异常会打断 Agent 的 ReAct 循环 | 工具失败返回 `{type: "error"}`，不抛异常 |
| 14 | 启用场景过多会膨胀 tool 列表、挤占上下文与增加误调用 | 首期启用场景控制在 5 个以内；按 agent 白名单裁剪列为后续 |
| 15 | 入参 `state` 由 LLM 生成，可能含幻觉内容 | 结果只作参考；真实转人工 / 权限动作仍需走既有 HITL 与权限体系 |

**P3 专用**

| # | 事项 | 应对 |
|---|---|---|
| 16 | **0.8B 准确率低，误拦代价高于漏拦** | **首期 pre 护栏只上 `warn`，不上 `block`**；`block` 留到换 4B 且阈值标定后再评估 |
| 17 | post 打分会把回复内容传给 kev | 审计只存 `state_digest` 不存原文；上线前确认数据外发边界与合规要求 |
| 18 | 重试叠加成本与延迟 | `max_retries` 默认 1；仅由 post 低分触发；同一 reply 不重复计分重试链 |
| 19 | 护栏阻断必须有可观测出口与一键关闭 | 落 `ai_kev_decision_log` + 发事件；`enabled=0` 立即失效 |

---

## 落地步骤

| Stage | 子项目 | 内容 | 门禁 |
|---|---|---|---|
| 0 | P0 | ① 升 `agentscope==2.0.9` 并安装 `agentscope[classifier-jev]`；② 跑 `pytest tests/unit tests/ai` 确认无回归；③ kev-server 设 `KEV_API_KEY` 重启；④ 用 `typesafe_sdk` 直连 `8008` 打一次 `systemone`；⑤ `curl 8008/v1/models` 断言 `run` / `temperature` / `max_state_tokens` | 既有测试无回归；无 key 401、带 key 200；SDK 与 kev 契约跑通 |
| 1 | P0 | `app/config/_kev.py` + mixin 登记；`classifier.py` / `scenario.py` / `audit.py`；场景表与留痕表 ORM 登记 | 缺依赖或未配置时返回 `None` 并 warning；留痕写入成功 |
| 2 | P1 | `ai_model_route_policy` / `ai_model_route_candidate` ORM；schemas / service / router；`router_registry` 登记 | CRUD 可用；候选重名与无效 `model_id` 被拒 |
| 3 | P1 | `policy.py` / `confidence.py` / `router_factory.py`；`agent_factory.py` 注入（默认关闭）；**实测中间件顺序并回写** | 三类输入落到三个候选；关闭开关时行为与今天一致 |
| 4 | P1 | `preview` 接口 + 诊断页 + `componentMap.ts` 登记 | 页面展示概率、置信度、阈值判定、最终选中 |
| 5 | P2 | `toolkit.py`；`build_toolkit()` 装配；场景 CRUD 接口 | 工具可被 Agent 调用并返回结构化结果；失败返回 error 不抛异常 |
| 6 | P3 | `ai_kev_guardrail_policy` ORM；`guardrail.py`（仅 `warn`）+ `quality.py` + 两个中间件装配 | 命中 warn 时有事件与留痕且回复正常；kev 不可用不影响回复 |
| 7 | P3 | 定位会话执行层并接入 `retry.py`（回写路径）；评估是否放开 `block` | 低分触发一次重试且换用 `upgrade_model_id`；重试不超过 `max_retries` |
| 8 | 全部 | 用诊断页与 playground `permute` 标定描述与阈值 | 三条验收主张全部通过 |

---

## 验证方式

**验收主张（可证伪）**

1. **P1**：简单问答 / 复杂推理 / 带附件 三类输入分别落到三个不同候选模型；kev 不可用时回落到
   Agent 自己的模型，无异常、无 5xx、延迟无显著增加；DB 改策略 5 分钟内生效。
2. **P2**：Agent 在需要判定时会调用对应 kev 工具并返回结构化概率；工具类异常不打断 ReAct 循环。
3. **P3**：命中 `warn` 场景时产生事件与留痕且不影响回复；post 低分时上层触发一次重试；
   kev 不可用时护栏放行、不打分、不重试。

**单元（mock，默认运行）**

- `build_kev_classifier()`：未配置或 `typesafe_sdk` 缺失 → `None` 并 warning。
- `scenario.py`：非法 `criteria` / 未知 `question_type` → `None`。
- `ThresholdedKevClassifier`：高于阈值透传、低于阈值改写；`BinaryAnswer` / `ScoreAnswer` 原样透传。
- `policy.py`：查不到策略、候选全禁用、`model_id` 失效 → `None`。
- `toolkit.py`：工具失败返回 error 结构；`low_conf_action='block'` 的场景被拒绝加载。
- `guardrail.py`：kev 不可用 → 放行；命中 `block` → 不调用 `next_handler`。
- `retry.py`：`score_result=None` → `False`；`attempt >= max_retries` → `False`。
- `audit.py`：落库失败仅告警，不影响返回值。

**集成（真实 HTTP 打到 kev:8008；默认 skip，仅当配置 `KEV_BASE_URL` 时运行）**

- `POST /v1/systemone` 的 `noul` / `choice` / `score` 三类型返回结构与 kev README 一致。
- P1 端到端：三类输入落到三个不同候选（断言 `ModelCallStartEvent.model_name`）。
- P2 端到端：Agent 收到"帮我判断这段投诉属于哪个部门"时调用 `kev_*` 工具。
- P3 端到端：构造命中 warn 的输入 → 有事件与留痕、回复正常；构造低质量回复 → 上层重试一次。
- 停掉 `kev-server` 容器 → 路由回落、工具返回 error、护栏放行，均无异常抛出。
- 契约：`GET /v1/models` 断言 `max_state_tokens == 65536`，并核对 `run` 与 `temperature`。

**前端**

- 诊断页手测：概率条与选中结果正常；kev 不可用时页面明确报错（诊断接口不静默降级）。
- `npm run build` 通过（按项目既有做法，用输出过滤只看本次改动路径）。

---

## 风险与后续

| 风险 | 说明 | 处理 |
|---|---|---|
| 0.8B 判定质量不足 | 新源准确率 0.648，误路由、误拦概率都不可忽略 | 首期仅链路验证；P3 首期只 `warn`；上生产前评估 4B |
| 2.0.8 升 2.0.9 的回归 | venv 长期停在 2.0.8，升级可能影响语音与 RAG 链路 | Stage 0 先跑 `tests/unit` 与 `tests/ai`；失败先修再继续 |
| `typesafe-sdk` 与 kev 契约漂移 | SDK 升级可能改请求字段 | 锁 `typesafe-sdk>=0.7` 并加契约测试（Stage 0 第 ④ 项） |
| 三个子项目联动导致中间件相互干扰 | 路由、护栏、质量都在 `on_reply` 上做文章 | 中间件顺序一次性实测并回写；每个子项目可独立关闭 |
| 回复内容外发到 kev | P3 post 打分需要把回复传给 kev | 审计只存摘要；上线前确认数据边界与合规 |
| 路由 / 护栏延迟进入首字 | 每轮同步 HTTP | 主链路超时 0.5s、`max_retries=0`、失败即降级 |
| 多模态候选判据不足 | 路由只看到文本 | 已写进约束；后续可考虑把附件 media type 拼进 state |
| 场景与微调闭环 | 判定效果最终要靠自己数据微调 | `ai_kev_decision_log` 已预留字段；导出脚本与微调跨仓库协作，不在本仓库 |
