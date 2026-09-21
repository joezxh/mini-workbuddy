# 全双工语音前端联调测试指南

> 页面入口：`/duplex/voice-demo`（需先在「语音模型配置」配置可用模型）。
> 协议参考：`docs/api/voice-ws-protocol.md`。

## 冒烟清单

### 1. 连接
- 选 DashScope + 语音模型 → 输入案件编号 → 「进入语音通道」→ 「连接」
- ✅ 收到 `voice.ready`，工具栏显示「已连接」，采样率显示 `16000/24000`

### 2. 语音对话
- 开启麦克风说一句话
- ✅ 时间线出现「当事人」转写（transcript.delta user）→ 助手语音播放 + 「调解员」转写

### 3. 打断（barge-in）
- 助手回复中开口插话
- ✅ 播放立即停止，出现 `playback.cancelled`；时间线后续过期帧被丢弃
- 点「打断」按钮
- ✅ 同上（显式 interrupt）

### 4. 工具确认
- 前置：Agent 配置绑定 MCP 工具；对话触发该工具且策略要求授权
- ✅ 时间线出现黄色「待确认」卡片（工具名 + 参数预览）
- 点「同意」→ ✅ `tool_result` 补全，卡片消失，状态为「已返回」
- 点「拒绝」→ ✅ 工具不执行
- 等待 5 分钟不操作 → ✅ 服务端按拒绝处理
- 打断时有待确认卡片 → ✅ 卡片被清空

### 5. 文字输入
- 对 Omni 模型（qwen3.5-omni-*）输入文字 → ✅ 收到 `text_unsupported` error 并提示
- 对 Qwen-Audio-3.0 模型输入文字 → ✅ 正常进入对话流

### 6. 麦克风韧性
- 通话中拔出 USB 麦克风 → ✅ 工具栏出现「麦克风恢复中…」，2s 内自动恢复
- 系统静音麦克风轨道 → ✅ 1.5s 宽限内恢复有声则不重启；超宽限后自动重建
- 拒绝浏览器麦克风权限 → ✅ 「麦克风不可用：权限被拒」且不无限重试

### 7. 断线重连
- 断网 10s 后恢复 → ✅ 前端指数退避重连，收到回放状态帧后恢复对话

### 8. 降级
- 未配置 Key 时选 `provider=openai` → ✅ `provider_unavailable` error + 4503 关闭
- agentscope==2.0.8 下选 openai 平台模型 → ✅ 明确的 `NotImplementedError` 提示文案

## 单测回归

```bash
cd frontend && npx vitest run src/composables/__tests__
cd backend && .venv\Scripts\python.exe -m pytest tests/duplex/voice/ tests/unit/test_voice_registry_select.py -v
```
