<template>
  <div class="voice-main">
    <div class="panel-title">
      <span class="dot" :class="{ active: status === 'open' }"></span>
      语音通道 (VoiceChannel)
    </div>

    <div class="voice-stage" :class="stageState">
      <div class="agent-ring">
        <div class="ring"></div>
        <div class="ring" :class="{ active: status === 'open' }"></div>
        <div class="core">{{ agentIcon }}</div>
      </div>
      <div class="agent-label">
        <div class="name">{{ activeAgentName }}</div>
        <div class="status-text">{{ statusText }}</div>
      </div>
      <div class="waveform">
        <div
          v-for="i in 24"
          :key="i"
          class="bar"
          :style="{ height: barHeight(i) + 'px' }"
        ></div>
      </div>
    </div>

    <div class="transcript-area">
      <div
        v-for="t in transcripts"
        :key="t.id"
        class="turn"
        :class="t.role"
      >
        <div class="role">
          <span class="tag">{{ t.role === 'user' ? '客户' : activeAgentName }}</span>
          <span class="time">{{ formatTime(t.started_at) }}</span>
        </div>
        <div class="text">{{ t.text }}</div>
      </div>
      <div v-if="!transcripts.length" class="empty-hint">
        点击「开启麦克风」开始对话，或在下方输入文字
      </div>
    </div>

    <div class="controls">
      <a-button v-if="status !== 'open'" type="primary" @click="emit('connect')">
        🔌 连接
      </a-button>
      <a-button v-else danger @click="emit('disconnect')">⏹ 断开</a-button>

      <a-button
        :type="micOn ? 'default' : 'primary'"
        :disabled="status !== 'open'"
        @click="emit('toggleMic')"
      >
        {{ micOn ? '🎤 关闭麦克风' : '🎤 开启麦克风' }}
      </a-button>

      <a-button :disabled="status !== 'open'" @click="emit('interrupt')">
        ⏹ 打断
      </a-button>

      <a-input
        :value="textInput"
        placeholder="输入文字与助手对话，回车发送"
        style="flex: 1; max-width: 360px"
        :disabled="status !== 'open'"
        @update:value="(v: string) => emit('update:textInput', v)"
        @pressEnter="submitText"
      />
      <a-button type="primary" :disabled="status !== 'open' || !textInput.trim()" @click="submitText">
        发送
      </a-button>

      <span v-if="ready" class="caps">
        {{ ready.input_sample_rate }}/{{ ready.output_sample_rate }}Hz · {{ ready.vad_mode }}
      </span>
    </div>

    <a-alert v-if="errorMsg" type="error" :message="errorMsg" show-icon class="error-alert" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { VoiceTurn, VoiceReadyPayload } from '@/types/voice'
import type { ChannelStatus } from '@/composables/useVoiceChannel'

const props = defineProps<{
  status: ChannelStatus
  ready: VoiceReadyPayload | null
  errorMsg: string | null
  transcripts: VoiceTurn[]
  audioLevel: number
  micOn: boolean
  activeAgentName: string
  agentIcon: string
  textInput: string
}>()

const emit = defineEmits<{
  connect: []
  disconnect: []
  toggleMic: []
  interrupt: []
  sendText: [text: string]
  'update:textInput': [value: string]
}>()

const statusText = computed(() => {
  const map: Record<string, string> = {
    idle: '待机中 · 等待语音输入',
    connecting: '连接中...',
    open: props.micOn ? '正在聆听...' : '已连接 · 点击麦克风开始',
    closed: '已断开',
    error: '连接错误',
  }
  return map[props.status] || props.status
})

const stageState = computed(() => {
  if (props.status === 'open' && props.micOn) return 'listening'
  if (props.status === 'open') return 'speaking'
  return ''
})

function barHeight(i: number): number {
  if (props.status !== 'open' || !props.micOn) return 4
  const base = Math.sin(Date.now() / 200 + i * 0.5) * 0.5 + 0.5
  return 4 + base * props.audioLevel * 30
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return ''
  }
}

function submitText() {
  const text = props.textInput.trim()
  if (!text) return
  emit('sendText', text)
}
</script>

<style scoped>
.voice-main {
  display: flex;
  flex-direction: column;
  height: 400px;
}
.panel-title {
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #374151;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.panel-title .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6b7280;
}
.panel-title .dot.active {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.voice-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px;
  background: radial-gradient(ellipse at center, rgba(99, 102, 241, 0.08) 0%, transparent 70%);
}
.agent-ring {
  position: relative;
  width: 92px;
  height: 92px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.agent-ring .ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid #374151;
}
.agent-ring .ring.active {
  border-color: #6366f1;
  animation: spin 4s linear infinite;
  border-top-color: transparent;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.agent-ring .core {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 0 24px rgba(99, 102, 241, 0.4);
  transition: transform 0.3s;
}
.voice-stage.listening .core {
  transform: scale(1.1);
  box-shadow: 0 0 36px rgba(16, 185, 129, 0.6);
}
.agent-label {
  margin-top: 8px;
  text-align: center;
}
.agent-label .name {
  font-size: 15px;
  font-weight: 600;
  color: #e5e7eb;
}
.agent-label .status-text {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.waveform {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 26px;
  margin-top: 8px;
}
.waveform .bar {
  width: 3px;
  background: #6366f1;
  border-radius: 2px;
  transition: height 0.1s;
}
.transcript-area {
  max-height: 140px;
  overflow-y: auto;
  padding: 8px 12px;
  border-top: 1px solid #374151;
  background: rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
}
.turn {
  margin-bottom: 6px;
}
.turn .role {
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.turn .role .tag {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  background: #1f2937;
}
.turn.user .role .tag {
  background: #3b82f6;
  color: white;
}
.turn.assistant .role .tag {
  background: #6366f1;
  color: white;
}
.turn .text {
  font-size: 13px;
  line-height: 1.6;
  padding: 6px 10px;
  background: #1f2937;
  border-radius: 8px;
  display: inline-block;
  max-width: 85%;
}
.turn.assistant .text {
  background: rgba(99, 102, 241, 0.15);
}
.empty-hint {
  text-align: center;
  color: #6b7280;
  font-size: 13px;
  padding: 20px;
}
.controls {
  padding: 8px 12px;
  border-top: 1px solid #374151;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.caps {
  margin-left: auto;
  font-size: 11px;
  color: #6b7280;
  font-family: monospace;
}
.error-alert {
  margin: 8px 12px 10px;
}
</style>
