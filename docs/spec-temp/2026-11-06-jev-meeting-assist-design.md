# 会中 Jev 会话辅助（判定 → 草稿 → 排序 → 一键填入）设计

> 状态：设计定版（2026-11-06） · 落点：`Demo-ai`（服务侧）+ `Demo-web`（会议页）+ `Demo-web/prototype/meeting-room.html`（评审演示）
> 关联：`2026-11-04-meeting-room-ui-design.md`（SP-1/2 会议 UI）、`2026-11-04-meeting-ai-spec-review-and-revision.md`（会中 AI 统一契约与门禁）、`2026-11-05-meeting-ai-specs-implementation.md`（SP-1/2 已交付实现）
> 需求来源：用户 2026-11-06 需求「在视频会议里增加基于 Jev like 模型 Kev 的会话辅助【主持人角色或由主持人授权】：① 读取对话、当事人等会话信息 ② 送入 Jev 判定模型（意图 / 紧张程度 / 风险等级 / 是否需立刻回复）③ 交给生成 LLM 输出 3 条回复草稿，Jev 给每条打分排序 ④ 悬浮面板展示分析 + 候选回复；一键填入输入框，**发送必须手动点**」

---

## 0. 一句话定义

在视频会议页增加一个**只读建议、不代发消息**的悬浮助手面板：把最近会话上下文交给 **Jev 判定模型**（意图 / 紧张度 / 风险等级 / 是否需立即回复），把判定结论作为约束交给**我方 LLM 池**生成 3 条Demo员口吻的回复草稿，再由 **Jev 对草稿打分排序**；面板展示分析与排序后的候选，主持人**一键填入**会中消息输入框，**发送动作必须本人手动点击**。

---

## 1. 背景与来源

### 1.1 Jev 的产品语义（本设计的形态来源）

参考实现 `jev-chat/jev-chat-jarvis`（MIT，桌面/Android/iOS 多端）的核心工作流是：

```
Read（读取对话） → Judge first（先判断意图/风险/建议动作） → Draft, check, rank（生成候选并检查排序）
→ 一键填入输入框 → 用户自行发送（工具永不自动发送）
```

本设计沿用该语义，并把它落到「Demo会议」域：Jev 判定服务是**独立部署**的外部模型服务（与仓库现有 `Kev` 决策模型同构的通用契约），我方负责上下文组装、LLM 草稿生成、面板呈现与「不代发」的强制约束。

> 注：Jev 官方应用无自有后端（Android 版直连用户自配模型服务商）。本设计中的「独立部署 Jev 服务」是**我方新增的对接方**，契约由本设计定版（见 §4）。

### 1.2 与仓库既有能力的关系

| 既有件 | 位置 | 本设计中的角色 |
|---|---|---|
| Kev 决策模型通道 | `Demo-ai/.../core/client/KevClient.java`、`core/config/KevProperties.java`、`core/client/ModelRouter.java` | **Jev 通道的模板**（同构契约 `state + questions`、独立熔断器、超时/重试语义） |
| `ai/capability/kev/system-one` | `Demo-ai-module-ai-api/.../api/ai/AiCapabilityApi.java` | **Jev 出口的模板**（新增 `jev/system-one`） |
| `AiLLMCallService.callModelForStructuredJson` | `Demo-ai/.../service/chat/AiLLMCallService.java` | 草稿生成（我方 LLM 池，`prompt_template` + `jsonSchema`） |
| 会中风险分析（SP-1/2） | `service/meeting/impl/MeetingAnalyzeServiceImpl.java` 等 | 开关权威、节流/限流、降级不编造、权限点等**行为范式** |
| 转录 SSE | `MeetingTranscriptService.listByRoom/subscribe` | 会话上下文来源 |
| 会议页前端四区 | `Demo-web/src/views/ai/meeting/` | 悬浮面板宿主、输入框宿主 |
| `jev-chat-jarvis` | GitHub | 交互语义参考（判断优先于生成、一键填入不代发） |

### 1.3 非目标（明确不做）

- **不自动发送任何消息**，不提供「一键发送」「自动回复」入口（代码层与测试层双重约束，见 §7.4）。
- 不做语音通道（TTS/ASR 已在 SP-1/2 链路），不接管 LiveKit data channel 消息（会中聊天仍为 P1）。
- 不做人脸/声学行为识别（SP-3/SP-4 范围），本设计只吃**文本转录 + 参会人上下文**。
- 不改 `Demo-web/prototype/` 之外的既有原型归档文件；不新增 npm 依赖；不改全局主题变量。
- 不做「Jev 判定=当事人定性」：判定结论一律标注「疑似/供主持人研判」，不作为证据或定性依据（沿用 SP-1/2 的措辞纪律）。

---

## 2. 范围（本次交付三段）

| 段 | 交付物 | 目的 |
|---|---|---|
| **S1 评审演示版** | `Demo-web/prototype/meeting-room.html` 增强：Jev 悬浮面板 + 可输入会中消息框 + 一键填入（双写）+ 手动发送 + `Jev` mock 适配器（可切真实 HTTP） | 让需求方在评审现场看到完整交互 |
| **S2 真实实现** | `Demo-ai` 新增 Jev 通道与 assist 编排/端点；`Demo-web` 新增悬浮面板组件 + composable + API + 输入框 | 真实会议页可用 |
| **S3 可复用契约** | 通用 `AssistContext` 契约、无会议耦合的 `JevPanel` 纯展示组件、接入指引（§10） | 其它模块（NERTC 视频Demo、Case办理页、Demo台）可接入 |

S1 与 S2 共用同一套**字段语义**（§4.3 判定字段、§7.2 面板数据结构），S1 的 mock 返回体按 S2 的响应结构构造，保证「原型所见 = 真实所得」。

---

## 3. 总体架构与数据流

```
┌── 前端（会议页 / 其它模块）──────────────────────────────┐
│ 转录缓冲 segments(useCaptionStream) ─┐                   │
│ 参会人/角色(useRoomSession)          ├→ 组装最近 N 段上下文│
│ JevPanel.vue（纯展示）               │                   │
│ ChatComposer.vue（可输入 + 手动发送）│                   │
└───────────────┬────────────────────┴───────────────────┘
                │ POST /admin-api/ai/meeting/assist/analyze { roomId, windowSize?, draftCount?, targetIdentity? }
┌───────────────▼─────────────────────────────────────────┐
│ ai-server                                            │
│ MeetingAssistController                               │
│  └ MeetingAssistService                               │
│     ├ AssistContextAssembler  ← 转录/参会人/场景       │
│     ├ AssistModelClient(Jev)  → ① judge                │
│     ├ AssistDraftGenerator(LLM) → ② 3 条草稿           │
│     └ AssistModelClient(Jev)  → ③ rank（6 题/一次调用） │
│ 响应：judge + drafts[]（含分数与排序）+ degraded 标记    │
└───────────────┬─────────────────────────────────────────┘
                │ JevClient（HTTP，独立熔断/超时/重试）
        ┌───────▼────────┐        ┌──────────────────┐
        │ Jev 独立服务     │        │ 我方 LLM 池        │
        │ POST {base}/jev │        │ prompt_template   │
        │ /v1/systemone   │        │ + jsonSchema      │
        └────────────────┘        └──────────────────┘
```

**调用序固定**：`judge → draft → rank`。判定失败则**不出草稿**（无判定依据的草稿会误导Demo员）；排序失败则**保留草稿并标注排序不可用**；任何一环都不伪造分数或结论（沿用 `MediaAnalysisServiceImpl` 的反面教材纪律）。

---

## 4. Jev 判定服务契约（定版）

### 4.1 传输层

**契约来源（2026-11-06 用户确认）**：以「Jev 能力 Demo」为准 —— `d:\work\kev\playground`（TypeSafe 兼容契约与 PRESETS 范例）+ `d:\work\kev\kev\serve.py`（服务端实现）+ `d:\work\kev\kev\api.py`（请求/答案归一化）。**该服务不提供 `score` 题型**（用户 2026-11-06 告知），故本设计的数值一律由 `choice` 档位 + 本地概率期望映射得到（见 §4.2）。

| 项 | 值 |
|---|---|
| 方法/路径 | `POST {jev.base-url}{jev.url}`；**已定版：`base-url=http://192.168.40.30:3000`（与既有 Kev 网关同一服务）、`url=/kev/v1/systemone`**（直连部署包 3008/3018 时为 `/v1/systemone`） |
| 模型 | **`jev-latest`**：该服务同时提供 `kev-latest` 与 `jev-latest` 两个别名，**同一权重**（jaredpalmer/kev-0.8b，Qwen3.5-0.8B-Base，temperature 2.35）；实测 `GET {base}/kev/v1/models` 返回两个别名 |
| 请求体 | `{"state": <Object|String>, "model": "<model>", "questions": { "<key>": {"type": "noul|choice", "instructions": "...", "criteria": {...}} }}` |
| 响应体 | `{"model": "...", "answers": {"<key>": {"type": "choice", "choice": "<选项名>", "confidence": 0.0-1.0, "probabilities": {"<选项名>": p}} \| {"type": "noul", "noul": p(yes)}}, "usage": {...}, "latency_ms": 1234}` |
| 答案语义 | `choice`：argmax 选项名 + 各选项概率 + 归一化置信度（0=均匀，1=确定）；`noul`：**只有 yes 的概率**（无文本）；`score`：**不支持** |
| 鉴权 | `Authorization: Bearer {jev.api-key}`（`jev.api-key` 为空则不发该头） |
| 超时 | connect 3s / read 5s（可配），重试 1 次（仅 429/5xx 重试；422 与其它 4xx 直接失败不重试） |
| 熔断 | 独立于 Kev 的 `SimpleCircuitBreaker`：`consecutiveFailures=5`、`windowMs=30s`、`errorRateThreshold=0.5`、`minCallsInWindow=5`、`openMs=30s`、`halfOpenMaxCalls=1` |
| 模型名 | `jev.default-model`（默认 `jev-latest`，与能力 Demo 的 `MODEL_NAMES` 一致；上线前与实际服务对齐） |
| 概率键 | `choice` → `criteria` 的选项名；`noul` → 仅 `noul` 字段（p(yes)） |

`state` 与 `questions` 由**调用方**构造，服务端只透传（与 `KevClient.systemOne` 一致）。Jev 服务不可用时不做「本地兜底判定」——宁可无结论，不伪造。

### 4.2 questions 设计（不使用 score 题型）

#### ① judge（1 次调用，5 题）

| key | type | criteria / 说明 | 用途 |
|---|---|---|---|
| `party_intent` | choice | `COOPERATE` 愿意配合 / `DISPUTE` 坚持争议 / `QUESTION` 追问澄清 / `REFUSE` 拒绝推进 / `EMOTIONAL` 情绪主导 / `WITHDRAW` 退出回避 / `SMALL_TALK` 无关话 | 对方意图 |
| `tension_level` | choice | `CALM` 平稳 / `LOW` 略紧 / `MID` 明显情绪化 / `HIGH` 激动指责 / `EXTREME` 失控威胁（**有序五档**） | 紧张程度 |
| `risk_level` | choice | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` | 风险等级 |
| `need_immediate_reply` | noul | instructions 问「是否需要主持人立即回应」 | 是否需立刻回复（取 `noul ≥ 0.5`） |
| `suggested_action` | choice | `ACK` 先安抚情绪 / `CLARIFY` 澄清事实 / `EXPLAIN` 说明程序 / `PROPOSE` 提出方案 / `PAUSE` 建议休会 / `ESCALATE` 升级处置 | 建议动作（**目录化**，因 noul 不返回文本） |

**数值映射（本地）**：
- 紧张度：`tension = round(Σ p(档位) × 档位分值)`，档位分值 `CALM=0 / LOW=25 / MID=50 / HIGH=75 / EXTREME=100`；映射缺失 → `null`（**不是 0**）。
- 紧张度**标签按期望分落档**（`≤12 平稳 / ≤37 略紧 / ≤62 明显情绪化 / ≤87 激动 / 其余 失控`），不用模型 argmax 档，否则会出现「70 分却标失控」的矛盾。
- 是否需立即回复：`need = noul ≥ 0.5`；置信度 `|noul − 0.5| × 2`。
- 建议动作：取 `suggested_action.choice` 的目录文案。

#### ② rank（1 次调用，4 题）

`state` 携带同一份上下文 **+ 3 条候选草稿**；`questions`：

| key | type | 说明 |
|---|---|---|
| `cand_1` / `cand_2` / `cand_3` | choice | 四档质量：`EXCELLENT` 可直接采用(92) / `GOOD` 较好可小改(76) / `ACCEPTABLE` 一般需重写(58) / `POOR` 不建议使用(32)；instructions 说明权重：与判定结论一致性 50% + 合规性（不代当事人表态/不承诺/不施压）30% + 可执行性 20% |
| `best_pick` | choice | `draft_1` / `draft_2` / `draft_3`，与最高分不一致时**以分数排序为准**并记 `disagreement=true`（交叉校验，不改排序） |

**排序分（本地）**：`score = round(Σ p(质量档) × 档位分值)`；缺失 → `null`（显示「未评分」，不显示 0）；排序按 `score` 降序，同分按生成顺序。

> 一次调用取 3 条分数，禁止 N 次逐条调用（成本与延迟）。

### 4.3 我方判定字段（对外契约，前后端一致）

```jsonc
{
  "judge": {
    "intent": "EMOTIONAL",
    "intentLabel": "情绪主导",
    "intentConfidence": 0.58,
    "tension": 70,                 // 0-100，由 choice 概率期望本地映射；缺失即 null
    "tensionLabel": "激动",         // 按期望分落档，非模型 argmax 档
    "risk": "HIGH",
    "riskLabel": "较高风险",
    "needImmediateReply": true,     // noul ≥ 0.5
    "needConfidence": 0.72,
    "suggestedAction": "ACK",
    "suggestedActionLabel": "先安抚情绪",
    "targetIdentity": "p3",        // 被判定对象（参会人 identity）
    "targetName": "王某某",
    "evidence": "转录「你们再逼我，别怪我不客气」 · 判定对象=王某某",
    "judgedAt": 1790000000000
  },
  "drafts": [
    { "id": "d1", "text": "……", "score": 67, "quality": "GOOD", "qualityLabel": "较好，可小改",
      "rank": 1, "style": "安抚+复述", "reason": "先承接情绪，避免对质" }
  ],
  "degraded": { "judge": false, "draft": false, "rank": false },
  "disagreement": false,           // best_pick 与最高分不一致时为 true（排序仍以分数为准）
  "latencyMs": 2410
}
```

**字段纪律**：`judge` 缺失即 `judge=null`（前端显示「判定服务不可用」）；`drafts[].score=null` 表示排序不可用，前端**不得显示 0 分或默认分**；`tension` 缺失即 null，**不得默认 0**（0 是有效值）。

---

## 5. 草稿生成契约（我方 LLM）

- 入口：`AiLLMCallService.callModelForStructuredJson(userQuery, promptCode, variables, jsonSchema)`（`Demo-ai/.../service/chat/AiLLMCallService.java`）。
- `promptCode = Demo_MEETING_ASSIST_DRAFT`（新增提示词模板，`ai_prompt_template` + `ai_prompt_template_key(key_name=user_query)`）。
- `variables`：`{user_query: <渲染好的上下文+判定结论>, format: <jsonSchema>}`（`{format}` 占位由渲染器支持，见 `AiLLMCallServiceImpl.renderTemplateManually`）。
- `jsonSchema`：

```jsonc
{"type":"object","properties":{"drafts":{"type":"array","minItems":3,"maxItems":3,
 "items":{"type":"object","properties":{
   "text":{"type":"string"},"style":{"type":"string"},"reason":{"type":"string"}},
   "required":["text","style","reason"]}}},"required":["drafts"]}
```

- **草稿硬约束**（写进提示词，且 rank 阶段作为 safety 维度复核）：
  1. Demo员第一人称口吻，不得替当事人表态、不得代签任何协议；
  2. 不得承诺赔偿/利息/时间表等实体承诺；
  3. 不得使用威胁、指责、羞辱性措辞；
  4. 长度 ≤ 120 字，一条一事；
  5. 三条风格必须不同（如：安抚复述 / 事实澄清 / 程序推进）。
- 生成失败（异常 / 空响应 / 非 object / 条数不足）→ `drafts=[]` 且 `degraded.draft=true`，**保留 judge 结论**。

---

## 6. 后端设计（`Demo-ai`，ai-server）

### 6.1 新增/改动清单

| 类型 | 文件 | 动作 |
|---|---|---|
| 配置 | `core/config/JevProperties.java` | 新增，`@ConfigurationProperties("jev")` |
| 客户端 | `core/client/JevClient.java` | 新增，仿 `KevClient`（重试/熔断/422 特判） |
| 出口 | `Demo-module-ai-api/.../api/ai/AiCapabilityApi.java` + `AiCapabilityApiImpl` + `AiCapabilityService(Impl)` + `dto/capability/JevSystemOneReqDTO/RespDTO` | 新增 `jev/system-one`（供其它服务 Feign 引用） |
| 服务 | `service/meeting/MeetingAssistService.java` + `impl/MeetingAssistServiceImpl.java` | 新增，编排 judge→draft→rank |
| 支持 | `service/meeting/support/AssistContextAssembler.java` | 新增，转录/参会人/场景 → `state` |
| 支持 | `service/meeting/support/AssistModelClient.java` | 新增，Jev judge/rank 调用 + `answers` 字段映射 |
| 支持 | `service/meeting/support/AssistDraftGenerator.java` | 新增，LLM 3 条草稿 |
| 支持 | `service/meeting/support/AssistPromptFactory.java` | 新增，渲染 `state` 文本 + 组装 `questions`（criteria 常量集中，避免散落） |
| 端点 | `controller/admin/meeting/MeetingAssistController.java` + `vo/`（4 个 VO） | 新增 3 个端点 |
| 开关 | `service/meeting/config/MeetingAnalyzeProperties.java` | 加 `assistGatePassed=true` |
| 开关 | `service/meeting/impl/MeetingAnalyzeSwitchServiceImpl.java` | `unavailableReason` 增加 `assist` 分支（平台总开关 + gatePassed + Jev 配置就绪） |
| Mapper | `dal/mysql/meeting/MeetingParticipantMapper.java` | 加 `selectByRoomId(Long roomId)` |
| 错误码 | `util/ErrorCodeConstants.java` | 追加 `1_040_061_008~011` |
| SQL | `Demo-ai/docs/sql/V3.61__meeting_assist_draft_prompt.sql` | 新增提示词模板种子 |

### 6.2 端点

| 方法 | 路径 | 权限点 | 请求 | 响应 |
|---|---|---|---|---|
| GET | `/admin-api/ai/meeting/assist/status?roomId=` | `ai:meeting:query` | — | `AssistStatusRespVO`：`enabled/available/reason/judgeModel/draftCount/jevConfigured/cost{judge,draft,rank,throttled,rejected}` |
| POST | `/admin-api/ai/meeting/assist/toggle` | `ai:meeting:analyze` | `{roomId, enabled, noticeConfirmed}` | `AssistStatusRespVO`（复用 `ai_meeting_analyze_switch` 的 `kind='assist'` 行；`noticeConfirmed=false` → 抛 `MEETING_ANALYZE_NOTICE_REQUIRED`） |
| POST | `/admin-api/ai/meeting/assist/analyze` | `ai:meeting:analyze` | `{roomId, windowSize?, draftCount?, targetIdentity?}` | `AssistAnalyzeRespVO`（§4.3） |

> **权限口径（用户 2026-11-06 定版）**：统一用既有 `ai:meeting:analyze` 判定「谁能用助手」，**不区分主持人/被授权人**（避免引入第二套授权体系）。设计中保留后续拆分 `ai:meeting:assist` 的路径，但本次**不新增权限点、不新增菜单行**（菜单号段 9499/9500 已占用，拆分时从 9512 起）。

### 6.3 开关与「零调用」纪律

- 复用 `ai_meeting_analyze_switch`（`room_id + kind` 唯一），新增 `kind='assist'`；开关**权威在服务端**，前端只照 `status` 渲染，绝不自行点亮。
- `available(assist) = 平台总开关 AND properties.gatePassed('assist') AND Jev 配置就绪(base-url/default-model 非空)`。
- **未开启 → analyze 直接拒绝，不产生任何 Jev/LLM 调用**（与 SP-1/2 同纪律）。

### 6.4 上下文组装（`AssistContext`）

通用契约（**跨模块可复用**，其它域只换 `scene` 与 criteria）：

```jsonc
{
  "conversation": [ { "seq": 12, "speaker": "王某某", "identity": "p3",
                      "role": "被申请人", "text": "……", "ts": 1790000000000, "audioLevel": -12 } ],
  "participants": [ { "identity": "p1", "name": "张旭辉", "role": "主持人" },
                     { "identity": "p3", "name": "王某某", "role": "被申请人" } ],
  "scene": { "domain": "Demo", "caseId": "2026-HZ-0381", "caseType": "借贷纠纷",
             "stage": "争议陈述", "extra": {} }
}
```

- 转录：`MeetingTranscriptService.listByRoom(roomId)` 全量升序 → 取最近 `windowSize` 段（默认 12，上限 40）。
- 参会人：`MeetingParticipantMapper.selectByRoomId(roomId)`（`role` 0 主持 / 1 参会 / 2 转录 worker）。
- 判定对象：显式 `targetIdentity` 优先；否则取「最近一条非主持人发言」。**主持人自己的发言不作为判定对象**。
- `scene.caseType/stage` 由调用方注入（会议页传Case类型与阶段；其它模块传自己的）。

### 6.5 节流、限流与成本

- 同一房间同一判定对象 **8s 内不重复**分析（沿用 `THROTTLE_MS=8000`）。
- 每房间 **6 次/分钟** 上限（沿用 `rateLimitPerMinute=6`）。
- 单次分析固定成本：**2 次 Jev + 1 次 LLM**；命中节流/限流 → `degraded` 不变但 `cost.throttled++`，返回明确文案「已跳过（节流）」。
- 计数写入 `MeetingAnalyzeCostRecorder`（键 `meeting:analyze:cost:{roomId}:assist_judge|assist_draft|assist_rank`）。

### 6.6 降级矩阵

| 故障 | 行为 |
|---|---|
| Jev 熔断打开 / 超时 / 4xx | `judge=null`、`drafts=[]`、`degraded.judge=true`，文案「判定服务不可用」；**不生成草稿** |
| Jev 返回体缺 `answers` / 字段类型不符 | 逐题降级为 null（不猜值），面板显示「—」 |
| LLM 失败 / 条数不足 | `judge` 保留、`drafts=[]`、`degraded.draft=true` |
| rank 失败 / 分数缺失 | `drafts` 保留（按生成顺序）、`score=null`、`degraded.rank=true` |
| 转录为空 | 直接返回 `judge=null` + 文案「暂无会话内容可分析」，零外呼 |
| 开关未开 / 无权限 | 403 / `MEETING_ANALYZE_NOTICE_REQUIRED`，零外呼 |

### 6.7 SQL

- `V3.61__meeting_assist_draft_prompt.sql`：插入 `ai_prompt_template`（code=`Demo_MEETING_ASSIST_DRAFT`，`model_id` 取 `ai_model` 里 `type=1` 的首个可用模型，幂等 `WHERE NOT EXISTS`）+ `ai_prompt_template_key`（`key_name='user_query'`、`public_status=1` SMALLINT）。
- **不新增表**：开关复用 `ai_meeting_analyze_switch`；草稿使用情况（是否被采用）本次**只在前端计数**，不落库（后续若要评估效果再补 `ai_meeting_assist_draft_log`）。
- **不新增菜单行**：权限点复用 `ai:meeting:analyze`。

---

## 7. 前端设计（`Demo-web`）

### 7.1 新增/改动清单

| 类型 | 文件 | 动作 |
|---|---|---|
| API | `src/api/ai/meeting.ts` | 新增 `getAssistStatus/toggleAssist/analyzeAssist` + 类型 `AssistStatus/AssistJudge/AssistDraft/AssistAnalyzeResult/AssistDegraded`（沿用该文件 `MEETING_BASE` + 具名函数风格） |
| 组件 | `src/views/ai/meeting/components/JevPanel.vue` | **纯展示**（props-only + emit），不引用任何会议专属 API，可被其它模块直接复用 |
| 组件 | `src/views/ai/meeting/components/ChatComposer.vue` | 会中消息输入框（受控 textarea + 发送按钮 + 回车发送），供「填入」与「手动发送」 |
| composable | `src/views/ai/meeting/composables/useJevAssist.ts` | 状态、analyze、fill、copy、权限判定、节流、错误提示、`JevSource` 适配层（http / demo） |
| 接入 | `src/views/ai/meeting/MeetingRoom.vue` | 挂载 `JevPanel`（右下角悬浮）+ `ChatComposer`（底部）+ 接线 |
| 接入 | `src/views/ai/meeting/components/ControlBar.vue` | 新增 `#btnJev` 开关按钮（仿 `#btnAi`） |
| 样式 | `src/views/ai/meeting/meeting.css` | 追加 `.jevpanel` / `.jev-draft` 等类（**仅在 `.meeting-room` 作用域内改**，不动全局变量） |
| 测试 | `src/views/ai/meeting/__tests__/` | 新增 `jevPanel.spec.ts`、`jevAssist.spec.ts`；改 `meetingLayout.spec.ts` 的 `vi.mock('@/api/ai/meeting')` 补新导出 |

### 7.2 面板结构与状态机

```
JevPanel（右下角悬浮，默认收起，ControlBar #btnJev 打开）
├ 头部：标题「Jev 会话辅助」· 开关（服务端权威）· 收起
├ 状态区：
│   ├ 无权限         → 「当前账号无 ai:meeting:analyze 权限」
│   ├ 未开启         → 说明 + 「开启（需向各方告知）」按钮
│   ├ 判定中/生成中/排序中 → 三段进度文案（阶段可见）
│   ├ 就绪           → 分析结果
│   └ 服务不可用     → 真实原因（不编造）
├ 分析区：意图 chip · 紧张度进度条 · 风险 chip · 是否需立即回复 chip · 建议动作 · 依据行
├ 候选区：3 条（按分降序）
│   └ 每条：分数条（score=null 时显示「未评分」）· 文本 · 风格/理由 · 「填入」「复制」
└ 预览区：面板内预览框（只读镜像，可直接改文案）+「复制全文」
```

### 7.3 交互流程

1. 主持人打开面板 → `getAssistStatus(roomId)` 渲染开关与可用性（**开关状态来自服务端**）。
2. 开启 → `toggleAssist({roomId, enabled:true, noticeConfirmed:true})`（服务端写 `ai_meeting_analyze_switch` + 审计）。
3. 点击「分析」→ `analyzeAssist({roomId, windowSize:12})` → 三段进度 → 渲染判定 + 3 条候选。
4. 点「填入」→ **同时**写入 ① 面板预览框 ② 底部 `ChatComposer` 的输入框；**不触发任何发送**；toast「已填入输入框，发送需你手动点击」。
5. 主持人可编辑文案 → 点「发送」→ 才产生一条会中消息（本地实现，见 §7.5）。
6. 复制按钮 → 写剪贴板（`navigator.clipboard`，失败降级为选中文本 + toast 提示）。

### 7.4 强制不变量（实现与测试双约束）

- `useJevAssist` **不暴露** `send` 能力；`fill(text)` 只写输入框状态。
- `ChatComposer` 的 `send` 事件只由**用户点击发送按钮或按下回车**触发；`JevPanel` 不持有 `ChatComposer` 引用（数据流单向：JevPanel → emit('fill') → MeetingRoom → composer 赋值）。
- 组件测试必须断言：点「填入」后 `chatMessages` 长度不变、`send` 事件未被触发。
- 代码评审检查项：任何 `fill` 路径都不得调用 `send`。

### 7.5 会中消息输入框（ChatComposer）

- 原 `ControlBar.vue` 的 `.draft` 是 `data-phase="P1"` 占位（`说点什么…`）→ 本次升级为**真实可输入**的会中消息输入框，标注「发送走 data channel 待 P1」。
- 发送行为：本地 `chatMessages` 数组（仅本端可见）+ toast「已发送（本地演示，data channel 待 P1）」；**不接 LiveKit data channel**（P1 范围）。
- 其它模块接入时，`ChatComposer` 可替换为真实聊天实现，助手侧契约不变。

### 7.6 其它模块接入方式

```ts
// 任意模块：只需提供状态与回调，面板不感知业务
<JevPanel :status="status" :judge="result?.judge" :drafts="result?.drafts ?? []"
          :loading="phase" :can-operate="canOperate" :degraded="result?.degraded"
          @fill="onFill" @copy="onCopy" @toggle="onToggle" @analyze="onAnalyze" />
```

接入方自己实现 `onAnalyze`（调本域后端或直接调 `/ai/meeting/assist/analyze`）与 `onFill`（写入本域输入框）。

---

## 8. 权限、合规与隐私

- **可见性**：助手面板与判定结论**仅对具备 `ai:meeting:analyze` 权限的账号可见**；Demo场景下当事人账号不应具备该权限（授权由 uaaa 管理，SQL 仅给 `role_id=1` 超管）。
- **知情告知**：开启前需向各方告知（沿用 `notice_confirmed` + 面板「开启」前的告知文案）。转录内容会**出域到独立部署的 Jev 服务**（外部模型服务），属敏感数据出域，需：
  1. 部署侧约束：Jev 服务部署在**内网/专线**，禁止公网暴露；
  2. 告知文案中明示「会话文本将提交给院内授权的辅助模型服务处理」；
  3. 后续若引入外部公网服务，须先过合规评审（不在本次范围）。
- **定性纪律**：判定与草稿均为「疑似/建议」，面板统一措辞「供主持人研判，不作为定性依据」，不写入Case记录、不进纪要（除非主持人主动引用）。
- **日志**：`[meeting]` 前缀；不打印完整转录全文、token、密钥；错误日志只记 key 与 code。
- **审计**：开关切换写 `AiConfigOperateLogService`（`MEETING_ANALYZE_TOGGLE` 同款），草稿「填入/发送」计数仅前端，不落库。

---

## 9. S1 评审演示版（原型 HTML）

`Demo-web/prototype/meeting-room.html`（**不入库**，`.gitignore` 已忽略 `/prototype/`）增量：

| 区块 | 内容 |
|---|---|
| 样式 | `.jevpanel`（右下角固定浮层 320px，可收起）、`.jev-judge`、`.jev-draft`、`.jev-bar`（分数条）、`.chatbox`（底部可输入消息框） |
| 脚本 | `JEV` 适配器：`systemOne(state, model, questions)` → mock 返回与 §4.3 同构的 `answers`；可切真实 HTTP（`?jevBase=` 或 localStorage，跨域需同源代理） |
| 状态 | `JV = {on, perm, phase, judge, drafts, degraded, preview}`；阶段 `'judge'|'draft'|'rank'|'ready'|'error'` |
| 交互 | 复用原型既有转录缓冲 `T`（取最近 12 段）与参会人 `P` 组装 `state`；`fill` 双写（面板预览 + 底部 chatbox）；发送按钮手动 |
| 演示 | 「模拟一段高风险发言」后自动可分析；沿用既有 `AN.perm` 按钮演示无权限态 |
| 边界 | 原型**不实现**真实 Jev 调用的鉴权/熔断；真实能力在 S2 |

**评审演示步骤（已实测通过）**：
1. 打开 `Demo-web/prototype/meeting-room.html` → 底部点「**Jev 辅助**」打开右下悬浮面板；
2. 面板内点「**开启助手**」（默认关闭，开启前有告知文案）；
3. 点「**插入一段发言**」（模拟 worker 回推定稿，可重复插入不同措辞）；
4. 点「**分析当前会话**」→ 三段进度（判定 → 生成草稿 → 打分排序）→ 出现分析结论与 3 条候选；
5. 点候选的「**填入输入框**」→ 文案同时进面板预览框与底部会中消息框，**底部消息区不出现任何消息**；
6. 手动点底部「**发送**」→ 才出现一条会中消息（本地 mock，data channel 待 P1）；
7. 降级演示：点「**模拟 Jev 不可用**」后再分析 → 面板只显示真实原因，**不出判定、不出草稿**；权限演示用 AI 分析面板的「以无权限账号预览」→ 助手面板只显示权限提示。

---

## 10. 跨模块复用契约（对外承诺）

| 层 | 复用单元 | 稳定契约 |
|---|---|---|
| 前端 | `JevPanel.vue` | props：`status/judge/drafts/loading/canOperate/degraded`；emits：`analyze/toggle/fill/copy`；**不 import 任何 `@/api`**，不感知 roomId |
| 前端 | `useJevAssist` | 通过 `JevSource` 接口注入数据源（`http`/`demo`），默认实现调 `/admin-api/ai/meeting/assist/*` |
| 后端 | `AssistContext` | `{conversation[], participants[], scene{}}`；域差异只体现在 `scene` 与 criteria |
| 后端 | `POST /ai/meeting/assist/analyze` | 入参 `roomId` + 可选 `windowSize/draftCount/targetIdentity`；其它模块可自带 roomId 语义或后续另开 `/ai/assist/analyze` 通用端点（本设计不预建） |

---

## 11. 测试与验收

### 11.1 后端（JUnit5 + Mockito，镜像被测包结构）

| 测试 | 断言 |
|---|---|
| `JevClientTest` | 请求体 `{state,model,questions}`；422 不重试；429/5xx 重试；熔断打开抛 `CircuitOpenException` |
| `AssistModelClientTest` | judge 四题解析（choice/score/noul 异构）；缺字段 → null 不猜值；rank 一次调用取 3 分数；`best_pick` 不一致 → `disagreement=true` 且排序不变 |
| `AssistContextAssemblerTest` | 最近 N 段截断；判定对象默认取非主持人最近发言；转录为空 → 直接短路 |
| `AssistDraftGeneratorTest` | schema 传入；失败 → `drafts=[]` + `degraded.draft=true`；保留 judge |
| `MeetingAssistServiceImplTest` | 调用序 judge→draft→rank；节流 8s；限流 6/min；三条降级路径；开关未开零外呼 |
| `MeetingAssistControllerTest`（`@WebMvcTest` 或 MockMvc） | 权限点缺失 → 403；`noticeConfirmed=false` → 业务异常 |

### 11.2 前端（vitest + jsdom）

| 测试 | 断言 |
|---|---|
| `jevAssist.spec.ts` | `answers` → 判定字段映射；`score=null` 不渲染 0；排序降序；降级文案；节流 |
| `jevPanel.spec.ts` | 三段进度渲染；无权限态不显示结论；点「填入」emit `fill` 且**不** emit 任何发送；`score=null` 显示「未评分」 |
| `chatComposer.spec.ts` | 只有点击发送/回车才 emit `send`；外部赋值不触发发送 |
| `meetingLayout.spec.ts`（改） | `vi.mock('@/api/ai/meeting')` 补齐新导出；整页不报错；面板默认收起 |

### 11.3 原型（S1）

一次性 jsdom 断言（脚本不入库，仿历史做法）：面板出现 / 判定渲染 / 填入双写 / 发送仅按钮触发 / 无权限态。

### 11.4 验收口径

- 「一键填入」后**没有任何消息被发出**（人工 + 自动断言双证）。
- Jev 不可用时面板**不出现**任何判定或草稿。
- 每条草稿都带来源分数或明确的「未评分」标记。

---

## 12. 交付清单

**S1 原型**：`Demo-web/prototype/meeting-room.html`（单文件增量）。

**S2 后端**（`Demo-ai`）：`JevProperties`、`JevClient`、`AiCapabilityApi(+Impl/Service/DTO)` 的 jev 出口、`MeetingAssistService(+Impl)`、`AssistContextAssembler`、`AssistModelClient`、`AssistDraftGenerator`、`AssistPromptFactory`、`MeetingAssistController` + 4 VO、`MeetingAnalyzeProperties`/`MeetingAnalyzeSwitchServiceImpl` 的 assist 分支、`MeetingParticipantMapper.selectByRoomId`、`ErrorCodeConstants` 4 个码、`V3.61` 提示词 SQL、6 个测试类。

**S2 前端**（`Demo-web`）：`api/ai/meeting.ts` 扩展、`JevPanel.vue`、`ChatComposer.vue`、`useJevAssist.ts`、`MeetingRoom.vue` 接线、`ControlBar.vue` 按钮、`meeting.css` 样式、3 个新测试 + 1 个改测试。

**S3 文档**：本设计 §10 接入指引（随本文档交付，不另建文档）。

---

## 13. 风险与未决

| # | 风险 | 处置 |
|---|---|---|
| R1 | Jev 独立服务的真实契约与模型名未定 | **已定（2026-11-06）**：契约以「Jev 能力 Demo」为准（§4.1），**无 score 题型**，数值改由 choice 档位 + 本地期望映射；`jev.default-model` 默认 `jev-latest`，上线前与实际服务对齐 |
| R2 | Jev 为外部服务，敏感文本出域 | 内网/专线部署 + 告知文案；公网暴露需先合规评审 |
| R3 | 判定误报可能带偏Demo员 | 措辞纪律（疑似/建议）+ 不自动发送 + 判定与草稿分离（判定失败即不出草稿） |
| R4 | 会中聊天仍是 P1（无 data channel） | ChatComposer 本地实现并显式标注；填入/发送链路已就绪，P1 只需替换发送通道 |
| R5 | 参会人 `role` 字段前端未接入 | 本次仅后端用于「判定对象=非主持人」，前端不伪造业务角色 |
| R6 | 每房间 6 次/分钟限流可能挡住密集发言 | 手动触发 + 节流；面板明示「已跳过（节流）」 |
| R7 | `ai_meeting_participant` 无参会查询方法 | 新增 `selectByRoomId`，缺失时降级为「按转录发言人推断」，不阻断 |

## 14. 未决事项（需上线前定版）

1. ~~Jev 服务实际 base-url、模型名、鉴权头、是否支持 `score` 题型~~ → **已定（2026-11-06，实测）**：**Jev 不再是「独立部署的新服务」，而是直接复用既有 Kev 决策服务** —— `base-url=http://192.168.40.30:3000`、`url=/kev/v1/systemone`、`model=jev-latest`（与 `kev-latest` 同服务同权重）、鉴权 `Authorization: Bearer`（当前 `kev.api-key` 为空即不鉴权）、**不支持 score**。配置已写入 `application.yaml` 与 `application-local.yaml` 的 `jev.*`（env：`JEV_BASE_URL/JEV_URL/JEV_MODEL/JEV_API_KEY`，默认回退 `KEV_*`）。
2. Jev 是否提供探活端点（当前设计**不依赖**探活，可用性以「配置就绪 + 调用结果」表达）。
3. `ai:meeting:assist` 是否从 `ai:meeting:analyze` 拆出（用户已定版本次不拆）。
4. 草稿使用效果是否落库统计（本次不落库）。
5. `Authorization: Bearer` 与既有 `KevClient` 的 `X-API-Key` 不一致：`JevProperties` 需支持 `jev.auth-header`（默认 `Authorization`）+ `jev.api-key`，便于两种部署形态切换。

---

## 15. 实施记录（2026-11-06）

### 15.1 实际交付清单

**后端 `Demo-ai`**

| 文件 | 说明 |
|---|---|
| `core/config/JevProperties.java` | 新增：`jev.base-url/url/default-model/api-key/auth-header/auth-header-template` + 熔断配置 + `configured()` |
| `core/client/JevClient.java` | 新增：`POST {base-url}{jev.url}`；422/4xx 不重试不计熔断、429/5xx 重试、独立熔断器、鉴权头可配 |
| `api/ai/dto/capability/JevSystemOneReqDTO/RespDTO.java` | 新增：透传契约（`state/model/questions` ↔ `model/answers/usage/latencyMs`） |
| `api/ai/AiCapabilityApi(.Impl)` + `AiCapabilityService(Impl)` | 新增 `POST /admin-api/ai/capability/jev/system-one`（透传，供其它服务 Feign 引用） |
| `service/meeting/support/AssistContext.java` | 新增：通用会话契约 `{conversation[], participants[], scene{}}` + `toState()` |
| `service/meeting/support/AssistContextAssembler.java` | 新增：转录+参会人 → 上下文；判定对象=最近一段非主持人/非 worker 发言；窗口默认 12、上限 40 |
| `service/meeting/support/AssistPromptFactory.java` | 新增：judge/rank 题目包 + 档位分值 + 中文标签 + `expectedScore` + `tensionBandOf` + `renderStateText` |
| `service/meeting/support/AssistJudge.java` / `AssistDraft.java` | 新增：判定结论与候选草稿 POJO（缺失字段即 null） |
| `service/meeting/support/AssistModelClient.java` | 新增：Jev judge/rank 调用与字段映射；**不提供本地兜底判定** |
| `service/meeting/support/AssistDraftGenerator.java` | 新增：LLM 生成 3 条草稿（promptCode `Demo_MEETING_ASSIST_DRAFT` + JSON Schema）；失败抛异常不返半成品 |
| `service/meeting/MeetingAssistSwitchService(+Impl)` | 新增：开关行复用 `ai_meeting_analyze_switch` 的 `kind='assist'`；可用性=平台开关 AND `assistGatePassed` AND Jev 配置就绪 |
| `service/meeting/MeetingAssistService(+Impl)` | 新增：编排 judge→draft→rank；8s 节流 + 6 次/分限流 + 成本计数 + 三条降级路径 |
| `controller/admin/meeting/MeetingAssistController.java` + 4 VO | 新增：`GET /ai/meeting/assist/status`、`POST /assist/toggle`、`POST /assist/analyze` |
| `dal/mysql/meeting/MeetingParticipantMapper.java` | 加 `selectByRoomId` |
| `service/meeting/config/MeetingAnalyzeProperties.java` | 加 `assistGatePassed`（默认 true） |
| `service/meeting/support/MeetingAnalyzeCostRecorder.java` | 加 `assist_judge/assist_draft/assist_rank` 计数 |
| `util/ErrorCodeConstants.java` | 加 `1_040_061_008~011`（会话为空 / 判定不可用 / 草稿失败 / 助手未开启） |
| `docs/sql/V3.61__meeting_assist_draft_prompt.sql` | 新增：提示词模板 `Demo_MEETING_ASSIST_DRAFT` + 模板变量 `user_query` |

**前端 `Demo-web`**

| 文件 | 说明 |
|---|---|
| `src/api/ai/meeting.ts` | 加 assist 类型 + `getAssistStatus/toggleAssist/analyzeAssist` |
| `src/views/ai/meeting/components/JevPanel.vue` | 新增：**纯展示**（不 import `@/api`、不感知 roomId），props/emit 跨模块复用 |
| `src/views/ai/meeting/components/ChatComposer.vue` | 新增：会中消息输入框，**只有点发送/回车才 emit('send')** |
| `src/views/ai/meeting/composables/useJevAssist.ts` | 新增：状态 + `JevAssistSource` 注入式数据源；**无 send 出口** |
| `MeetingRoom.vue` / `ControlBar.vue` / `MeetingIcon.vue` / `meeting.css` | 接线：`#btnJev` 开关悬浮面板、消息框替换原 `.draft` 占位、`spark` 图标、SP-6 样式 |
### 15.2 与设计文档的偏差（已定版）

| # | 设计原口径 | 实际实现 | 原因 |
|---|---|---|---|
| D1 | 复用 `MeetingAnalyzeSwitchService`（kind 走 `AnalyzeKind`） | 新增独立 `MeetingAssistSwitchService`，开关行仍复用 `ai_meeting_analyze_switch`（kind='assist'） | `AnalyzeKind` 合法集被 SP-1/2 契约锁死为 voice/ser/video，助手不应混进「AI 分析」卡片列表 |
| D2 | Jev 鉴权沿用 Kev 的 `X-API-Key` | `JevProperties.authHeader` 可配，默认 `Authorization: Bearer {key}` | 能力 Demo 用 `Authorization: Bearer`，两套部署形态都能覆盖 |
| D3 | `suggested_action` 为 noul 自由文本 | 改为 `choice` 动作目录（6 档） | noul 只返回 yes 概率、不返回文本 |
| D4 | 紧张度/草稿分值用 score | 改为 `choice` 档位 + 本地概率期望映射 | 用户告知 Jev 不支持 score |
| D5 | 排序失败时草稿仍带分数 | 排序失败 → `score=null`，显示「未评分」 | 不伪造分数 |

### 15.3 测试结果（2026-11-06）

| 套件 | 结果 |
|---|---|
| `JevClientTest` | 7 passed（请求体三字段 / 422 不重试不计熔断 / 4xx 不重试 / 熔断快速失败 / 网络错误重试 / 未配置零外呼 / 鉴权头） |
| `AssistModelClientTest` | 5 passed（choice+noul 映射 / 缺字段即 null / 判定空抛错 / 排序降序+best_pick 冲突 / 排序不可用不伪造分） |
| `AssistDraftGeneratorTest` | 5 passed（3 条解析 / 未成功抛错 / 非法 JSON / 条数不足 / 去代码围栏） |
| `AssistContextAssemblerTest` | 5 passed（空转录短路 / 窗口截断 / 判定对象默认非主持人 / 显式 target 优先 / state 结构） |
| `MeetingAssistServiceImplTest` | 7 passed（开关未开零外呼 / 会话为空零外呼 / 调用序 / 三条降级 / 节流跳过） |
| 前端 `src/views/ai/meeting/__tests__` | **11 文件 / 77 用例全绿**（新增 jevPanel 5、chatComposer 5、jevAssist 6；meetingLayout 补 1 例） |

### 15.4 上线前必做

1. 配置 `jev.base-url`（内网/专线部署的 Jev 服务）与 `jev.default-model`（默认 `jev-latest`）；否则助手返回「Jev 决策服务未配置」。
2. 执行 `Demo-ai/docs/sql/V3.61__meeting_assist_draft_prompt.sql`（幂等，可重复执行）。
3. 告知文案需覆盖「会话文本将提交给院内授权的判定模型服务处理」（数据出域到 Jev 服务）。
4. 助手权限沿用 `ai:meeting:analyze`：当事人账号**不得**授予该权限点。
---

## 16. 其它模块接入指引（可执行版）

### 16.1 前端（任意模块，数行接线）

```vue
<script setup lang="ts">
import JevPanel from '@/views/ai/meeting/components/JevPanel.vue'   // 纯展示组件，不绑定会议
// jevStatus / jevResult 由本域数据源填充
async function onAnalyze() {
  // 调本域后端，或直接调 /admin-api/ai/meeting/assist/analyze
  jevResult.value = await analyzeAssist({ roomId: roomId.value })
}
function onFill(text: string) {
  myInputRef.value.setText(text)   // 只写输入框；发送由用户手动触发
}
</script>

<template>
  <JevPanel
    :status="jevStatus" :judge="jevResult?.judge" :drafts="jevResult?.drafts ?? []"
    :phase="'ready'" :can-operate="true" :degraded="jevResult?.degraded"
    :preview="preview" @analyze="onAnalyze" @fill="onFill" @update:preview="preview = $event"
  />
</template>
```

约束：`JevPanel` 不 import 任何 `@/api`；调用方自己实现「分析」与「填入」；**发送永远由调用方的输入框组件负责**。

### 16.2 后端

- 直接复用：前端调 `POST /admin-api/ai/meeting/assist/analyze`（`/admin-api/ai` 已在 vite 代理与 Nginx 分流中）。
- 自建编排：复用 `AssistModelClient`（judge/rank 映射）+ `AssistDraftGenerator`（草稿）+ 自建上下文（实现 `AssistContext`），域差异只体现在 `scene` 与 criteria。
- 换 Jev 部署形态：只改 `JevProperties`（base-url / model / 鉴权头），代码零改动。

### 16.3 契约边界（不可越界的三条）

1. **助手永不发送**：`useJevAssist` 无 send 出口；`ChatComposer.send` 只由用户点击/回车触发。
2. **不伪造**：判定失败不出草稿；草稿失败保留判定；排序失败草稿未评分；缺失值一律 null（不填 0）。
3. **服务端权威**：开关状态、成本计数、降级标记全部来自服务端返回，前端不得自行点亮或补默认值。
### 15.5 Jev 服务复用与真实调用实测（2026-11-06）

**结论：Jev 不是新服务，而是既有 Kev 决策服务的 `jev-latest` 别名**（同一权重 jaredpalmer/kev-0.8b / Qwen3.5-0.8B-Base，temperature 2.35）。`GET http://192.168.40.30:3000/kev/v1/models` 实测返回 `kev-latest` 与 `jev-latest` 两个别名 → 配置直接复用 Kev 的地址与鉴权，`JevClient` 保持独立客户端（独立熔断、独立超时），避免与既有风险分级互相牵连。

**真实调用实测（冒烟脚本 `Demo-ai/docs/jev-smoke-test.ps1`）**

| 环节 | 结果 |
|---|---|
| judge（choice×4 + noul×1） | 70.3ms，`model=jev-latest`；`party_intent=EMOTIONAL/DISPUTE`、`tension_level=HIGH`、`risk_level=CRITICAL`、`need_immediate_reply` noul=0.5851（→ 需立即回复）、`suggested_action=ESCALATE` |
| rank（题干预内嵌候选正文） | 52.9ms；三条候选各自返回不同分布（cand_1 POOR 0.086 / cand_2 POOR 0.097 / cand_3 EXCELLENT 0.408），`best_pick=d3` |
| 4B 权重（直连 3018） | **未启动**（connection refused）→ 现场只有 0.8B |

**实测暴露的两个语义问题与已落地的修正**

| # | 问题 | 修正（已实施） |
|---|---|---|
| E1 | 题目只写「这条候选回复的质量如何」时，三道同构题返回**几乎相同**的概率分布（无区分度）→ 排序完全不可用 | rank 题目改为**把候选全文内嵌进 `instructions`**（实测分布随候选变化，方向正确） |
| E2 | 0.8B 逐条打分置信度仅 0.02~0.11，且**会把含威胁的「施压回击」判为 EXCELLENT 并排到第一**（实测两次） | ① 新增**本地合规词表兜底**（`AssistPromptFactory.complianceViolation`）：命中威胁/施压/指责/代当事人表态/承诺类词的草稿在 `AssistDraftGenerator` 阶段**直接剔除**，全被剔除则判「草稿生成失败」；② 逐条 `confidence` 随草稿透出到前端，面板明示「排序为低置信参考」；③ `best_pick` **只作冲突标记**，不参与排序 |

> 结论口径（写进 UI 文案）：**判定（judge）可用**（粗粒度分类，argmax 方向与语义一致）；**排序（rank）仅作参考**，必须以本地合规过滤后的候选为准，且不得据此断言「某条文案更好」。

### 15.6 配置与 SQL 落地状态

| 项 | 状态 |
|---|---|
| `application.yaml` / `application-local.yaml` 的 `jev.*` | **已落地**（`base-url`/`url`/`default-model`/`api-key`/`auth-header`/`auth-header-template`/超时/重试/熔断），env 前缀 `JEV_*`，默认回退 `KEV_*` |
| `meeting.analyze.assist-gate-passed` | **已落地**（默认 true；Jev 已内网部署并实测可达） |
| `V3.61__meeting_assist_draft_prompt.sql`（提示词模板） | **已由用户执行** |
| `V3.62__meeting_assist_permission_guard.sql`（权限守护） | **已生成待执行**：幂等确保 `ai:meeting:analyze`(9499)/`ai:meeting:alert-ack`(9500) 菜单 → 只授予 `role_id=1` 超管 → **防御性回收**「当事人/申请人/被申请人/PARTY」类角色已有的该权限 → 末尾附核查查询（人工确认清单里没有当事人类角色） |
| 告知文案 | **已落地**（面板「默认关闭」块 + 操作区提示 + 开启 toast）：「会话文本将提交给**院内授权的判定模型服务（Jev，内网部署）**处理」 |
| 冒烟脚本 | `Demo-ai/docs/jev-smoke-test.ps1`（探活 + judge + rank，只读，可反复执行） |
### 15.7 前端「助手状态获取失败：服务端不可达」误报修正（2026-11-06）

**现象**：会议页打开 Jev 面板后状态区显示「助手状态获取失败：服务端不可达」，但后端其实正常。

**排查结论（逐层实测）**

| 层 | 实测结果 | 判定 |
|---|---|---|
| ai-server 8086 直连 | `GET /admin-api/ai/meeting/assist/status?roomId=1` → HTTP 200 + `{"code":401,"msg":"账号未登录"}` | 端点**已注册**（新增 `MeetingAssistController` 生效，后端已重启加载新代码）；失败在**鉴权** |
| 网关 8080 | 同上，返回同样的 401 | 网关路由 `/admin-api/ai/**` 正常 |
| vite 5173（前端同源路径） | `/api/admin-api/ai/meeting/assist/status?roomId=1` → 200 + `{"code":401,...}` | 前端 → 网关 → ai-server **链路全通** |
| 结论 | — | **不是「服务端不可达」**，而是请求被鉴权拒绝（登录态失效 401，或账号缺权限点 403）；前端把 401/403/404/网络错误**一律压成「服务端不可达」**，把真实原因掩盖了 |

**修正（已实施）**

1. `useJevAssist` 新增 `describeAssistError(e)`，把失败分为 `unauthenticated` / `forbidden` / `not-deployed` / `network` / `server` / `unknown` 六类，各带**真实原因**（后端 `msg` 优先）与**可执行提示**：
   - 401 → 「登录态已失效，请重新登录后再开启助手」
   - 403 → 「缺权限点：查状态需 `ai:meeting:query`，开启与分析需 `ai:meeting:analyze`（执行 V3.62 授权后重试）」
   - 404 → 「后端未包含 assist 端点：ai-server 需重新构建并重启」
   - 无响应 → 「确认 ai-server(8086) 与网关(8080) 已启动，vite 代理目标 `VITE_AI_PROXY_TARGET` 正确」
   - 5xx → 「查看 ai-server 日志 [meeting] 段」
2. 面板新增 `errorKind` / `errorHint` 两个 prop，失败时**红底显示真实原因 + 排查提示**（不再只报一句「服务端不可达」）。
3. `loadStatus` / `toggle` / `analyze` 三处统一走该分类器；服务端 `available=false` 时直接回显 `status.reason`。
4. 新增前端用例 6 条（`jevAssist.spec.ts`），锁定「不得笼统报服务端不可达」的分类行为。