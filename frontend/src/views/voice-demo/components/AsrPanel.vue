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
        <!-- 录音电平波形（VAD 每帧 RMS；停止后归零静止） -->
        <VoiceWaveform v-if="rec.isRecording.value" :level="rec.level.value" class="rec-wave" />
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
      尚未转写。上传音频或录音后点「转写」。<br />
      <span class="muted">POST /api/v1/voice-demo/asr/transcribe（multipart）→ {text, language, cost_ms}</span>
    </div>
    <div v-else class="results">
      <div v-for="(seg, i) in segments" :key="i" class="seg-card">
        <div class="seg-meta">
          <span class="muted">#{{ i + 1 }} · {{ seg.startMs }}–{{ seg.endMs }}ms · {{ seg.language }} · {{ seg.costMs }}ms</span>
        </div>
        <div class="seg-cols">
          <div class="seg-col">
            <div class="col-label muted">转写文本</div>
            <div class="seg-text">{{ seg.text }}</div>
          </div>
          <div class="seg-col">
            <div class="col-label muted">纠正结果</div>
            <div v-if="seg.correcting" class="seg-text muted">LLM 纠正中…</div>
            <div v-else-if="seg.correctError" class="seg-text err">{{ seg.correctError }}</div>
            <div v-else class="seg-text">{{ seg.corrected || '—' }}</div>
          </div>
        </div>
      </div>

      <!-- 全部录音停止后：各段原文拼接 → LLM 整体纠正 -->
      <div v-if="fullCorrected || fullCorrecting || fullError" class="full-card">
        <div class="col-label">全部段落整体纠正（各段转写原文拼接后一次送 LLM；超长时后端截取前 4000 字符）</div>
        <div v-if="fullCorrecting" class="seg-text muted">LLM 整体纠正中…</div>
        <div v-else-if="fullError" class="seg-text err">{{ fullError }}</div>
        <div v-else class="seg-text">{{ fullCorrected }}</div>
      </div>
    </div>

    <div class="note">
      <b>分段时间戳来自客户端 VAD 切段</b>（Silero VAD，静音≈400ms 即切段；不停顿时语音累计满 20s 强制收束送转写；仅按静音切分，不区分说话人），逐段送转写后追加；REST 服务仅返回
      <code>{"text","language"}</code>，无服务端分段/说话人。录音模式产出 16kHz mono WAV（Float32→PCM16）。
      每段转写后异步调 <code>/asr/correct</code>（后端默认对话模型）纠正，不阻塞转写流程。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { transcribeAsr, correctAsrText } from '@/api/voiceDemo'
import VoiceWaveform from '@/components/voice/VoiceWaveform.vue'
import { useVadRecorder } from '../composables/useVadRecorder'

interface AsrSegment {
  text: string; language: string; costMs: number; startMs: number; endMs: number
  corrected?: string; correcting?: boolean; correctError?: string
}

const mode = ref<'upload' | 'record'>('upload')
const language = ref('auto')
const file = ref<File | null>(null)
const busy = ref(false)
const segments = ref<AsrSegment[]>([])

// 整体纠正（停止录音后触发）
const fullCorrected = ref('')
const fullCorrecting = ref(false)
const fullError = ref('')
const pendingSegs = ref(0) // 在途分段转写数：停止录音时末段可能还在飞，整体纠正需等其落定
let fullPending = false
watch(pendingSegs, () => {
  if (fullPending && pendingSegs.value === 0) { fullPending = false; void correctAll() }
})

function correctErrMsg(e: any): string {
  return e?.response?.data?.detail?.message || e?.message || '纠正失败'
}

/** 单段异步纠正（不阻塞转写流程） */
async function correctSegment(seg: AsrSegment) {
  if (!seg.text?.trim()) return
  seg.correcting = true
  seg.correctError = ''
  try {
    const r = await correctAsrText(seg.text)
    seg.corrected = r.text
  } catch (e: any) {
    seg.correctError = correctErrMsg(e)
  } finally {
    seg.correcting = false
  }
}

/** 各段转写原文拼接 → 一次整体纠正 */
async function correctAll() {
  const full = segments.value.map(s => s.text).filter(Boolean).join('\n')
  if (!full.trim()) return
  fullCorrecting.value = true
  fullError.value = ''
  try {
    fullCorrected.value = (await correctAsrText(full)).text
  } catch (e: any) {
    fullError.value = correctErrMsg(e)
  } finally {
    fullCorrecting.value = false
  }
}

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
    void correctSegment(segments.value.at(-1)!)
  } catch (e: any) {
    message.error(e?.response?.data?.detail?.message || e?.message || '转写失败')
  } finally {
    busy.value = false
  }
}

const rec = useVadRecorder({
  onSegment: async (blob, startMs, endMs) => {
    // 逐段送转写并追加结果卡（分段起止 ms 来自客户端 VAD）
    pendingSegs.value++
    try {
      const form = new FormData()
      form.append('file', blob, `segment-${startMs}.wav`)
      form.append('language', language.value)
      const r = await transcribeAsr(form)
      segments.value.push({ ...r, costMs: r.cost_ms, startMs, endMs })
      void correctSegment(segments.value.at(-1)!)
    } catch (e: any) {
      message.error(e?.response?.data?.detail?.message || e?.message || '分段转写失败')
    } finally {
      pendingSegs.value--
    }
  },
})

async function toggleRec() {
  if (rec.isRecording.value) {
    rec.stop()
    // 全部录音停止：在途分段落定后自动发起一次整体纠正（各段原文拼接）
    if (segments.value.length) {
      fullPending = true
      if (pendingSegs.value === 0) { fullPending = false; void correctAll() }
    }
  } else {
    try {
      await rec.start()
    } catch (e: any) {
      message.error(e?.message || '无法访问麦克风（需授权，且浏览器需支持 AudioWorklet）')
    }
  }
}
</script>

<style scoped>
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.rec-wave { margin-top: 8px; min-width: 220px; max-width: 420px; }
.f { display: block; font-size: 12px; color: var(--fg-secondary, var(--text-2, #5a6b80)); margin-bottom: 5px; }
.muted { color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 12px; }
select { border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 7px; padding: 5px 10px; font-size: 13px; color: var(--fg, var(--text)); background: var(--bg-input, #fff); }
.empty { border: 1px dashed var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 26px; text-align: center; color: var(--fg-muted, var(--text-3, #9ca3af)); font-size: 13px; }
.results { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.seg-card { border: 1px solid var(--border, var(--line, #d9d9d9)); border-radius: 8px; padding: 10px 12px; background: var(--bg-subtle, #fafafa); }
.seg-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 4px; }
.seg-col { min-width: 0; }
.col-label { font-size: 12px; margin-bottom: 3px; }
.seg-text { font-size: 13.5px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.seg-text.err { color: var(--danger, #e6554d); }
.full-card { border: 1px solid var(--accent, var(--primary, #4aa3ff)); border-radius: 8px; padding: 12px 14px; background: var(--accent-soft, var(--primary-weak, #eaf4ff)); }
.full-card .col-label { font-weight: 600; color: var(--fg, var(--text)); }
@media (max-width: 760px) { .seg-cols { grid-template-columns: 1fr; } }
.note { border-left: 3px solid var(--accent, var(--primary, #4aa3ff)); background: var(--bg-subtle, #fafafa); padding: 10px 14px; border-radius: 0 8px 8px 0; color: var(--fg-secondary, var(--text-2, #5a6b80)); font-size: 12.5px; margin-top: 14px; line-height: 1.7; }
.note b { color: var(--fg, var(--text)); }
code { background: var(--bg-subtle, #f0f0f0); border-radius: 4px; padding: 1px 6px; font-family: var(--font-mono, monospace); font-size: 12px; }
</style>
