<template>
  <div class="panel io-panel">
    <div class="io-head">
      <span class="src">数据源：<b>{{ sourceLabel }}</b></span>
      <span class="spacer"></span>
      <a-button v-if="isHistory" size="small" @click="emit('backToLive')">↩ 返回当前语音会话</a-button>
    </div>

    <a-alert v-if="error" type="error" :message="error" show-icon class="io-error" />

    <div v-else-if="loading" class="io-loading">加载消息中...</div>

    <div v-else class="io-grid">
      <div class="io-col in">
        <h4>🎤 麦克风 STT / 客户输入 <span class="cnt">{{ inputMessages.length }} 条</span></h4>
        <div v-for="m in inputMessages" :key="m.key" class="io-item">
          <div class="meta">
            <span class="tm">{{ m.time }}</span>
            <span :class="['st', m.source === 'history' ? 'cfg' : 'live']">{{ m.statusLabel || (m.source === 'history' ? '用户输入' : 'STT 已定稿') }}</span>
          </div>
          <div class="tx">{{ m.text }}</div>
        </div>
        <div v-if="!inputMessages.length" class="io-empty">暂无客户输入 · 开启麦克风或输入文字开始</div>
      </div>

      <div class="io-col out">
        <h4>🔊 TTS / 助手输出 <span class="cnt">{{ outputMessages.length }} 条</span></h4>
        <div v-for="m in outputMessages" :key="m.key" class="io-item">
          <div class="meta">
            <span class="tm">{{ m.time }}</span>
            <span :class="['vst', voiceStatusClass(m.voiceStatus)]">{{ voiceStatusLabel(m.voiceStatus) }}</span>
            <span v-if="m.channelTargets?.length" class="target">→ {{ m.channelTargets.join(' · ') }}</span>
          </div>
          <div class="tx">{{ m.text }}</div>
        </div>
        <div v-if="!outputMessages.length" class="io-empty">暂无助手输出 · 等待回复生成</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IoMessage, VoiceStatus } from '../types'

defineProps<{
  sourceLabel: string
  isHistory: boolean
  loading: boolean
  error: string | null
  inputMessages: IoMessage[]
  outputMessages: IoMessage[]
}>()

const emit = defineEmits<{ backToLive: [] }>()

function voiceStatusClass(s?: VoiceStatus): string {
  return s || 'none'
}

function voiceStatusLabel(s?: VoiceStatus): string {
  const map: Record<VoiceStatus, string> = {
    playing: '● 播放中',
    done: '播放完成',
    none: '无语音',
    failed: '发送失败',
  }
  return map[s || 'none']
}
</script>

<style scoped>
.io-panel {
  grid-column: 1 / -1;
}
.io-head {
  padding: 8px 14px;
  border-bottom: 1px solid #374151;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.io-head .src {
  font-size: 12px;
  color: #9ca3af;
}
.io-head .src b {
  color: #818cf8;
}
.io-head .spacer {
  flex: 1;
}
.io-error {
  margin: 10px 14px;
}
.io-loading {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 30px 0;
}
.io-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}
.io-col {
  padding: 11px 14px;
  min-height: 150px;
  max-height: 210px;
  overflow-y: auto;
}
.io-col + .io-col {
  border-left: 1px solid #374151;
}
.io-col h4 {
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 9px;
}
.io-col.in h4 {
  color: #93c5fd;
}
.io-col.out h4 {
  color: #c4b5fd;
}
.io-col h4 .cnt {
  margin-left: auto;
  font-size: 10px;
  color: #6b7280;
  font-weight: 400;
}
.io-item {
  padding: 7px 9px;
  border-radius: 8px;
  margin-bottom: 6px;
  background: #1f2937;
  font-size: 12px;
}
.io-col.in .io-item {
  border-left: 2px solid #3b82f6;
}
.io-col.out .io-item {
  border-left: 2px solid #6366f1;
}
.io-item .meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: #6b7280;
  margin-bottom: 3px;
  flex-wrap: wrap;
}
.io-item .tm {
  font-family: monospace;
}
.io-item .tx {
  color: #e5e7eb;
  word-break: break-word;
}
.io-empty {
  text-align: center;
  color: #6b7280;
  font-size: 12px;
  padding: 30px 0;
}
.st {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 6px;
}
.st.cfg {
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}
.st.live {
  background: rgba(16, 185, 129, 0.14);
  color: #6ee7b7;
}
.vst {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 6px;
}
.vst.playing {
  background: rgba(16, 185, 129, 0.16);
  color: #6ee7b7;
}
.vst.done, .vst.none {
  background: rgba(148, 163, 184, 0.14);
  color: #9ca3af;
}
.vst.failed {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}
.target {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.14);
  color: #818cf8;
}
</style>
