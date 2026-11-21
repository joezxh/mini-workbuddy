# 全双工语音编排管理设计（Agent / 渠道 / 输出 / 会话）

日期：2026-11-16
范围：`backend/app/duplex/voice/*`、`backend/app/routers/duplex/orchestration.py`、`frontend/src/views/duplex/*`

## 1. 背景与目标

全双工语音演示页从「架构说明型」转为「真实交互型」：主工作区三 Tab（语音通道 / 输出渠道管理 / Agent 编排器设计管理），右侧会话列表，底部输入/输出流。后端需为两类管理 Tab 提供配置读写能力，并把 Agent 切换原因、输出目标、播放状态结构化回传给前端。

设计原则：
- **增量增强，不重写**：在既有 `orchestrator.py` / `channels/*` / `websocket_gateway.py` 上扩展。
- **如实标注**：渠道真实外发能力用 `capability` 表达，模拟分发不伪装成发送成功。
- **优雅降级**：REST 不可用时前端保留本地默认配置，不阻断语音会话。
- **零迁移**：配置存于进程内单例（`orchestration_store`），重启回落内置默认；生产可平滑替换为 DB。

## 2. 数据流

```
前端三 Tab ──REST(/api/v1/duplex/*)──> orchestration_store（Agent/渠道配置）
     │                                        │
     │                              网关建会话时读取配置
     │                                        ▼
     └──WS(channel_config/切换帧)──> websocket_gateway ──> orchestrator / ChannelRegistry
                                          │
                          playback.ended  │  agent_switched(带 reason)
                                          ▼
                          AiChatMessage.extra_data + output.dispatched 事件
                                          ▼
                          底部 IO 流展示输出目标 / 播放状态 / 激活原因
```

## 3. Agent 编排器设计管理

### 3.1 数据模型（`orchestration_store.AgentConfig`）
| 字段 | 类型 | 说明 |
|---|---|---|
| key | str | 与后端插件 key 一一对应（ecommerce_sales 等 5 个） |
| name | str | 展示名称 |
| icon / desc | str | 展示元数据 |
| enabled | bool | 启停；停用后网关不注册该插件，无法被切换 |
| priority | int | 编排优先级；网关在无默认 Agent 时取优先级最小者 |
| prompt | str | System Prompt（来自插件） |
| rules | str[] | 触发规则（意图/关键词） |
| tools | str[] | 工具绑定 |

### 3.2 切换原因（reason）
`VoiceAgentOrchestrator.switch_to(key, reason)` 记录 `_last_switch_reason`，`agent_switched` 帧携带：
```json
{"type":"agent_switched","data":{
  "agent_key":"cross_border","agent_name":"跨境贸易助手",
  "previous_agent":"ecommerce_sales","reason":"intent"}}
```
reason 取值：`intent`（意图命中）/ `state_yield`（状态让渡）/ `manual`（手动）/ `default`（默认）。前端据此映射细粒度徽章（语音激活/文字激活/意图命中/当前默认）。

### 3.3 REST
- `GET /api/v1/duplex/agents` — 列出全部 Agent 配置
- `POST /api/v1/duplex/agents` — 按 key 幂等新增/更新
- `DELETE /api/v1/duplex/agents/{key}` — 删除配置（回落插件默认）

## 4. 输出渠道管理

### 4.1 能力状态（capability，如实标注）
| 值 | 含义 |
|---|---|
| enabled | 后端已具备真实外发 |
| configured | 已配置凭据，真实外发待启用 |
| pending_backend | 当前模拟分发（日志+事件帧） |
| unsupported | 后端未接入（如短信），启用仅记日志 |

### 4.2 "关闭/不发送"语义
后端 `OutputMode` 仅接受 `text/voice/both`。界面选择「关闭」时：前端下发 `active=false` 且 `output` 保留上一合法值；REST `output=off` 亦映射为 `active=false`，避免后端静默忽略。

### 4.3 ACK 回执
`channel_config` 控制帧处理后，网关下发：
```json
{"type":"channel_config_ack","data":{
  "applied":true,"active_count":2,"channels":[/* snapshot */]}}
```
前端同步状态：idle「已下发（本地）」→ pending「等待 ACK」→ acked「后端已确认」。

### 4.4 REST
- `GET /api/v1/duplex/channels` — 列出全部渠道配置
- `POST /api/v1/duplex/channels` — 按 key 幂等新增/更新
- `DELETE /api/v1/duplex/channels/{key}` — 删除

## 5. 输出信息回传

`playback.ended` 时：
1. 编排器 `on_assistant_response_end` 调用 `dispatcher.dispatch_detailed()` 生成结构化分发结果（每渠道 key/name/mode/capability/status）。
2. 助手消息落库 `AiChatMessage`：`message_type="voice"`，`extra_data` 含 `playback_status/agent_key/channels/dispatch`。
3. 下发 `output.dispatched` 事件供前端 IO 流展示"→ 微信(语音) · WhatsApp(文字)"与播放完成状态。

`_save_chat_message` 扩展签名支持 `message_type` 与 `extra_data`，不改变既有 `content` 语义。

## 6. 会话列表

`GET /api/v1/duplex/sessions?session_type=voice` 直接按 `AiChatSession.session_type` 过滤（不修改 `AiChatService` 签名），返回标题/消息数/更新时间/session_id/状态，供右侧会话列表。点击后用既有 `getSession/getSessionMessages` 加载历史消息到底部 IO 流；用户消息=输入，助手/系统消息=输出，`message_type=voice` 标注语音完成状态。

## 7. 前端组件结构

```
DuplexDemo.vue（组合主页面，持有 composable / 配置 / 会话 / 事件日志）
├── components/VoiceChannelPanel.vue   语音通道 Tab
├── components/ChannelManagerPanel.vue 输出渠道管理 Tab（完整 CRUD）
├── components/AgentOrchestratorManagerPanel.vue Agent 设计管理 Tab（完整 CRUD）
├── components/SessionListPanel.vue    右侧会话列表
├── components/IoStreamPanel.vue       底部输入/输出流
├── components/EventLogPanel.vue       运行时事件流
└── types.ts                           归一化消息与展示模型
```

## 8. 验证

- 前端：`npm run build` 过滤 `views/duplex` 路径 0 报错。
- 后端：`pytest tests/unit/test_voice_channels.py tests/unit/test_duplex_orchestration.py` — 17 passed。
- 兼容：核心连接/麦克风/打断/文字/模型选择/会话详情弹窗行为零改动；存量 8 个渠道测试保持通过。
