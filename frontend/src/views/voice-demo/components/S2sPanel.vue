<template>
  <div class="s2s-panel">
    <div class="archstrip muted">
      浏览器 AudioWorklet / BufferSource <span class="arrow">⇄</span> FastAPI WS 桥接（JWT + 并发闸）
      <span class="arrow">⇄</span> s2s /v1/realtime（Realtime 事件流）
    </div>

    <div class="s2s-grid">
      <!-- 左：对话区 -->
      <div class="chat-col">
        <div class="ctrl-row">
          <a-button
            :type="connected ? 'default' : 'primary'"
            :danger="connected"
            @click="connected ? s2s.disconnect() : s2s.connect()"
          >
            {{ connected ? '■ 结束对话' : '● 开始对话' }}
          </a-button>
          <a-button :disabled="!connected || s2s.state.value !== 'responding'" @click="s2s.interrupt()">打断</a-button>
          <a-button :disabled="!connected" @click="s2s.micActive.value ? s2s.stopMic() : s2s.startMic().catch(() => message.error('无法访问麦克风'))">
            {{ s2s.micActive.value ? '🎙 关闭麦克风' : '🎙 开启麦克风' }}
          </a-button>
          <a-tag :color="stateColor">{{ stateLabel }}</a-tag>
          <span class="muted">轮次 {{ turnCount }}</span>
        </div>

        <div ref="chatBox" class="chat">
          <div v-if="!s2s.messages.value.length" class="empty muted">
            尚无对话。开启「开始对话」后可通过麦克风说话，或在下方输入模拟发言（Mock/真实模式均可）。
          </div>
          <div v-for="(m, i) in s2s.messages.value" :key="i" class="bubble" :class="m.role">
            <span v-if="m.partial" class="partial-mark">…</span>
            <span :class="{ partial: m.partial }">{{ m.text }}</span>
            <span v-if="m.interrupted" class="interrupted-mark">（已打断）</span>
          </div>
        </div>

        <div class="simbox">
          <a-input
            v-model:value="simText"
            placeholder="模拟一句语音（文字直通 input_text，触发回复）"
            @press-enter="sendSim"
          />
          <a-button type="primary" :disabled="!connected" @click="sendSim">发送</a-button>
        </div>
        <div class="muted status-line">
          状态机：idle → connecting → listening ⇄ responding → closed；服务端 VAD speech_started 于 responding 时自动打断。
        </div>
      </div>

      <!-- 右：事件流 -->
      <div class="log-col">
        <div class="log-title">事件流（新事件在上）</div>
        <div class="eventlog">
          <div v-for="(e, i) in logReverse" :key="i" class="evt" :class="e.dir">
            <span class="dir">{{ e.dir === 'in' ? '↓' : '↑' }}</span>
            <span class="etype">{{ e.type }}</span>
            <span class="muted at">{{ fmtAt(e.at) }}</span>
          </div>
          <div v-if="!s2s.events.value.length" class="muted">暂无事件</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useRealtimeS2s } from '../composables/useRealtimeS2s'

const s2s = useRealtimeS2s()
const simText = ref('')
const chatBox = ref<HTMLElement | null>(null)

const connected = computed(() => s2s.state.value !== 'idle' && s2s.state.value !== 'closed')
const stateLabel = computed(() => ({
  idle: '未连接', connecting: '连接中…', listening: '聆听中', responding: '回复中', closed: '已断开',
}[s2s.state.value]))
const stateColor = computed(() => ({
  idle: 'default', connecting: 'processing', listening: 'success', responding: 'warning', closed: 'default',
}[s2s.state.value]))
const turnCount = computed(() => s2s.events.value.filter(e => e.dir === 'in' && e.type === 'response.created').length)
const logReverse = computed(() => [...s2s.events.value].reverse())

// 新消息自动滚底
watch(() => s2s.messages.value.length, async () => {
  await nextTick()
  chatBox.value?.scrollTo({ top: chatBox.value.scrollHeight })
})

function sendSim() {
  const t = simText.value.trim()
  if (!t || !connected.value) return
  s2s.sendSimText(t)
  simText.value = ''
}

function fmtAt(at: number): string {
  const d = new Date(at)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}
</script>

<style scoped>
.s2s-panel { display: flex; flex-direction: column; gap: 12px; }
.archstrip { border: 1px dashed var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 8px 12px; font-size: 12px; text-align: center; }
.arrow { color: var(--accent, var(--primary, #4aa3ff)); margin: 0 6px; }
.s2s-grid { display: grid; grid-template-columns: 1fr 320px; gap: 12px; min-height: 380px; }
.ctrl-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.muted { color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 12px; }
.chat { border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 12px; height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; background: var(--bg-subtle, #fafafa); }
.empty { margin: auto; text-align: center; }
.bubble { max-width: 78%; padding: 8px 12px; border-radius: 12px; font-size: 13.5px; line-height: 1.6; background: var(--bg-input, #fff); border: 1px solid var(--border, var(--line, #e5e7eb)); align-self: flex-start; white-space: pre-wrap; }
.bubble.user { align-self: flex-end; background: var(--accent-soft, var(--primary-weak, #eaf4ff)); }
.partial { font-style: italic; opacity: 0.75; }
.partial-mark { color: var(--accent, var(--primary, #4aa3ff)); margin-right: 4px; }
.interrupted-mark { color: var(--danger, #e6554d); font-size: 12px; margin-left: 6px; }
.simbox { display: flex; gap: 8px; margin-top: 10px; }
.status-line { margin-top: 6px; }
.log-col { display: flex; flex-direction: column; border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 8px; overflow: hidden; }
.log-title { padding: 8px 12px; font-size: 12px; color: var(--fg-secondary, var(--text-2, #5a6b80)); background: var(--bg-subtle, #fafafa); border-bottom: 1px solid var(--border, var(--line, #eee)); }
.eventlog { padding: 8px 10px; overflow-y: auto; flex: 1; max-height: 380px; font-family: var(--font-mono, monospace); font-size: 11.5px; }
.evt { display: flex; gap: 6px; padding: 2px 0; }
.evt .dir { width: 14px; }
.evt.in .dir { color: var(--success, #34a853); }
.evt.out .dir { color: var(--accent, var(--primary, #4aa3ff)); }
.etype { flex: 1; word-break: break-all; }
.at { white-space: nowrap; }
@media (max-width: 900px) { .s2s-grid { grid-template-columns: 1fr; } }
</style>
