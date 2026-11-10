<template>
  <div class="asr-panel">
    <div class="row" style="align-items: flex-end; margin-bottom: 12px">
      <div>
        <label class="f">音频来源</label>
        <div class="row">
          <a-button size="small" :type="mode === 'upload' ? 'primary' : 'default'" @click="mode = 'upload'">上传文件</a-button>
          <a-button size="small" :type="mode === 'record' ? 'primary' : 'default'" @click="mode = 'record'">录音（VAD 分段）</a-button>
        </div>
      </div>
      <div v-if="mode === 'upload'">
        <label class="f">选择音频文件</label>
        <input type="file" accept="audio/*" @change="onFile" />
      </div>
      <div v-else>
        <label class="f">麦克风录音</label>
        <div class="row">
          <a-button size="small" :type="rec.isRecording.value ? 'default' : 'primary'" :danger="rec.isRecording.value" @click="toggleRec">
            {{ rec.isRecording.value ? '■ 停止录音' : '● 开始录音' }}
          </a-button>
          <span class="muted">{{ rec.isRecording.value ? '录音中，说话后停顿即自动分段转写' : '未录音' }}</span>
        </div>
      </div>
      <div>
        <label class="f">语言</label>
        <select v-model="language">
          <option value="auto">auto</option>
          <option value="zh">中文</option>
          <option value="en">English</option>
        </select>
      </div>
      <a-button type="primary" :loading="busy" :disabled="mode === 'upload' && !file" @click="runUpload">转写</a-button>
    </div>

    <div v-if="!segments.length" class="empty">
      尚未转写。上传音频或录音后点「转写」（Mock 下使用样例数据）。<br />
      <span class="muted">POST /api/v1/voice-demo/asr/transcribe（multipart）→ {text, language, cost_ms}</span>
    </div>
    <div v-else class="results">
      <div v-for="(seg, i) in segments" :key="i" class="seg-card">
        <div class="seg-meta">
          <span class="muted">#{{ i + 1 }} · {{ seg.startMs }}–{{ seg.endMs }}ms · {{ seg.language }} · {{ seg.costMs }}ms</span>
        </div>
        <div class="seg-text">{{ seg.text }}</div>
      </div>
    </div>

    <div class="note">
      <b>分段时间戳来自客户端 VAD 切段</b>（Silero VAD，redemption≈700ms），逐段送转写后追加；REST 服务仅返回
      <code>{"text","language"}</code>，无服务端分段/说话人。录音模式产出 16kHz mono WAV（Float32→PCM16）。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { transcribeAsr } from '@/api/voiceDemo'
import { useVadRecorder } from '../composables/useVadRecorder'

interface AsrSegment { text: string; language: string; costMs: number; startMs: number; endMs: number }

const mode = ref<'upload' | 'record'>('upload')
const language = ref('auto')
const file = ref<File | null>(null)
const busy = ref(false)
const segments = ref<AsrSegment[]>([])

function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  file.value = f ?? null
}

async function runUpload() {
  if (!file.value) return
  busy.value = true
  try {
    const form = new FormData()
    form.append('file', file.value)
    form.append('language', language.value)
    const r = await transcribeAsr(form)
    segments.value.push({ ...r, costMs: r.cost_ms, startMs: 0, endMs: 0 })
  } catch (e: any) {
    message.error(e?.response?.data?.detail?.message || e?.message || '转写失败')
  } finally {
    busy.value = false
  }
}

const rec = useVadRecorder({
  onSegment: async (blob, startMs, endMs) => {
    // 逐段送转写并追加结果卡（分段起止 ms 来自客户端 VAD）
    try {
      const form = new FormData()
      form.append('file', blob, `segment-${startMs}.wav`)
      form.append('language', language.value)
      const r = await transcribeAsr(form)
      segments.value.push({ ...r, costMs: r.cost_ms, startMs, endMs })
    } catch (e: any) {
      message.error(e?.response?.data?.detail?.message || e?.message || '分段转写失败')
    }
  },
})

async function toggleRec() {
  if (rec.isRecording.value) {
    rec.stop()
  } else {
    try {
      await rec.start()
    } catch {
      message.error('无法访问麦克风（需授权，且浏览器需支持 AudioWorklet）')
    }
  }
}
</script>

<style scoped>
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.f { display: block; font-size: 12px; color: var(--fg-secondary, var(--text-2, #5a6b80)); margin-bottom: 5px; }
.muted { color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 12px; }
select { border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 7px; padding: 5px 10px; font-size: 13px; color: var(--fg, var(--text)); background: var(--bg-input, #fff); }
.empty { border: 1px dashed var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 26px; text-align: center; color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 13px; }
.results { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.seg-card { border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 10px 12px; background: var(--bg-subtle, #fafafa); }
.seg-text { font-size: 13.5px; line-height: 1.65; margin-top: 4px; }
.note { border-left: 3px solid var(--accent, var(--primary, #4aa3ff)); background: var(--bg-subtle, #fafafa); padding: 10px 14px; border-radius: 0 8px 8px 0; color: var(--fg-secondary, var(--text-2, #5a6b80)); font-size: 12.5px; margin-top: 14px; line-height: 1.7; }
.note b { color: var(--fg, var(--text)); }
code { background: var(--bg-subtle, #f0f0f0); border-radius: 4px; padding: 1px 6px; font-family: var(--font-mono, monospace); font-size: 12px; }
</style>
