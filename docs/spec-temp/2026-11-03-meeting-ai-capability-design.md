# Demo平台「视频会议 + AI 音视频能力」设计（Meeting Demo / 能力地图）

- 文档日期：2026-11-03
- 状态：待评审（Design Spec，尚未进入实施计划）
- 实测更新：2026-11-04 经 plink SSH 在 137 本机完成 **TTS→ASR 端到端回环**，文本完全吻合（0.37s）；据此 §9 Q8/Q9/Q10/Q12/Q14/Q15 定案（Q10 voice 列表由服务方补齐）、Q11/Q13 部分确证，并修正 §12.1/§12.4 相应表述。
- **事实订正（2026-11-06，评审方案 C21/F3）**：本文多处写「会议字幕复用 `SseEmitterPool`」不成立。`util/ai/SseEmitterPool.java` 确实存在，但只被 chat 模块（`AiChatServiceImpl` / `GraphRagChatServiceImpl`）使用；`MeetingTranscriptServiceImpl` 自管理 `ConcurrentHashMap` 的 `SseEmitter` 订阅表、SSE 事件名为 `transcript`。下列 §2/§3.1/§3.3/§4.1/§4.2 已就地订正，实施时以后者为准。
- 适用范围：Demo_platform（AI 智能矛盾纠纷Demo平台）
- 关联基线：`Demo-ai/docs/2026-09-ai-capability-design.md`（既有 AI 业务能力层：OCR / 要素提取 / 分类 / 派单）。本设计为**独立成篇的新能力扩展**，不改动基线文档。
- 本地依赖：`livekit-local`（容器 `mwb-livekit`，`livekit-server:v1.13.11`，端口 7880/7881/7882）+ 本地 `redis`（6379，`--requirepass`）。

## 0. 评审导读与关键决策

本设计交付三件事：**① 端到端可用的视频会议 Demo（含服务端实时转录 + 会后 AI 纪要回写）；② 两条直连 137 的独立语音演示线（ASR 转写 / TTS 合成）；③ 面向会议/Demo/音视频场景的完整 AI 能力地图**（逐项盘点既有资产、真实缺口、依赖、边界、验收）。核心原则延续基线文档：**最大复用、最小新增**——本仓库已存在大量可复用资产（见 §2），真正新增的只有「LiveKit 会议外壳」、「Python 转录 worker」与「137 语音演示外壳」，ASR/TTS/VAD/S2S 服务本体 137 已具备。

经多轮澄清已锁定的关键决策：

| 编号 | 决策项 | 结论 |
|---|---|---|
| M1 | 本期 Demo 深度 | **方案 C**：会议打通 + 服务端实时转录 + 会后 AI 纪要，且走「草稿→人工确认→回写Case」全链路 |
| M2 | 实时转录落地 | **方案 T2**：独立 **Python `livekit-agents` worker** 作为"转录参会者"进房，逐轨 ASR + 说话人分离 + 时间戳，结果经内部 REST 回推 Java 落库并 SSE 下推 |
| M3 | 转录 ASR 供商 | **可插拔 `AsrProvider`**，**默认 137 内网 `qwen3-asr`**（原 DashScope 降为外网备选；依用户决策 Q14，会议转录 + 全双工语音**统一改用 137**）|
| M4 | 令牌与鉴权 | **方案 N1**：后端复用登录态 `@PreAuthorize` + `uaa_menu` 菜单权限；LiveKit access token 由 Java 侧 **HS256 自签**（无官方 Java SDK） |
| M5 | worker 运行时 | **Python**（`livekit-agents` + `livekit-plugins-*`），新增独立容器；worker 与 livekit-server 经同一 Redis 组网 |
| M6 | 转录回推通道 | worker → Java 走**带共享密钥的内部 REST**（`@PermitAll`，不出公网），而非跨语言 Data Channel，便于观测与鉴权 |
| M7 | 纪要回写安全边界 | **AI 只产草稿**，`status=DRAFT` 一律不写业务字段；仅主持人"确认"后经既有 `SuperagentCheckpointManager` 状态机才回写 `CaseContextApi.addDemoRecord` 并留痕 |
| M8 | 后端落点 | `Demo-module-ai-server` 内新增 `com.tianque.module.ai.meeting` 包，**不新建 Maven 模块**（对齐 superagent 惯例） |
| M9 | 前端落点 | `Demo-web` 新增 `views/ai/meeting` + `api/ai/meeting.ts`，引入 `livekit-client`；复用既有 SSE 消费范式（同 `stores/superagentFeed`） |
| M10 | 数字人 | 会议室内**可视化数字人**排为后续迭代（迭代 3）；本期仅语音人格 `AudioAgentRole` 复用，不做形象渲染 |
| M11 | 运行时数据库 | PostgreSQL（`application.yaml` 实际数据源），建表用 PG 方言（BIGSERIAL/JSONB/COMMENT ON），菜单入 `uaa_menu` |
| M12 | 语音演示 Demo | 新增 **ASR 演示 + TTS 演示**两条独立线，直连 `192.168.1.137:8765`，与会议 Demo **完全解耦**（不依赖 LiveKit/worker/token），纳入本期 P0 |
| M13 | ASR/TTS 链路 | ASR 走 137 `POST /v1/audio/transcriptions`（上传式 multipart，REST 同步）；TTS 走 `POST /v1/audio/speech`（JSON→音频字节）；**均由 Java 代理**，前端不直连内网 137 |
| M14 | 分段与时间戳边界（实测）| 137 ASR REST **实测仅返回 `{"text","language"}`**，不接 `response_format`、不产 VAD 分段/时间戳/说话人分离（`--no_enable_live_transcription`）→ 分段与时间戳由**客户端/worker 侧 VAD 提供**（见 M18）；说话人靠参会轨身份（非声纹） |
| M15 | 语音接入实现 | 新增薄封装 `VoiceGatewayClient`（`java.net.http`）直连 137，配置全占位符（base-url/model/voice/api-key）；落 `com.tianque.module.ai.voicedemo` 包 |
| M16 | 语音入口结构 | **推荐单菜单「语音能力演示」+ 页内 ASR/TTS 两 Tab**（详见 §13.1）；会议为独立一级菜单；三线各自入口 |
| M17 | 密钥与内网地址 | 137 内网地址属敏感信息、当前无鉴权（`api_key=not-needed`），全部走配置中心，不硬编码；REST 端点为运行时补丁注入，重建容器后失效（部署约束见 §9） |
| M18 | 客户端 VAD 分段 | **新增必需能力**：因 137 服务端不产时间戳/分段，ASR 演示在浏览器用 **Silero VAD（`@ricky0123/vad-web`，WASM/ONNX）** 将录音切为话语段（自带客户端 start/end ms）逐段送 137 转写；会议链路由 worker 用 `silero-vad` 对每条轨切段。详见 §12.4 |
| M19 | 统一 137 供商（Q14 定案）| 会议 worker ASR、全双工语音网关、演示 ASR/TTS **统一指向 137 内网**；aiDemo 的 Qwen Gateway 降为备选/历电链路 |
| M20 | 单实例并发约束 | 实测 `/v1/pool` **`size:1`**→实时/S2S 同时仅一路会话、REST ASR/TTS 串行；本期 Demo 单路即可，多房/高并发需多 pipeline 实例 + 队列/超时（见 §9 Q13） |

## 1. 目标与范围

### 1.1 本期目标（Demo，P0）
1. 浏览器多端进入同一 LiveKit 房间，实现本地/远端画面、静音/取消、开关摄像头、成员列表、入会/离会、连接状态提示。
2. 后端签发房间 access token、维护会议生命周期并落库。
3. worker 服务端实时转录，字幕经 SSE 滚动下推前端。
4. 会后 AI 生成纪要草稿，主持人确认后回写DemoCase记录，全程审计留痕。
5. ASR 演示（上传/录音音频→经 Java 代理调 137 转写）与 TTS 演示（文本→137 合成→播放/下载），各自独立、零会议依赖。

### 1.2 非目标（本期不做，见 §6 迭代规划）
共享屏幕、录制/Egress 落盘、翻译字幕、会中视频理解的实时帧采样、可视化数字人参会者、自动派单闭环、纪要入 KMS/知识图谱。

## 2. 现状盘点：既有资产 vs 真实缺口

| 能力 | 既有实现（可直接复用） | 本期缺口 |
|---|---|---|
| OCR/要素提取/分类/派单 | `service/capability/*`（`AiCapabilityService`、`OcrEngineFactory`、`PaddleOcrEngine`、`VisionModelOcrEngine`）、`callModelForStructuredJson`、`promptCode` 机制 | 无（作纪要要素抽取引擎复用） |
| 全双工实时语音 | `aiDemo/*`（`GatewaySession` Qwen Gateway WS、`AiDemoWebSocketHandler`、barge-in 打断、转人工、`AudioAgentRole` 语音人格） | 已有但为"电话/SIP Demo"链路；会议室音频接入为编排复用 |
| 视频/图像/STT 离线理解 | `disputehall.MediaAnalysisService`（`analyzeVideo`/`analyzeImage`/`speechToText`/情感、`SceneResultVO`/`VideoAnalysisResultVO`） | 文件式离线已具备；房间实时转写为新增 |
| 回写与审批状态机 | `superagent.chat.SuperagentCheckpointManager`（`AWAITING_CONFIRM`→`DONE`）、`SuperagentWritebackService`、`CaseContextApi.addDemoRecord`、`AgentOperationLogDO` | 会议版纪要草稿/确认外壳为新增 |
| 流式基建 | `SseEmitterPool`（chat 模块专用）、`FeedStreamService`、`DemoSummaryStreamController` | **不复用 `SseEmitterPool`**；会议字幕由 `MeetingTranscriptServiceImpl` 自管理 `SseEmitter` 订阅表（C21 订正） |
| 模型/提示词/文件/日志 | `AiChatModelFactory`、`ModelService`、`PromptTemplateService`、`FileApi`、`ChatLlmLogService` | 无 |
| **视频会议本体** | 仅本地 `mwb-livekit` 容器（已配 Redis+密码，见 §8） | **后端令牌/房间服务 + 前端房间页 + worker 转写服务**（全新） |

**结论**：能力地图中 A（全双工语音）、E（视频理解离线）、C 的引擎与回写状态机均**已存在**；本期真正新增 = LiveKit 会议外壳（meeting 包 + 前端页）+ Python 转录 worker + 137 语音演示外壳（voicedemo 包，服务本身 137 已具备）。

### 2.1 137 语音服务接入事实（实测确证；来源 `137.md` + `openapi.json` + `patch_pipeline_rest.py` + 容器启动参数 + 端到端回环）

| 能力 | 形态 | 接入方式 | 实测确证 |
|---|---|---|---|
| ASR/STT | REST | `POST /v1/audio/transcriptions` | 入参仅 `file`(UploadFile 或裸 body)、`language`(默认 auto)、`model`(默认 qwen3-asr)；**无 `response_format`**；soundfile 解码→mono→重采样 16k→`_transcribe`；**实测仅返回 `{"text","language"}`，无 segments/时间戳/说话人**；GPU 空闲时实测 0.37s（含 TTS 产出的 24kHz mono WAV 输入）；错误 503/400/400/500 |
| TTS | REST | `POST /v1/audio/speech` | 支持 JSON 或 form；字段 `input/text`、`voice/speaker`（**合法 9 音色：中文 `Vivian`/`Serena`/`Uncle_Fu`/`Dylan`/`Eric`、英语 `Ryan`/`Aiden`(默认)、日语 `Ono_Anna`、韩语 `Sohee`，另支持自定义**）、`language`(默认 Auto)、`response_format`(**解析但忽略、恒输出 WAV**)；`speed` **未生效**；输出 **24kHz mono PCM WAV**（实测：`/tmp/out.wav` 经转写端点正确识别，回环文本完全吻合）；REST 走非流式 batch；错误 400/503/500 |
| VAD | 内置(无独立 REST) | 仅随 S2S `/v1/realtime` | Silero, `min_silence_ms=700`, `--no_smart_turn`；pipeline 以 `--no_enable_live_transcription` 启动（**无逐字 partial、仅整句转写**） |
| S2S 全双工 | WS + WebRTC | `ws://…/v1/realtime`；另有 `POST /v1/realtime/calls`(SDP) + `DELETE /v1/realtime/calls/{id}` | OpenAI Realtime 事件；输入 16k PCM；VAD+STT+LLM(GPUStack `192.168.40.30/v1-openai` Qwen3-8B)+TTS 闭环 |

**并发与硬约束（实测）**：`/v1/pool` **`size:1`（单实例）**→实时/S2S 同时只能一路会话，REST ASR/TTS 复用同一 in-process handler、`asyncio.to_thread` 跑单卡 → **近乎串行**；三端点共用 8765；服务**无 `/health`**（用 `/v1/pool` 或 WS 101）；ASR/TTS REST 由 `patch_pipeline_rest.py` 运行时打补丁注入，**重建容器即失效需重打**；`api_key=not-needed`；GPU `PIPELINE_GPU_ID=1`。→ 本期缺口 = Demo 外壳 + Java 代理 + **客户端/worker 侧 VAD 分段**（因服务端不产时间戳）。

## 3. 视频会议 Demo 架构

### 3.1 组件与数据流

```
Demo-web (livekit-client)        Demo-ai/meeting (Java)          livekit-worker (Python agents)
  房间页/入会/会中 UI                     MeetingController/Service           进房订阅各音轨
     │ ①POST /ai/meeting/token ────────► HS256 自签 access token             ASR(DashScope, AsrProvider)
     │ ②WebRTC 直连 :7880/:7881  ◄──────  房间生命周期落 PG                     │ diarization + 时间戳
     │   (信令 WS + 媒体 UDP)             (ai_meeting_room/participant)         │
     │ ③SSE /ai/meeting/transcript/stream ◄── 会议自管理 SseEmitter 表 ◄─ 内部 REST 回推 ◄┤ ④POST /internal/transcript(共享密钥)
     │                                                                        (worker ⇄ livekit-server 同 Redis 组网)
     │ ⑤离会/结束 → POST /room/end       MeetingMinutesService → LLM(promptCode)
  审批抽屉(草稿→确认) ──确认──► /minutes/confirm → CheckpointManager → addDemoRecord + OperationLog
```

- **媒体面**（WebRTC）：浏览器**直连 livekit-server**（宿主机 7880 信令/7881 媒体 UDP/7882 ICE-TCP），不经 Java，避免 Java 承担 SFU/音频转发。
- **控制面**（token、房间 CRUD、字幕、纪要）：经 Java REST/SSE，纳入登录态与菜单权限。
- **转录面**：worker 以"参会者"身份进房，拿到服务端视角的**独立音轨**（优于浏览器混音），转写后经内部 REST 回推 Java，Java 落库 + SSE 广播。

### 3.2 后端包结构（新增 `com.tianque.module.ai.meeting`）

```
meeting/
├── controller/admin/meeting/    MeetingController, MeetingMinutesController
│   └── vo/                      MeetingTokenReqVO, MeetingRoomCreateReqVO,
│                                MeetingRoomRespVO, TranscriptSegmentVO,
│                                MinutesDraftRespVO, MinutesConfirmReqVO
├── controller/internal/         MeetingTranscriptInternalController  # worker 回推
├── service/meeting/             MeetingRoomService, MeetingTokenService(HS256),
│   │                            MeetingTranscriptService(SSE 分发), MeetingMinutesService
│   └── impl/
├── dal/dataobject/meeting/      MeetingRoomDO, MeetingParticipantDO,
│                                MeetingTranscriptDO, MeetingMinutesDO
├── dal/mysql/meeting/           *Mapper (BaseMapperX)
└── enums/                       MeetingStatus, ParticipantRole, MinutesStatus(DRAFT/CONFIRMED)
```

### 3.3 后端接口草案（遵循 java-backend.md：`CommonResult`、`@Operation`、`@PreAuthorize`）

| 端点 | 方法 | 说明 | 权限串 |
|---|---|---|---|
| `/ai/meeting/room/create` | POST | 建会议（绑 caseId、标题、主持人），落 `ai_meeting_room` | `ai:meeting:create` |
| `/ai/meeting/token` | POST | 签发入会 token（roomId + identity + displayName） | `ai:meeting:join` |
| `/ai/meeting/room/get` · `/page` | GET | 会议详情/分页（含参与者、状态） | `ai:meeting:query` |
| `/ai/meeting/room/end` | POST | 结束会议，异步触发纪要草稿 | `ai:meeting:update` |
| `/ai/meeting/transcript/stream` | GET(SSE) | 会中实时字幕/事件流（会议侧自管理 SSE，**不复用** `SseEmitterPool`） | `ai:meeting:query` |
| `/ai/meeting/minutes/draft/{roomId}` | GET | 取纪要草稿（LLM 生成，未写库） | `ai:meeting:query` |
| `/ai/meeting/minutes/confirm` | POST | **确认后才**回写CaseDemo记录 | `ai:meeting:update` |
| `/ai/meeting/internal/transcript` | POST | worker 回推转写段；`@PermitAll` + 共享密钥头 | 内部 |

### 3.4 关键数据流（纪要回写，M7 硬边界）
1. 会中：worker 持续回推 → `MeetingTranscriptService` 落 `ai_meeting_transcript`（含 speaker、startTs、endTs、text）→ SSE 推前端。
2. 结束：`MeetingMinutesService` 读全文转录 → `callModelForStructuredJson(promptCode=Demo_MEETING_MINUTES)` → 得结构化纪要草稿存 `ai_meeting_minutes(status=DRAFT)`；**不动业务表**。
3. 审批：前端 `MinutesDrawer` 展示草稿（段落↔转录时间戳锚点可回溯原文）→ 主持人可编辑 → 点"确认"。
4. 回写：`confirm` → `SuperagentCheckpointManager` 置 `AWAITING_CONFIRM`→`DONE` → `CaseContextApi.addDemoRecord` 追加Demo记录 → `AgentOperationLog` 留痕（操作人/时间/来源=MEETING/关联 roomId）。

### 3.5 前端页面结构（`Demo-web/src`）

```
api/ai/meeting.ts                     # token/房间/纪要/SSE 封装 + 类型
views/ai/meeting/
├── MeetingList.vue                   # 会议入口/列表 + 快速建房(绑Case)
├── MeetingRoom.vue                   # 会中主界面（核心）
│  components/
│   ├── VideoGrid.vue                 # 本地+远端画面自适应网格
│   ├── LocalTile.vue / RemoteTile.vue# 单 track 卡（静音/关像遮罩、说话指示）
│   ├── ControlBar.vue                # 静音/取消·开关摄像头·离开 ·(P1:共享屏幕)
│   ├── ParticipantList.vue           # 成员列表 + 角色/入会状态
│   ├── CaptionPanel.vue              # SSE 实时字幕滚动
│   ├── MeetingStatus.vue             # 连接状态/重连/错误 toast
│   └── MinutesDrawer.vue            # 会后纪要草稿→确认
```

**交互流程**：列表点「入会」→ `POST /token` → `new Room().connect(url, token)` → 采集本地 `audio+video` track → `startAudio/startVideo` 发布 → 监听 `TrackSubscribed` 渲染远端 → `ControlBar` 切换轨静音/禁用 → `CaptionPanel` 走 `EventSource`/fetch-SSE 订阅字幕 → 「离开」`room.disconnect()` → 「生成纪要」`/room/end`+轮询草稿 → `MinutesDrawer` 审批确认 → 回写。

**依赖**：新增 `livekit-client`（前端）、后端 HS256 JWT 库（复用 `hutool-jwt`，仓库已含 hutool）。

## 4. AI 能力地图（会议 / Demo / 音视频场景）

### 4.1 分层能力清单

```
L5 业务编排   会议生命周期 · 纪要审批回写 · 派单建议          → meeting/ + superagent(回写复用)
L4 场景能力   B 实时转录 · C 纪要生成 · D 转录翻译 · E 视频理解 · F 数字人 · A 全双工语音 · G ASR演示 · H TTS演示
L3 原子能力   OCR · 要素提取 · 分类 · 派单(已落地) + STT · TTS · LLM · 视觉
L2 引擎适配   PaddleOcrEngine · VisionModelOcrEngine · AsrProvider(DashScope / 137 qwen3-asr) · TtsProvider(137 qwen3-tts) · Qwen Gateway · VoiceGatewayClient(137) · Embedding
L1 基础设施   PromptTemplateService(promptCode) · AiChatModelFactory · ModelService · FileApi · Redis · LiveKit · SseEmitterPool(chat 专用) · 会议自管理 SSE 订阅 · 137 语音服务(8765)
```

> G/H（ASR/TTS 演示）为本期新增独立演示能力，直连 137，不进会议链路；详见 §4.2 与 §12。

### 4.2 逐项规格（A–H）

**A. 全双工语音（Full-duplex Voice）**
- 定位：听-想-说闭环实时对话。输入：PCM 帧。输出：转写文本 + AI 语音帧 + 对话状态。触发：拨号/入会。
- 依赖：Qwen Gateway（ASR/TTS）、SIP、Redis、`AudioAgentRole`。复用：`aiDemo/*` **整套已具备**（含 barge-in、语音仲裁、转人工）。新增：会议室音频源与既有电话链路的编排合流（避免双采）。
- 数据流：`浏览器音频 ⇄ AiDemoWebSocketHandler ⇄ GatewaySession ⇄ Qwen Gateway`。
- 权限：`ai:aiDemo:*`（既有）。隐私：语音为个人信息，留存加密+脱敏+知情提示。降级：Gateway 断→提示转人工/稍后重试。验收：打断响应 < 阈值、无持续双讲冲突。
- 137 对照：137 `/v1/realtime`（S2S，OpenAI Realtime 兼容，含 VAD+STT+LLM+TTS）是**同形态的第二实现**，可替换/并存 Qwen Gateway；接入细节见 §12.1 实时对照项。

**B. 会议实时转录（Meeting Realtime Transcript）**
- 定位：房间内逐轨转写 + 说话人分离 + 时间戳 + 片段定位。输入：房间各参会者音频。输出：分段字幕（speaker/text/startTs/endTs）。触发：会议进行中。
- 依赖：**Python livekit-agents worker**、DashScope 实时 ASR（可插拔）、Redis 组网、SSE。复用：`disputehall.speechToText`（离线兜底 T3）；**不复用** chat 模块的 `SseEmitterPool`，会议侧自管理 `SseEmitter` 订阅（C21 订正）。新增：worker 服务、`ai_meeting_transcript`、`/internal/transcript`、`/transcript/stream`。
- 数据流：见 §3.1。权限：`ai:meeting:query`；内部端点共享密钥。隐私：转写含纠纷敏感内容→脱敏、留存期、双方知情。降级：worker/ASR 断→字幕停更不断流→回落离线补转。验收：双真人发言字幕 3s 内滚动、说话人标签正确率达标、断线重连不丢历史。
- ASR 供商候选：M3 默认 DashScope（外网）；137 提供**内网 `qwen3-asr`**（REST/S2S）可作 `AsrProvider` 备选以省外网依赖——是否切换见 §9 Q14，本节目暂不改 M3。

**C. 会议文字自动写入（Auto Minutes & Writeback）**
- 定位：转录→纪要/纠纷要素/派单建议，**确认后**回写Case。输入：会议转录全文 + Case上下文。输出：结构化纪要草稿→确认后业务Demo记录。触发：会议结束/主持人。
- 依赖：LLM + `promptCode`（复用要素提取/分类/派单）、`SuperagentCheckpointManager`、`CaseContextApi.addDemoRecord`、`AgentOperationLog`。新增：`Demo_MEETING_MINUTES` 模板、`ai_meeting_minutes`、纪要服务。
- **安全边界（M7）**：DRAFT 不触业务字段；仅 confirm 后经状态机回写；派单为"建议"非自动派发。验收：未确认前Case记录零变化；确认后留痕可审计、可回溯转录锚点。

**D. 转录文本翻译（Transcript Translation）**
- 定位：字幕/纪要译为目标语，术语一致。输入：源文 + 目标语言。输出：译文 + 人工校正版。触发：会中/会后按需。
- 依赖：LLM + 术语表（prompt 变量或 KMS 检索）。复用：`callModelForStructuredJson`、`promptCode`。新增：`Demo_TRANSCRIPT_TRANSLATE` 模板、译文落库、导出（复用 `docxBuilder.ts`）。
- 隐私：跨境语种涉敏感内容需合规评估。验收：术语一致、可人工校正、可导出。

**E. 视频理解（Video Understanding）**
- 定位：会议画面/录屏/摄像头/录制视频→场景/证据/合规/摘要。输入：视频文件或关键帧。输出：结构化分析（场景、要点、提示）。触发：会后离线为主。
- 依赖：`qwen-vl-plus` 视觉模型。复用：`MediaAnalysisService.analyzeVideo/analyzeImage/SceneResult` **离线已具备**。新增：Egress 录制落盘（MinIO/FileApi）→ 关键帧抽取喂同一服务；会中帧采样（增强项）。
- 边界：合规/证据为"辅助提示"不做自动裁决；关键帧含隐私需打码。验收：离线视频出结构化摘要、关键帧定位可用。

**F. 视频会议数字人（Digital Human）**
- 定位：虚拟参会者（形象 + 语音 + 对话）。输入：触发文本/播报。输出：语音(TTS) + 形象帧入会。触发：播报/接待。
- 依赖：worker 承载 TTS（`AudioAgentRole` 声音人格）+ 形象渲染服务（边界外置）。复用：`AudioAgentRole`、worker。新增：avatar 渲染接入、房间视频轨发布。
- 排期：**迭代 3**（本期仅声音人格复用，不做可视化，M10）。

**G. 语音转写演示（ASR Demo，直连 137）**
- 定位：独立验证 137 文件式转写，作会议转录（worker/DashScope）的对照组，零会议依赖。输入：一段音频（上传/浏览器录音）。输出：转写文本（**实测仅 `{"text","language"}`**）；时间戳分段由**客户端 VAD** 提供（M18，见 §12.4）。触发：页面「转写」按钮。
- 依赖与 137 配置：`voice.gateway.base-url`、`asr-model`(默认 `qwen3-asr`)、`api-key`（占位）；端点 `POST /v1/audio/transcriptions`（multipart）。输入格式已确证兼容 137 TTS 产出的 24kHz mono WAV（回环实测）。复用：无（新独立线）。新增：`voicedemo` 包、`VoiceGatewayClient`、`AsrPanel.vue`、`api/ai/voiceDemo.ts`。
- 数据流：`浏览器 → Java(/ai/voice-demo/asr/transcribe 登录态) → VoiceGatewayClient 转发 137 → {text/segments} → 回传展示`。权限：`ai:voice-demo:asr`。降级：137 不可达→`1_040_062_000`；缺音频→`1_040_062_002`。验收：上传样例得非空文本；关掉 LiveKit/worker 仍可运行。
- 完整规格见 §12.1。

**H. 语音合成演示（TTS Demo，直连 137）**
- 定位：独立验证 137 文本转语音并选音色/语速即时播放/下载，与 ASR 演示无耦合。输入：`input` 文本、`voice`(默认 `Aiden`)、`speed`、`response_format`。输出：音频（前端 `<audio>` 播放 + 下载）。触发：页面「合成并播放」。
- 依赖与 137 配置：`tts-model`(默认 `qwen3-tts`)、`default-voice`、`base-url`；端点 `POST /v1/audio/speech`（JSON→音频字节）。新增：`TtsPanel.vue`。权限：`ai:voice-demo:tts`。降级：137 不可达→`1_040_062_000`；空文本→`1_040_062_004`；非法音色透传错误（合法 voice 列表见 §9 Q10）。验收：给定文本产出可播放 wav。
- 完整规格见 §12.2。

## 5. 错误码 / 配置 / 数据表

### 5.1 错误码（建议新增会议段，紧接基线能力段 `1_040_060_xxx`）
```
1_040_061_000 会议房间不存在: {}
1_040_061_001 入会令牌签发失败
1_040_061_002 转录内部回推密钥无效
1_040_061_003 纪要草稿不存在或未生成
1_040_061_004 纪要确认状态非法（非 AWAITING_CONFIRM）

// ========== 137 语音演示（voicedemo）1-040-062-000 ==========
1_040_062_000 语音服务不可用（137 不可达）: {}
1_040_062_001 ASR 转写失败: {}
1_040_062_002 ASR 缺少音频
1_040_062_003 TTS 合成失败: {}
1_040_062_004 TTS 文本为空
```

### 5.2 数据表（PG 方言；`uaa_menu` 注册；对齐既有迁移风格）
- `ai_meeting_room`：id、room_sid、case_id、title、host_user_id、status、start_time、end_time、create_time…
- `ai_meeting_participant`：id、room_id、identity、display_name、role、join_time、leave_time
- `ai_meeting_transcript`：id、room_id、speaker_identity、text、start_ts、end_ts、seq、create_time
- `ai_meeting_minutes`：id、room_id、content(JSONB)、elements(JSONB)、status(DRAFT/CONFIRMED)、reviewer、confirm_time

### 5.3 配置样例（值走配置中心/密钥，不硬编码）
```yaml
# Demo-ai application.yaml
livekit:
  server-url: ws://localhost:7880        # 浏览器侧（宿主机映射）
  api-url: http://localhost:7880         # Java 侧房间管理
  api-key: ${LIVEKIT_API_KEY}            # 须与 livekit.yaml keys 对齐且升级为 ≥32 位
  api-secret: ${LIVEKIT_API_SECRET}
  token-ttl: 3600
meeting:
  internal-transcript-token: ${MEETING_INTERNAL_TOKEN}   # worker 回推共享密钥
  minutes-prompt-code: Demo_MEETING_MINUTES

# 137 语音服务（ASR/TTS 演示直连；值走配置中心，137 内网地址属敏感信息）
voice:
  gateway:
    base-url: ${VOICE_GATEWAY_BASE_URL}          # http://192.168.1.137:8765
    realtime-ws-url: ${VOICE_REALTIME_WS_URL}    # ws://192.168.1.137:8765/v1/realtime（P1 对照用）
    api-key: ${VOICE_GATEWAY_API_KEY}            # 现部署为 not-needed（无鉴权）；占位以备加鉴权
    asr-model: ${VOICE_ASR_MODEL}                # 默认 qwen3-asr
    tts-model: ${VOICE_TTS_MODEL}                # 默认 qwen3-tts
    default-voice: ${VOICE_TTS_VOICE}            # 默认 Aiden
    connect-timeout: 5000
    read-timeout: 30000                           # 长音频上限，超限拒绝（见 §9 Q13）
```
worker（Python）`config`：`LiveKitAPI(url, api_key, api_secret)`、`ASR_PROVIDER=dashscope`（默认）、回推 `POST {java}/ai/meeting/internal/transcript` + `X-Internal-Token`。

## 6. 实施顺序 / 优先级

| 期次 | 交付 | 覆盖能力 |
|---|---|---|
| **本期 Demo(P0)** | token+房间页(入会/离会/静音/关像/成员/状态)+worker 实时转录+SSE 字幕+纪要草稿/确认回写 | B、C（复用 A/E 引擎，仅会议外壳） |
| **本期 P0（并行）** | ASR 演示(上传转写) + TTS 演示(文本合成播放/下载)，单菜单双 Tab，直连 137 | G、H（零会议依赖；见效快，可先冒烟） |
| 迭代 1 | 共享屏幕、翻译字幕、离线转录兜底(T3) | D + E |
| 迭代 2 | 会后视频理解（Egress→analyzeVideo）、证据/合规提示 | E |
| 迭代 3 | 会议室内可视化数字人参会者 | F（+ A 语音复用） |
| 迭代 4 | 派单建议闭环、纪要入 KMS/知识图谱 | C→派单/知识 |

## 7. 本地验证步骤

1. `docker ps`：`mwb-livekit`(7880/7881/7882)、`redis`(6379) 健康（Redis 已验，密码 `password123`）。
2. Redis：`livekit_version`、`nodes` 键存在（已验=LiveKit 成功接入带密码 Redis 并注册节点）。
3. 起 worker 容器：日志显示进房 + ASR 就绪；`POST /internal/transcript` 返回 200。
4. 后端起：`POST /ai/meeting/token` 返回 JWT（校验 grants.room / identity）。
5. 浏览器两开房间页：互见画面、`CaptionPanel` 字幕滚动。
6. 「结束会议」→ 取纪要草稿 → 确认 → 目标CaseDemo记录新增一条 + `ai_agent_operation_log` 留痕。
7. curl 直连 137 冒烟：`POST /v1/audio/transcriptions`（样例 wav, qwen3-asr）返回 `text`；`POST /v1/audio/speech`（Aiden）落盘可播 wav。存活探测用 `/v1/pool` 或 WS 握手（**无 `/health`**）。（2026-11-04 已经 plink SSH 在 137 本机实测通过：TTS 产出 wav 直接送转写端点，文本完全吻合，耗时 0.37s。）
   - 2026-11-04 实施期从**宿主机网络**再次实测（不经 SSH）：`GET /v1/pool` 返 `{"size":1,"in_use":0,...}`；`POST /v1/audio/speech`（Aiden）产出合法 `RIFF....WAVE` 115,244 字节；将该 wav 回送 `POST /v1/audio/transcriptions`（qwen3-asr）返 `{"text":"你好，世界测试合成。","language":"Chinese"}`，与合成入参完全吻合 —— 直连契约成立，Java 侧 `VoiceGatewayClient` 的 form/JSON 组装与之对齐（V2 单测 4 项绿、V3 单测 3 项绿）。
8. 经 Java：登录态 `POST /ai/voice-demo/asr/transcribe`、`/tts/synthesize` 各返 200。（**本实施会话环境未执行**：需起完整 ai-server + 网关 + uaa 登录取 token；本地 docker 无 `Demo_db`（该库在远端 192.168.100.80），无法自主拉起带鉴权的服务栈。留待联调环境按 curl 命令执行，鉴权前缀 `Authorization: Bearer` + `tenant-id: 1`，权限点 `ai:voice-demo:asr`/`:tts`/`:query`。）
9. 页面「语音能力演示」：上传得文本、合成得可播放音频；**停掉 worker/LiveKit 仍可用**（独立性验收）。（**本实施会话环境未执行**：需浏览器 + 麦克风交互；语音线与会议线代码完全解耦——前端仅依赖 `@/api/ai/voiceDemo`→`/admin-api/ai/voice-demo`，不引用任何 meeting/livekit 模块，独立性由代码边界保证。）

## 8. LiveKit 访问 Redis 的方式（Docker Desktop 场景，已落地）

- 现状：`mwb-livekit` 在 `mwb-infra-network`，`redis` 在 `infra_net`，**两网隔离**，容器名互不可达。
- 采用：`livekit.yaml` `redis.address: host.docker.internal:6379` + `password`，经宿主机 6379 端口映射访问；容器重启后 LiveKit 成功注册节点、Redis 出现 `livekit_version`/`nodes`（端到端已验证）。
- 备选：把 livekit/worker/redis 加入**同一 Docker 网络**，用 `redis:6379` 容器名直连（生产更干净，免走宿主机）。worker 必须与 livekit-server 能经同一 Redis 组网。
- 待确认配置项：`requirepass` 值来源与轮换、`bind_addresses`、跨 NAT 的 TURN/TLS（本机冒烟无需，生产按官方 `turn` 段配）。

## 9. 假设与待确认（评审时逐条锁定）

> 未答复即按下述默认假设推进实施计划。

1. **说话人分离精度**：默认「按 participant identity 分轨」标注说话人（服务端逐轨，天然分离，无需声纹 diarization）；若需声纹级 diarization（同一轨多人）再评估 pyannote 类插件。→ 默认前者。
2. **会议↔Case绑定**：默认一个会议固定绑定一个 `caseId`，回写落 `addDemoRecord`。→ 如需多Case/无Case再调整。
3. **录制留存**：本期不做 Egress 落盘（迭代 1/2 再定 MinIO vs FileApi）。
4. **数字人**：确认排迭代 3，不进本期。
5. **多方规模**：默认 Demo 2–4 人同房（VideoGrid 自适应，worker 处理 2–4 轨）。→ 若需更大规模影响 worker 轨数与并发。
6. **翻译语言集**：本期不做（迭代 1）；届时确认目标语言清单与小语种/民族语言合规。
7. **LiveKit 密钥**：当前 `devkey:secret`（过短告警），实施前必须换 ≥32 位并与 Java/`.env` 对齐。

**137 语音服务接入细节缺口（Q8–Q16；2026-11-04 TTS→ASR 回环实测后状态如下，仍开放项不得臆造）**
8. **时间戳分段**：✅ **定案**：137 REST 实测仅返回 `{"text","language"}`（`language=auto` 正确返 `"English"`），无 `segments`/时间戳，且端点无 `response_format` 入参 → ASR 演示带时间戳分段唯一路径 = 客户端/worker 侧 VAD 切段（M18，§12.4）。
9. **说话人分离**：✅ **定案**：REST 形态无 diarization（实测输出无 speaker 字段）→ 会议链路按 participant identity 分轨（Q1 默认），演示场景不涉及多说话人。
10. **合法 voice 列表**：✅ **定案**（137 服务方提供）：内置 9 个音色——中文 `Vivian`（明亮略带锋芒女声）/`Serena`（温暖温柔女声）/`Uncle_Fu`（低沉稳重男声）/`Dylan`（北京男声）/`Eric`（成都男声、四川话）；英语 `Ryan`（活力男声）/`Aiden`（阳光男声，默认）；日语 `Ono_Anna`；韩语 `Sohee`。**另支持自定义音色**。→ 前端音色下拉按语种分组列出这 9 个 + 「自定义」输入项（见 §12.2）。
11. **音频格式/采样率约束**：🔶 **部分确证**：实测 137 自身 TTS 产出的 **24kHz mono 16-bit PCM WAV** 可被转写端点正确识别（soundfile 解码→mono→重采样 16k，任意采样率理论可消化）；ogg/mp3 依赖宿主机 libsndfile 编解码能力、上传大小上限、中文转写质量 → 实施期冒烟确认。
12. **鉴权与网络**：✅ **定案（网络已通）**：本机（开发机同内网）可直达 137（SSH 与 8765 均通；本次探测经 plink SSH 在 137 本机以 `127.0.0.1:8765` 执行，Demo-ai 后端本地运行同可达），服务现 `api_key=not-needed` 内网裸连不加 token；若后续部署至其他网段再复核路由。注：探测经 **SSH 凭据**登录执行，属敏感信息，不写入代码/配置。
13. **并发/吞吐/超时**：🔶 **部分确证**：`/v1/pool` `size:1` → ASR/TTS 近乎串行；短音频（约 3s）转写实测 0.37s → 演示串行调用可行；长音频大小/时长上限与排队策略仍未测（沿用 `read-timeout` 30s 防护，见 §5.3）。
14. **是否切换供商**：✅ **定案（用户决策，M19）**：会议 worker 转录、全双工语音网关、演示 ASR/TTS **统一切 137 内网**（服务可用已由 Q12 确证）；DashScope/Qwen Gateway 降为外网备选/既有电话链路。
15. **实时 ASR 是否入本期**：✅ **定案**：137 无纯 ASR 实时端点（VAD 只随 S2S `/v1/realtime`、且 `--no_enable_live_transcription` 无逐字 partial）→ 接受「上传整段 + 客户端 VAD 分段逐段送转写」满足分段体验（§12.4）；S2S 实时对照维持 P1。
16. **补丁常驻**：⏳ **仍开放**：REST 端点为运行时打补丁、重建容器即失效——由谁固化（固化镜像/启动自动重打脚本）需 137 运维方确认。

## 10. 落地产物清单

| 类型 | 产物 |
|---|---|
| 前端(新) | `api/ai/meeting.ts`、`views/ai/meeting/**`、依赖 `livekit-client` |
| 后端 Java(新) | `com.tianque.module.ai.meeting/**`（controller/service/dal/enums/vo）、HS256 token 服务 |
| worker(新) | `deploy/livekit-worker/`：`worker.py`、`Dockerfile`、`requirements.txt`、`AsrProvider`（**默认 137 `qwen3-asr`**，DashScope 降外网备选，M3/M19） |
| 修改 | `ErrorCodeConstants`(会议段)、`application.yaml`(livekit/meeting)、权限/菜单种子 SQL(`uaa_menu`) |
| 种子数据 | `ai_prompt_template`：`Demo_MEETING_MINUTES`(+ 翻译 `Demo_TRANSCRIPT_TRANSLATE` 迭代1) |
| DDL | `ai_meeting_*` 四表（PG 方言，临时 PG 容器验证幂等） |
| 前端(新·语音) | `api/ai/voiceDemo.ts`、`views/ai/voice-demo/**`（`VoiceDemo.vue` + `AsrPanel.vue`/`TtsPanel.vue`） |
| 后端 Java(新·语音) | `com.tianque.module.ai.voicedemo/**`（controller/service/client/vo） |
| 修改·语音 | `ErrorCodeConstants`(`1_040_062_xxx` 段)、`application.yaml`(`voice.gateway.*` 占位符) |
| 种子·菜单 | `uaa_menu` 会议线 9490–9494 + 语音线 9495–9498（PG，从 9490 起、9484–9489 留缓冲避让，见 §13.2）+ 角色授权 |
| 设计原型 HTML | `Demo-docs/superpowers/prototypes/meeting-voice-demo.html`（纯前端自包含模拟三条演示线，**仅供设计评审，非实现代码、不入 Demo-web**） |

## 12. 语音演示 Demo（ASR / TTS，直连 137）

> M12–M17 决策下的两条独立演示线，与 §3 视频会议 Demo **完全解耦**：不依赖 LiveKit 房间、不依赖转录 worker、不需要入会令牌，仅需后端可达 `192.168.1.137:8765`。

### 12.0 三线边界与入口关系

| 演示线 | 入口菜单 | 运行依赖 | 后端落点 |
|---|---|---|---|
| ① 视频会议 | 「视频会议」一级目录 | LiveKit + worker + Redis（+ 137 可选） | `com.tianque.module.ai.meeting` |
| ② ASR 演示 | 「语音能力演示」目录（页内 Tab） | 仅 137 `/v1/audio/transcriptions` | `com.tianque.module.ai.voicedemo` |
| ③ TTS 演示 | 同上（另一 Tab） | 仅 137 `/v1/audio/speech` | `com.tianque.module.ai.voicedemo` |

ASR 与 TTS **互不依赖**，可各自单独运行；②③共用一个页面（双 Tab），与①在菜单、路由、包、api 文件上完全隔离。取舍结论见 §13.1。

### 12.1 ASR 演示（转写）

| 维度 | 规格 |
|---|---|
| 能力定位 | 独立验证 137 转写质量，作会议转录链路（worker/DashScope）的**对照组**，不绑定会议 |
| 输入 | 一段音频：文件上传（wav 等，格式约束见 §9 Q11）或浏览器 `MediaRecorder` 录音后上传；参数 `language`(zh/en/auto)。录音模式配合客户端 VAD 分段逐段送转写（§12.4，M18）；`responseFormat` 参数**不透传**（137 REST 无此入参，恒返 JSON） |
| 输出 | 转写文本；**实测仅返回 `{"text","language"}`**，无服务端 segments/时间戳/说话人（VAD 只在 S2S、diarization 不可得）——时间戳分段由浏览器 Silero VAD 切段提供（§12.4，M18），说话人演示场景不涉及、会议链路按参会轨身份标注 |
| 触发 | 页面「转写」按钮（同步等待） |
| 依赖服务 | 137 `POST /v1/audio/transcriptions`；Java `VoiceGatewayClient`；配置占位符 `voice.gateway.base-url`/`api-key`(现 not-needed)/`asr-model`(默认 qwen3-asr)/超时 |
| 前端结构 | `AsrPanel.vue`：音频选择/录音（录音模式挂 §12.4 VAD 分段）→ 参数区（语言下拉）→「转写」→ 结果区（文本 + 可折叠 segment 表）+ 耗时显示 |
| 交互流程 | 选音频 → 点「转写」→ `POST /ai/voice-demo/asr/transcribe`（multipart）→ loading → 渲染结果/错误 toast |
| 接口契约 | 前端↔Java：`POST /ai/voice-demo/asr/transcribe`（`MultipartFile file`, `String language`）→ `CommonResult<AsrTranscribeRespVO>`（`text`, `segments[]{start,end,text}?`（客户端 VAD 拼接，非 137 返回）, `costMs`）；Java↔137：原样 multipart 转发（仅 `file`/`language`/`model`） |
| 关键数据流 | 浏览器 →(登录态) Java 代理 →(multipart) 137 → `{text}` → VO 回传。**前端绝不直连 137**（内网地址/CORS/混合内容/密钥隔离） |
| 鉴权策略 | `@PreAuthorize("@ss.hasPermission('ai:voice-demo:asr')")`；137 侧现无鉴权，`api-key` 占位以备启用 |
| 错误/降级 | 137 不可达/连接超时 → `1_040_062_000`（前端提示"语音服务不可用"）；转写失败 → `1_040_062_001`；空音频 → `1_040_062_002`；超过 `read-timeout` → 按失败返回；**P0 不整段重试大文件**，提示分段 |
| 实时对照(P1) | 浏览器 → Java → `ws://…/v1/realtime` 桥接（`VoiceGatewayClient` 预留 WS），展示 VAD `speech_started/stopped` + 逐段转写。**须显式标注该链路连带 LLM+TTS，非纯 ASR**；不做则不影响 P0 验收 |
| 本地验证 | §7 步骤 7（curl 直连）→ 8（经 Java）→ 9（页面） |
| 验收标准 | 上传样例音频返回非空文本；错误/降级可触发；关闭 LiveKit/worker/token 全流程后 ASR 演示仍可用 |

### 12.2 TTS 演示（合成）

| 维度 | 规格 |
|---|---|
| 能力定位 | 独立验证 137 文本转语音与音色/语速参数效果，与 ASR 无任何依赖关系 |
| 输入 | `input` 文本、`voice`（默认 `Aiden`；**合法列表已定案 §9 Q10**：中文 `Vivian`/`Serena`/`Uncle_Fu`/`Dylan`/`Eric`、英语 `Ryan`/`Aiden`、日语 `Ono_Anna`、韩语 `Sohee`，另支持自定义音色）、`speed`（倍率，**实测未生效**，保留入参占位）、`responseFormat`（wav/pcm/mp3，**实测解析但忽略、恒输出 WAV**） |
| 输出 | 音频字节（默认 wav）；前端 `<audio>` 即时播放 + 下载 |
| 触发 | 页面「合成并播放」按钮 |
| 依赖服务 | 137 `POST /v1/audio/speech`；配置 `tts-model`(默认 qwen3-tts)/`default-voice`/超时 |
| 前端结构 | `TtsPanel.vue`：文本域（限长提示）→ 音色下拉（按语种分组：中文/英语/日语/韩语 9 项 + 「自定义」输入框）→ 语速滑杆（UI 保留，实测不生效，标注）→ 格式选择（UI 保留，实测恒 WAV，标注）→「合成」→ 播放器 + 下载按钮 + 历史记录（可选） |
| 交互流程 | 填文本选参数 → 点「合成」→ `POST /ai/voice-demo/tts/synthesize` → 收 blob → 自动播放/可下载 |
| 接口契约 | `POST /ai/voice-demo/tts/synthesize`（JSON `input`,`voice`,`speed`,`responseFormat`）→ **音频二进制流**（Java 透传 Content-Type；本期直返 blob，不落盘） |
| 关键数据流 | 浏览器 →(登录态) Java 代理 →(JSON) 137 → 音频字节 → 回传 blob |
| 鉴权策略 | `@PreAuthorize("@ss.hasPermission('ai:voice-demo:tts')")` |
| 错误/降级 | 不可达 → `1_040_062_000`；合成失败/非法音色 → `1_040_062_003`（透传服务端消息 + 提示合法取值）；空文本 → `1_040_062_004`（前端也校验）；超长文本 → 前端截断提示 |
| 本地验证 | §7 步骤 7（curl 落盘）→ 8 → 9 |
| 验收标准 | 给定文本产出可播放音频；voice/speed/format 参数生效；关闭会议全组件仍可用 |

### 12.3 后端包结构与客户端

```
voicedemo/
├── controller/admin/voicedemo/  VoiceDemoController（/ai/voice-demo/**）
│   └── vo/                      AsrTranscribeRespVO, TtsSynthReqVO
├── service/voicedemo/           VoiceDemoService(+Impl)
└── client/                      VoiceGatewayClient  # java.net.http：STT multipart、TTS JSON、
                                 # 健康探测(/v1/pool 或 WS 101)、预留 S2S WS 桥接(P1)
```
风格对齐既有 `capability/ocr` 远程封装（`PaddleOcrClient`）：超时/错误码转换/日志统一在 client 层。演示不落库（无 DO/表），结果只在会话内展示。

### 12.4 客户端 VAD 分段（M18，ASR 演示必需能力）

因 137 REST 转写实测仅返 `{"text","language"}`（无服务端分段/时间戳，§9 Q8 已定案），带时间戳的分段转写体验由**客户端 Web 侧 Silero VAD** 提供：

| 维度 | 规格 |
|---|---|
| 选型 | `@ricky0123/vad-web`（浏览器端 Silero VAD，WASM/ONNX 推理，零服务端依赖）；与 12.1「实时对照(P1)」的 S2S 链路无关 |
| 录音模式流程 | `getUserMedia` 麦克风 → VAD 监听 `speech_started`/`speech_stopped`（默认 `minSilence` 取 700ms，与 137 服务端 VAD 行为对齐）切出话语段（每段携客户端 start/end ms）→ 逐段送 `POST /ai/voice-demo/asr/transcribe` → 前端拼接为分段表 `segments[]{start,end,text}` 展示 |
| 上传文件模式 | 整段直送转写（仅得纯文本）；如需带时间戳，可前端解码后离线跑同一 VAD 切段再逐段送转（P1） |
| 会议链路对称项 | worker（Python）对每条参会轨用 `silero-vad` 切段后逐段送 137/DashScope ASR，段间时间戳由 worker 维护（M2/M14） |
| 依赖与代价 | 前端新增 `@ricky0123/vad-web`（含 ONNX 模型资源，首次加载体积较大）；Java/137 零改动；逐段多次请求受 137 单实例串行约束（M20），段长受 `read-timeout` 防护 |
| 验收 | 录音中说停后得到 ≥1 条带起止毫秒与文本的分段行；关闭 LiveKit/worker 仍可用；VAD 未切出段时不发起空请求 |

## 13. 菜单、权限与前端落点（uaa_menu / PG）

### 13.1 ASR/TTS 入口取舍（推荐结论）

- **推荐：单菜单「语音能力演示」+ 页内两 Tab（ASR/TTS）**。理由：两者同属"137 语音服务演示"，共享 `voice.gateway.*` 配置与 `VoiceGatewayClient`；单路由、少占菜单/授权行；后续 VAD/S2S 演示可作第 3 Tab 平滑扩展；可见性仍可用按钮级权限 `ai:voice-demo:asr`/`ai:voice-demo:tts` 分别控制 Tab 渲染。
- 拆两子菜单的代价：多两组菜单/授权记录与两条路由，仅当 ASR、TTS 需要**不同角色可见**或独立埋点统计时才值得——本期无此诉求，**不推荐**。

### 13.2 菜单 ID 规划（顺延 9460–9472 区间 + 避让原则）

- 现状：超级智能体系列已占 **9460–9472**（目录/目标/点子/对话/动态）与 **9480–9483**（通道绑定，同挂 9460）。→ 新线**从 9490 起分配**（9484–9489 留作缓冲，防并行分支占位冲突），会议与语音各自独立一级目录，三线互不混排。
- 分配（每条线一个迁移脚本，含 Step-0 防呆：目标 id 被占即 `RAISE EXCEPTION` 回滚，沿用 V3.40 范式）：

```
线① 视频会议（新建一级目录，仿 9460 挂载）
  9490 目录  视频会议          type=1 parent=0     permission —
  9491 菜单  会议演示          type=2 parent=9490  ai:meeting:query（页面，含 create/join/update 按钮）
  9492 按钮  创建会议          type=3 parent=9491  ai:meeting:create
  9493 按钮  加入会议          type=3 parent=9491  ai:meeting:join
  9494 按钮  结束/纪要确认     type=3 parent=9491  ai:meeting:update
线②③ 语音能力演示（单菜单双 Tab，M16）
  9495 目录  语音能力演示      type=1 parent=0
  9496 菜单  ASR/TTS 演示      type=2 parent=9495  ai:voice-demo:query
  9497 按钮  语音转写(ASR)     type=3 parent=9496  ai:voice-demo:asr
  9498 按钮  语音合成(TTS)     type=3 parent=9496  ai:voice-demo:tts
```

- **避让原则**：① 与 9460–9483 已占用段不相交；② 每条线连续小段、互留空隙便于后续插按钮；③ 脚本执行前必须 `SELECT MAX(id) FROM uaa_menu` + 目标段防呆复核——本仓多分支并行，静态扫描不保证唯一，冲突则整段顺延并同步改授权；④ 授权沿用既有范式：超管 `uaa_role_menu.id = 100000 + menu_id`（role_id=1, tenant_id=1），如演示需全员可见再按 400000+ 段 `ROW_NUMBER` 全角色授权（对齐 V3.40 Step4）。
- PG 方言：`INSERT ... ON CONFLICT (id) DO UPDATE`；`uaa_menu` 列集 `id,name,permission,type,sort,parent_id,creator,create_time,updater,update_time,deleted`；页面 `path/component/icon` 由前端路由表承载（与既有 type=2 菜单做法一致）。
- 文件命名：`Demo-ai/docs/sql/V3.xx__meeting_menu.sql` 与 `V3.xx__voice_demo_menu.sql`（两线分离脚本，含回滚 `DELETE` 注释段，对齐 `docs/sql/` 规范）。

### 13.3 前端落点（Demo-web）

```
api/ai/voiceDemo.ts                 # asrTranscribe(multipart) / ttsSynthesize(responseType:'blob')
views/ai/voice-demo/
├── VoiceDemo.vue                   # 单页双 Tab（a-tabs），按权限过滤 Tab
└── components/
    ├── AsrPanel.vue                # 上传/录音 + 语言/格式 + 结果(文本/segment 表)
    └── TtsPanel.vue                # 文本 + 音色/语速/格式 + 播放/下载
（会议线沿用 §3.5 views/ai/meeting/** 与 api/ai/meeting.ts，两线互不引用；状态轻，可不用独立 store）
```

## 14. 自检（Spec Self-Review）

- **占位符**：无 TBD；决策 M1–M20 已锁定；§9 开放项中 137 语音 Q8/Q9/Q10/Q12/Q14/Q15 已定案（Q10 voice 列表由 137 服务方补齐：内置 9 音色 + 自定义），Q11/Q13 部分确证（待实施期冒烟收尾），仍开放仅 Q16（补丁常驻）；会议线 Q1–Q7 带默认假设。
- **一致性**：§3 架构 ↔ §3.2/§3.3/§3.4 ↔ §12 voicedemo 包/接口/数据流互相指向；§12 接口 ↔ §13 权限串（`ai:voice-demo:asr/tts`、`ai:meeting:*`）↔ §5.1 错误码（`1_040_062_xxx`）↔ §5.3 `voice.gateway.*` 配置互相对齐；§13.2 ID 段（9490–9498）与现状扫描（9460–9472、9480–9483）不相交；§2.1 的 137 事实与 §12 规格逐项可回溯到 `137.md`；M14（REST 无 VAD/diarization）在 §4 B/G、§12.1、§12.4、§9 Q8/Q9 表述一致；M18 引用的 §12.4 已存在；M3 已依用户决策（M19/Q14）统一切 137，DashScope 降为备选。
- **范围**：本期三条演示线（会议 P0 + ASR/TTS P0 并行）；实时对照(S2S)、翻译、录制、数字人显式后置；语音演示不落库、零会议依赖，符合"最大复用、最小新增"。
- **歧义**：DRAFT 不写库(M7)、内部端点鉴权(M6)、Java 代理不直连 137(M13)、单菜单双 Tab 推荐(M16)、时间戳/说话人默认不可得(M14)均已显式约定。
