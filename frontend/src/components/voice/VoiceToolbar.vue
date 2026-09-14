<template>
  <a-space wrap>
    <a-button v-if="status !== 'open'" type="primary" @click="$emit('connect')">连接</a-button>
    <a-button v-else danger @click="$emit('disconnect')">断开</a-button>
    <a-button :type="micOn ? 'default' : 'dashed'" @click="$emit('toggleMic')">
      {{ micOn ? '关闭麦克风' : '开启麦克风' }}
    </a-button>
    <a-button :disabled="status !== 'open'" @click="$emit('interrupt')">打断</a-button>
    <a-tag :color="statusColor">{{ statusText }}</a-tag>
  </a-space>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChannelStatus } from '@/composables/useVoiceChannel'

const props = defineProps<{ status: ChannelStatus; micOn: boolean }>()
defineEmits<{ connect: []; disconnect: []; toggleMic: []; interrupt: [] }>()

const statusText = computed(
  () =>
    ({
      idle: '空闲',
      connecting: '连接中',
      open: '已连接',
      closed: '已断开',
      error: '错误',
    }[props.status]),
)
const statusColor = computed(
  () =>
    ({
      idle: 'default',
      connecting: 'processing',
      open: 'success',
      closed: 'default',
      error: 'error',
    }[props.status]),
)
</script>
