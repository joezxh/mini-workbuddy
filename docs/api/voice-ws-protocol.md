# 调解语音 WebSocket 协议 v2（AgentScope RealtimeAgent 内核）

> 更新：2026-09-22。内核已替换为 AgentScope 2.0.8 `RealtimeAgent`
> （`backend/app/duplex/voice/providers/agentscope.py`），协议 v2 主链路不变。
> 本文档为前后端对接的权威参考。

## 1. 端点与握手

```
ws(s)://<host>/api/v1/duplex/voice/ws
    ?case_number=<案件号>            # 可选，缺省回退 session_id
    &session_id=<会话ID>             # 可选，缺省自动生成 uuid
    &participant_id=<当事人ID>       # 可选，缺省 party_a
    &provider=dashscope|openai       # 可选，缺省 dashscope
    &model_id=<语音模型ID>           # 可选，缺省数据库默认语音模型
    &agent_id=<语音Agent配置ID>      # 可选，绑定时注入 MCP 工具
    &client_caps=<URL编码JSON>       # 可选，客户端能力声明
```

`client_caps` 示例（当前仅消费 `vad_mode`）：

```json
{"vad_mode": "server", "transcription": true}
```

握手成功后服务端首先下发 `voice.ready`；未配置语音模型 / API Key 为空 /
模型名无效时下发 `error` 帧并以 **4503** 关闭连接。

## 2. 上行（客户端 → 服务端）

### 2.1 二进制音频帧

裸 **PCM16** 字节流：16kHz、单声道、小端 int16。无任何包头。
前端经流式重采样保证 16k（`frontend/src/utils/audioDsp.ts` 的 `createStreamingResampler`）。

> openai 平台模型上行率 24kHz，与服务端 `input_sample_rate` 不一致时由
> 服务端 BrowserTransport 线性插值重采样（前端无感）。

### 2.2 JSON 控制帧

```jsonc
// 文本输入（受 15s inactivity 超时保护；Qwen-Omni 不支持文本输入，
// 将收到 code=text_unsupported 的 error 帧）
{"type": "input.message", "text": "你好"}

// 用户打断：代际 +1，此后过期 generation 帧（audio.delta/transcript.delta）
// 应被客户端丢弃；同时触发服务端 barge-in 截断
{"type": "interrupt"}

// 工具确认结果（见 §3.2）
{"type": "tool.confirm", "data": {"confirm_id": "call_1", "approved": true}}

// 心跳（服务端直接回 pong，不转发上游）
{"type": "ping"}

// 存量 no-op（保留兼容，服务端忽略）
{"type": "input.mute"}
{"type": "output.mode"}
```

## 3. 下行（服务端 → 客户端）

### 3.1 状态与数据帧

```jsonc
// 握手完成（首个帧）。客户端据此设置采集重采样目标率与播放采样率
{"type": "voice.ready", "data": {
    "session_id": 123,
    "provider": "dashscope",
    "input_sample_rate": 16000,
    "output_sample_rate": 24000,
    "server_vad": true,
    "native_transcription": true,
    "supports_interrupt": true,
    "vad_mode": "server"
}}

// 转写增量（role: user|assistant；generation 用于代际仲裁）
{"type": "transcript.delta", "data": {"text": "你好", "role": "user"}, "generation": 3}
{"type": "transcript.final",  "data": {"text": "...", "role": "user"}}

// 音频增量：二进制 PCM16 @ output_sample_rate（24kHz），无 JSON 包裹
// （二进制帧即音频本体）

// 轮次与状态
{"type": "turn.started", "data": {}}
{"type": "response.started", "data": {}}
{"type": "voice.state", "data": {"state": "listening|processing|speaking|idle"}}
{"type": "playback.cancelled", "data": {"item_id": "...", "played_ms": 500, "reason": "barge_in"}}

// 工具调用开始（call_id 供 tool_result 关联）
{"type": "tool_call", "data": {"call_id": "call_1", "name": "database_query"}}

// 工具执行结果（state 为 AgentScope ToolResultState：success|error|interrupted|denied|running）
{"type": "tool_result", "data": {"call_id": "call_1", "state": "success"}}

// 回复结束（playback.ended 为内核透传帧）
{"type": "playback.ended", "data": {"reply_id": "...", "finished_reason": "completed"}}

// 心跳应答
{"type": "pong"}

// 错误（code 见 §4）
{"type": "error", "code": "provider_unavailable", "message": "..."}
```

### 3.2 工具确认（tool.confirm_required，新增）

Agent 绑定的 MCP 工具需要用户授权时，服务端下发确认请求（**语音流不中断**）：

```jsonc
{"type": "tool.confirm_required", "data": {
    "confirm_id": "call_1",          // 回传 tool.confirm 时使用
    "tool_name": "database_query",
    "arguments": {"query": "select 1"},
    "timeout_ms": 300000             // 5 分钟，超时服务端按拒绝处理
}}
```

客户端回传（§2.2）：

```json
{"type": "tool.confirm", "data": {"confirm_id": "call_1", "approved": true}}
```

流程要点：
- 确认执行后结果经 `tool_result` 帧补全（按 `call_id` 关联）；
- 用户打断 / `playback.cancelled` 时服务端清空待确认请求，客户端应同步撤卡；
- 旧前端无确认 UI 时主链路不受影响（超时自动拒绝）。

## 4. 代际仲裁与错误码

**generation**：轮次代际计数。客户端 `interrupt` 或服务端 VAD barge-in
（`playback.cancelled`）都会 +1；`audio.delta` / `transcript.delta` 帧携带
发出时的 generation，客户端对 `generation < 本地当前值` 的帧直接丢弃
（`useTurnState.isStale()`）。

**error code 一览**：

| code | 场景 | 客户端处置 |
|---|---|---|
| `provider_unavailable` | 未配置语音模型 / API Key 为空 / 连接失败 | 提示后重连（服务端随发 4503 关闭） |
| `inactivity` | 文本输入后 15s 无响应 | 复位聆听态，提示重试 |
| `text_unsupported` | 模型不支持文本输入（Qwen-Omni） | 禁用文字输入入口 |
| `not_connected` | 会话未就绪时收到控制帧 | 忽略 / 提示重连 |
| `fatal` | 内核事件泵异常 | 断开重连 |
| `other` | 其它 | 记录日志 |

**WS 关闭码**：`4503` = Provider 不可用（握手阶段失败）。

## 5. Provider 差异

| | dashscope（默认） | openai（备选） |
|---|---|---|
| 模型 | `qwen3.5-omni-*-realtime`、`qwen-audio-3.0-realtime-*` | `gpt-realtime-*` |
| 文本输入 | **不支持**（`text_unsupported`） | 支持 |
| 上行采样率 | 16kHz（与前端一致，无重采样） | 24kHz（服务端重采样） |
| 截断（truncation） | NONE（以 PlayoutPosition 修正上下文） | 同左 |
| 可用性 | 需 DashScope API Key | **需 agentscope > 2.0.8**（当前版本连接时返回明确 `NotImplementedError` 文案） |

## 6. 断线重连

- 客户端断线重连（同一 `session_id`）后，服务端先回放 `ReplayBuffer` 缓冲的
  状态帧（不含二进制音频），再下发 `voice.ready`；
- 模型侧空闲超时（DashScope 约 3 分钟）由 AgentScope 自动重连恢复，
  历史转写随 `agent.state` 重放，对客户端透明。

