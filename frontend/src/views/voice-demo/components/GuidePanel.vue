<template>
  <div class="guide">
    <h3>功能总览</h3>
    <table class="seg">
      <thead><tr><th>Tab</th><th>能力</th><th>通信方式</th><th>依赖</th></tr></thead>
      <tbody>
        <tr><td>语音转写（ASR）</td><td>上传转写 / 录音 VAD 分段转写（起止 ms + 文本）</td><td>HTTP REST（multipart）</td><td>s2s /v1/audio/transcriptions</td></tr>
        <tr><td>语音合成（TTS）</td><td>文本→音频，9 音色按语种分组，播放 / 下载</td><td>HTTP REST（JSON→blob）</td><td>s2s /v1/audio/speech</td></tr>
        <tr><td>语音对话（S2S）</td><td>连续语音对话：服务端 VAD 切轮次、逐句转录上屏、流式音频回放、可打断</td><td>WebSocket（OpenAI Realtime 事件集）</td><td>s2s /v1/realtime</td></tr>
        <tr><td>使用手册</td><td>静态说明（本页内容）</td><td>—</td><td>无</td></tr>
      </tbody>
    </table>

    <h3>实时对话链路</h3>
    <ol class="flow">
      <li><b>浏览器 AudioWorklet</b>：48kHz 采集 → 16kHz PCM16 分片（base64）</li>
      <li><b>WebSocket</b>：JWT 鉴权 query 参数（对齐 duplex/voice 先例）</li>
      <li><b>后端 WS 桥接网关</b>：<code>/api/v1/voice-demo/ws</code> · 会话登记 / 事件透传 / 心跳与超时</li>
      <li><b>WebSocket</b>：OpenAI Realtime 协议</li>
      <li><b>speech-to-speech 服务</b>：VAD(Silero) → STT(Parakeet) → LLM(OpenAI 兼容) → TTS(Qwen3)</li>
      <li><b>事件回流</b>：转录 / response.audio.delta / response.done</li>
      <li><b>浏览器播放链</b>：PCM16 24kHz → 重采样 → 噪声门 → 播放（复用 audioDsp）</li>
    </ol>

    <h3>后端接口一览（新增模块 /api/v1/voice-demo）</h3>
    <table class="seg">
      <thead><tr><th>方法</th><th>路径</th><th>说明</th><th>鉴权</th></tr></thead>
      <tbody>
        <tr><td>GET</td><td><code>/api/v1/voice-demo/health</code></td><td>探测上游服务（GET /v1/pool）+ 返回生效配置摘要</td><td>JWT</td></tr>
        <tr><td>POST</td><td><code>/api/v1/voice-demo/asr/transcribe</code></td><td>multipart 转发 ASR → {text, language, cost_ms}</td><td>JWT</td></tr>
        <tr><td>POST</td><td><code>/api/v1/voice-demo/tts/synthesize</code></td><td>JSON 转发 TTS → audio/wav 二进制</td><td>JWT</td></tr>
        <tr><td>WS</td><td><code>/api/v1/voice-demo/ws?token=&lt;JWT&gt;</code></td><td>OpenAI Realtime 双向桥接；connect 自动 session.update 注入人设</td><td>query JWT（对齐 duplex 网关先例）</td></tr>
      </tbody>
    </table>

    <h3>配置项（backend/.env，config/_voice_demo.py 的 VOICE_DEMO_* 段）</h3>
    <table class="seg">
      <thead><tr><th>变量</th><th>默认值</th><th>说明</th></tr></thead>
      <tbody>
        <tr><td><code>VOICE_DEMO_ENABLED</code></td><td>true</td><td>模块总开关</td></tr>
        <tr><td><code>VOICE_DEMO_BASE_URL</code></td><td>http://127.0.0.1:8765</td><td>REST 基址（探测 /v1/pool + ASR/TTS 转发）</td></tr>
        <tr><td><code>VOICE_DEMO_REALTIME_WS_URL</code></td><td>ws://127.0.0.1:8765/v1/realtime</td><td>实时对话上游</td></tr>
        <tr><td><code>VOICE_DEMO_API_KEY</code></td><td>not-needed</td><td>上游鉴权占位</td></tr>
        <tr><td><code>VOICE_DEMO_TTS_VOICE</code> / <code>_TTS_LANGUAGE</code> / <code>_INSTRUCTIONS</code></td><td>Aiden / auto / 工作台助手人设</td><td>TTS 与会话默认值</td></tr>
        <tr><td><code>VOICE_DEMO_CONNECT_TIMEOUT_MS</code> / <code>_READ_TIMEOUT_MS</code> / <code>_WS_IDLE_TIMEOUT_S</code></td><td>5000 / 30000 / 300</td><td>HTTP 超时与 WS 空闲超时</td></tr>
      </tbody>
    </table>

    <h3>真实服务（2026-11-10 已实测，直连）</h3>
    <p>本地 <code>127.0.0.1:8765</code> 同主机提供 OpenAI 兼容 REST 与 <code>/v1/realtime</code>，默认配置即真实全功能：<br />
      ASR：<code>POST /v1/audio/transcriptions</code>（multipart file+language）→ <code>{"text","language"}</code>（language 为语言名，如 "Chinese"）；<br />
      TTS：<code>POST /v1/audio/speech</code>（JSON input/voice/response_format，仅 wav，无 speed 字段）→ WAV 字节；voice=Aiden 实测有效；<br />
      WS 容器内 E2E：<code>docker exec speech-to-speech-thirdparty-pipeline-1 python3 /tmp/e2e_realtime_test.py --url ws://127.0.0.1:8765/v1/realtime --audio /tmp/prompt.wav --out-dir /tmp/e2e --timeout 90</code>。</p>

    <h3>主题</h3>
    <p>浅色 / 深色 / 紫色（Catppuccin，与超级智能体一致；内部 key 为 purple）三套主题可切换（顶栏下拉），与控制台一致：<code>&lt;html data-theme="light|dark|purple"&gt;</code> + <code>localStorage['app-theme']</code>，默认浅色。复用 <code>useAppStore().setTheme()</code> 与 <code>styles/tokens.css</code> 三套皮肤变量，不另建主题机制。</p>

    <h3>已知限制与风险</h3>
    <ul>
      <li>s2s 为<b>单实例串行</b>（pool size 1）：多用户并发需排队或扩容（后端桥接层并发闸门，抢不到回 UPSTREAM_BUSY）。</li>
      <li>会话上下文由 s2s 服务端持有，<b>无持久化</b>：刷新即新会话；如需落库沿用 duplex 既有会话存储方案（P1）。</li>
      <li>浏览器兼容：Chrome / Edge ≥ 110（AudioWorklet）；Electron 下需核对麦克风权限；无 WebRTC fallback（预留）。</li>
      <li>音色固定为服务端 speaker 集；speed / response_format 服务端暂未生效（实测仅 wav）。</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
// 静态手册页：内容 1:1 自原型 docs/prototypes/voice-demo-preview.html 手册 Tab 迁移
</script>

<style scoped>
.guide h3 { margin: 20px 0 10px; font-size: 15px; }
.guide p, .guide li { font-size: 13px; line-height: 1.7; color: var(--fg); }
.guide code { background: var(--bg-subtle); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.seg { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.seg th, .seg td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
.seg th { background: var(--bg-subtle); }
.flow { padding-left: 18px; }
</style>
