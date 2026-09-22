<template>
  <div class="turn-timeline">
    <a-empty v-if="turns.length === 0 && toolCalls.length === 0 && pendingConfirms.length === 0" description="暂无对话" />
    <div v-for="t in turns" :key="t.id" class="turn-item" :class="t.role">
      <span class="role">{{ roleLabel(t.role) }}</span>
      <span class="text">{{ t.text || '（静音/无文本）' }}</span>
    </div>
    <div v-for="c in pendingConfirms" :key="c.id" class="confirm-card">
      <div class="confirm-title">
        <a-tag color="orange">待确认</a-tag>
        <span class="name">{{ c.name }}</span>
      </div>
      <pre class="confirm-args">{{ JSON.stringify(c.arguments, null, 2) }}</pre>
      <div class="confirm-actions">
        <a-button size="small" type="primary" @click="$emit('confirm', c.id, true)">同意</a-button>
        <a-button size="small" danger @click="$emit('confirm', c.id, false)">拒绝</a-button>
      </div>
    </div>
    <div v-for="c in toolCalls" :key="c.id" class="tool-item">
      <a-tag :color="tagColor(c)">工具</a-tag>
      <span class="name">{{ c.name }}</span>
      <span v-if="c.ok === false" class="err">调用失败：{{ c.error }}</span>
      <span v-else-if="c.ok" class="ok">已返回</span>
      <span v-else class="running">执行中…</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { VoiceTurn, ToolCall } from '@/types/voice'

withDefaults(
  defineProps<{ turns: VoiceTurn[]; toolCalls: ToolCall[]; pendingConfirms?: ToolCall[] }>(),
  { pendingConfirms: () => [] },
)

defineEmits<{ (e: 'confirm', id: string, approved: boolean): void }>()

function roleLabel(r: string): string {
  return (
    { user: '当事人', assistant: '调解员', system: '系统', party_a: '甲方', party_b: '乙方' }[r] ||
    r
  )
}

function tagColor(c: ToolCall): string {
  if (c.ok === true) return 'green'
  if (c.ok === false) return 'red'
  return 'blue'
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
.tool-item .running {
  color: #1677ff;
}
.confirm-card {
  border: 1px solid #ffd591;
  background: #fffbe6;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
}
.confirm-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.confirm-title .name {
  font-weight: 600;
}
.confirm-args {
  margin: 6px 0;
  font-size: 12px;
  background: #fff;
  border-radius: 6px;
  padding: 6px 8px;
  max-height: 120px;
  overflow: auto;
}
.confirm-actions {
  display: flex;
  gap: 8px;
}
</style>
