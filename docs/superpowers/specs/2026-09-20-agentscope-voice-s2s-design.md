# AgentScope 2.0.8 内核替换全双工语音 Provider — 设计文档

- 日期：2026-09-20
- 状态：已批准（用户确认；前端设计模块于同日补充）
- 范围：`backend/app/duplex/voice/**`、`backend/app/config/_voice.py`、`backend/requirements.txt`、`frontend/src`（语音相关增量）、文档
- 非目标：主链路协议变更与前端迁移、Dify 集成保留、本地分体式 ASR/LLM/TTS 管线保留、网关鉴权接入、AudioWorklet 重写

## 1. 背景与目标

MinWorkBuddy 现有全双工语音（`backend/app/duplex/voice/**`）通过手写 WebSocket 对接三个 Provider：dashscope（Qwen 实时音频端到端）、s2s（本地 Docker qwen-audio-s2s）、local（Silero VAD + Paraformer + CosyVoice2 分体式管线）。其中：

- dashscope 手写实现与 AgentScope 2.0.8 的 realtime 能力重复；
- s2s 依赖外部 Docker 服务；local 管线重依赖（torch/funasr/cosyvoice）且缺依赖时产出占位假数据。

AgentScope 2.0.8 提供 `RealtimeAgent` + `DashScopeRealtimeModel`（Qwen-Omni）/ `DashScopeAudioRealtimeModel`（Qwen-Audio-3.0）/ `OpenAIRealtimeModel`，内建回合检测、打断与上下文截断、工具调用与用户确认、断线自动恢复。浏览器传输官方"即将上线"，需自定义 `TransportBase` 子类桥接。

**目标**：保留现有 `/duplex/voice/ws` 协议 v2 网关外壳与前端主链路（前端无需迁移），把手写 Provider 内核替换为 AgentScope RealtimeAgent，清理后端废弃实现与前端死代码，并新增工具确认（tool.confirm）前端增量。

**已确认的四项决策**：

1. **架构路线**：保留网关换内核（非全新端点重建、非双轨过渡）。
2. **Provider 范围**：DashScope 全换 AgentScope 内核 + 新增可选 OpenAI 备选；删除 s2s 与 local 管线。
3. **工具集成**：RealtimeAgent 原生 Toolkit（含 MCP 工具注入与 tool_policy 权限映射）；废弃 agent_adapter 的 Dify 路径，仅保留 AgentScope 直连。
4. **前端设计**：主链路协议不变（采集/播放/DSP composable 整体保留）；参考 qwen-audio-agent 前端与 AgentScope 官方示例的模式，新增 tool.confirm 确认 UI，清理前端 provider 死选项（详见 §9）。

## 2. 总体架构

```
浏览器（主链路协议 v2 不变，前端无需迁移；增量见 §9）
   │ 上行：裸 PCM16 二进制（16kHz）+ JSON 控制帧
   │ 下行：JSON 状态帧 + 二进制 PCM16（24kHz）
   ▼
websocket_gateway.py —— 保留全部外壳：
   能力协商（protocol_adapter/capabilities）、代际仲裁（turn_state）、
   重连回放（replay_buffer）、降级（fallback）、metrics、会话/轮次持久化
   ▼
providers/agentscope.py（新，唯一的真实 RealtimeProvider 实现）
   ├─ AgentscopeRealtimeProvider：实现现有 RealtimeProvider ABC
   ├─ BrowserTransport：继承 agentscope.realtime.TransportBase
   ├─ 模型工厂：按 model_id 与平台选择模型类
   └─ Toolkit 构建：tool_policy 映射 + MCP 会话工具注入
```

### 2.1 AgentscopeRealtimeProvider

实现现有 `RealtimeProvider` ABC（`connect / send_audio / send_text / configure_session / events / close / get_capabilities`）：

- 内部持有每会话一个 `agentscope.agent.RealtimeAgent`（构造参数：name、system_prompt（来自 duplex_voice_config 角色配置）、model、toolkit）。
- `send_audio(pcm)`：写入 BrowserTransport 上行队列。
- `send_text(text)`：映射为 `ControlFrame(TEXT)`；若模型不支持文本输入（`supports_text_input=False`，如 Qwen-Omni），返回明确 error 帧。
- `events()`：`async for event in agent.reply_stream(transport)` 驱动，映射为 ProviderEvent（见 §3）。
- 生命周期由网关按现有方式管理（connect/close/fallback）。

### 2.2 BrowserTransport（TransportBase 子类）

| TransportBase 成员 | 实现 |
|---|---|
| `start()` / `close()` | 队列与水位状态初始化 / 释放 |
| `incoming()` | 异步迭代器：网关收到的 PCM → `AudioFrame`；`input.message` → `ControlFrame(TEXT)`；`interrupt` → `ControlFrame(INTERRUPT)`；工具确认结果 → `ControlFrame(USER_CONFIRM)` |
| `send_audio(pcm, item_id)` | 推入下行队列，网关侧消费者转为 `audio.delta` 二进制帧下发，并累计发送水位 |
| `clear_audio()` | 清空下行队列、通知网关停止下发，返回 `PlayoutPosition`（基于发送水位模拟：无真实声卡，以已下发 PCM 累计时长为 played_ms） |
| `playout()` | 同水位计算，不清理 |
| `input_sample_rate` / `output_sample_rate` | 来自所选模型的 `model.input_sample_rate / output_sample_rate` |

重采样点：DashScope 上行 16kHz 与前端一致；OpenAI 上行 24kHz 与前端 16k 不匹配，在 BrowserTransport 内做线性插值重采样（服务端唯一保留的重采样点）。

### 2.3 模型工厂

| 条件 | 模型类 | 凭据 |
|---|---|---|
| model_id 为 `qwen3.5-omni-*-realtime` / `qwen3-omni-flash-realtime` / `qwen-omni-turbo-realtime` | `DashScopeRealtimeModel` | `DashScopeCredential(api_key)` |
| model_id 为 `qwen-audio-3.0-realtime-*` | `DashScopeAudioRealtimeModel` | 同上 |
| model_id 为 `gpt-realtime-*` 且 provider=openai | `OpenAIRealtimeModel` | `OpenAICredential(api_key)` |

- api_key / base_url 仍从数据库 `ai_api_key` / `ai_chat_model`（type=7 语音实时）解析（`voice_config.py` 现有逻辑保留，白名单改为模型类 `list_models()` 卡片推导）。
- 音色等 `parameters`（如 `DashScopeRealtimeModel.Parameters(voice=...)`）来自 `duplex_voice_config` 角色配置。

### 2.4 Toolkit 构建

- 现有 `tool_policy`（`duplex_voice_config` 关联的工具权限）映射为 agentscope Toolkit 注册的工具及权限级别。
- `mcp_session_resolver` 保留：会话级 MCP 工具注入 → 注册进同一 Toolkit。
- `RequireUserConfirmEvent` → 网关下发新协议帧 `tool.confirm_required`（§3.2）；客户端确认后以控制帧回注 `ControlFrame(USER_CONFIRM)`；超时 5 分钟按拒绝处理（AgentScope 默认行为，不中断语音流）。

## 3. 协议映射

### 3.1 事件映射（AgentScope 事件 → 现有协议 v2 帧）

| AgentScope 事件 | 协议 v2 帧 | 说明 |
|---|---|---|
| `ReplyStartEvent(role=user)` | 无（内部记录 user_turns） | |
| `ReplyStartEvent(role=assistant)` | `response_started` | |
| `TextBlockDeltaEvent` | `transcript.delta` | 带 generation；user/assistant 角色 |
| `DataBlockDeltaEvent`（音频增量） | `audio.delta` | 二进制 PCM16 下发 |
| `ReplyEndEvent` | 轮次终态 + `voice.state` + SLO 延迟记录 | |
| `ToolCallStartEvent` / `ToolCallEndEvent` | `tool_call` / `tool_result` | |
| `RequireUserConfirmEvent` | `tool.confirm_required`（新增） | 见 §3.2 |
| `ModelDisconnectedError` | provider 内部消化 | AgentScope 自动重连（DashScope ~3min 空闲），网关无感 |
| 用户打断（barge-in 或显式 `interrupt`） | `clear_audio()` → `PlayoutPosition` → 上下文截断 → generation bump → `playback_cancelled` | DashScope `truncation=NONE`：无显式截断指令，以 PlayoutPosition 修正上下文 |

### 3.2 新增协议帧（唯一增量）

服务端 → 客户端：

```json
{"type": "tool.confirm_required", "data": {"confirm_id": "...", "tool_name": "...", "arguments": {...}, "timeout_ms": 300000}}
```

客户端 → 服务端（复用现有 JSON 控制帧通道）：

```json
{"type": "tool.confirm", "data": {"confirm_id": "...", "approved": true}}
```

前端未实现该帧时不影响既有流程（工具将按超时拒绝执行）；前端可后续增量支持弹确认 UI。

### 3.3 能力协商

`voice.ready` 字段语义不变：`server_vad / native_transcription / input_sample_rate / output_sample_rate / supports_interrupt / vad_mode` 全部从 model card（`model.card`）与模型属性推导。`capabilities.py` 的 `ProviderCapabilities` 由模型工厂填充。

## 4. 清理清单

删除：

- `providers/dashscope.py`、`providers/s2s.py`（手写 WS 实现）
- `providers/local.py`、`pipeline/`（vad.py / stt.py / tts.py，含 Silero/Paraformer/CosyVoice2）
- `audio_codec.py`（后端重采样占位实现；16k 上行由前端流式重采样保证，24k 场景见 §2.2）
- `agent_adapter.py` 全部适配器（DifyAdapter / AgentScopeAdapter / DirectLLMAdapter）与 `tool_call_handler.py`（被原生 Toolkit 取代）；`AiAgentConfig.type` 枚举收敛为 `agentscope`
- `config/_voice.py`：删除 `VOICE_LOCAL_*` 六项；`VOICE_DEFAULT_PROVIDER` 值域改为 `dashscope|openai`；新增 `VOICE_OPENAI_*`（可选）
- `requirements.txt`：移除 `onnxruntime`（Silero VAD 专用）；torch/torchaudio 若无其它模块使用一并移除；确认 `agentscope[realtime]` 服务端最小依赖（自定义 Transport 不需要本地声卡/PortAudio）

修复（顺手项）：

- `ping` 控制帧误发给上游 Provider 的 bug → 改回客户端 `pong`
- `ProviderKey` 枚举与实际注册一致（`dashscope|openai`）
- `fallback.py` `resolve_backup` 改为 dashscope ⇄ openai 真实互备

保留不动：

- 网关外壳全部（websocket_gateway、protocol_adapter、capabilities、turn_state、replay_buffer、reconnect_backoff、fallback、metrics、voice_ownership）
- `voice_config.py` / `voice_session_service.py` / `voice_turn_service.py`
- 数据库表结构、`admin_voice_config` 管理端 CRUD
- 前端全部代码
- 网关鉴权 TODO 保持现状（明确超范围）

## 5. 错误处理

- 未配置 API Key / 模型不在卡片列表：沿用现有 `error` 帧 + `close(4503)` 路径。
- 模型断线：`ModelDisconnectedError` 由 provider 内部处理（AgentScope 在用户下次说话时自动重连，`agent.state` 历史转写附于系统提示后），网关与前端无感。
- Provider 故障降级：现有 `VoiceFallback`（主 → 备 → 文字模式）保留，备选映射更新为 dashscope ⇄ openai。
- 工具执行失败：Toolkit 内建错误处理，`tool_result` 帧携带失败信息，不中断语音流。

## 6. 测试策略

- 单测：
  - 事件映射（AgentScope 事件 → 协议帧，含 generation 语义）
  - BrowserTransport 队列语义（incoming/send_audio/clear_audio/playout 水位）
  - 工具确认流（confirm_required → user_confirm → 执行 / 超时拒绝）
  - 16k→24k 重采样正确性
  - 代际仲裁回归（打断后过期帧丢弃）
- 集成：mock 模型类驱动完整 WS 往返（连接 → 说话 → 回复 → 打断 → 工具调用 → 关闭）
- 冒烟：真实 DashScope API Key 端到端脚本（人工执行）
- 回归：现有 `tests/` 中语音相关用例全部通过（删除 local/s2s 相关用例）

## 7. 交付物

1. 后端代码：`providers/agentscope.py`（含 BrowserTransport、模型工厂、Toolkit 构建）+ 清理后模块
2. API 文档：`docs/api/voice-ws-protocol.md`（协议 v2 全量 + 新增 confirm 帧说明）
3. 部署配置说明：环境变量、数据库配置（ai_api_key）、`agentscope[realtime]` 依赖安装
4. 前端联调测试指南：VoiceDemo 页面冒烟步骤、确认帧增量接入说明

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| AgentScope 自动重连与现有重连回放机制交互未定义 | provider 内部消化 `ModelDisconnectedError`，网关无感；集成测试覆盖 |
| OpenAI 24kHz 上行与前端 16k 不匹配 | BrowserTransport 内重采样（§2.2） |
| `agentscope[realtime]` extra 可能引入声卡依赖 | 仅安装服务端所需子集，必要时直接依赖 `agentscope==2.0.8` 并手动补最小依赖 |
| Qwen-Omni 不支持文本输入 | `supports_text_input=False` 时 `input.message` 返回明确 error 帧，前端文字输入功能对该模型禁用提示 |
| 删除 Dify 路径影响存量配置 | `AiAgentConfig.type=dify` 的存量行在启动校验时给出明确警告日志 |

## 9. 前端设计模块

### 9.1 参考实现结论（探查事实）

| 参考源 | 实际内容 | 对本方案的价值 |
|---|---|---|
| `D:\projects\github\agentscope\examples\web_ui` | **不是** realtime 语音示例——是 React 19 聊天控制台（REST + SSE，无 WS 音频流）；全仓无 `BrowserTransport` 实现 | 借鉴其**模式**而非代码：`useMessages` 的事件聚合（REPLY_START 建 bubble → `appendEvent` 增量 → REPLY_END 收口）、`ConfirmCard` 确认卡片（`UserConfirmResultEvent{confirm_results:[{confirmed, tool_call, rules}]}` JSON 形状与 realtime `user_confirm` 控制帧 data 完全同构）、`interrupting` phase + 10s 安全超时的健壮性模式 |
| `examples/realtime/local_mic.py` + `src/agentscope/realtime/_transport/_local.py` | 官方唯一的 TransportBase 实现（声卡版） | BrowserTransport 的**实现模板**：上行限深队列（100 块满丢最旧）、下行 `_pending` 缓冲按 item_id 归零记账、`clear_audio()` 取队首 30ms 线性淡出后返回 `PlayoutPosition` |
| `D:\work\qwen-audio-agent`（web/src/realtime） | 生产级 WebUI：`useRealtimeVoice.js`（37KB 语音总控）、ScriptProcessorNode(2048) 采集、连续时间轴播放队列、麦克风生命周期管理 | 与本项目前端同构度高；其麦克风韧性（设备切换/track ended 1.5s 宽限/退避重试）列为后续可选增强，不进本期范围 |
| 本项目 `frontend/src`（现有实现） | 采集链（AEC/NS/AGC + DcBlocker + NoiseGate + 流式重采样 + PCM16）与播放链（连续时间轴 cursor + DSP + 打断即停）已**优于**官方与 qwen-audio-agent 的基础版本 | **主链路整体保留**，不做 AudioWorklet 重写（非目标） |

### 9.2 前端组件依赖图（现状）

```
router/index.ts (/duplex/voice-demo) ─► views/duplex/VoiceDemo.vue
componentMap.ts ─► 'voice-demo'        → VoiceDemo.vue
                ─► 'voice-roles'       → views/admin/duplex/config/VoiceSessionConfig.vue
                ─► 'voice-models'      → views/admin/duplex/config/VoiceModelConfig.vue
                ─► 'voice-agents'      → views/admin/ai-config/agents/AgentConfigPanel.vue
                ─► 'voice-tool-policy' → views/admin/ai/components/ToolPolicyEditor.vue

VoiceDemo.vue ─► VoiceChannel.vue ─► VoiceToolbar.vue / VoiceWaveform.vue / TurnTimeline.vue
              ─► useVoiceChannel.ts ─► api/voice.ts(buildVoiceWsUrl) / useTurnState / useReconnect
                                     ─► useToolCalls / useVoicePlayback ─► utils/audioDsp.ts
```

### 9.3 处置清单（保留 / 修改 / 新增 / 删除）

**整体保留（与内核无关）**：

| 文件 | 理由 |
|---|---|
| `composables/useVoicePlayback.ts` | 协议无关，只吃 PCM16 + 采样率 |
| `composables/useReconnect.ts` | 指数退避，无协议耦合 |
| `composables/useTurnState.ts` | 代际 + VoiceState 状态机，事件语义不变 |
| `utils/audioDsp.ts` + `utils/__tests__/audioDsp.spec.ts` | 纯 DSP 层 |
| `components/voice/VoiceWaveform.vue`、`VoiceToolbar.vue` | 纯展示/操作层 |
| `views/admin/duplex/config/VoiceSessionConfig.vue`、`VoiceModelConfig.vue`、`ToolPolicyEditor.vue` | 管理 REST 接口不变 |

**修改**：

| 文件 | 改动 |
|---|---|
| `types/voice.ts` | `VoiceProvider` 收敛为 `'dashscope' \| 'openai'`（删 `s2s`/`local`/`loopback`，`openai` 由死枚举转真实）；`VoiceEventType` 增加 `'tool.confirm_required'`；新增 `ToolConfirmPayload{confirm_id, tool_name, arguments, timeout_ms}`；`ToolCall` 增加 `status: 'pending'\|'executed'\|'rejected'` |
| `composables/useVoiceChannel.ts` | `handleFrame` 新增 `case 'tool.confirm_required'`（入 pending）；新增动作 `respondToolConfirm(callId, approved)` → 上行 `{"type":"tool.confirm","data":{"confirm_id","approved"}}`（§3.2）；`onInterrupt`/`playback_cancelled` 分支清理 pending |
| `views/duplex/VoiceDemo.vue` | provider 选项重写为 dashscope/openai；删除 `modelsFor` 平台过滤与 s2s 自适应三段（L49-88 相关）；过时 M2 里程碑文案更新 |
| `components/voice/TurnTimeline.vue` | 新增待确认卡片：参数预览 + 同意/拒绝按钮，emit 到 VoiceChannel → `respondToolConfirm`；样式参考 assistant 模块 `ToolCallRow` 与 agentscope web_ui `ConfirmCard` 模式 |
| `api/voice.ts` | `buildVoiceWsUrl` 默认 provider 保持 `dashscope`（无需改值，校验注释更新） |
| `views/admin/ai-config/agents/AgentConfigPanel.vue` | `typeOptions` 硬编码收敛为 `agentscope` 单选（删 `dify`/`direct` 死选项）；存量 dify/direct 配置行前端给只读警告提示 |

**新增**：

| 内容 | 说明 |
|---|---|
| `tool.confirm_required` 确认 UI（在 TurnTimeline 内） | 见 §9.4 |

**删除（前端死代码清理）**：

| 位置 | 内容 |
|---|---|
| `types/voice.ts` L27 | `'s2s' \| 'local' \| 'loopback'` 枚举值 |
| `VoiceDemo.vue` | s2s/local 选项、"本地 S2S（Docker）"/"本地回退"文案、`m.platform === 's2s'` 过滤逻辑 |
| `AgentConfigPanel.vue` L86-90 | `typeOptions` 中 `dify`/`direct` |
| `useToolCalls.ts` | 无删除（`update()`/`pending` 此前是死代码，本期被 confirm 流程激活） |

**注意边界（勿误删）**：`workspace.ts` 中的 `'local'` 是执行/沙箱模式；`i18n` 中 `providerDashscope` 属通用 Agent 管理页；`views/assistant` 的 Dify/SSE 渲染器与语音无关——均不在清理范围。

### 9.4 工具确认（tool.confirm_required）交互设计

```
服务端 RequireUserConfirmEvent
  → 网关下发 {"type":"tool.confirm_required","data":{"confirm_id","tool_name","arguments","timeout_ms"}}
  → 前端 pending 卡片（TurnTimeline 内联，语音不中断）
  → 用户点击 同意/拒绝
  → 上行 {"type":"tool.confirm","data":{"confirm_id","approved":true|false}}
  → 网关桥接 ControlFrame(USER_CONFIRM) → RealtimeAgent 继续执行/放弃
  → 执行完成后服务端下发 tool_call 结果帧 → 前端 update() 补全状态
```

- 超时：服务端 5 分钟（AgentScope 默认）自动按拒绝处理；`timeout_ms` 透出在前端卡片上展示倒计时（超时由服务端裁决，前端倒计时仅提示）。
- 打断联动：`playback_cancelled` / 用户 `interrupt` 时清空 pending 卡片（对应 AgentScope 侧确认请求随 reply 取消）。
- 未升级的旧前端（无确认 UI）：仅看不到卡片，工具按超时拒绝，主链路不受影响（向后兼容）。

### 9.5 PlayoutPosition 记账取舍

- `TransportBase` 契约要求 `clear_audio()` 返回"用户实际听到的毫秒数"作为 barge-in truncate 依据。官方 `_local.py` 在声卡回调记账，注释明言"浏览器端等价位置是 AudioWorklet"。
- 本期**前端零迁移**原则下，BrowserTransport 采用**服务端发送水位模拟**：`played_ms = 已下发 PCM 样本数 × 1000 / output_sample_rate`，`first_played_at = 首块下发时刻`。该值略高估（未扣网络与前端播放缓冲 ~100ms），导致 truncate 前缀偏长——对 DashScope（`truncation=NONE`，无显式截断指令）仅影响上下文修正精度，可接受。
- **后续可选增强**（不进本期）：`voice.ready` 增加 `playback_report` 能标志 → 前端基于播放 cursor 回报真实 `played_ms` → BrowserTransport `playout()/clear_audio()` 等待回报帧（官方契约推荐做法）。

### 9.6 前端测试

- 保留：`audioDsp.spec.ts`。
- 新增：`useToolCalls` 的 confirm 流转测试（pending → confirmed → executed / rejected / 超时清理 / 打断清理）；`VoiceDemo` provider 选项渲染快照更新。
- 联调：见交付物 4 的冒烟指南（VoiceDemo 页面：连接 → 对话 → 打断 → 触发带确认的工具 → 确认/拒绝 → 文字输入对 Omni 模型的禁用提示）。
