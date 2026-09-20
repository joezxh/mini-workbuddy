# AgentScope 2.0.8 内核替换全双工语音 Provider — 设计文档

- 日期：2026-09-20
- 状态：已批准（用户确认）
- 范围：`backend/app/duplex/voice/**`、`backend/app/config/_voice.py`、`backend/requirements.txt`、文档
- 非目标：前端改动、Dify 集成保留、本地分体式 ASR/LLM/TTS 管线保留、网关鉴权接入

## 1. 背景与目标

MinWorkBuddy 现有全双工语音（`backend/app/duplex/voice/**`）通过手写 WebSocket 对接三个 Provider：dashscope（Qwen 实时音频端到端）、s2s（本地 Docker qwen-audio-s2s）、local（Silero VAD + Paraformer + CosyVoice2 分体式管线）。其中：

- dashscope 手写实现与 AgentScope 2.0.8 的 realtime 能力重复；
- s2s 依赖外部 Docker 服务；local 管线重依赖（torch/funasr/cosyvoice）且缺依赖时产出占位假数据。

AgentScope 2.0.8 提供 `RealtimeAgent` + `DashScopeRealtimeModel`（Qwen-Omni）/ `DashScopeAudioRealtimeModel`（Qwen-Audio-3.0）/ `OpenAIRealtimeModel`，内建回合检测、打断与上下文截断、工具调用与用户确认、断线自动恢复。浏览器传输官方"即将上线"，需自定义 `TransportBase` 子类桥接。

**目标**：保留现有 `/duplex/voice/ws` 协议 v2 网关外壳与前端零改动，把手写 Provider 内核替换为 AgentScope RealtimeAgent，并清理废弃实现。

**已确认的三项决策**：

1. **架构路线**：保留网关换内核（非全新端点重建、非双轨过渡）。
2. **Provider 范围**：DashScope 全换 AgentScope 内核 + 新增可选 OpenAI 备选；删除 s2s 与 local 管线。
3. **工具集成**：RealtimeAgent 原生 Toolkit（含 MCP 工具注入与 tool_policy 权限映射）；废弃 agent_adapter 的 Dify 路径，仅保留 AgentScope 直连。

## 2. 总体架构

```
浏览器（协议 v2 完全不变，前端零改动）
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
{"type": "tool.confirm_required", "data": {"confirm_id": "...", "tool_name": "...", "arguments": {...}}}
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
