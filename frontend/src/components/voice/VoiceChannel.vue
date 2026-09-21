<template>
  <div class="voice-channel">
    <a-card title="调解语音通道（实时 RTC）" class="channel-card">
      <VoiceToolbar
        :status="status"
        :mic-on="micOn"
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
import { ref } from 'vue'
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
