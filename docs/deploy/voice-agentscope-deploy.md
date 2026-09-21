# 全双工语音（AgentScope RealtimeAgent 内核）部署配置说明

> 适用：`feature/agentscope-voice-s2s` 及之后版本。协议详见 `docs/api/voice-ws-protocol.md`。

## 1. 依赖

| 项 | 说明 |
|---|---|
| Python | 3.11+（与后端一致） |
| agentscope | `==2.0.8`（realtime 内核；已固定于 `backend/requirements.txt`） |
| mcp | `>=1.15.0,<2.0.0`（agentscope streamable_http_client 要求） |
| 已移除 | `torch / torchvision / torchaudio / sentence-transformers / onnxruntime`（原 local 语音管线与本地 embedding 专用） |
| 外部服务 | **无**（原 s2s Docker 已废除；DashScope 走公网 WebSocket） |

安装：

```bash
cd backend
pip install -r requirements.txt
# 验证 realtime 内核可导入
python -c "from agentscope.realtime import DashScopeRealtimeModel, DashScopeAudioRealtimeModel; print('ok')"
```

## 2. 环境变量（backend/app/config/_voice.py）

| 变量 | 默认 | 说明 |
|---|---|---|
| `VOICE_DEFAULT_PROVIDER` | `dashscope` | 值域 `dashscope \| openai` |
| `VOICE_INPUT_SAMPLE_RATE` | `16000` | 上行采样率（dashscope） |
| `VOICE_OUTPUT_SAMPLE_RATE` | `24000` | 下行采样率 |
| `VOICE_RESPONSE_START_TIMEOUT_MS` | `3000` | 首响应超时 |
| `VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS` | `15000` | 文本输入不活动超时 |
| `VOICE_RECONNECT_MAX` | `5` | 客户端重连上限 |

已删除：`VOICE_LOCAL_PIPELINE_URL / VOICE_LOCAL_ENABLED / VOICE_LOCAL_VAD_MODEL /
VOICE_LOCAL_STT_MODEL / VOICE_LOCAL_TTS_MODEL / VOICE_LOCAL_TTS_SPEED`。

## 3. 数据库配置

语音模型复用 `ai_api_key` + `ai_chat_model`（type=7）两表，管理页「语音模型配置」：

1. **API Key 管理**：新增 Key，`platform` 填 `DashScope`（或 `openai`），填入真实 api_key；
2. **语音模型配置**：新增模型行绑定该 Key，`model` 必须是有效实时模型名：
   - DashScope：`qwen3.5-omni-plus-realtime`、`qwen3.5-omni-flash-realtime`、
     `qwen-audio-3.0-realtime-plus`、`qwen-audio-3.0-realtime-flash`
   - openai：`gpt-realtime-*`（**需 agentscope > 2.0.8**，当前版本连接时返回明确错误）
3. 设默认模型（或前端 `model_id` 指定）。

工具确认：Agent 配置（`ai_agent_config`，type 固定 `agentscope`）的 `mcp_bindings`
绑定 MCP 服务后，会话建立时自动注入工具 schema；需要用户授权的工具会在
语音流中下发 `tool.confirm_required` 帧。

## 4. 启动验证

```bash
# 指标端点可访问
curl http://127.0.0.1:8000/api/v1/duplex/voice/metrics
# VoiceDemo 页面（/duplex/voice-demo）连接 → 收到 voice.ready 即部署成功
```
