
# 会议室四区布局重构 + 会中 AI 风险分析（SP-1 分析外壳 / SP-2 文本情感+音量）设计

> **修订索引（2026-11-04，以 `2026-11-04-meeting-ai-spec-review-and-revision.md` 为准）**
> 本文主体保留作为设计对照，以下结论已被用户裁决或读码复核推翻，实施时以评审方案为准：
> **实施定版指针（2026-11-05）**：本文实施以 `2026-11-05-meeting-ai-specs-implementation.md` 的 D1–D6 为准；`AnalyzeSource.toggle(kind,enabled)` 两参、同意 scope 五值、`available(kind)` 统一门禁见评审方案 §3 与 §6.1。
> 1. **§3.7 主色判给 `--accent-cyan #1A5FB4` 作废**，§9 有意差异③、§12 自检对应结论同步作废。用户裁决按原型绿 `#00A870`，新增 `--meeting-accent` 等会议专有 token 且**作用域限定会议根容器**（新文件 `meeting.css`），全局 `variables.css` 既有变量取值一个不动。
> 2. **§3.7 行号/色值引用错误**：`.know` 底色是原型 `:230` 的 `#eaf2ff`（`border #bedaff`），`:233` 的 `#f6fff9` 是 `.acard[data-on=1]` 背景；P1 角标在 `:218`（`#eaf2ff/#4080ff`），`:136`/`:115` 分别是 banner 底色与 tile focus 描边。P2 为 `#fff3e8/#ff7d00`。
> 3. **§3.1 `focusPinned`（点击钉住焦点、说话不抢回、钉徽标）删除**：原型只有点击切 `st.focus`，无钉住态。钉住列为 P1 可选增强。
> 4. **§4.1.1 `kind=video` 判定行替换为统一门禁**：`available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)`；未通过时 `enabled=false/available=false/不写开关行/不产该 kind 告警`，`reason` 给真实原因（服务未部署、门禁未过、缺单独同意）。门禁通过后才允许翻转，且需 `noticeConfirmed` + 有效单独同意。
> 5. **§3.2 组件契约补充**：`MeetingStatus` 融入 `MeetingTopBar`（连接态四态文案 + `ConnectionQualityChanged` 驱动质量）；`btnMinutes` 接 `MinutesDrawer`、`btnEnd` 走二次确认 + `endRoom` + 开抽屉（原型仅 toast 占位，属有意差异）；视频卡语义改为「人像到场一致性核验（CompreFace 1:1）」，原型的行为理解描述为示意。
> 6. **§3.3 迁移映射补充**：SSE 订阅抽 `useCaptionStream`，渲染迁 `TranscriptPanel`；`captions.ts` 四个纯函数与 `tileAttach.spec.ts` 三例保留并扩展；新增可选 SSE 事件 `partial` 与 `alert`，旧后端不发送时按定稿降级、未知事件忽略；`VideoGrid/CaptionPanel/ParticipantList` 确认仅被 `MeetingRoom.vue` 引用后删除。
> 7. **§3.5 同意口径统一**：`noticeConfirmed` 降级为操作人确认动作（写审计），不再充当单独同意凭据；统一走 `ai_party_consent.scope`（`VOICE_ANALYZE|IDCARD_VERIFY|FACE_COMPARE|SER_ANALYSIS`），`version` 等值、撤回置 `revoked_at`。
> 8. **§10.3「原型 jsdom 79 断言全绿」标注为外部一次性验证**：脚本不在仓库、被 `.gitignore` 排除且不在 vitest include 内，不可复现；本轮验收以 `src/views/ai/meeting/__tests__/` 下新增 vitest 为准。§0.4 双前缀「实测响应」同理，仓库内无留档，以注册路径推导 + 新增路径断言单测为准。
> 9. **工程能力订正**：前端权限判断是 `accessStore.hasAccess(code)` 而非 `hasPermission`；`request.ts` 无 `patch`（删除叫 `del`）；`getRoom` 已定义但从未调用，顶栏 `caseCode` 无数据链，改显示 `Case #caseId`，不虚构Case编号字符串；成员「未入会」分组在无名单接口时显示明确空态。
> 10. **§1.2 非目标中 SP-5 描述**以 `2026-11-04-party-identity-verification-design.md` 的拆分结论为准（证件 OCR 文本一致性 = SP-5 P1；人像 1:1 = SP-3，本轮改用 CompreFace verification 1:1）。
> 11. **SP-4 实施同步（2026-11-06）**：按 `2026-11-04-acoustic-ser-design.md` §0 的四处修订已随实施落地 —— ①开关 `kind` 合法集由 `voice|video` 扩为 `voice|ser|video`（第三张卡由服务端返回驱动，S1）；②`ai_meeting_alert` 的单列唯一索引 `uk_ai_meeting_alert_transcript` 已由 `V3.55` DROP 并重建为 `(transcript_id, kind) WHERE deleted = FALSE` 部分唯一索引（S2，破坏性修订；回滚须先删 `kind='ser'` 行）；③§8 不变量②的「`video` 永远不产告警行」改按统一门禁 `available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)` 判定，门禁通过后允许翻转，未通过时 `video=false` 且 reason 给真实原因；④§11「SP-4 立项必须先解决 137 并发容量」由 SER 独立服务（不调 137）＋ 分支 B 一级门命中段筛选 ＋ §8.3 阈值自动降级解决。SP-4 逐项实施状态与**未完成的 PoC 门禁**见该文档 §13.1。

- 日期：2026-11-04
- 状态：待用户复核（原型已评审通过：`Demo-web/prototype/meeting-room.html`，925 行；jsdom 断言为外部一次性验证，见修订索引 8）
- 上游文档：`2026-11-03-meeting-ai-capability-design.md`（会议 Demo 与能力地图，本文只写增量与差异）
- 落地范围：`Demo-web`（会议室前端）、`Demo-ai`（后端 + livekit-worker）、`Demo-ai/docs/sql`（迁移）
- 本文所有接口路径、字段名、错误码、菜单 ID、迁移号、CSS 变量名均以**读码 + 运行时实测**为准，出处逐条标在 §2

---

## 0. 与 2026-11-03 文档的三处边界差异（评审先读这里）

| # | 2026-11-03 原文 | 本文的决定 | 差异性质 | 理由 |
|---|---|---|---|---|
| D1 | §1.2 非目标逐字列了「共享屏幕」 | 屏幕共享**提前进 P0**，纯前端 `getDisplayMedia` + LiveKit `publishVideoTrack` 实现，不新增后端接口 | 范围扩大 | 腾讯会议同构布局里共享是舞台区一等公民（`#btnShare`、缩略条、画中画）；砍掉它四区布局就缺一整块状态，评审看不出舞台的三种形态（演讲者/宫格/共享）到底能不能自洽 |
| D2 | §1.2 非目标列了「会中视频理解的实时帧采样」；§4.2 E 项写明「会后离线为主」 | 会中帧采样**进入设计但排在 P1**（SP-3），本文给出采样频率、检出边界与不承诺项；P0 只交付 SP-2 文本情感+音量 | 边界改写 | 原设计把它整体划为非目标会让「AI 分析」Tab 在 P0 只剩语音一半，界面与文案要提前定稿，否则 SP-3 来了要返工；本期用「能力卡片显式标注不可用 + 点击无效」把边界画清楚，而不是假装存在 |
| D3 | §4.2 E/§2 把视频/图像/STT 理解当作「离线已具备」的既有资产（`MediaAnalysisService`） | **推翻该结论**：`MediaAnalysisServiceImpl` 逐方法返回硬编码模拟值（`analyzeSentimentInternal` 恒 `"calm"`、`speechToText` 返回 `"这是模拟的语音转文字结果..."`、`analyzeVideo` 的 `keyFrames` 为空集合），而 `getCapabilities()` 却汇报 `sentimentEnabled=true / visionEnabled=true / videoEnabled=true`；据此把人脸+视觉（SP-3）、声学情感 SER（SP-4）、身份证 1:1 核验（SP-5）**各自独立成文**，不进本 spec | 事实纠正 + 拆分 | 伪能力一旦被当作既有资产，spec 会写成「复用即可」，实现时才发现要从零部署。本文只承诺代码里真跑得通的东西：`AiLLMCallService.callModelForStructuredJson(...)`、livekit-worker 的 VAD+ASR 链路、SSE 分发 |

### 0.4 本次读码新发现的 P0 阻塞缺陷（不属于差异，属于必修）

`MeetingTranscriptInternalController` 现位于包 `com.tianque.module.ai.controller.admin.meeting`，类上写的是字面量
`@RequestMapping("/admin-api/ai/meeting/internal")`，而其 javadoc 声称「置于 `controller.internal` 包，框架不会追加前缀」——**该 javadoc 与事实不符**。框架 `TianqueWebAutoConfiguration#webMvcRegistrations` 对
`@RestController` 且包名匹配 `**.controller.admin.**`（`WebProperties.adminApi` 默认值）的类追加 `/admin-api` 前缀，于是真实注册路径变成 `/admin-api/admin-api/ai/meeting/internal/transcript`。

2026-11-04 直连 ai-server（`:8086`）实测：

| 请求 | 响应 | 判读 |
|---|---|---|
| `POST /admin-api/ai/meeting/internal/transcript?roomSid=x`（`X-Internal-Token: wrong`） | `{"code":401,"msg":"账号未登录"}` | 无该 handler，落到安全链兜底 |
| `POST /admin-api/admin-api/ai/meeting/internal/transcript?roomSid=x` | `{"code":1040061002,"msg":"转录内部回推密钥无效"}` | **命中的是这个双前缀路径**（已进入 service 层密钥校验） |

`worker.py` 推送的是 `f"{JAVA_BASE}/admin-api/ai/meeting/internal/transcript"`（`worker.py:43`），因此**当前分支上转录回推必然失败**，而 worker 侧 `push()` 只 `print` 异常（`worker.py:50`），失败静默。引入原因：提交 `20902b1 refactor(module-ai): 重构 agent 和 superagent 包为统一分层结构` 把该文件从 `ai/meeting/controller/internal/` 移到 `ai/controller/admin/meeting/`（`git log --follow` 的 R089 记录），移动时未同步改 `@RequestMapping` 字面量。

**修复方案（P0，本 spec §6.5）**：保持包位置不变，把 mapping 字面量改为 `/ai/meeting/internal`，最终注册为 `/admin-api/ai/meeting/internal/transcript`——与 `worker.py` 现网调用、与 2026-11-03 §3.3 接口表**三者一致**，不改 worker、不改网关。SP-2 的告警链路挂在 `ingest()` 之后，此缺陷不修则整条链路无从验收。

---

## 1. 目标与范围

### 1.1 本期目标（P0）

1. `MeetingRoom.vue` 由「页头 + 网格 + 控制条 + 双列面板」的流式布局，重构为腾讯会议同构的**四区固定布局**：顶栏 48px / 舞台（主画面 + 缩略条 + 画中画 + 字幕叠加条 + 风险条）/ 右侧栏 320px（成员·转录·会议信息·**AI 分析**四 Tab）/ 底部控制栏 68px。
2. 右侧栏新增第 4 个 Tab「AI 分析」= **SP-1 分析外壳**：服务端权威的开关、权限降级、知情告知条、三级告警流、统计与筛选、Tab 未读角标、舞台 danger 红条。
3. **SP-2 语音情感分析**：对已定稿转录分段做两级判定（本地冲突词表 + 音量 → 命中才送大模型），同一发言人 8s 节流 + 每分钟调用上限，产出 danger/warn/info 三级告警并随纪要留存、写审计。
4. 修复 §0.4 的转录回推双前缀缺陷；修复远端音频不发声缺陷（§3.6）。
5. 色值全面对齐 `src/styles/variables.css` 主题变量，会议界面专有 token 集中新增（§3.7）。

### 1.2 非目标（本期明确不做，逐条给归属）

| 项 | 归属 | 界面如何交代 |
|---|---|---|
| 人脸识别与身份比对、会中帧采样 | SP-3（独立 spec） | 「视频行为分析」卡片标 `SP-3 · P1`，`available=false` + 不可用原因，点击无效 |
| 声学情感（SER，137 无 emotion 端点、需自建模型服务） | SP-4（独立 spec） | 语音卡片文案只说「文本 + 音量」，不出现「声纹/语调」字样 |
| 证件 **OCR 文本一致性核验**（姓名 + 公民身份号码 vs `party_identity` 底库；跨服务取数 + 敏感个人信息 + 单独同意前置门 + 留存期） | **SP-5 本期（P1，独立 spec，零新模型、零 GPU）** | 不出现在 AI 分析 Tab，入口在当事人档案页；结论只表述「系统内自洽性校验」，不代表身份真实性认证 |
| 身份证人像 **1:1 比对**（证件照 vs 会中/现场人脸、活体） | **移交 SP-3**（CompreFace `POST /api/v1/verification/verify` 两图比对；不建 subject 底库、不建人脸向量表、平台不持有向量） | 不出现在 AI 分析 Tab；复用 SP-5 的 `ai_party_consent` 的 `FACE_COMPARE` 取值，不另建同意模型 |
| 邀请入会、会中聊天、举手 | P1 | 按钮带 `P1` 角标，点击提示需后端接口 |
| 录制/Egress、会议管控（静音他人、移出）、设置 | P2 | 置灰 + `P2` 角标 + title 说明前置条件（token `roomAdmin` / Egress） |
| 逐方知情告知记录落库（每个参与人的告知时间、告知人、告知方式） | P1 | **后端已落（2026-11-07，`V3.63` `ai_meeting_notice_record` + 菜单 9505/9507，字段范围定版见 `2026-11-07-dev-closure-round5.md` §2）**：只记「已告知」事实，不构成单独同意；会议侧 UI 待接线 |
| 告警自动休会、自动通知安保等处置动作 | 不做 | 告警只呈现，处置始终由人 |

### 1.3 子项目拆分

```
SP-1 分析外壳        本文 §3 §4 §6 §7     P0   无新增算法，纯交互 + 权限 + 落库 + SSE
SP-2 文本情感+音量   本文 §5 §6 §8        P0   零新部署：复用 callModelForStructuredJson + worker 既有 PCM
SP-3 人脸 + 视觉     独立 spec（待写）    P1   insightface 自建内网容器 + 人像底库表 + 帧采样
SP-4 声学 SER        独立 spec（待写）    P1   137 无 emotion 端点，需新模型服务
SP-5 证件 OCR 文本核验 独立 spec         P1   跨服务取底库 + 单独同意 + 留存期合规；人像 1:1 移交 SP-3（CompreFace）
```

---

## 2. 读码核实的事实基线（本设计的唯一依据）

| 主题 | 事实 | 出处 |
|---|---|---|
| 既有会议端点 | `POST /ai/meeting/room/create`(`ai:meeting:create`)、`POST /ai/meeting/token`(`ai:meeting:join`)、`GET /room/get`、`GET /room/page`(`ai:meeting:query`)、`POST /room/end`(`ai:meeting:update`)、`GET /transcript/stream`(SSE，`@PermitAll`) | `MeetingController.java:43-124` |
| 纪要端点真实形态 | `GET /ai/meeting/minutes/draft?roomId=`、`POST /ai/meeting/minutes/confirm`(body `MinutesConfirmReqVO`)——**不是** 11-03 §3.3 写的路径变量式 `/draft/{roomId}` | `MeetingMinutesController.java:26-48`、`api/ai/meeting.ts:73-78` |
| 转录回推端点 | 类级 `@PermitAll`，鉴权实为 service 层比对 `X-Internal-Token` 与配置 `meeting.internal-transcript-token`；当前注册路径被双前缀污染 | `MeetingTranscriptInternalController.java:29-46`、`MeetingTranscriptServiceImpl.java:50-54` |
| 分段字段 | `TranscriptSegmentVO { speakerIdentity, text, startTs(Long ms), endTs(Long ms) }`，**无 audioLevel** | `TranscriptSegmentVO.java:9-19` |
| ingest 行为 | 密钥校验 → 按 `roomSid` 查房 → `selectMaxSeq(roomId)+1` 起算 → 逐段 insert → `pushToRoom` | `MeetingTranscriptServiceImpl.java:59-71` |
| SSE 事件名与负载 | `SseEmitter.event().name("transcript").data(row)`，data 是整个 `MeetingTranscriptDO`（含 `id/seq/roomId`）；超时 30 分钟；连接池 `ConcurrentHashMap<Long, CopyOnWriteArrayList<SseEmitter>>` 自管理 | `MeetingTranscriptServiceImpl.java:36,78-91` |
| 前端 SSE 解析 | 裸 `fetch` + `Authorization`/`tenant-id` 头，按 `\n\n` 切帧，**只接受 `event: transcript`**，其余忽略（新增事件类型天然向后兼容） | `CaptionPanel.vue:26-42,51-55` |
| worker 音频形态 | `rtc.AudioStream(track, sample_rate=16000, num_channels=1)` + silero VAD，`END_OF_SPEECH` 时手里就有该段完整 `pcm: bytearray` → **算 RMS 得 dBFS 零额外采集**；逐轨 `asyncio.create_task` 并发；push 失败仅 `print` | `worker.py:34,53-80,87` |
| 大模型结构化调用 | `ChatModelResponse callModelForStructuredJson(String userQuery, String promptCode, Map<String,String> variables, String jsonSchema)`；多模态变体 `callModelForStructuredJsonWithMedia(byte[], String mimeType, String ptCode, Map)` | `AiLLMCallService.java`（`service/chat`） |
| 审计 | `AiConfigOperateLogService.record(String type, String content)` / `record(String type, String content, String result)`，常量 `RESULT_SUCCESS="success"`、`RESULT_FAIL="fail"` | `AiConfigOperateLogService.java` |
| Redis | ai-server 内已注入 `RedisTemplate<String,Object>`（`BaseChatServiceImpl:134`、`SuperagentChatServiceImpl:84`）→ 节流用 `setIfAbsent(key, v, Duration)`，上限用计数器 | 上述两文件 |
| 错误码已占区间 | 会议段 `1_040_061_000…004` 已用；语音段 `1_040_062_000…006` 已用 | `module/ai/util/ErrorCodeConstants.java:255-268` |
| 菜单 ID 已占区间 | `9490–9494` 会议（V3.46）、`9495–9498` 语音演示（V3.47）；`9499+` 经全仓 SQL 扫描无占用 | `V3.46__meeting_menu.sql:13,23-43`、`V3.47__voice_demo_menu.sql:14,24-43` |
| 迁移号 | 最新为 `V3.48__meeting_minutes_prompt.sql` → 本文用 V3.49/3.50/3.51 | `docs/sql` 目录列举 |
| 提示词表范式 | `ai_prompt_template(code,title,prompt_template,model_id,status,public_status BOOLEAN,sort,tenant_id,…)` + `ai_prompt_template_key(tenant_id,key_name,extractor,template_id,remark,status,model_id,public_status SMALLINT,label,sort,…)`；模型须同租户 `tenant_id=1` 且 `type=1` | `V3.48__meeting_minutes_prompt.sql:8-23` 及头部注释 |
| 137 语音服务 | 仅 ASR/TTS/VAD/S2S 四形态，**无 emotion 端点**；`/v1/pool` `size:1` 近串行；无 `/health` | 11-03 §2.1 表 + §2.1 并发段（本次复核 `voice.gateway.*` 配置仅 `asr-model/tts-model/default-voice`） |
| 人脸能力 | 全仓（`Demo-ai` + `Demo-platform-biz`）grep `insightface\|face_recognition\|FaceEmbed\|arcface\|人脸检测` **零命中**；无人像底库表 | grep 结果（本文 §1.2） |
| 主题变量 | `src/styles/variables.css`：`--bg-page/--bg-card/--bg-gray #fafafa`、`--border-glow #e2e8f0`、`--text-primary #1b2a4a`、`--text-dim #64748b`、`--accent-cyan #1A5FB4`、`--accent-green #26A569`、`--accent-yellow #E5A50A`、`--accent-red #C01C28`、`--accent-orange #f59e0b`、`--risk-high #C01C28`、`--risk-mid #E5A50A`、`--risk-low #26A569`；`stores/app.ts:101 primaryColor = ref('#1A5FB4')` | `variables.css:6-70`、`stores/app.ts:101` |
| 前端既有护栏 | `__tests__/tileAttach.spec.ts` 三例（本地/远端 track 晚到仍 attach、关摄像头 detach）；`captions.ts` 四个纯函数；`MeetingRoom.vue` 用 `shallowRef speakers`（内含 track 实例，防深层 unwrap）、`identity` 重连复用、`describeConnectFailure` 五层原因分类 | `MeetingRoom.vue:29-30,52-84,102-128` |
| 部署边界 | 网关 `Path=/admin-api/ai/**` 原样转发到 `ai-server`；`WhiteListConfig.paths` **不含** `/admin-api/ai/meeting/internal/**` → worker 必须直连 ai-server（`:8086`），经网关必 401 | `Demo-gateway/application.yaml:66-71`、`WhiteListConfig.java:21-57` |

---

## 3. 四区布局重构（SP-1 的界面承载）

### 3.1 区域与尺寸

```
┌──────────────────────────── MeetingTopBar  48px ────────────────────────────┐
│ 会议标题 · Case号 · 计时 00:00:00 · 录制徽标(默认隐藏,P2) │ 质量 · 视图 · 设置(P2) · 全屏 · 侧栏 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                        │  SidePanel  320px                  │
│   StageView                            │  ┌ 成员 │ 转录 │ 会议信息 │ AI 分析① ┐ │
│   ├ StageMain（演讲者 / 宫格 / 共享）    │  ├ pane ────────────────────────┤ │
│   ├ ThumbStrip  96px（≤1023px 时 72px） │  │ ParticipantPanel             │ │
│   ├ Pip（非焦点的本地自视图）            │  │ TranscriptPanel              │ │
│   ├ Banner「正在讲话：X」               │  │ RoomInfoCard                 │ │
│   ├ RiskBanner（danger 红条，覆盖态）    │  │ AnalysisPanel  ← SP-1        │ │
│   └ CaptionOverlay（字幕叠加条）         │  └──────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ 聊天入口(P1) │ 麦 像 共享 │ 邀请(P1) 成员 聊天(P1) 举手(P1) │ AI 分析 字幕 纪要 录制(P2) 会控(P2) │ 结束 │
└──────────────────────── ControlBar  68px ────────────────────────────────────┘
```

| 约束 | 取值 | 说明 |
|---|---|---|
| 顶栏 / 侧栏 / 控制条 / 缩略条高度宽度 | `--meeting-top: 48px`、`--meeting-side: 320px`、`--meeting-bar: 68px`、`--meeting-strip: 96px` | 与原型 `:root` 同值；折叠侧栏时 `--meeting-side: 0` |
| 1024–1439px | 侧栏转为**浮层**（`position:absolute; right:0; top:48px; bottom:68px; z-index:12` + 左投影） | 原型 `@media (max-width:1439px)` 同款：小屏不挤压舞台 |
| ≤1023px | `--meeting-strip: 72px`、缩略 tile 宽 116px、隐藏会中聊天入口 | 原型 `@media (max-width:1023px)` |
| 宫格列数 | `cols(n) = clamp(1, ceil(sqrt(n)), innerWidth < 1024 ? 2 : 3)` | 原型 `cols()` 逐字移植，避免评审后二次调整 |
| 焦点来源 | **【2026-11-04 订正：删除 `focusPinned`】** 演讲者模式下焦点 = 手动点击缩略条/主画面 tile 设定的 `identity`，默认本地参与者；说话高亮只改 `data-cam` 描边，不抢焦点、不显示钉徽标 | 原型只有「点击切 `st.focus`」，无钉住态；钉住/自动追焦列为 P1 可选增强，需原型同步后再评审 |

### 3.2 组件契约（`src/views/ai/meeting/`）

| 组件 / 文件 | 职责 | props | emits / 暴露 | 分期 |
|---|---|---|---|---|
| `MeetingRoom.vue` | 编排四区 + 会话生命周期；持有 `room` 实例与 `speakers` | 路由 query `roomId`、`identity` | — | P0 |
| `composables/useRoomSession.ts` | 从 `MeetingRoom.vue` 抽出 `join/reconnect/leave/refresh/describeConnectFailure`（逻辑逐字保留，只搬家不改写） | `roomId` | `{ connState, lastError, connecting, speakers, identity, join, reconnect, leave }` | P0 |
| `components/MeetingTopBar.vue` | 标题/Case/计时/质量/视图切换/全屏/侧栏折叠；`#rec` 徽标默认 `display:none` | `title, caseCode, elapsed, qualityLv, mode, sideOpen` | `update:mode`, `update:sideOpen`, `toggle-full` | P0 |
| `components/StageView.vue` | 主画面 + 缩略条 + PiP + banner + risk banner + 字幕叠加条；**唯一**能重建 tile DOM 的地方 | `speakers, mode, focus, sharing, captionText, captionWho, risk` | `set-focus` | P0 |
| `components/LocalTile.vue` / `RemoteTile.vue` | 单 track 卡（沿用，仅按 §3.6 修音频与色值） | `tile: ParticipantTile` | — | P0 |
| `components/CaptionOverlay.vue` | 舞台底部两行叠加（说话人 + 当前句），`data-cap=0` 时整体隐藏 | `who, text, visible` | — | P0 |
| `components/SidePanel.vue` | 四 Tab + 未读角标 `<i class="acnt">` + 折叠 | `tab, alertUnread, canAnalyze` | `update:tab` | P0 |
| `components/ParticipantPanel.vue` | 会议中/未入会分组 + 搜索 + 行内操作（P1 呼叫、P2 静音/移出 置灰） | `speakers` | — | P0（按钮 P1/P2） |
| `components/TranscriptPanel.vue` | 转录滚动 + 情感 chip + 告警跳转高亮（`data-hit`） | `segments, jumpId` | `jump-ack` | P0 |
| `components/RoomInfoPanel.vue` | 房间号/Case/参与者数/字幕状态/**AI 风险分析状态行**/知情提示 | `room, captionOn, analyzeStates` | — | P0 |
| `components/AnalysisPanel.vue` | SP-1 主体：两张开关卡 + 知情条 + 降级条 + 统计 + 筛选 + 告警流 + 演示条 | `states, alerts, cost, filter, perm, loading` | `toggle(kind)`, `ack(id)`, `jump(id)`, `update:filter` | P0 |
| `components/ControlBar.vue` | 15 个按钮（含新增 `AI 分析`）+ 结束；每项带 `data-phase` | `mic, cam, sharing, capOn, sideOpen, tab, busy, connState` | 同名 `update:*` + `leave/end/reconnect` | P0 |
| `analyze.ts` | 纯函数（§10.2 可测）：`applySwitch`、`unreadCount`、`filterAlerts`、`sortAlerts`、`dedupeAlerts`、`levelTag`、`switchHint` | — | — | P0 |
| `api/ai/meeting.ts` | 追加 §6 的 5 个方法与 6 个类型 | — | — | P0 |

**舞台重绘禁令（写进组件注释与用例）**：`AnalysisPanel`/告警链路**只重绘右栏与 banner 文案，绝不触发 `StageView` 的 tile 重建**——重建 `<video>` 会让已 attach 的真实摄像头画面反复闪断。落地方式：风险状态用 `stage.dataset.risk` + 独立 `RiskBanner` 元素表达，不进 `speakers` 派生链。

### 3.3 与现有 `MeetingRoom.vue` 的迁移映射

| 现状（282 行） | 去向 |
|---|---|
| `a-page-header` + 页面级 `a-alert` | `MeetingTopBar` + `useRoomSession` 抛出的 `lastError`（错误分层文案**逐条保留**，含「permissions denied → 缺 `roomJoin` grant」这类判别，不得退回笼统「检查网络」） |
| `VideoGrid` | 并入 `StageView`（演讲者/宫格/共享三态），`VideoGrid.vue` 删除 |
| `a-row` 双列（`ParticipantList` + `CaptionPanel`） | `SidePanel` 的两个 Tab pane；`CaptionPanel` 的 SSE 订阅逻辑上移为 `useCaptionStream.ts`，把「订阅」与「渲染」分离（渲染仍在 `TranscriptPanel`） |
| `ControlBar` | 扩为 15 项 + `data-phase`，`@leave/@end/@reconnect` 契约不变 |
| `MinutesDrawer` | 不动 |
| 模块顶层 `const room = new Room()` | **必须**移入 `useRoomSession`（setup 内创建），现状写法在 HMR/多实例下共享同一 Room，属隐患 |

### 3.4 键盘与可达性

`M` 麦、`E` 摄像头、`F` 全屏、`Esc` 退全屏（与原型 legend 一致）；Tab 焦点顺序 = 顶栏→舞台→侧栏 Tab→告警卡操作→控制条；所有开关按钮 `aria-pressed`，Tab 用 `role=tablist/aria-selected`（原型已如此，落地不得降级）；告警卡对读屏输出完整句子（等级 + 「疑似」措辞 + 发言人），不允许只读图标。

### 3.5 数据与文案的所有权

- **开关状态**：服务端唯一权威（§4.1）。前端 `localStorage` 只存视图偏好（`mode`/`side`/`tab`/`cap`），**不存分析开关**（原型用 `localStorage` 模拟是演示手段，实现禁止沿用）。
- **告警文案**：由后端 `AlertLevel.getMessage()` 返回并落库（`reason` 存模型依据摘要），前端只渲染，不拼接定性语句。
- **发言人身份**：取 LiveKit `participantIdentity` / `ai_meeting_participant.identity`，告警依据栏固定写「身份取自参会轨 `identity=<identity>`（非人脸推断）」。

### 3.6 必修的真实缺陷（远端声音）

`RemoteTile.vue` 现两处叠加导致**远端参会者声音听不见**：

1. `<video v-if="tile.videoTrack" ref="videoEl" ... muted>` —— 无画面时元素根本不存在，`sync()` 里「无画面则把音频轨挂到同一元素」的 `else if` 分支不可达（`RemoteTile.vue:22-25`）。
2. 有画面时元素带 `muted`，即便 attach 了音频也不出声。

修法：音频与视频分离——`<audio>` 专用元素（无 `muted`）始终渲染并 attach `audioTrack`，`<video muted>` 只负责画面；`sync()` 改为 `videoEl`/`audioEl` 各自判空，`flush:'post'` 与无参 `detach()` 的既有约束保留。新增用例见 §10.2。

### 3.7 色值统一（原型变量 → 主题 token）

规则：**组件内不得出现十六进制字面量**；主题无对应语义的会议专有量，统一在 `src/styles/variables.css` 新增「会议界面」分组，而不是各组件各写一套。

| 原型（`meeting-room.html`） | 值 | 落地取值 | 备注 |
|---|---|---|---|
| `--accent` | `#00a870` 腾讯绿 | **新增 `--meeting-accent: #00A870`**（会议模块局部 token，作用域限定会议根容器） | **【2026-11-04 用户裁决修订】** 原判给 `--accent-cyan #1A5FB4` 的结论作废：用户要求与原型效果一致，按原型绿；全局 `variables.css` 既有变量取值一个不动，仅在 `meeting.css` 定义会议专有 token。说话中高亮、Tab 下划线、开关开启态、chip 一律用 `--meeting-accent` |
| `--danger` | `#f53f3f` | `--risk-high` `#C01C28` | danger 红条、危险计数、角标 |
| `--warn` | `#ff7d00` | `--risk-mid` `#E5A50A` | warn |
| info / `#52c41a`（`RemoteTile .speaking`） | 绿 | `--risk-low` `#26A569` | 硬编码绿一并收编 |
| `--chrome` | `#fff`（`meeting-room.html:9`） | `--bg-card` | 卡片与面板底色，直接用主题既有 token，不新增取值 |
| `--line` | `#e5e6eb`（`:10`） | `--border-glow` `#e2e8f0` | 分隔线与描边；两值仅差 3–4 阶亮度，肉眼不可辨，**以主题为准** |
| `--text` | `#1d2129`（`:11`） | `--text-primary` `#1b2a4a` | 正文色，主题偏蓝黑，接受 |
| `--sub` | `#86909c`（`:12`；另有散落的 `#a8a29a` 字面量，`:588`） | `--text-dim` `#64748b` | 原型两个次级灰一律归一到 `--text-dim`，不得并存 |
| `--tint` | `#f2f3f5`（`:13`） | `--bg-gray` `#fafafa` | 浅底容器与表头 |
| `--stage`、`--tile` | `#14161a`、`#1f2226`（`:14`、`:15`；另有 `RemoteTile.vue:50` 的 `#1f1f1f`） | **新增** `--meeting-stage: #14161a`、`--meeting-tile: #1f2226` | 深色舞台是会议专有，主题无该语义；**取值逐字沿用已评审通过的原型**，不另调新值；`RemoteTile.vue:50` 的 `#1f1f1f` 收到 `--meeting-tile` |
| `--hit`（`.tr[data-hit]` 行高亮） | `#fffbe6`（`:275`；`:194` 是 `.notice` 底色，非行高亮） | **新增** `--meeting-hit: rgba(229,165,10,.14)` | 由原型行高亮 `#fffbe6` 派生的半透明版，避免与告警黄争权；色值来源以 `:275` 为准（C05 订正） |
| 知情条 `.know` 底 | `#eaf2ff` + `border #bedaff`（`:230`） | 原型蓝底 + 蓝描边，会议局部 token 承接 | 2026-11-06 就地订正（C05）：旧稿写成 `#f6fff9`（`:233`）并判「原型绿底作废」属行号与色值双误；`:233` 实为 `.acard[data-on=1]` 背景。原型知情条本来就与 P1 角标同蓝系，不改全局主题 |
| P1 角标底色与字色 | `#eaf2ff`、`#4080ff`（`:218`） | 会议局部 token 承接原型蓝系 | 2026-11-06 就地订正（C05）：旧稿标的 `:136`/`:115` 实为 banner 底色与 tile focus 描边，P1 角标只在 `:218` |
| P2 角标底 | `#fff3e8` / `var(--warn)=#ff7d00`（`:219`；`:171` 是 `.chip.sys`） | **新增** `--meeting-p2-bg: rgba(245,158,11,.12)` | 由 `--accent-orange` 派生；原型 `:171` 为系统轨 chip，非角标 |
| tile 名字条底 | `rgba(0,0,0,.4)` | **新增** `--meeting-overlay: rgba(0,0,0,.45)` | 深色舞台上的半透明名字底；微调到 `.45` 以保证字幕与姓名的对比度 |

【2026-11-04 用户裁决修订】新增 token 清单改为**落在会议模块局部样式文件 `meeting.css`，作用域限定会议根容器，不改 `variables.css`**：色 `--meeting-accent`（`#00A870` 原型绿）及其亮色/浅底变体、`--meeting-stage`、`--meeting-tile`、`--meeting-hit`（`#fffbe6` 派生）、`--meeting-p2-bg`、`--meeting-overlay`；尺寸 `--meeting-top`、`--meeting-side`、`--meeting-bar`、`--meeting-strip`。全局 `variables.css` 既有变量取值一个不动（其注释存在编码乱码现象，故**不改写该文件**，新文件按 UTF-8 写入）。原「落 `variables.css` 的 `:root` 共 9 个」结论作废。

---

## 4. SP-1 分析外壳

### 4.1 开关权威在服务端

```
前端 AnalysisPanel 点开关
   → POST /ai/meeting/analyze/toggle {roomId, kind, enabled, noticeConfirmed}
   → 服务端判定（§4.1.1）
   → 返回 AnalyzeToggleRespVO{ kind, enabled(实际生效), available, reason }
   → 前端【无条件】以返回值渲染卡片，不保留本地期望值
```

#### 4.1.1 服务端判定规则（逐条可实现，无自由裁量）

| 条件（自上而下短路） | `enabled` | `available` | `reason` | 是否落库 |
|---|---|---|---|---|
| `kind` ∉ {`voice`,`ser`,`video`}（SP-4 实施同步，S1 扩合法集） | — | — | 抛 `1_040_061_005` | 否 |
| 当前用户无 `ai:meeting:analyze` | — | — | 由 `@PreAuthorize` 返回 403 | 否 |
| `meeting.analyze.enabled=false` | `false` | `false` | 「会中风险分析已被平台配置关闭」 | 否 |
| `kind=video`（**统一门禁，2026-11-04 替换原「本期未交付」行**） | `false` 直到门禁通过 | `平台开关 AND 探活成功 AND g3Passed` | 未通过时给真实原因：人脸服务未部署 / G0–G3 门禁未过 / 缺 `FACE_COMPARE` 单独同意；门禁通过后按 `kind=voice` 同规则处理 | 未通过时否（不写开关行，避免「已开启」假象）；通过后 upsert + 审计 |
| `kind=voice`、`enabled=true`、`noticeConfirmed!=true` | `false` | `true` | 「开启前须确认已向各方告知」，抛 `1_040_061_006` | 否 |
| `kind=voice`、`enabled=true`、`noticeConfirmed=true` | `true` | `true` | `null` | upsert 开关行 + 审计 |
| `kind=voice`、`enabled=false` | `false` | `true` | `null` | upsert 开关行 + 审计 |

- 关闭必须真正停止分析：`ingest()` 后提交给分析器前**先查开关**（§8 步骤 3），开关行为 `false` 时直接返回，一次模型调用都不发。
- 会议结束（`/room/end`）后开关行只读；再次入会须重新确认告知。
- `GET /ai/meeting/analyze/status?roomId=` 返回两张卡片的完整状态（含 `label`、`sp`、`phase`、`available`、`reason`），前端**进面板即调一次**，据此渲染——即「默认不打开」由服务端保证，而非前端默认值。

### 4.2 权限与降级

| 权限点 | 授予能力 | 菜单 | 缺失时表现 |
|---|---|---|---|
| `ai:meeting:analyze` | 查看开关状态 + 切换开关 | 9499（`type=3`，父 9491） | 卡片开关 `disabled`，面板顶部 `.deg` 条：「当前账号无「会中风险分析」权限：开关不可操作，仅可查看历史告警」；`status` 接口照常可读（`ai:meeting:query` 已覆盖读） |
| `ai:meeting:alert-ack` | 点「已知悉」 | 9500（`type=3`，父 9491） | 告警卡只显状态不显按钮 |

后端二次校验不可省（`@PreAuthorize`），前端 `hasPermission` 只做视觉降级；403 走全局拦截提示，不静默。

### 4.3 知情告知

- 任一能力开启即在面板顶部常驻 `.know`：「本会议已开启 AI 风险分析：告警与依据随纪要留存并写入审计日志，仅供主持人研判，**不作为定性依据**。开启前请向各方告知。」
- P0 落地面：`noticeConfirmed` 必传（服务端拒绝未确认的开启，`1_040_061_006`）+ `AiConfigOperateLogService.record("MEETING_ANALYZE_TOGGLE", "roomId=<id> kind=<k> enabled=<v> noticeConfirmed=true", "success")`。
- P0 不落地面：逐参与人的告知时间/方式记录（§1.2 归 P1）。会议信息 Tab 的 `.notice` 保留「入会前请向各方告知并留存知情记录」。

### 4.4 告警等级与文案（`AlertLevel` 枚举，后端唯一来源）

| level | code | `message`（固定文案，含「疑似/请确认」） | 舞台红条 | Tab 角标 | 随纪要 |
|---|---|---|---|---|---|
| `danger` | 3 | `疑似威胁性表述——请主持人确认，必要时休会或转线下` | 是（15s 自动撤下，人工知悉后一并撤下） | 计入未读 | 是 |
| `warn` | 2 | `情绪明显激动（anger）——建议主持人安抚或短暂休会` | 否 | 计入未读 | 是 |
| `info` | 1 | `音量升高、语气偏激动——留意冲突升级` | 否 | 计入未读 | 是 |

全部告警的展示句式统一为「`<发言人>`：<message>」，禁止出现「认定/构成/构成威胁」等定性措辞；`evidence`（模型摘录的原文片段）作为依据并列展示。

### 4.5 面板信息层次（自上而下，与原型一致）

1. `.know` 知情条（任一开启）→ 2. `.deg` 降级条（无权限）→ 3. 语音卡片 → 4. 视频卡片（含 `.err` 不可用原因）→ 5. `.stats`（已分析 N 段 / 危险 / 提醒 / 信息）→ 6. `.bywho` 筛选（全部 + 三级 + 出现过的发言人）→ 7. `.alist` 告警卡（等级徽标 + 发言人 + 来源类型 + 时刻 + message + 依据栏「转录原文 · 音量 X dBFS · 情感 Y · identity=…」 + 「已知悉 / 定位原文」）→ 8. `.dev` 演示条（生产构建剔除，`import.meta.env.DEV` 包裹）。

开关运行态文案：`分析中 · 已送模型 N 次（规则命中 M，8s 节流跳过 K）`，计数来自 `GET /ai/meeting/analyze/cost?roomId=`（§6），让「成本可控」在界面上可验证而非口头承诺。

---

## 5. SP-2 语音情感分析（文本 + 音量，零新部署）

### 5.1 音量信号来源

`worker.py` 在 `END_OF_SPEECH` 时已持有该段完整 PCM，就地计算：

```python
rms = math.sqrt(sum(x * x for x in samples) / len(samples))   # samples = int16 mono 16k
audio_level = 20 * math.log10(rms / 32768) if rms > 0 else -96.0
```

`push()` 的分段体新增 `audioLevel`（`float`，dBFS，四舍五入到整数即可）。Java 侧 `TranscriptSegmentVO.audioLevel`（`Short`，**可空**）+ `ai_meeting_transcript.audio_level`（`SMALLINT NULL`）。**可空是硬要求**：worker 未升级时字段为 `null`，一级门退化为「仅词表」，不得 NPE、不得因此丢分析。

### 5.2 一级门（本地零成本，`RiskLexicon`）

词表与原型 `LEXICON` 逐字一致，宁宽勿漏（精度交给二级门与「疑似」措辞）：

| 命中层级 | 词 |
|---|---|
| `danger` | `逼我`、`收拾`、`弄死`、`不客气`、`没完`、`告你们`、`滚` |
| `warn` | `凭什么`、`闭嘴`、`骗`、`不讲理`、`欺人太甚`、`过分` |

匹配：`text.contains(word)` 逐词表按 danger→warn 优先级，首个命中即定位层级与预设情感（danger→`anger/威胁`，warn→`anger`）。

**送模型条件**：`词表命中 || (audioLevel != null && audioLevel >= -18)`。二者皆无 → 直接结束，本次零模型调用（这是 P0 最重要的成本控制，必须在单测里以 `verify(llmCallService, never())` 钉死）。

### 5.3 二级门（大模型情感分类）

```java
llmCallService.callModelForStructuredJson(text, emotionPromptCode, variables, EMOTION_JSON_SCHEMA);
```

`variables`：`{ "speakerRole": <ai_meeting_participant.role 对应中文>, "recentTopics": <该发言人前 2 段转录，用 ｜ 连接，不足则空串> }`。

JSON Schema（写死为 Java 常量 `EMOTION_JSON_SCHEMA`）：

```json
{"type":"object",
 "properties":{
   "emotion":{"type":"string","enum":["calm","anxious","agitated","anger","threat"]},
   "level":{"type":"string","enum":["info","warn","danger"]},
   "confidence":{"type":"number","minimum":0,"maximum":1},
   "evidence":{"type":"string"}},
 "required":["emotion","level","confidence","evidence"]}
```

裁决规则（冲突时取更保守的一侧，防止模型一句 `info` 把词表的 `danger` 吞掉）：

- `finalLevel = max(levelFromLexicon, levelFromModel)`，`max` 按 danger>warn>info 排序；词表未命中时取模型值。
- `confidence < 0.6` → 降一级（danger→warn、warn→info），并在 `reason` 追加「（模型置信度较低）」。
- `emotion=calm` 且词表未命中 → **不落告警**，只把情感写回 `ai_meeting_transcript`（走 `alert` 事件的 `silenced=true` 变体？否——写回不走 SSE，仅落库，避免刷屏）。

提示词模板 `Demo_MEETING_EMOTION`（V3.51 落库，`user_query` 为待判定分段）：

> 你是Demo会中的情绪风险提示助手。给你一句已定稿的转录原文、说话人角色与其前文，判断说话人当下的情绪与风险等级。只依据文本与前文事实，不做任何法律或事实认定。`level` 取 info/warn/danger：出现对他人的威胁、伤害暗示取 danger；明显愤怒、敌意取 warn；仅情绪偏激动取 info。`evidence` 摘录原文中最关键的连续片段（≤20 字）。

### 5.4 节流与上限（Redis，多实例安全）

| 用途 | 键 | 值/TTL | 判定 |
|---|---|---|---|
| 同一发言人 8s 节流 | `ai:meeting:analyze:throttle:{roomId}:{identity}` | `"1"`，TTL `meeting.analyze.throttle-seconds`（默认 8s） | `setIfAbsent` 返回 `false` → 跳过模型调用，`throttled++` |
| 每房间每分钟模型调用上限 | `ai:meeting:analyze:ratelimit:{roomId}:{yyyyMMddHHmm}` | 计数，TTL 60s | `increment` 后 > `max-model-calls-per-minute`（默认 6）→ 跳过，`rejected++`，`log.warn` 一条 |
| 房间开关缓存 | `ai:meeting:analyze:switch:{roomId}:{kind}` | `"1"/"0"`，TTL 60s + 变更时主动删 | 减少 `ingest` 路径上的 DB 读 |

单会议（4 人）成本上限推导：30 分钟会议转录分段约 180–300 段 → 一级门命中估 25–35% → 节流后模型调用理论封顶 `4 人 × 30 分 = 120` 次，而分钟上限把它压到 `6 × 30 = 180` 次不构成约束，真正约束来自节流；**预期实际 20–45 次/场**，每次约 1.2k 输入 token + 120 输出 token。展示口径：`models`（已送模型）/`rules`（一级门命中）/`throttled`（节流跳过）/`rejected`（超分钟上限拒送）四个计数。

### 5.5 异步与失败

- 分析**不得阻塞** `ingest()`：worker 侧 `push` 的 `timeout=10s`，而 VL/LLM 单次 1.5–4s，同步会把字幕链路拖垮。`ingest()` 落库并推 `transcript` 事件后，把分段提交给专用线程池（§6.6）。
- 模型异常/超时/非法 JSON → `log.warn("[meeting-analyze] roomId={} transcriptId={} 分析失败: {}", ...)`，**不产告警、不重试**（宁缺毋滥；缺的是提示，错的是伤害）。
- 队列 `AbortPolicy` 丢弃时记 `rejected++` 并 warn 一条，绝不 CallerRuns（否则 worker 回推线程被拖累）。

### 5.6 幂等

`ai_meeting_alert.transcript_id` 建唯一索引 `uk_ai_meeting_alert_transcript`：一条转录分段至多一条告警，worker 重推或 SSE 重连后重复分析不会叠加告警。

> 【SP-4 实施同步，S2 破坏性修订】上句的单列唯一索引已由 `V3.55__meeting_ser_columns.sql` DROP 并重建为 `(transcript_id, kind) WHERE deleted = FALSE` 部分唯一索引：同一分段可各有一行 `voice`（文本语义）与 `ser`（声学情感）告警，否则先到的文本行会永久占位、SP-4 上线后几乎不出声学告警且表现为「静默无数据」。刷屏由 SP-4 §5.3 情形 A「已有文本告警时只补写不新建」挡住。回滚前须先 `DELETE FROM ai_meeting_alert WHERE kind='ser'`。

---

## 6. 接口契约（新增，全部置于 `controller.admin.meeting`，实注册前缀 `/admin-api`）

### 6.1 端点

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/ai/meeting/analyze/status` | GET | `ai:meeting:query` | 进面板即调；返回两张卡片权威状态 |
| `/ai/meeting/analyze/toggle` | POST | `ai:meeting:analyze` | 切换；返回**实际生效**状态 |
| `/ai/meeting/analyze/cost` | GET | `ai:meeting:query` | 四个计数 + 已分析段数 |
| `/ai/meeting/alert/list` | GET | `ai:meeting:query` | 告警列表（含已 ack），用于 SSE 断线后的补齐 |
| `/ai/meeting/alert/ack` | POST | `ai:meeting:alert-ack` | 知悉并随纪要留存 |

请求/响应（字段名即 VO 属性名，驼峰）：

```
GET  /ai/meeting/analyze/status?roomId=12
→ CommonResult<List<AnalyzeStatusRespVO>>
  // C18 定版（评审方案 §3.3）：三值由服务端返回驱动，卡片数量与顺序不硬编码
  AnalyzeStatusRespVO { kind:"voice"|"ser"|"video", label, sp, phase:"P0"|"P1",
                        enabled:boolean, available:boolean, reason:string|null }

POST /ai/meeting/analyze/toggle   AnalyzeToggleReqVO{ roomId:Long@NotNull,
      kind:String@NotBlank, enabled:Boolean@NotNull, noticeConfirmed:Boolean }
→ CommonResult<AnalyzeToggleRespVO{ kind, enabled(实际生效), available, reason }>

GET  /ai/meeting/analyze/cost?roomId=12
→ CommonResult<AnalyzeCostRespVO{ segCount:int, models:int, rules:int, throttled:int, rejected:int })

GET  /ai/meeting/alert/list?roomId=12&level=&speakerIdentity=
→ CommonResult<List<MeetingAlertVO>>

POST /ai/meeting/alert/ack   AlertAckReqVO{ id:Long@NotNull }
→ CommonResult<Boolean>   // 不存在 → 1_040_061_007；已 ack → 幂等返回 true，不报错

MeetingAlertVO {
  id:Long, roomId:Long, transcriptId:Long, kind:String, level:Short(1|2|3), levelLabel:String,
  message:String, speakerIdentity:String, speakerName:String, textSnippet:String,
  audioLevel:Short|null, emotion:String, evidence:String, modelCalled:Boolean,
  ack:Boolean, ackBy:Long|null, ackTime:LocalDateTime|null, createTime:LocalDateTime
}
```

### 6.2 SSE 事件扩展（复用同一条流，不新开端点）

`/ai/meeting/transcript/stream` 上新增事件名 `alert`，`data` 为 `MeetingAlertVO` 的 JSON：

- 后端：`MeetingTranscriptServiceImpl.pushToRoom` 旁路新增 `pushAlertToRoom(roomId, vo)`，`SseEmitter.event().name("alert").data(vo)`。
- 前端：`useCaptionStream` 的帧解析从「只认 `transcript`」改为「按 `event` 分派，未知事件忽略」。**兼容性已由现状保证**：`CaptionPanel.vue:35` 对非 `transcript` 事件直接 return，所以旧代码遇到 `alert` 不会报错——新事件先上、前端后跟也安全。
- 顺序：`alert` 可能早于/晚于对应 `transcript` 到达（分析在异步线程），UI 不假设顺序；`TranscriptPanel` 靠 `transcriptId` 关联，未到达则依据栏只显示文本片段。

### 6.3 错误码（`module/ai/util/ErrorCodeConstants.java`，紧接 004）

```
1_040_061_005  会议分析能力类型非法: {}
1_040_061_006  开启分析前须确认已向各方告知
1_040_061_007  会议风险告警不存在: {}
```

### 6.4 worker 契约变更

`TranscriptSegmentVO` 加 `audioLevel`（可空）→ worker 的 `push` 体加同名键；`asr_provider` 不变；`SAMPLE_RATE=16000` 下 int16 单声道可直接算 RMS。worker 侧 `push()` 失败从 `print` 升级为 `print` + 非零返回码不改变（保持不阻断其他轨），但**必须打印 HTTP 状态码与响应体前 200 字符**——本次双前缀缺陷正是被「只 print 异常」掩盖的。

### 6.5 双前缀修复（P0 首项）

`MeetingTranscriptInternalController`：`@RequestMapping("/admin-api/ai/meeting/internal")` → `@RequestMapping("/ai/meeting/internal")`；javadoc 里「置于 `controller.internal` 包故不追加前缀」的错误表述改写为「本类在 `controller.admin.meeting` 包，前缀由框架追加，故此处只写 `/ai/meeting/internal`」。`worker.py` 与网关配置**均不改**（§0.4 修复方案）。

### 6.6 配置项（`Demo-module-ai-server/src/main/resources/application.yaml`）

```yaml
meeting:
  internal-transcript-token: ${MEETING_INTERNAL_TOKEN:change-me-internal-token}   # 既有
  minutes-prompt-code: Demo_MEETING_MINUTES                                   # 既有
  analyze:
    enabled: ${MEETING_ANALYZE_ENABLED:true}
    emotion-prompt-code: Demo_MEETING_EMOTION
    volume-threshold-dbfs: -18          # 一级门音量阈值（dBFS）
    throttle-seconds: 8                 # 同一发言人最小分析间隔
    max-model-calls-per-minute: 6       # 单房间模型调用上限
    executor:
      core-size: 2
      max-size: 4
      queue-capacity: 200
```

线程池 `meetingAnalyzeExecutor` 在 `service/meeting/config/MeetingAnalyzeConfiguration.java` 声明，拒绝策略 `AbortPolicy`（§5.5）。

---

## 7. 数据表与迁移（PG 方言，对齐 V3.45 风格：`BIGSERIAL` + 审计列 + `tenant_id`）

| 文件 | 内容 |
|---|---|
| `V3.49__meeting_analyze_tables.sql` | 两张新表 + `ai_meeting_transcript` 加列 |
| `V3.50__meeting_analyze_menu.sql` | 菜单 9499/9500 + 超管授权 |
| `V3.51__meeting_emotion_prompt.sql` | 提示词模板 `Demo_MEETING_EMOTION`（对齐 V3.48 的 `model_id` 子查询 + `WHERE NOT EXISTS` 幂等；`ai_prompt_template_key.public_status` 写 `1` 而非 `true`） |

### 7.1 V3.49 DDL

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS ai_meeting_analyze_switch (
  id                BIGSERIAL    NOT NULL,
  room_id           BIGINT       NOT NULL,
  kind              VARCHAR(16)  NOT NULL,            -- voice / video
  enabled           BOOLEAN      NOT NULL DEFAULT FALSE,
  notice_confirmed  BOOLEAN      NOT NULL DEFAULT FALSE,
  last_operator     BIGINT,
  last_toggle_time  TIMESTAMP,
  creator           VARCHAR(64)  DEFAULT '',
  create_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater           VARCHAR(64)  DEFAULT '',
  update_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id         BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_meeting_analyze_switch IS '会中分析开关（服务端唯一权威，前端不落本地）';
COMMENT ON COLUMN ai_meeting_analyze_switch.kind IS 'voice 语音情感 / video 视频行为（SP-3 前不会被置为 true）';
COMMENT ON COLUMN ai_meeting_analyze_switch.notice_confirmed IS '开启时操作人确认已向各方告知';
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_meeting_analyze_switch
  ON ai_meeting_analyze_switch (room_id, kind) WHERE deleted = FALSE;

CREATE TABLE IF NOT EXISTS ai_meeting_alert (
  id                BIGSERIAL    NOT NULL,
  room_id           BIGINT       NOT NULL,
  transcript_id     BIGINT       NOT NULL,            -- 依据的转录分段
  kind              VARCHAR(16)  NOT NULL,            -- voice / video
  level             SMALLINT     NOT NULL,            -- 1信息 2提醒 3危险
  emotion           VARCHAR(32),                      -- calm/anxious/agitated/anger/threat
  text_snippet      TEXT         NOT NULL,            -- 触发原文（留存依据）
  audio_level       SMALLINT,                         -- 该段 dBFS，可空（worker 未升级时）
  evidence          VARCHAR(256),                       -- 模型摘录的关键片段
  message           VARCHAR(256) NOT NULL,             -- 后端 AlertLevel 文案，非定性结论
  model_called      BOOLEAN      NOT NULL DEFAULT FALSE,-- 本条是否经大模型二级判定
  ack               BOOLEAN      NOT NULL DEFAULT FALSE,
  ack_by            BIGINT,
  ack_time          TIMESTAMP,
  creator           VARCHAR(64)  DEFAULT '',
  create_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updater           VARCHAR(64)  DEFAULT '',
  update_time       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
  tenant_id         BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id)
);
COMMENT ON TABLE  ai_meeting_alert IS '会中风险告警（疑似提示，随纪要留存，不作定性依据）';
COMMENT ON COLUMN ai_meeting_alert.level IS '1信息 2提醒 3危险';
COMMENT ON COLUMN ai_meeting_alert.message IS 'AlertLevel 枚举固定文案，含「疑似/请主持人确认」';
CREATE UNIQUE INDEX IF NOT EXISTS uk_ai_meeting_alert_transcript ON ai_meeting_alert (transcript_id);
-- 【SP-4 实施同步】本行 DDL 属 V3.49 初版；V3.55 已 DROP 该单列索引，
-- 改为 CREATE UNIQUE INDEX uk_ai_meeting_alert_transcript_kind
--   ON ai_meeting_alert (transcript_id, kind) WHERE deleted = FALSE;（回滚须先删 kind='ser' 行）
CREATE INDEX IF NOT EXISTS idx_ai_meeting_alert_room_level ON ai_meeting_alert (room_id, level);
CREATE INDEX IF NOT EXISTS idx_ai_meeting_alert_room_ack    ON ai_meeting_alert (room_id, ack);

ALTER TABLE ai_meeting_transcript ADD COLUMN IF NOT EXISTS audio_level SMALLINT;
COMMENT ON COLUMN ai_meeting_transcript.audio_level IS '该分段音量(dBFS)，worker 由 PCM 计算；可空';

COMMIT;
-- 回滚：DROP TABLE IF EXISTS ai_meeting_alert, ai_meeting_analyze_switch;
--       ALTER TABLE ai_meeting_transcript DROP COLUMN IF EXISTS audio_level;
```

`MeetingAlertDO` / `MeetingAnalyzeSwitchDO` 继承 `TenantBaseDO`（与 `MeetingTranscriptDO` 同）；Mapper 继承 `BaseMapperX`，并给 `MeetingAlertMapper` 加 `List<MeetingAlertDO> selectByRoom(Long roomId, Integer level, String identity)` 与 `int countUnacked(Long roomId)`。

### 7.2 V3.50 菜单（ID 段 9499–9500，沿用 V3.46 的防呆与幂等写法）

```sql
-- Step 0 防呆：SELECT count(*) FROM uaa_menu WHERE id BETWEEN 9499 AND 9500;  > 0 则 RAISE EXCEPTION 回滚
-- Step 1 9499 '会中风险分析' permission='ai:meeting:analyze'     type=3 sort=4 parent_id=9491
-- Step 2 9500 '风险告警知悉' permission='ai:meeting:alert-ack'   type=3 sort=5 parent_id=9491
-- Step 3 超管授权 role_id=1 tenant_id=1，id = 100000 + menu_id（NOT EXISTS 幂等）
```

列序与类型对齐 V3.46 实测结论：`type/sort/status` 为 `INTEGER`，`visible/keep_alive/always_show` 为 `SMALLINT`（0/1），`deleted` 为 `BOOLEAN`；`component_name` 对按钮行填 `NULL`。

---

## 8. 告警链路端到端（含每步的失败出口）

```
1 worker.py：VAD END_OF_SPEECH → pcm → RMS→dBFS → ASR → push(segments[{speakerIdentity,text,startTs,endTs,audioLevel}])
    └─ HTTP 失败：打印状态码 + 响应体前 200 字符；不阻断其他轨（字幕缺段可被离线补转兜住）
2 Java MeetingTranscriptInternalController.ingest(roomSid, X-Internal-Token, segments)
3 MeetingTranscriptServiceImpl.ingest：密钥校验 → 按 roomSid 查房 → seq → insert（含 audio_level）→ pushToRoom("transcript")
    ├─ 密钥不符 → 1_040_061_002
    ├─ 房间不存在 → 1_040_061_000
    └─ 随后 meetingAnalyzeExecutor.submit(roomId, transcriptId, identity, text, audioLevel)  ← 不阻塞本线程
4 MeetingAnalyzeService.analyze(seg)
    ├─ 查开关（Redis 60s 缓存）：meeting.analyze.enabled=false 或 voice 未开启 → return（零调用）
    ├─ segCount++
    ├─ 一级门：RiskLexicon.hit(text)==null && (audioLevel==null || audioLevel < -18) → return（零调用）
    ├─ rules++
    ├─ 节流：redis.setIfAbsent(throttleKey,"1",8s)==false → throttled++ ; return
    ├─ 上限：incr(ratelimitKey) > 6 → rejected++ ; return
    ├─ models++ → callModelForStructuredJson(text, Demo_MEETING_EMOTION, vars, EMOTION_JSON_SCHEMA)
    │     └─ 异常/非法 JSON/confidence 缺失 → log.warn + return（不产告警）
    ├─ finalLevel = max(词表, 模型)，confidence<0.6 降一级
    ├─ finalLevel==info && emotion==calm && 词表未命中 → 仅写回情感，不建告警
    ├─ insert ai_meeting_alert（transcript_id 唯一，冲突则忽略）
    └─ pushAlertToRoom(roomId, MeetingAlertVO) → SSE event: alert
5 前端 useAnalyzePanel：收到 alert → dedupeAlerts → 未读角标 +1；danger → stage.dataset.risk='danger' + 15s 定时撤下
6 主持人点「已知悉」→ POST /alert/ack → 落库 ack/ack_by/ack_time → 该条标「已知悉 · 随纪要留存」
    └─ 全部 ack 后角标隐藏、风险条撤下；告警行不删除（审计与纪要留存要求）
7 审计：开关每次变更 record("MEETING_ANALYZE_TOGGLE", ...)；ack 每次 record("MEETING_ALERT_ACK", ...)
```

不变量（写进单测）：①两项分析默认关闭时，整条链路一次模型调用都不发生；②【SP-4 实施同步，修订索引 #3】`video` 在门禁未通过时不产出 `kind='video'` 的告警行；门禁通过与否按统一公式 `available = 平台开关 AND 探活成功 AND g3Passed(运维显式置位)` 求值，未通过时 `video=false`、`reason` 给真实原因、不写开关行；门禁通过后允许翻转，三份 spec 口径一致，不再写「恒 false / 作废」；③告警文案永远来自 `AlertLevel` 枚举（SP-4 的声学四条文案亦由该枚举提供，`threat` 封顶 `warn`）；④分析失败只少一条提示，绝不失败成「误报」。

---

## 9. 分期对齐表（原型角标 ↔ 本文，逐条核对）

原型图例定义：`P0 本次实现 · P1 原型可点但需后端 · P2 置灰（需改 token 权限/Egress）`。

| 界面元素 | 原型角标（`data-phase`/title） | 本文分期 | 一致 |
|---|---|---|---|
| 共享屏幕 `#btnShare` | 无角标 + title「P0 纯前端 getDisplayMedia」 | P0（§1.1，差异 D1） | 是 |
| 顶栏视图/全屏/侧栏/计时/质量 | 无角标 | P0（§3.1） | 是 |
| 顶栏「设置」 | `P2` | P2（§1.2） | 是 |
| 侧栏 Tab 成员/转录/会议信息/AI 分析 | 无角标 | P0（§3.2） | 是 |
| 侧栏「邀请」`#btnInvite`、控制条「邀请/聊天/举手」、聊天输入框 | `P1` | P1（§1.2） | 是 |
| 控制条「AI 分析」`#btnAi`、「字幕」、「纪要」、「结束会议」 | 无角标 | P0 | 是 |
| 控制条「录制」「会议管控」 | `P2` + `disabled` | P2 | 是 |
| 成员行内「静音/移出」 | `P2` + `disabled`（title 说明需 `roomAdmin`） | P2 | 是 |
| 成员行内「呼叫」 | `P1` + `disabled` | P1 | 是 |
| AI 卡片「语音情感分析」 | `SP-2 · P0`（`ready:true`） | P0（§5） | 是 |
| AI 卡片「视频行为分析」 | `SP-3 · P1`（`ready:false` + `.err` 原因） | P1（§1.2，差异 D2） | 是 |
| 会议信息「知情告知状态落库」 | 文案显式标注「属 P1，原型仅展示提示文案」 | P1（§4.3） | 是 |
| 顶栏「录制中」徽标 `#mRec` | 无角标但 CSS `display:none`（仅 `data-on=1` 出现，本期无人置位） | 随录制 P2 | 是（本期恒隐藏，落地保留元素不点亮） |

原型与实现的**有意差异**（评审时按实现为准，原型不改）：①原型开关存 `localStorage`，实现改为 `analyze/status` 服务端权威（§4.1）；②原型音量由标点与风险词推算，实现取 worker PCM 的 RMS dBFS（§5.1）；③原型视频卡描述为「行为理解」（争执/对峙/遮挡/离席）示意，真实能力按 SP-3 收敛为「人像到场一致性核验（CompreFace 1:1）」；④原型纪要/结束按钮仅 `toast`，实现接 `MinutesDrawer` 与 `endRoom`；⑤原型连接质量为随机 mock、计时取本地启动时刻，实现接 `ConnectionQualityChanged` 并注明计时口径；⑥原型 partial 字幕由 mock 脚本驱动，实现依赖可选 SSE `partial` 事件，旧后端不发时按定稿降级。
**【2026-11-04 用户裁决】原第 ③ 条「原型绿改主题蓝」已删除**：主色按原型绿 `#00A870`（会议局部 token），不再作为差异项。

---

## 10. 测试与验收

### 10.1 后端单测（JUnit5 + Mockito；测试类镜像被测类包结构）

| 测试类 | 必录用例 |
|---|---|
| `MeetingTranscriptInternalMappingTest`（`@SpringBootTest`） | `/admin-api/ai/meeting/internal/transcript` 命中 handler；断言 `handlerMapping.getHandlerPaths()` 中**不存在**任何以 `/admin-api/admin-api/` 开头的路径（§0.4 回归锁） |
| `MeetingAnalyzeServiceImplTest` | ①开关关闭 → `verify(llmCallService, never())`；②一级门未命中（无词 + `audioLevel=-40`）→ `verify(llmCallService, never())`；③仅音量命中（无词 + `audioLevel=-12`）→ 调用 1 次、`level=info`；④词表 danger + 模型返回 `info` → `finalLevel=danger`（保守取高）；⑤`confidence=0.3` 且模型 `danger` → 降为 `warn`；⑥`setIfAbsent=false` → 不调用、`throttled=1`；⑦分钟计数超 6 → 不调用、`rejected=1`；⑧模型抛异常 → 无告警行、无异常外抛；⑨`audioLevel=null` → 不 NPE，仅词表判定 |
| `MeetingAnalyzeSwitchServiceImplTest` | ①`kind=video` 请求 `enabled=true` → 返回 `enabled=false, available=false`，且开关表零写入；②`noticeConfirmed` 缺失 → 抛 `1_040_061_006`；③正常开启 → upsert + `record(...,"success")` 被调；④`meeting.analyze.enabled=false` → `available=false` |
| `RiskLexiconTest` | danger 优先于 warn（同句含「收拾」「凭什么」→ danger）；空串/纯标点 → 未命中；七个 danger 词与六个 warn 词逐词参数化 |
| `MeetingTranscriptIngestTest` | `audioLevel` 落 `audio_level`；null 时列可为空；push 事件名仍为 `transcript`（不改既有契约） |
| `MeetingAlertMapperTest` | 同一 `transcript_id` 二次插入被唯一索引挡掉且不抛给调用方（§5.6） |

### 10.2 前端 vitest（与 `__tests__` 同层）

| 文件 | 用例 |
|---|---|
| `analyze.spec.ts`（测 `analyze.ts` 纯函数） | `applySwitch` 用服务端返回覆盖本地（点 video 后 `on.voice` 不变、`video.enabled=false`）；`unreadCount` 只数未 ack；`dedupeAlerts` 按 `id`；`filterAlerts` 三级 + 按发言人 + `all`；`levelTag` 文案取服务端 `message` 不含本地拼接；`switchHint` 在 `available=false` 时返回 `reason` |
| `captionStream.spec.ts` | 帧分派：`event: transcript` 进 segments、`event: alert` 进 alerts、未知事件被忽略、多帧粘包（一次 read 出两块）切分正确 |
| `tileAttach.spec.ts`（**扩展现有 3 例，不替换**） | 新增：远端无 `videoTrack` 时仍渲染 `<audio>` 且 `audioTrack.attach` 被调用 1 次；该元素不带 `muted`；关摄像头后 `video` 消失但 `audio` 仍在（对应 §3.6） |
| `stageStability.spec.ts` | 插入一条 danger 告警后，舞台 tile 的 DOM 节点引用与插入前同一（`toBe`）——锁死「告警不重建舞台」 |

### 10.3 原型（已跑，作为交互基线证据）

【2026-11-04 订正】`prototype/meeting-room.html` jsdom 断言「79 通过 / 0 失败」属**外部一次性验证，脚本不在仓库、不可复现**：`prototype/` 被 `.gitignore:55` 忽略，且 `vitest.config.ts` 的 `include` 只收 `src/**/__tests__/**/*.spec.ts|test.ts`。本轮验收改以 `src/views/ai/meeting/__tests__/` 下新增的 `analyze.spec.ts`、`captionStream.spec.ts`、`stageStability.spec.ts`、`meetingLayout.spec.ts` 及扩展后的 `tileAttach.spec.ts`/`captions.spec.ts` 为准。当时声明的断言覆盖范围为：视频开关点击后仍 `data-on=0`、`AN.alerts` 中零 `kind==='video'`、无权限时全部 `.sw` disabled 且出现 `.deg`、一级门未命中时 `AN.cost.models` 增量为 0、同一发言人二次命中被节流、依据栏含 `identity=p3` 与「非人脸推断」、告警后 `#stageMain .tile` 元素同一、全部知悉后角标隐藏且告警标「随纪要留存」。

### 10.4 端到端冒烟（本地，worker 直连 `http://127.0.0.1:8086`）

```powershell
# 1) 修复前现状复现（应返回 401 账号未登录）
Invoke-WebRequest -Uri 'http://localhost:8086/admin-api/ai/meeting/internal/transcript?roomSid=x' `
  -Method POST -Headers @{'X-Internal-Token'='wrong'} -ContentType 'application/json' -Body '[]'
# 2) 修复后期望：单前缀命中业务校验 → {"code":1040061002,"msg":"转录内部回推密钥无效"}
#    且双前缀路径不再存在（返回 401/404 皆视为已消失，但须以 1) 的对照为准）
# 3) 带正确密钥 + 真实 roomSid 灌一段含「再逼我我就收拾你」的分段
#    → ai_meeting_transcript 落 1 行（audio_level 非空）
#    → 3~5s 内 ai_meeting_alert 落 1 行 level=3 model_called=true
#    → 已连的浏览器右栏出现 danger 告警卡、Tab 角标=1、舞台红条出现
# 4) 未开启分析重复第 3 步 → ai_meeting_alert 零增长、models 计数为 0（默认关断可验证）
# 5) 点「已知悉」→ ack/ack_by/ack_time 落库，角标归零，红条撤下，卡片保留并标「随纪要留存」
# 6) 双人真机入会：远端声音可听（§3.6 修复验证），字幕 3s 内滚动，摄像头开关不闪断
```

### 10.5 验收指标

| 指标 | 阈值 | 口径 |
|---|---|---|
| 默认状态零成本 | 两项分析未开启时模型调用次数 = 0 | `ai_meeting_alert` 与 `models` 计数 |
| 一级门拦截率 | ≥ 60% 的定稿分段不送模型 | `1 - models/segCount` |
| 告警时延 | 分段入库到 `alert` 事件 ≤ 5s（P95） | 服务端日志时间戳差 |
| 告警误报伤害 | 定性措辞出现次数 = 0 | 对 `AlertLevel` 文案与前端拼接做 grep + 用例断言 |
| 节流生效 | 同一发言人 8s 内 ≤ 1 次模型调用 | `models` vs `throttled` 计数 |
| 舞台稳定性 | 告警期间 `<video>` 不重建 | `stageStability.spec.ts` |
| 转录链路修复 | 双前缀路径不存在；单前缀返回业务错误码而非 404 | §10.4 步骤 1–2 + `MeetingTranscriptInternalMappingTest` |
| 无障碍 | Tab 可达全部开关与告警操作、焦点可见 | 键盘走查 + `aria` 属性断言 |

---

## 11. 风险与遗留

| 项 | 状态 | 处置 |
|---|---|---|
| 入会 token 的 video grant 键名必须是 `roomJoin`（写成 `canJoin` 会被 LiveKit 静默忽略，表现为「permissions denied」） | 已修代码，**需重启 `AiApplication` 才生效**；`MeetingRoom.vue` 的 `describeConnectFailure` 已按此分层提示 | 实施首日第一步就验证 grant：取一个 token 解 JWT 检查 `grants.video.roomJoin === true` |
| 转录回推双前缀（§0.4） | 未修，属本 spec P0 首项 | 单测 + 冒烟双锁 |
| 远端音频不可闻（§3.6） | 未修，属本 spec P0 | 用例 + 双人真机验证 |
| `MediaAnalysisServiceImpl` 的伪能力与 `getCapabilities()` 的谎报 | 本 spec 不依赖、不复用；`video` 卡片按 `available=false` 呈现 | 建议单开一次小改造：`getCapabilities` 改为按真实 provider 探活返回（未做之前，任何 spec 不得引用它作为「已具备」证据） |
| 137 `/v1/pool` 单实例近串行 | SP-2 不用 137（复用既有转录链路 + 大模型），无影响 | 【SP-4 实施同步，S3 已关闭该遗留】SP-4 同样不调 137（其配置类无 emotion 端点），改为独立 SER 服务（emotion2vec 容器，端口 8020/8021）＋ 分支 B 只覆盖一级门命中段 ＋ §8.3 延迟/断路阈值自动降级；字幕链路与情感推理彻底解耦，无需扩 137 容量 |
| 多实例部署下 SSE 进程内连接池（`ConcurrentHashMap`）只覆盖本实例订阅者 | 本期 dev 单实例，风险记存 | 告警走 `alert/list` 补齐（前端进面板先拉列表再消费流），后续再评估跨实例广播 |
| 词表内置于 Java 常量 | 调整需发版 | P1 迁至 `infra_config` 或 Nacos；本期保持与原型逐字一致以便评审对照 |
| `prototype/` 被 `Demo-web/.gitignore:55 /prototype/` 忽略 | 原型不入库，仅作评审载体 | 本文档为实现唯一依据 |

---

## 12. Spec 自检（写完后逐条核对）

| 检查项 | 结论 |
|---|---|
| 占位符（TODO/待定/xxx/空表格） | 无。全文无 `TODO`、`待定`、`TBD`、`待补充`、`xxx`；每张表每格均有内容；无空的代码块或空标题 |
| 接口路径 | 全部按读码结果书写：既有 6 + 2 个会议端点、纪要 `draft?roomId=`/`confirm`（并纠正 11-03 §3.3 的路径变量写法）、内部端点当前实际为双前缀（附实测响应）。新增 5 个端点均显式给出前缀推导（类在 `controller.admin.meeting` 包，包名匹配 `**.controller.admin.**` 后框架追加 `/admin-api`，故 mapping 字面量一律不含前缀） |
| 字段名 | `speakerIdentity/text/startTs/endTs`（+ 新增 `audioLevel`）与 `TranscriptSegmentVO`、`api/ai/meeting.ts:39-44`、`worker.py:75-78` 三处逐字一致；DO 列名与 V3.45 风格（下划线 + 审计列 + `tenant_id`）一致 |
| 错误码 | `1_040_061_005/006/007` 紧接既有 `000–004`，不与 `1_040_062_*` 语音段冲突 |
| 菜单 ID | 9499/9500，已扫描确认未被任何 SQL 占用（9495–9498 为语音演示占用） |
| 迁移号 | V3.49/3.50/3.51，紧接现存最新 V3.48 |
| P0/P1/P2 与原型角标 | §9 逐条核对 14 项，全部一致；三处有意差异单独列出并标注「以实现为准」 |
| SP 分期 | SP-1/SP-2 = 本文；SP-3/SP-4/SP-5 各自独立成文（§1.3），与原型卡片 `SP-x · Pn` 角标一致 |
| 色值 | 【2026-11-04 修订】§3.7 给完整映射；结论是组件内零十六进制字面量，token 集中在会议模块局部 `meeting.css`（含 `--meeting-accent:#00A870`）；**原「把 `#00a870` 与主题 `#1A5FB4` 的冲突判给主题」作废**，用户裁决按原型绿、全局主题变量不动；舞台/瓦片两个专有深色**逐字取原型实测值** `#14161a`/`#1f2226`（已核 `meeting-room.html:14-15`），不自行改值；另订正 §3.7 的 `.know` 底色（`:230` 的 `#eaf2ff`）与 P1 角标（`:218`）行号/色值引用 |
| 内部一致性 | §4.1 判定表、§6.1 契约、§7 表结构、§8 链路时序四者互相引用无矛盾：`video` 不落开关行（§4.1）↔ 不产 `kind='video'` 告警（§8 不变量②）↔ 卡片 `available=false`（§3.5 文案所有权）；`noticeConfirmed` 必填（§4.1）↔ 落 `notice_confirmed` 列（§7.1）↔ 逐方告知记录属 P1（§1.2/§4.3） |
| 未验证即写入的内容 | 【本节经历一次错误纠正，现以实读代码为最终结论】首稿写「`PartyIdentityDO.id_card_front_url`」；2026-11-04 一次复核时仅在 `Demo-platform-biz` 与 `Demo-ai` 两仓 grep，得「零命中」后**误判为虚构并改成了 MySQL 表 `user_profile`**——错因是**搜索范围漏了 `Demo-basic` 仓库（uaa 模块正在其中）**。现按完整路径实读：`Demo-module-uaa/Demo-module-uaa-server/src/main/java/com/tianque/uaa/dal/dataobject/party/PartyIdentityDO.java:16-71` → `@TableName("party_identity")` + `@KeySequence("party_identity_seq")`、**继承 `TenantBaseDO`**（即 PG 方言、有 `tenant_id`/`deleted`），字段含 `authType`（1自然人 2企业）、`identityNo`、`realName`、`creditCode`、`idCardFrontUrl`、`idCardBackUrl`、`status`（0待认证 1已认证 2已驳回 3已失效）、`rejectReason`——**首稿引用本来就是对的**。`user_profile`（uaa 的 `UserProfileController`）是平台用户/Demo员档案，与当事人身份是两套体系，不是本能力的底库。教训：跨仓 grep 必须先确认仓库清单完整，不得在部分证据上下结论 |
| 范围风险 | 本期含 3 个必修缺陷（§6.5、§3.6、§11 第一项）+ 1 个新 Tab + 1 条新分析链路；如评审要瘦身，唯一可切的是 §3.3 的 `useRoomSession` 抽取（保留现逻辑原地不动也能交付），其余不可切 |
| 复核轮清理（2026-11-04 二次核对） | 落盘后重新逐行扫描发现并修正 6 处：①§6.1 `MeetingAlertVO` 原用跨行反引号（行内代码不能换行，会渲染成裸文本）→ 改并入代码块；②§12「接口路径」行的前缀推导反引号嵌套错乱 → 改写为完整包名匹配式；③§13 残留一处写作自问（`MeetingAnalyzeSwitchController`? 否——…）→ 删除，只保留最终类名；④§3.2 与 §13 的方法/类型计数（4 方法 5 类型 / 5 VO）与 §6.1 实际的 5 端点 6 类型不符 → 三处统一；⑤§3.7 把新增 token 说成「四条」却列了 5 个，与 §12/§13 的「9 个」矛盾 → 统一为 9（5 色 + 4 尺寸）；⑥§3.7 自造的 `#17191d`/`#23262b` 与已评审原型不一致 → 改回核实的 `#14161a`/`#1f2226`（`meeting-room.html:14-15`）。修正后本表首行「无占位符」结论方为成立 |

---

## 13. 交付清单（实施完成后逐项存在）

- `Demo-ai`：`MeetingTranscriptInternalController`（路径修正）、`MeetingAnalyzeController`（含 `analyze/*` 与 `alert/*` 五个方法）、`vo/` 新增 6 个 VO、`service/meeting/MeetingAnalyzeService` + `impl/MeetingAnalyzeServiceImpl` + `MeetingAnalyzeSwitchService` + `impl`、`service/meeting/support/RiskLexicon`、`service/meeting/config/MeetingAnalyzeConfiguration`、`dal/dataobject/meeting/MeetingAlertDO` + `MeetingAnalyzeSwitchDO`、`dal/mysql/meeting/MeetingAlertMapper` + `MeetingAnalyzeSwitchMapper`、`enums/meeting/AlertLevel` + `AnalyzeKind`、`util/ErrorCodeConstants` 追加 3 码、`application.yaml` 追加 `meeting.analyze.*`、`deploy/livekit-worker/worker.py`（RMS + 日志增强）、`docs/sql/V3.49~V3.51`、§10.1 全部测试类
- `Demo-web`：`api/ai/meeting.ts`（+5 方法 +6 类型）、`views/ai/meeting/MeetingRoom.vue`（四区编排）、`composables/useRoomSession.ts` + `useCaptionStream.ts` + `useAnalyzePanel.ts`、`analyze.ts`、§3.2 全部组件（新增 7 个、改造 4 个、删除 `VideoGrid.vue`）、`styles/variables.css`（+9 token）、§10.2 测试
- `Demo-docs`：本文档
