<template>
  <div class="tts-panel">
    <div class="field">
      <label class="f">待合成文本</label>
      <textarea v-model="text" rows="3">你好，我是 MiniWorkBuddy 语音助手。今天有三项待办，需要我按时间顺序为你读一遍吗？</textarea>
    </div>
    <div class="row" style="align-items: flex-end; margin-bottom: 12px">
      <div style="min-width: 230px">
        <label class="f">音色 voice</label>
        <a-select v-model:value="voice" style="width: 100%">
          <a-select-opt-group v-for="(names, lang) in VOICES_BY_LANG" :key="lang" :label="lang">
            <a-select-option v-for="v in names" :key="v" :value="v">{{ v }}</a-select-option>
          </a-select-opt-group>
          <a-select-option value="__custom__">自定义…</a-select-option>
        </a-select>
      </div>
      <div v-if="voice === '__custom__'" style="min-width: 170px">
        <label class="f">自定义音色名</label>
        <a-input v-model:value="customVoice" placeholder="custom-speaker" />
      </div>
      <div>
        <label class="f">
          语速 speed
          <a-tag color="warning" style="font-size: 10px">服务端暂未生效</a-tag>
        </label>
        <input type="range" min="0.5" max="2" step="0.1" value="1" disabled />
        <span class="muted">1.0×</span>
      </div>
      <div>
        <label class="f">
          格式
          <a-tag color="warning" style="font-size: 10px">恒输出 WAV</a-tag>
        </label>
        <span class="muted">wav</span>
      </div>
      <a-button type="primary" :loading="busy" @click="runTts">合成并播放</a-button>
    </div>

    <div v-if="!audioUrl" class="empty">
      尚未合成。<span class="muted">POST /api/v1/voice-demo/tts/synthesize → audio/wav blob</span>
    </div>
    <div v-else class="result">
      <audio :src="audioUrl" controls />
      <a :href="audioUrl" download="tts.wav" class="dl">下载 tts.wav</a>
    </div>

    <div class="note">
      真实链路：后端代理转发至 s2s 兼容端点（<code>POST /v1/audio/speech</code>），返回 <b>24kHz mono WAV</b>
      字节，前端 blob 播放 / 下载，不落盘。实测仅支持 wav、无 speed 字段（UI 已置灰标注）。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { synthesizeTts, VOICES_BY_LANG } from '@/api/voiceDemo'

const text = ref('你好，我是 MiniWorkBuddy 语音助手。今天有三项待办，需要我按时间顺序为你读一遍吗？')
const voice = ref('Aiden')
const customVoice = ref('')
const busy = ref(false)
const audioUrl = ref('')

function effectiveVoice(): string {
  return voice.value === '__custom__' ? (customVoice.value.trim() || 'Aiden') : voice.value
}

async function runTts() {
  const t = text.value.trim()
  if (!t) { message.warning('请输入待合成文本'); return }
  busy.value = true
  try {
    const blob = await synthesizeTts({ text: t, voice: effectiveVoice() })
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = URL.createObjectURL(blob)
  } catch (e: any) {
    message.error(e?.response?.data?.detail?.message || e?.message || '合成失败')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.f { display: block; font-size: 12px; color: var(--fg-secondary, var(--text-2, #5a6b80)); margin-bottom: 5px; }
.muted { color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 12px; }
.field { margin: 10px 0; }
textarea { width: 100%; resize: vertical; border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 7px; padding: 7px 10px; font-size: 14px; color: var(--fg, var(--text)); background: var(--bg-input, #fff); font-family: inherit; }
.empty { border: 1px dashed var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 26px; text-align: center; color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 13px; }
.result { display: flex; gap: 14px; align-items: center; margin-top: 8px; }
.dl { font-size: 13px; color: var(--accent, var(--primary, #4aa3ff)); }
.note { border-left: 3px solid var(--accent, var(--primary, #4aa3ff)); background: var(--bg-subtle, #fafafa); padding: 10px 14px; border-radius: 0 8px 8px 0; color: var(--fg-secondary, var(--text-2, #5a6b80)); font-size: 12.5px; margin-top: 14px; line-height: 1.7; }
.note b { color: var(--fg, var(--text)); }
code { background: var(--bg-subtle, #f0f0f0); border-radius: 4px; padding: 1px 6px; font-family: var(--font-mono, monospace); font-size: 12px; }
</style>
