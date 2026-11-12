<template>
  <div class="voice-channel">
    <a-card title="调解语音通道（实时 RTC）" class="channel-card">
      <VoiceToolbar
        :status="status"
        :mic-on="micOn"
        :mic-state="micState"
        @connect="connect"
        @disconnect="disconnect"
        @toggle-mic="onToggleMic"
        @interrupt="sendInterrupt"
      />

      <div class="wave-row">
        <VoiceWaveform :level="audioLevel" />
        <span v-if="ready" class="caps">
          采样率 {{ ready.input_sample_rate }}/{{ ready.output_sample_rate }} · VAD: {{ ready.vad_mode }}
        </span>
      </div>

      <!-- 当前活跃 Agent 状态（编排器热切换时实时更新） -->
      <div class="agent-status-bar">
        <span class="agent-label">当前 Agent：</span>
        <a-tag :color="agentColor">{{ activeAgent.name }}</a-tag>
        <span class="agent-key">({{ activeAgent.key }})</span>
      </div>

      <a-alert v-if="errorMsg" type="error" :message="errorMsg" class="error" show-icon />

      <div class="input-row">
        <a-input-search
          v-model:value="textInput"
          placeholder="输入文字与调解员对话，回车发送"
          enter-button="发送"
          :disabled="status !== 'open'"
          @search="onSendText"
        />
      </div>

      <TurnTimeline
        :turns="transcripts"
        :tool-calls="toolCallList"
        :pending-confirms="pendingConfirms"
        @confirm="onToolConfirm"
      />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useVoiceChannel } from '@/composables/useVoiceChannel'
import type { VoiceProvider } from '@/types/voice'
import VoiceToolbar from './VoiceToolbar.vue'
import VoiceWaveform from './VoiceWaveform.vue'
import TurnTimeline from './TurnTimeline.vue'

const props = withDefaults(
  defineProps<{
    caseNumber: string
    participantId?: string
    provider?: VoiceProvider
    agentId?: string
    modelId?: number
  }>(),
  { participantId: 'party_a', provider: 'dashscope' },
)

const {
  status,
  ready,
  errorMsg,
  transcripts,
  audioLevel,
  micOn,
  micState,
  activeAgent,
  toolCalls,
  connect,
  disconnect,
  sendInterrupt,
  sendText,
  respondToolConfirm,
  startMic,
  stopMic,
} = useVoiceChannel({
  caseNumber: props.caseNumber,
  participantId: props.participantId,
  provider: props.provider,
  agentId: props.agentId,
  modelId: props.modelId,
})

const toolCallList = toolCalls.calls
const pendingConfirms = toolCalls.pending

// 不同 Agent 用不同颜色标签展示
const agentColorMap: Record<string, string> = {
  ecommerce_sales: 'blue',
  product_catalog: 'cyan',
  cross_border: 'purple',
  marketing: 'orange',
  dispute_resolution: 'red',
}
const agentColor = computed(() => agentColorMap[activeAgent.value.key] || 'default')

function onToolConfirm(id: string, approved: boolean) {
  respondToolConfirm(id, approved)
}

const textInput = ref('')
function onSendText() {
  const t = textInput.value.trim()
  if (!t) return
  sendText(t)
  textInput.value = ''
}

function onToggleMic() {
  if (micOn.value) stopMic()
  else void startMic()
}
</script>

<style scoped>
.voice-channel {
  width: 100%;
  max-width: 100%;
}
.channel-card {
  width: 100%;
}
.wave-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.agent-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 6px;
}
.agent-label {
  font-size: 13px;
  color: #8c8c8c;
}
.agent-key {
  font-size: 12px;
  color: #8c8c8c;
  font-family: monospace;
}
.caps {
  color: #8c8c8c;
  font-size: 12px;
}
.input-row {
  margin-top: 12px;
}
.error {
  margin-top: 12px;
}
</style>
