# 调解语音 RTC 部署与运维说明（M4）

对应计划：`2026-09-08-mediation-voice-rtc.md` Milestone 4。

## 1. 部署形态

**内嵌部署，无新增服务**：语音能力全部内嵌在既有 FastAPI 后端中。

| 组件 | 位置 | 说明 |
|------|------|------|
| WS 网关 | `app/mediation/voice/websocket_gateway.py` | 挂载于 `/api/v1/mediation/voice/ws` |
| Provider | `app/mediation/voice/providers/` | `dashscope`（云端）/ `local`（本地私有化） |
| 本地管线 | `app/mediation/voice/pipeline/` | Silero VAD / Paraformer STT / CosyVoice2 TTS |
| 配置端点 | `app/routers/admin_voice_config.py` | `/api/v1/admin/mediation/config/*` |
| 指标端点 | `/api/v1/mediation/voice/metrics` | Prometheus 文本格式 |

前端入口：`/mediation/voice-demo`（语音 RTC 演示）。
配置面板：`AgentConfigPanel` / `VoiceSessionConfig` / `ToolPolicyEditor`。

## 2. 配置项（`app/config.py`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VOICE_DEFAULT_PROVIDER` | `dashscope` | 默认 Provider |
| `VOICE_INPUT_SAMPLE_RATE` | `16000` | 上行采样率 |
| `VOICE_OUTPUT_SAMPLE_RATE` | `24000` | 下行采样率 |
| `VOICE_RESPONSE_START_TIMEOUT_MS` | `3000` | 首响应超时 |
| `VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS` | `15000` | 响应不活动超时（超时下发 `error(inactivity)`） |
| `VOICE_RECONNECT_MAX` | `5` | 最大重连次数 |
| `VOICE_LOCAL_PIPELINE_URL` | `ws://127.0.0.1:8765` | 本地管线端点 |
| `VOICE_VAD_THRESHOLD` | `0.55` | VAD 阈值 |
| `VOICE_LOCAL_ENABLED` | `False` | **本地管线总开关** |
| `VOICE_LOCAL_VAD_MODEL` | `""` | `silero_vad.onnx` 路径 |
| `VOICE_LOCAL_STT_MODEL` | `""` | Paraformer 模型名/路径 |
| `VOICE_LOCAL_TTS_MODEL` | `""` | CosyVoice2 模型路径 |
| `VOICE_LOCAL_TTS_SPEED` | `0.95` | TTS 语速 |

配置通过环境变量或 `.env` 覆盖（`SettingsConfigDict(env_file=[".env", "backend/.env"])`）。

## 3. 本地私有化管线启用步骤

1. 安装重型依赖（**仅 M4 需要，M1–M3 不依赖**）：
   ```bash
   pip install onnxruntime funasr
   # CosyVoice2 按其官方仓库说明安装与下载权重
   ```
2. 准备模型：
   - Silero VAD：下载 `silero_vad.onnx`，配置 `VOICE_LOCAL_VAD_MODEL` 指向该文件
   - Paraformer：配置 `VOICE_LOCAL_STT_MODEL`（如 `paraformer-zh-streaming`）
   - CosyVoice2：配置 `VOICE_LOCAL_TTS_MODEL` 指向权重目录
3. 打开开关：
   ```bash
   VOICE_LOCAL_ENABLED=1
   VOICE_DEFAULT_PROVIDER=local
   ```
4. 启动后端，访问 `/api/v1/mediation/voice/metrics` 观察指标。

> **未装依赖时的行为**：各 stage 惰性加载，缺依赖时优雅降级
> （能量法 VAD / 占位转写 / 静音 wav），编排仍可跑通，但**不具备生产精度**。
> 生产上线前必须确认三个 `available()` 均为 True。

## 4. 降级链

```
LocalProvider 未配置（VOICE_LOCAL_ENABLED=0 或模型缺失）
      ↓ ProviderRegistry.select() 自动回退
DashScopeProvider
      ↓ 连接失败（Provider 不可用）
VoiceFallback.with_fallback → 备用 Provider
      ↓ 全部失败
降级为文字模式（text_only）
```

- 选型：`ProviderRegistry.select("local")` —— local 未配置时自动返回 `dashscope` 并打告警日志。
- 超时：`input.message` 受 `VOICE_RESPONSE_INACTIVITY_TIMEOUT_MS` 保护，超时下发 `error(inactivity)` 并复位聆听态。
- 重连：客户端指数退避（0.5s 起、×2、上限 8s、最多 `VOICE_RECONNECT_MAX` 次），重连后回放缓冲帧。

## 5. 数据库与迁移

语音相关共 5 张表：

| 表 | 迁移 |
|----|------|
| `mediation_voice_session` | `20260908_mediation_voice_tables` |
| `mediation_voice_turn` | `20260908_mediation_voice_tables` |
| `mediation_voice_config` | `20260908_mediation_voice_config_tables` |
| `ai_agent_config` | `20260908_mediation_voice_config_tables` |
| `tool_policy` | `20260908_mediation_voice_config_tables` |

- 开发环境：`AUTO_CREATE_TABLES=True` 时由 `Base.metadata.create_all` 自动建表
  （模型登记唯一来源：`app/db/init_models.py`）。
- 生产环境：置 `AUTO_CREATE_TABLES=False`，执行
  ```bash
  cd backend && alembic upgrade head
  ```
  迁移均为幂等（建表前检查 `information_schema`）。

## 6. 健康检查与观测

- 指标端点：`GET /api/v1/mediation/voice/metrics`（Prometheus 文本格式）
- 关键指标：
  - `voice_ws_connections`：活跃 WS 连接数
  - `voice_e2e_latency_seconds`：用户说完 → AI 首音频
  - `voice_bargein_latency_seconds`：打断生效延迟
  - `voice_provider_errors_total{provider}`：Provider 错误
  - `voice_tool_call_failures_total`：工具调用失败
- `is_configured()` 用于就绪判定：本地管线不可用时切勿将其选为默认 Provider。

## 7. 压测与故障注入

```bash
cd backend
python scripts/voice_loadtest.py --concurrency 50 --turns 3 \
    --url ws://127.0.0.1:8000/api/v1/mediation/voice/ws
```

故障注入建议：
1. **Provider 不可用**：关闭本地管线端点或置错误密钥 → 观察是否降级到备用/文字模式，
   `voice_provider_errors_total` 递增。
2. **WS 断连**：压测中 kill 客户端 → 观察指数退避重连与缓冲帧回放。
3. **响应超时**：注入慢响应 → 观察 `error(inactivity)` 与状态复位。

## 8. 安全

- `_authenticate()` 当前为开发态放行，**生产接入前必须接 JWT**（见网关内 TODO）。
- 建议按 `participant_id` 做会话级鉴权，避免越权接入他人调解会话。

---

## 9. 验收后配置补充（M2–M4 收尾）

> M2–M4 落地后、UAT 阶段暴露并修复的问题，对应部署/运维侧必须补齐的配置项。

### 9.1 依赖：prometheus_client 必须安装

- `app/mediation/voice/metrics.py` 已对 `prometheus_client` 做 `try/except ImportError` 降级（缺失时指标端点不可用，但主应用可正常启动）。
- **部署要求**：在目标环境安装 `prometheus_client>=0.20.0`（`requirements.txt` 已加入），否则 `/metrics` 类指标不可用。

### 9.2 语音模型必须初始化并填 Key

- 语音实时模型配置**已数据库化**（不再依赖环境变量 `DASHSCOPE_API_KEY`）。
- **部署步骤**：
  1. 执行种子 SQL：`docs/sql/45_voice_realtime_init.sql`
     - 插入 `ai_api_key`（平台 `DashScope`，`url=wss://dashscope.aliyuncs.com/api-ws/v1/realtime`）。
     - 插入 `ai_chat_model`（`model=qwen-audio-3.0-realtime-plus`，`type=7` 语音实时，`is_default=true`）。
     - SQL 幂等，可重复执行；含 `UPDATE ai_chat_model SET type=7 WHERE type=6` 归正早期误写值。
     - 默认模型按「同 type 全局唯一」维护（同一时刻仅一个 `is_default=true`）。
  2. 在 `ai_api_key` 行填入**真实 DashScope API Key**（种子中 `api_key` 为空占位；`voice_config.resolve_voice_config` 在 `api_key` 为空时返回 `configured=False, reason=empty_key`，连接会被拒绝并报「请在『API Key 管理』中填写真实 Key」——注意密钥在「API Key 管理」页填写，「语音模型配置」页改不了密钥）。
  3. 后台「语音模型配置」页可切换默认模型。
- **健康检查**：`GET /api/v1/admin/mediation/config/voice-models/default` 返回 `configured`（`true/false`）与 `reason`（`no_model` / `empty_key`），可用于上线前确认语音模型已配置且密钥非空。
- **参考**：模型参数取自 `qwen-audio-agent` 的 `config/settings.json`（`voice.dashscope`）。

### 9.3 前端菜单录入

- 执行语音 RTC 设置菜单录入 SQL（演示 + 配置共 4 条），使菜单在「设置」下可见；admin 菜单通过 `componentMap` 按 `menuKey=path 末段` 注册组件（`voice-demo` / `voice-models` 等）。

### 9.4 前端 WS 连接参数

- 前端连接 `/api/v1/mediation/voice/ws` 必须携带 `case_number` / `participant_id` / `provider` 参数；网关已对 `case_number`/`participant_id` 取默认值兜底，缺参不再整体拒绝（422）。
