# 调解语音 RTC 音频质量修复设计（方案 A：根因修复 + 轻量 DSP 播放链）

- 日期：2026-09-14
- 范围：`frontend/src/composables/useVoiceChannel.ts` 及新增音频 DSP 模块；`backend/app/mediation/voice/providers/dashscope.py`
- 对标项目：`qwen-audio-agent`（web/src/realtime/audio.js、useRealtimeVoice.js；server/src/voice/providers/dashscope.mjs）
- 目标：消除 AI 调解员回复音频中的背景噪音/回声/咔哒声，达到与 qwen-audio-agent 基本一致的语音品质

## 1. 根因清单（诊断结论）

| # | 根因 | 位置 | 严重度 |
|---|------|------|--------|
| 1 | 上行 PCM 未重采样：AudioContext 48k 采样直接发送，模型按 16k 解析，音频拉慢 3 倍、频谱畸变 | useVoiceChannel.ts `startMic` | 🔴 |
| 2 | getUserMedia 未显式声明 AEC/NS/AGC：外放时扬声器 TTS 被麦克回采，模型"听到自己"产生回声噪声 | useVoiceChannel.ts `startMic` | 🔴 |
| 3 | 下行播放无连续时间轴：逐 delta 立即 `src.start()`，重叠/缝隙产生周期性咔哒声 | useVoiceChannel.ts `playAudio` | 🟡 |
| 4 | session.update 缺 turn_detection：默认 VAD 阈值不可控，回声易误触发 | dashscope.py `configure_session` | 🟡 |
| 5 | 播放链无任何后处理：无滤波/噪声门/压缩器，底噪嘶声与削波不受控 | useVoiceChannel.ts `playAudio` | ⚪ |

## 2. 改动设计

### 2.1 新增 `frontend/src/utils/audioDsp.ts`（纯 DSP 工具，可单测）

对标 qwen-audio-agent `web/src/realtime/audio.js`，集中可测试的纯函数与轻量类：

- `createStreamingResampler()`：跨 chunk 保留插值相位的线性插值流式重采样（逐字节移植 qwen 实现），用于上行 48k→16k，避免逐帧独立重采样的相位断裂。
- `decodePcm16ToFloat(bytes) / encodeFloatToPcm16(samples)`：PCM16 ↔ Float32 转换（含 clamp）。
- `removeDcOffset(samples)`：一阶高通去直流（TTS 静音段底噪/哼声来源之一）。
- `NoiseGate` 类：样本域软噪声门。
  - 播放链阈值 `-60dBFS`、上行阈值 `-50dBFS`；attack 5ms / release 120ms（含 hangover，避免切字头字尾）。
  - 状态跨 buffer 保持（成员变量），满足"静音段 ≤ -60dBFS"验收。
- `createPlaybackChain(ctx)`：构建并返回下行 WebAudio 节点链
  `source → BiquadFilter(HPF, 80Hz, Q 0.7) → BiquadFilter(LPF, 8kHz, Q 0.7) → DynamicsCompressor(threshold -12dB, ratio 3:1, attack 3ms, release 250ms, knee 6dB) → GainNode(+2dB 补偿) → destination`
  - 所有节点随 AudioContext 运行于 48kHz。
- `AUDIO_DSP_CONFIG` 常量集中所有参数（滤波截止、门限、压缩比、采样率），**一行即可切换 300–3400Hz 电话带宽**（用户保留选项，默认采用 80Hz–8kHz 以保留 TTS 自然度）。

### 2.2 新增 `frontend/src/composables/useVoicePlayback.ts`（下行播放，~150 行）

从 useVoiceChannel 抽出播放职责（同时满足 AGENTS.md 单文件 < 400 行约束）：

- PCM 队列：合并小 delta（~100ms 批量），初始预留 0.12s 抖动缓冲，防 underrun（对标 `createPcmPlaybackQueue`，按本项目非 remote 场景简化）。
- 连续调度：`cursor = max(ctx.currentTime + 0.02, cursor)`，`source.start(cursor)`，杜绝重叠/缝隙；`source.onended` 回收。
- 每 buffer 过 `removeDcOffset` + 播放侧 `NoiseGate` 后再 `copyToChannel`。
- `interrupt()`：stop 全部未播 source、清队列、reset cursor（对接 `playback_cancelled` / `turn.onInterrupt`）。
- 暴露 `level`（peak）给波形条，替代原 `audioLevel` 逻辑。

### 2.3 改造 `frontend/src/composables/useVoiceChannel.ts`（上行 + 组装）

- `ensureAudioCtx`：`new AudioContext({ sampleRate: 48000 })`（Safari ≥14.1 支持；不支持时回退默认采样率并以其为重采样源率）。
- `startMic`：
  - `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })`。
  - 上行链：`source → ScriptProcessor(2048) → [去直流 + 上行软噪声门] → StreamingResampler(ctx.sampleRate → voice.ready.input_sample_rate，默认 16000) → PCM16 → WS`。
  - 重采样器在重连/换会话时 reset（对标 qwen 的 `inputResamplerSocket` 逻辑）。
- 下行接入 `useVoicePlayback`；`audio.delta`/`audio`/二进制帧 → `playback.push()`；`playback_cancelled` → `playback.interrupt()`。
- `ready.output_sample_rate` 作为下行 buffer 采样率（24kHz，浏览器统一重采样到 48k ctx，流内相位连续）。

### 2.4 后端 `dashscope.py: configure_session`

- 增加 `turn_detection`：默认 `{"type": "smart_turn"}`（默认模型 qwen-audio-3.0-realtime-plus 属 audio 家族，支持 smart_turn，与 qwen-audio-agent 模型目录一致）；允许 session_config 覆盖，`"off"` 时不下发（回退服务端默认 VAD）。
- 增加 `input_audio_transcription`：仅当 session_config 提供时下发（默认不下发，避免无效字段导致整个 session.update 被拒）。
- `_parse_event` 增加 `error` 事件处理：记 warning 日志（含 session.update 被拒的可观测性）。
- 不改 `input/output_sample_rate`（16k/24k 与 DashScope 一致，正确）。

## 3. 验证方案

### 3.1 单测（Node 内置 `node:test` + 原生 TS 类型剥离，零新增依赖；`frontend/src/utils/__tests__/audioDsp.spec.ts`，`npm test` 运行）

纯函数合成信号验证，可重复运行：

1. **重采样正确性**：48k→16k，1kHz 正弦 48000 样本 → 输出 16000±1 样本，过零率对应 1kHz。
2. **噪声门静音抑制**：白噪声幅值 0.0001（约 -80dBFS）过门 → 输出 RMS ≤ -60dBFS。
3. **语音保留**：-6dBFS 正弦突发过门 → 能量保留 ≥ 90%，无字头截断（attack 段）。
4. **SNR 提升**：1kHz 信号 + 带外白噪声（初始 SNR 0dB）过 HPF80+LPF8k（用双二阶系数的 JS 参考实现仿真）+ 噪声门 → SNR 提升 ≥ 15dB。
5. **PCM roundtrip**：Float→Int16→Float 误差 ≤ 1/32768。
6. **去直流**：叠加 0.01 直流的信号 → 处理后均值 |·| < 1e-4。

### 3.2 手动验收清单

- 进入「调解语音 RTC 演示」→ 进入语音通道，外放音量 50%：
  - 静音等待期无嘶声/哼声（贴近扬声器听感，目标 ≤ -60dBFS）；
  - 全程对话无周期性咔哒声（连续调度生效）；
  - 外放情况下 AI 不因回声自言自语（AEC 生效）；
  - 打断按钮：AI 播放立即停止、无残响拖尾；
  - 用户语音转写与 qwen-audio-agent 体验一致（重采样修复后 ASR 正常）。

### 3.3 已知边界

- ≥15dB SNR 的实测需现场录音分析；单测提供合成信号下限保障。
- ScriptProcessorNode 已被标记 deprecated，但 qwen-audio-agent 同样使用且 2048 帧延迟可控；AudioWorklet 迁移不在本次范围。

## 4. 不做的事（YAGNI）

- ❌ RNNoise WASM（~900KB + CPU 代价，TTS 源底噪低，收益存疑；验证不达标再引入）
- ❌ AudioWorklet 迁移
- ❌ 声纹/说话人增强
- ❌ 后端 LocalProvider 降噪

## 5. 风险与回退

| 风险 | 缓解 |
|------|------|
| 48k 强制采样率在旧浏览器不支持 | try/catch 回退默认采样率，以其为重采样源率 |
| smart_turn 对非默认模型无效致 session.update 被拒 | session_config 可覆盖/关闭；error 事件落日志可观测 |
| 噪声门误切轻声尾音 | release 120ms + hangover；阈值仅 -60dBFS（只切嘶声不切语音） |
| DynamicsCompressor 引入可感延迟 | attack 3ms/release 250ms，DynamicsCompressorNode 无 lookahead，实测延迟 < 10ms |
