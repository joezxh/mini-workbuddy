<template>
  <div class="turn-timeline">
    <a-empty v-if="turns.length === 0 && toolCalls.length === 0" description="暂无对话" />
    <div v-for="t in turns" :key="t.id" class="turn-item" :class="t.role">
      <span class="role">{{ roleLabel(t.role) }}</span>
      <span class="text">{{ t.text || '（静音/无文本）' }}</span>
    </div>
    <div v-for="c in toolCalls" :key="c.id" class="tool-item">
      <a-tag :color="c.ok ? 'green' : 'red'">工具</a-tag>
      <span class="name">{{ c.name }}</span>
      <span v-if="!c.ok" class="err">调用失败：{{ c.error }}</span>
      <span v-else class="ok">已返回</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { VoiceTurn, ToolCall } from '@/types/voice'

defineProps<{ turns: VoiceTurn[]; toolCalls: ToolCall[] }>()

function roleLabel(r: string): string {
  return (
    { user: '当事人', assistant: '调解员', system: '系统', party_a: '甲方', party_b: '乙方' }[r] ||
    r
  )
}
</script>

<style scoped>
.turn-timeline {
  margin-top: 12px;
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.turn-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.turn-item .role {
  flex: 0 0 56px;
  color: #8c8c8c;
  font-size: 12px;
}
.turn-item.assistant .role {
  color: #1677ff;
}
.turn-item .text {
  background: #f5f7fa;
  padding: 6px 10px;
  border-radius: 8px;
  flex: 1;
}
.tool-item {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}
.tool-item .err {
  color: #cf1322;
}
.tool-item .ok {
  color: #389e0d;
}
</style>
