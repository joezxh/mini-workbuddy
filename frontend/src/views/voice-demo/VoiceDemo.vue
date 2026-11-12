<template>
  <div class="voice-demo app-page">
    <a-card>
      <div class="vd-head">
        <div>
          <h2>语音能力演示</h2>
          <div class="vd-desc">后端 FastAPI 代理 / WS 桥接 · speech-to-speech（VAD→STT→LLM→TTS）· 直连真实服务</div>
        </div>
        <div class="vd-pills">
          <a-tag :color="health?.pool ? 'success' : 'error'">
            {{ health?.pool ? '上游已连接' : '上游未连接' }}
          </a-tag>
          <a-tag>BASE: {{ health?.base_url || '—' }}</a-tag>
          <a-tooltip title="切换深色/浅色主题（useAppStore）">
            <a-button size="small" @click="app.toggleTheme()">{{ app.isDark ? '☀️ 浅色' : '🌙 深色' }}</a-button>
          </a-tooltip>
        </div>
      </div>
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="asr" tab="📝 语音转写（ASR）"><AsrPanel /></a-tab-pane>
        <a-tab-pane key="tts" tab="🔊 语音合成（TTS）"><TtsPanel /></a-tab-pane>
        <a-tab-pane key="s2s" tab="🗣 语音对话（实时 S2S）"><S2sPanel /></a-tab-pane>
        <a-tab-pane key="guide" tab="📖 使用手册"><GuidePanel /></a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAppStore } from '@/stores/app'
import { getVoiceDemoHealth, type VoiceDemoHealth } from '@/api/voiceDemo'
import AsrPanel from './components/AsrPanel.vue'
import TtsPanel from './components/TtsPanel.vue'
import S2sPanel from './components/S2sPanel.vue'
import GuidePanel from './components/GuidePanel.vue'

const app = useAppStore()
const activeTab = ref('asr') // D2：ASR 默认选中
const health = ref<VoiceDemoHealth | null>(null)
onMounted(async () => { try { health.value = await getVoiceDemoHealth() } catch { /* 未探测到时展示占位 */ } })
</script>

<style scoped>
/* 铺满主布局右栏（.app-page：height 100% + overflow auto 超长滚动）；卡片纵向撑满 */
.voice-demo { max-width: none; margin: 0; }
.voice-demo :deep(.ant-card) { flex: 1 1 auto; min-height: 0; }
.vd-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.vd-desc { color: var(--fg-secondary); font-size: 13px; }
.vd-pills { display: flex; gap: 8px; align-items: center; }
</style>
