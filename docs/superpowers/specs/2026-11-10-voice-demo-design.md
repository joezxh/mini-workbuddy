# MinWorkBuddy 语音能力 Demo 设计方案

> 日期：2026-11-10 · 状态：**待评审**
> 基准原型：`docs/prototypes/voice-demo-preview.html`（双主题可切换，零外部依赖，用户已确认交互）
> 上游参考：`docs/spec-temp/2026-11-04-meeting-voice-demo-p0.md`（Track V 语音线，只读分析，不机械复制）
> 参考工程（只读）：`D:\work\mediation_platform\mediation-ai\...\mediation-module-ai-server`（Java REST 代理）+ `mediation-web/src/views/ai/voice-demo`（3 Tab + VAD）
> 依赖服务：`docker/speech-to-speech`（`127.0.0.1:8765`，WS `/v1/realtime` + OpenAI 兼容 REST ASR/TTS 同主机）
>
> **实测依据（2026-11-10 用户实测）**：① ASR `POST /v1/audio/transcriptions`（multipart `file`+`language`）→ `{"text","language"}`，language 为语言名（如 `"Chinese"`）而非 ISO 码；② TTS `POST /v1/audio/speech`（JSON `input`/`voice`/`response_format`，**仅 wav，无 speed 字段**）→ WAV 字节；③ WS 链路容器内 E2E 脚本通过（§5.3）。voice=`Aiden` 实测有效。
>
> **阅读约定**：对现状的描述标注依据（文件:行号）；推断与未实测内容集中在 §7，正文不做无据断言。

---

## 0. 已定调的六项决策

以下六项于 2026-11-10 前后由用户逐项裁决，是本方案全部设计的承重前提。

| # | 决策点 | ✅ 裁决 | 放弃的备选 | 直接后果 |
|---|---|---|---|---|
| **D1** | 能力范围 | **方案 B**：参考 P0 等价（ASR / TTS / 手册，REST 代理）**+ 第 4 个「语音对话」Tab**（WS 桥接 s2s `/v1/realtime`，真正连续语音对话） | A 严格 P0（无连续对话，不满足需求清单第 2/4 条）；C 仅对话 Tab（与「与参考工程功能一致」有偏差） | 覆盖用户全部 9 项核心能力；实现重心在 S2S 桥接网关与前端事件状态机 |
| **D2** | Tab 默认与顺序 | **ASR Tab 默认选中**；顺序 ASR → TTS → 对话 → 手册（对齐参考工程） | 原型草稿曾把对话 Tab 放首位 | 用户 2026-11-10 裁决，原型已同步 |
| **D3** | WS 鉴权 | **query 参数传 JWT**（`/ws?token=<JWT>`），对齐 `backend/app/duplex/voice/websocket_gateway.py:62` `_authenticate` 先例 | `Authorization` 头（浏览器 WebSocket API 不支持自定义请求头） | token 会进访问日志——Demo 可接受，手册注明 |
| **D4** | 主题 | **浅色/深色双主题可切换**，机制复用工程既有：`<html data-theme>` + `localStorage['app-theme']`（键名与默认 light 对齐 `frontend/src/stores/app.ts:11,34`），token 值对齐 `frontend/src/styles/tokens.css` 双皮肤 | 独立主题机制 / 单主题 | 原型 CSS 变量即工程 token 的别名映射，Vue 实现时直接对照迁移 |
| **D5** | Mock 默认 | **`VOICE_DEMO_MOCK=true` 默认开启**，4 个 Tab 全部可 Mock，本地零真实服务依赖可跑 | 默认直连真实服务 | 真实服务接入仅改 env（§6.2 迁移步骤） |
| **D6** | 挂载方式 | **独立 Demo 模块**：后端 `app/routers/voice_demo.py` + 服务子包，前端 `views/voice-demo/` 独立目录 | 并入现有 `views/duplex/VoiceDemo.vue`（另一套 AgentScope RTC 演示，**保持不动**） | 对既有文件零语义修改，仅清单式追加（§2.3） |

---

## 1. 目标与范围

### 1.1 目标

在当前工程内交付一个**功能等价于参考工程 Track V、并增强实时对话能力**的语音 Demo：前端 4 Tab 交互页面 + 后端 FastAPI 网关模块，Mock 默认本地可跑，配置化切换真实 speech-to-speech 服务。

一句话验收标准：**登录后打开「语音演示」页，在 Mock 模式下四个 Tab 全部可操作（转写出文本、合成出声、对话走完 Realtime 事件流、手册可读）；把 env 指向本地 s2s 服务并关闭 Mock 后，对着麦克风说话能得到流式语音应答且可打断。**

### 1.2 能力边界

| 做（P0） | 不做（明确排除） | 原因 |
|---|---|---|
| ASR Tab：上传文件转写 + 录音（客户端 VAD 分段）转写 | 服务端 VAD / 说话人分离（参考工程 REST 服务本就只返回 `{text, language}`） | 上游无此能力，客户端 VAD 已覆盖分段需求 |
| TTS Tab：文本合成、9 音色下拉 + 自定义、播放/下载、blob 不落盘 | speed 参数生效 / 非 wav 格式（实测上游仅 wav、请求无 speed 字段，占位透传——原型已标注） | 对齐上游实测行为，不做假开关 |
| S2S Tab：服务端 VAD 切轮次、逐句转录上屏、流式音频回放、打断 | 会话持久化落库、多轮历史回放 | s2s 服务端持有上下文，刷新即新会话；落库沿 duplex 方案进 P1 |
| WS 桥接：connect 注入 session.update（人设 + server_vad）、事件透传、心跳/空闲超时、并发闸 | WebRTC 媒体直连（`/v1/realtime/calls`）、多房间 | P0 单一 WS 通道已满足 Demo；WebRTC 留接口不做 |
| Mock 模式全覆盖（REST 样例 + WAV 提示音 + Realtime 事件脚本） | Mock 模拟真实 ASR 识别任意音频内容 | Mock 的目的是联调链路，不是模拟模型质量 |
| 双主题切换、JWT 鉴权（REST 头 + WS query）、统一错误处理 | 数字错误码段（参考工程 `1_040_062_xxx` 体系） | 当前工程无集中式数字错误码（全仓 Grep 无 `1_04x` 体系命中），沿用统一异常处理 + HTTPException detail |

### 1.3 与现有 duplex 语音演示的边界（**防止两套语义撞车**）

`frontend/src/views/duplex/VoiceDemo.vue` 是**另一套**基于 AgentScope RTC（DashScope/OpenAI provider + VoiceChannel）的语音演示，配置走 DB（`admin_voice_config`），**本方案不修改它的任何文件与路由**。两套并存，入口、命名、路由完全隔离：

| | duplex 语音演示（现有） | 本方案 voice-demo（新增） |
|---|---|---|
| 路由 | `/duplex/voice-demo`（`name: 'DuplexVoiceDemo'`） | `/voice-demo`（`name: 'VoiceDemo'`） |
| 上游 | AgentScope RealtimeAgent（dashscope/openai provider） | s2s pipeline `/v1/realtime`（OpenAI Realtime 事件集） |
| 配置 | DB `admin_voice_config` | 环境变量 `VOICE_DEMO_*` |
| 用途 | 业务语音通道验证 | 语音能力演示与联调 |

落地要求：新模块代码与文案不得引用 `duplex` 域的 provider/model 概念；`config/_voice.py` 既有 `VoiceSettings`（`backend/app/config/_voice.py:5-17`）不动，新配置独立放 `_voice_demo.py`。

---

## 2. 总体架构

### 2.1 三层职责

| 层 | 归属 | 职责 | 明确不做 |
|---|---|---|---|
| 展示层 | `frontend/src/views/voice-demo/**` | 4 Tab 交互、采集重采样（48k→16k PCM16）、VAD 分段、24k 回放链、事件流可视化 | 不直连上游服务（全部经后端网关） |
| 网关层 | `backend/app/routers/voice_demo.py` + `app/services/voice_demo/**` | JWT 鉴权、REST 转发、WS 双向桥接（session.update 注入 / 事件透传 / 心跳 / 并发闸）、Mock 生成器 | 不做 ASR/TTS/LLM 本身；不落库 |
| 服务层 | `docker/speech-to-speech`（既有，外部进程） | Silero VAD → Parakeet STT → LLM → Qwen3 TTS，`/v1/realtime` + `/v1/pool` | 不为本 Demo 改造（patches 不动） |

### 2.2 两条数据流

**REST 链（ASR / TTS Tab，对齐参考工程 VoiceGatewayClient 行为）**

```
浏览器（FormData / JSON）
  → POST /api/v1/voice-demo/asr/transcribe   （JWT Authorization 头）
     └ Mock: 返回样例 {text, language, cost_ms}
     └ 真实: httpx 转发 POST {VOICE_DEMO_BASE_URL}/v1/audio/transcriptions (multipart：file+language)
             （实测无需 model，如需可经 VOICE_DEMO_ASR_MODEL 可选透传）→ {text, language}（实测 language 为语言名，如 "Chinese"）→ 加 cost_ms 回传
  → POST /api/v1/voice-demo/tts/synthesize   （JWT）
     └ Mock: wave 模块生成 24kHz mono 16bit 提示音 WAV 字节
     └ 真实: httpx 转发 POST {VOICE_DEMO_BASE_URL}/v1/audio/speech
             {input, voice, response_format:"wav"}（实测无 speed 字段）→ audio/wav 字节原样回传
```

**WS 桥接链（对话 Tab，OpenAI Realtime 事件集）**

```
浏览器 AudioWorklet：48k 采集 → audioDsp 重采样 16k → PCM16 → base64
  → input_audio_buffer.append ──▶ 网关鉴权(token query) ──▶ websockets 连上游 /v1/realtime
       ▲                                        │ connect 时注入 session.update
       │                                        │   {instructions: 人设, voice, server_vad + interrupt_response}
       │                                        ▼
  ◀── response.audio.delta (base64 PCM16/24k) ── s2s: VAD→STT→LLM→TTS
  ◀── 转录事件（speech_started/stopped、transcription.completed/delta）
  打断：浏览器 response.cancel → 网关透传 → 本地播放立即停止
```

### 2.3 挂载点（清单式追加，共 4 处，均不动既有语义）

| 挂载 | 做法 | 依据 |
|---|---|---|
| 后端路由 | `backend/app/core/router_registry.py` SPECS 清单追加一条 `RouterSpec(module="app.routers.voice_demo", attr="router", prefix="/api/v1/voice-demo", tags=["voice-demo"])` | RouterSpec dataclass（`router_registry.py:55-68`）；导入失败自动进 router_failures 上报 `/health` |
| 后端配置 | `backend/app/config/_voice_demo.py` 新增 `VoiceDemoSettings(BaseModel)`，并入 `config/__init__.py` Settings 多重继承 | `_voice.py` mixin 组合先例 |
| 前端路由 | `frontend/src/router/index.ts` AppLayout children 追加 `{path:'voice-demo', name:'VoiceDemo', ...}` | `duplex/voice-demo` 注册先例（同文件） |
| 前端菜单 | 提供幂等 SQL `docs/sql/menu_voice_demo.sql`（INSERT…WHERE NOT EXISTS，风格对齐既有菜单 SQL）；是否执行由用户定 | §7 未决 |

---

## 3. 后端设计

### 3.1 文件清单（全部新增，仅 router_registry / config/__init__ / router 是追加式修改）

| 文件 | 职责 |
|---|---|
| `backend/app/config/_voice_demo.py` | `VoiceDemoSettings` 配置段（§3.5） |
| `backend/app/routers/voice_demo.py` | 4 个端点 + WS，鉴权依赖（REST 用 `deps.get_current_user`，WS 用 query token，对齐 `websocket_gateway.py:62` 先例） |
| `backend/app/services/voice_demo/__init__.py` | 导出网关 / 桥接 / Mock |
| `backend/app/services/voice_demo/gateway.py` | REST 上游客户端：httpx AsyncClient（`requirements.txt:32` 已有），pool 探测、transcriptions/speech 转发、超时（§3.5） |
| `backend/app/services/voice_demo/realtime_bridge.py` | WS 桥接：`websockets.connect`（`requirements.txt:129` 已有）连上游、事件透传、session.update 注入、空闲超时、并发闸（asyncio 信号量） |
| `backend/app/services/voice_demo/mock.py` | Mock 实现：样例转写、wave 正弦提示音、Realtime 事件脚本生成器 |
| `backend/tests/voice_demo/test_voice_demo_api.py` 等 | §5.1 |

依赖变更：**后端零新增依赖**（httpx、websockets 均已在 requirements.txt）。

### 3.2 接口设计（4 端点）

| 方法 | 路径 | 请求 | 响应 | 鉴权 |
|---|---|---|---|---|
| GET | `/api/v1/voice-demo/health` | — | `{mock, base_url, realtime_ws_url, pool:{size,in_use,units}\|null, ok}` | JWT 头 |
| POST | `/api/v1/voice-demo/asr/transcribe` | multipart：`file`（音频）+ 可选 `language` | `{text, language, cost_ms}` | JWT 头 |
| POST | `/api/v1/voice-demo/tts/synthesize` | JSON：`{text, voice, speed, response_format}` | `audio/wav` 二进制（`Content-Disposition` 附文件名） | JWT 头 |
| WS | `/api/v1/voice-demo/ws?token=<JWT>` | OpenAI Realtime 客户端事件（JSON 文本帧） | OpenAI Realtime 服务端事件（JSON 文本帧） | query JWT |

真实模式转发目标：`{BASE_URL}/v1/audio/transcriptions`（multipart：`file` + `language`；实测无需 `model`，可选透传）与 `{BASE_URL}/v1/audio/speech`（JSON：`input`/`voice`/`response_format:"wav"`），均 OpenAI 兼容且已于 2026-11-10 在本地 `127.0.0.1:8765` 实测通过。ASR 的 `language` 字段返回语言名（如 `"Chinese"`）而非 ISO 码，前端直接透传展示。BASE_URL 与 REALTIME_WS_URL 相互独立，可分别指向不同主机。

### 3.3 WS 桥接协议

**事件映射**（网关只增不改不删——透传为主，注入一处）：

| 来源 | 事件 | 网关行为 |
|---|---|---|
| 浏览器→上游 | `input_audio_buffer.append`、`response.cancel`、`response.create` | 透传；`response.cancel` 时另发本地 `playback.clear` 提示前端停播 |
| 网关注入（connect 时一次） | `session.update` | `{instructions: VOICE_DEMO_INSTRUCTIONS, voice: VOICE_DEMO_TTS_VOICE, turn_detection: server_vad + interrupt_response}` |
| 上游→浏览器 | `session.created/updated`、`input_audio_buffer.speech_started/stopped`、转录 delta/completed、`response.audio.delta`（base64 PCM16/24k）、`response.audio_transcription.delta`、`response.done`、`error` | 透传 |

**生命周期与保护**：
- 鉴权：query token 解 JWT 失败 → accept 前 close（1008）；对齐 duplex 网关先例
- 并发闸：`asyncio.Semaphore(VOICE_DEMO_MAX_CONCURRENCY)`（默认 1，对齐 s2s pool size 1）；满员时 accept 后发 `error {code:'UPSTREAM_BUSY'}` 并关闭
- 空闲超时：`VOICE_DEMO_WS_IDLE_TIMEOUT_S`（默认 300s）无任何帧 → 双向关闭
- 上游断连：向浏览器发 `error {code:'UPSTREAM_DISCONNECTED'}` 后关闭；前端按现有重连节流自恢复
- 心跳：上游 ping/pong 由 websockets 库托管；网关不造私有心跳

### 3.4 Mock 行为定义（无真实服务时的完整链路）

| 端点 | Mock 输出 |
|---|---|
| health | `pool` 返回 `{size:1, in_use:0, units:['mock']}`，`mock:true` |
| ASR | 固定样例文本（zh）+ `cost_ms` 模拟值；language 取请求值 |
| TTS | `wave` 模块生成 1.5s 正弦提示音（440/660Hz 交替），24kHz mono 16bit，response_format 忽略恒 wav |
| WS | connect 后回放脚本：`session.created` → 收到 append 累计 ≥ 阈值后 `speech_started` → 静默 600ms `speech_stopped` + `input_audio_transcription.completed`（三种样例轮换）→ `response.created` → 8~12 片 `response.audio.delta`（静音/微正弦 base64）+ `response.audio_transcription.delta`（逐字）→ `response.done`；`response.cancel` → 立即 `response.done`（status cancelled）|

Mock 事件形状与真实 s2s 事件**逐一同构**，前端联调不感知 Mock 与真实的差异（仅 health 与 UI 徽标区分）。

### 3.5 配置项（`VOICE_DEMO_*`，默认值即 Mock 本地可跑）

| 变量 | 默认 | 说明 |
|---|---|---|
| `VOICE_DEMO_ENABLED` | `true` | 模块总开关；false 时路由不注册 |
| `VOICE_DEMO_MOCK` | `true` | Mock 总开关（D5） |
| `VOICE_DEMO_BASE_URL` | `http://127.0.0.1:8765` | REST 上游（探测 `/v1/pool` + ASR/TTS 转发；2026-11-10 实测可用） |
| `VOICE_DEMO_REALTIME_WS_URL` | `ws://127.0.0.1:8765/v1/realtime` | 对话上游，独立于 BASE_URL（2026-11-10 实测可用） |
| `VOICE_DEMO_API_KEY` | `not-needed` | 上游鉴权占位（137 部署无鉴权） |
| `VOICE_DEMO_ASR_MODEL` | （空 = 不传） | 可选透传 multipart 的 model 参数（实测上游无需此字段） |
| `VOICE_DEMO_TTS_VOICE` / `_LANGUAGE` | `Aiden` / `auto` | TTS 默认音色/语言（9 音色清单由前端内置） |
| `VOICE_DEMO_INSTRUCTIONS` | MinWorkBuddy 工作台助手人设 | connect 注入的 instructions |
| `VOICE_DEMO_CONNECT_TIMEOUT_MS` / `_READ_TIMEOUT_MS` | `5000` / `30000` | httpx 超时 |
| `VOICE_DEMO_WS_IDLE_TIMEOUT_S` | `300` | 桥接空闲超时 |
| `VOICE_DEMO_MAX_CONCURRENCY` | `1` | 桥接并发闸（对齐 pool size 1） |

### 3.6 错误处理

沿用工程统一异常处理（loguru 记日志 + HTTPException），**不引入**参考工程的数字错误码段（工程现状无此体系，见 §1.2）：

| 场景 | 行为 |
|---|---|
| 上游 REST 不可达/超时 | 502 + detail `UPSTREAM_UNAVAILABLE`（含上游错误摘要）；日志 loguru warning |
| 上游返回非 200 | 透传状态语义：4xx→400（附上游 message），5xx→502 |
| 转写文件过大/格式不支持 | 413 / 415，上限常量 25MB |
| WS 上游忙 | `error {code:'UPSTREAM_BUSY'}` 后关闭（§3.3） |
| JWT 无效（REST/WS） | 401 / close 1008，走工程既有语义 |

---

## 4. 前端设计

### 4.1 文件清单（全部新增）

| 文件 | 职责 |
|---|---|
| `frontend/src/api/voiceDemo.ts` | REST 封装（`@/utils/request`）+ `buildVoiceDemoWsUrl()`（对齐 `api/voice.ts` 的 buildVoiceWsUrl 先例，附加 `token` query） |
| `frontend/src/views/voice-demo/VoiceDemo.vue` | 页面骨架：顶栏状态 pill（Mock/后端/BASE/WS）+ 配置抽屉 + 4 Tab（默认 `asr`，D2） |
| `frontend/src/views/voice-demo/components/AsrPanel.vue` | 上传 / VAD 录音双模式、波形条、结果与分段展示 |
| `frontend/src/views/voice-demo/components/TtsPanel.vue` | 文本、音色（9 音色按语种分组 + 自定义）、语速/格式占位、播放/下载 |
| `frontend/src/views/voice-demo/components/S2sPanel.vue` | 聊天气泡（含 partial/interrupted 态）、模拟发言输入、打断按钮、事件流日志、轮次计数 |
| `frontend/src/views/voice-demo/components/GuidePanel.vue` | 手册（原型内容 1:1 迁移） |
| `frontend/src/views/voice-demo/composables/useRealtimeS2s.ts` | WS 状态机（idle→connecting→listening→responding→interrupted）、发送音频分片、事件分发、24k 回放 |
| `frontend/src/views/voice-demo/composables/useVadRecorder.ts` | `@ricky0123/vad-web` 分段录音 → 16k mono WAV → 逐段调 transcribe |

依赖变更：**唯一前端新依赖 `@ricky0123/vad-web`**（对齐参考工程选型；精确版本实现时取参考工程 package.json）。

### 4.2 原型 → Vue 组件映射

原型 `voice-demo-preview.html` 的 DOM 结构/交互即组件蓝本：顶栏 pill 与 Mock 开关 → `VoiceDemo.vue` 工具条；`.wave` 波形 → AsrPanel；`.chat`/`.eventlog`/打断 → S2sPanel；`.drawer` 配置 → 抽屉组件（开发态读 env 注入，运行态值以 `VOICE_DEMO_*` 为准，前端下拉仅展示）。

### 4.3 音频管线（复用 `frontend/src/utils/audioDsp.ts`，289 行既有工具）

| 环节 | 实现 |
|---|---|
| 采集重采样 | 48kHz AudioWorklet 采集 → `createStreamingResampler`(48000→16000) → `encodeFloatToPcm16` → base64 分片 |
| 服务端/客户端 VAD | 对话 Tab 用服务端 VAD（s2s）；ASR 录音 Tab 用 vad-web（Silero，参数对齐参考：positive 0.5 / negative 0.35 / minSpeech 250ms / redemption 700ms） |
| 回放链 | `decodePcm16ToFloat`（24kHz）→ `createPlaybackChain`（HPF→LPF→压缩器→补偿增益）→ 播放；`response.cancel`/`playback.clear` 即刻清队 |
| 电平条 | `rmsDb` 驱动波形动画 |

### 4.4 主题复用（D4）

不做新主题机制：`useAppStore().toggleTheme()` + `tokens.css` 双皮肤；原型变量名（`--primary/--card/--text…`）在实现时映射回工程 token（`--accent/--bg-surface/--fg…`），映射表见原型 `:root` 别名注释块。

---

## 5. 测试与本地验证

### 5.1 后端（pytest，Mock 路径全覆盖）

| 用例组 | 覆盖 |
|---|---|
| `test_health` | mock 开关、pool 形状、鉴权 401 |
| `test_asr_mock` / `test_tts_mock` | multipart/JSON 入参、响应形状、WAV 可解析（wave.open 校验帧数） |
| `test_ws_mock_bridge` | `TestClient.websocket_connect`：connect → 收 `session.created`；发 append → 收 speech_started/stopped/转录/audio.delta/response.done；cancel → cancelled |
| `test_ws_auth` | 无/坏 token → close 1008 |
| `test_concurrency_gate` | 占满信号量后第二连接收 `UPSTREAM_BUSY` |
| `test_gateway_forward` | httpx MockTransport 验证转发 URL/参数/超时分支 |

### 5.2 前端（vitest）

`useRealtimeS2s` 状态机（事件序列驱动各态与打断复位）、`api/voiceDemo.ts` URL 构造（token query）、`useVadRecorder` 分段回调（mock vad-web）。

### 5.3 端到端验证步骤与预期结果

**Mock 模式（默认，零外部依赖）**
1. 后端：`uvicorn app.main:app` → `/health` 的 router_failures 无 voice-demo
2. 前端：`npm run dev` → 登录 → 打开「语音演示」
3. 预期：ASR Tab 上传任意音频出样例文本；TTS Tab 合成出提示音；对话 Tab「开始对话」→ 事件流跑完一轮脚本、气泡逐字出现、打断按钮即时停播；顶栏 Mock 徽标显示开启；深浅主题切换即时生效

**真实模式（本地 s2s，2026-11-10 已实测全功能）**
1. 服务侧（已部署）：`127.0.0.1:8765` 同主机提供 REST ASR/TTS 与 WS `/v1/realtime`
2. WS 链路先行自测（容器内 E2E 脚本）：
   `docker exec speech-to-speech-thirdparty-pipeline-1 python3 /tmp/e2e_realtime_test.py --url ws://127.0.0.1:8765/v1/realtime --audio /tmp/prompt.wav --out-dir /tmp/e2e --timeout 90`
3. REST 链路自测：curl 转写与合成各一发（命令形状见头部「实测依据」）
4. `.env`：置 `VOICE_DEMO_MOCK=false`（BASE_URL/REALTIME_WS_URL 默认已指向 `127.0.0.1:8765`，无需改）
5. 预期：health 显示真实 pool；ASR Tab 录音/上传出真实识别文本；TTS Tab 出真实语音（Aiden）；对话 Tab 对麦克风说话 → 服务端 VAD 切轮次 → 流式语音应答可打断

---

## 6. 风险与迁移

### 6.1 风险表

| # | 风险 | 缓解 |
|---|---|---|
| R1 | s2s 单实例串行（pool size 1）：多用户并发阻塞 | 网关并发闸（§3.3）+ `UPSTREAM_BUSY` 友好提示；扩容属部署侧 |
| R2 | 会话上下文由 s2s 服务端持有、无持久化，刷新即新会话 | Demo 明示于手册；P1 落库沿用 duplex 会话存储方案 |
| R3 | REST `/v1/audio/*` 属容器扩展面（上游 s2s 项目源码自带路由仅 WS/pool/usage/WebRTC，已核 `websocket_router.py`），镜像升级/换部署时可能缺失 | health 探测 `/v1/pool` + REST 冒烟各一发；缺失时 REST Tab 报 UPSTREAM_UNAVAILABLE、WS 对话不受影响；2026-11-10 本地实测两线均通 |
| R4 | query token 进访问日志 | Demo 可接受（D3）；生产化时换短时一次性 ticket |
| R5 | 浏览器兼容：AudioWorklet 需 Chrome/Edge ≥ 110；Electron 麦克风权限 | 手册列明；Electron 下验证权限配置 |
| R6 | vad-web 首次加载 Silero ONNX wasm 有延迟 | 手册提示；录音模式首帧前预加载 |

### 6.2 接入真实服务迁移步骤

1. 本地默认即真实全功能（`127.0.0.1:8765` REST + WS 同主机，2026-11-10 实测）：`.env` 仅置 `VOICE_DEMO_MOCK=false`
2. 先跑 §5.3 的容器内 E2E 与 curl 自测确认服务健康，再浏览器冒烟
3. 换主机部署：改 `VOICE_DEMO_BASE_URL` / `_REALTIME_WS_URL` / `_API_KEY`（两者可指向不同主机）
4. 回滚 = 恢复 `VOICE_DEMO_MOCK=true`，代码不动

---

## 7. 未决问题（实现前需拍板或实现时取值）

1. **菜单 SQL 是否执行**：`docs/sql/menu_voice_demo.sql` 已随实现提供，是否在本地库执行由用户定（不执行时页面可经 URL 直达 `/voice-demo`）
2. **`VOICE_DEMO_INSTRUCTIONS` 文案**：默认给「MinWorkBuddy 工作台助手」中性人设，用户可后续改 env
3. **`@ricky0123/vad-web` 精确版本**：实现时读参考工程 `mediation-web/package.json` 取同版本
4. **9 音色清单**：前端内置常量（对齐参考工程 Vivian/Serena/Uncle_Fu/Dylan/Eric/Ryan/Aiden/Ono_Anna/Sohee 按语种分组），实现时与参考前端再核对一遍分组
