<template>
  <a-space wrap>
    <a-button v-if="status !== 'open'" type="primary" @click="$emit('connect')">连接</a-button>
    <a-button v-else danger @click="$emit('disconnect')">断开</a-button>
    <a-button :type="micOn ? 'default' : 'dashed'" @click="$emit('toggleMic')">
      {{ micOn ? '关闭麦克风' : '开启麦克风' }}
    </a-button>
    <a-button :disabled="status !== 'open'" @click="$emit('interrupt')">打断</a-button>
    <a-tag :color="statusColor">{{ statusText }}</a-tag>
    <a-tag v-if="micTag" :color="micTag!.color">{{ micTag!.text }}</a-tag>
  </a-space>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChannelStatus } from '@/composables/useVoiceChannel'
import type { MicState } from '@/composables/useMicLifecycle'
import { classifyMicError } from '@/composables/useMicLifecycle'

const props = defineProps<{
  status: ChannelStatus
  micOn: boolean
  micState?: MicState | null
}>()
defineEmits<{ connect: []; disconnect: []; toggleMic: []; interrupt: [] }>()

const statusText = computed(
  () =>
    ({
      idle: '空闲',
      connecting: '连接中',
      open: '已连接',
      closed: '已断开',
      error: '错误',
    })[props.status],
)
const statusColor = computed(
  () =>
    ({
      idle: 'default',
      connecting: 'processing',
      open: 'success',
      closed: 'default',
      error: 'error',
    })[props.status],
)

/** 麦克风韧性状态徽标（recovering/unavailable；ready 不显示） */
const micTag = computed<{ color: string; text: string } | null>(() => {
  const s = props.micState
  if (!s || s.state === 'ready' || s.state === 'starting') return null
  if (s.state === 'recovering') return { color: 'processing', text: '麦克风恢复中…' }
  const kind = s.error ? classifyMicError(s.error) : 'unknown'
  const reasonText =
    ({
      permission_denied: '权限被拒',
      device_missing: '设备缺失',
      device_unavailable: '设备占用',
      unsupported: '不支持',
      unknown: '未知原因',
    })[kind] || '未知原因'
  return { color: 'error', text: `麦克风不可用：${reasonText}` }
})
</script>
