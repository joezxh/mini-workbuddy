/**
 * 状态标签组件
 */
<template>
  <a-tag :color="tagColor">
    {{ tagText }}
  </a-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  status: string
  type?: 'event' | 'disposal' | 'deduction'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'event'
})

const tagColor = computed(() => {
  const colorMaps: Record<string, Record<string, string>> = {
    event: {
      pending: 'orange',       // 待处理 - 橙色，提示需要关注
      processing: '#1677ff',   // 处理中 - 蓝色，进行中
      resolved: 'success',     // 已解决 - 绿色，正向完成
      closed: '#8c8c8c'        // 已关闭 - 中性灰，终态
    },
    disposal: {
      pending: 'default',
      assigned: 'blue',
      processing: 'processing',
      completed: 'success',
      closed: 'default'
    },
    deduction: {
      pending: 'default',
      running: 'processing',
      completed: 'success',
      failed: 'error'
    }
  }
  return colorMaps[props.type]?.[props.status] || 'default'
})

const tagText = computed(() => {
  const textMaps: Record<string, Record<string, string>> = {
    event: {
      pending: '待处理',
      processing: '处理中',
      resolved: '已解决',
      closed: '已关闭'
    },
    disposal: {
      pending: '待分配',
      assigned: '已分配',
      processing: '处理中',
      completed: '已完成',
      closed: '已关闭'
    },
    deduction: {
      pending: '待执行',
      running: '执行中',
      completed: '已完成',
      failed: '失败'
    }
  }
  return textMaps[props.type]?.[props.status] || props.status
})
</script>

