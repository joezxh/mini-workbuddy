<template>
  <div class="hitl-confirm-panel">
    <div class="hcp-header">
      <span class="hcp-badge"><SafetyCertificateOutlined /> 人工确认（HITL）</span>
      <span v-if="timeoutMinutes" class="hcp-timeout">超时 {{ timeoutMinutes }} 分钟自动拒绝</span>
    </div>

    <div class="hcp-tools">
      <div v-for="tc in toolCalls" :key="tc.id" class="hcp-tool">
        <div class="hcp-tool-name">
          <code>{{ tc.name }}</code>
          <span v-if="tc.id" class="hcp-tool-id">#{{ tc.id }}</span>
        </div>
        <pre class="hcp-tool-input">{{ formatInput(tc.input) }}</pre>
        <div v-if="tc.suggested_rules?.length" class="hcp-rules">
          <a-tag v-for="r in tc.suggested_rules" :key="r" color="gold">{{ r }}</a-tag>
        </div>
      </div>
    </div>

    <a-checkbox v-model:checked="acceptRules" class="hcp-accept">
      接受全部建议规则
    </a-checkbox>

    <div class="hcp-actions">
      <a-button type="primary" size="small" :loading="loading" @click="handle('approve')">
        <CheckOutlined /> 通过并继续
      </a-button>
      <a-button size="small" danger :loading="loading" @click="handle('reject')">
        <CloseOutlined /> 拒绝
      </a-button>
      <a-button size="small" :loading="loading" @click="handle('interrupt')">
        <StopOutlined /> 中断
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { CheckOutlined, CloseOutlined, StopOutlined, SafetyCertificateOutlined } from '@ant-design/icons-vue'
import type { EventEnvelope, HitlToolCall } from '@/types/agentEvents'
import { confirmExecution } from '@/api/agentExecution'

const props = defineProps<{
  executionId: string
  pause: EventEnvelope
}>()

const emit = defineEmits<{
  (e: 'resolved', action: string): void
}>()

const loading = ref(false)
const acceptRules = ref(false)

const toolCalls = computed<HitlToolCall[]>(() => props.pause.content?.tool_calls || [])
const timeoutMinutes = computed<number | undefined>(() => props.pause.content?.timeout_minutes)

function formatInput(input: unknown): string {
  try {
    return typeof input === 'string' ? input : JSON.stringify(input, null, 2)
  } catch {
    return String(input)
  }
}

async function handle(action: 'approve' | 'reject' | 'interrupt') {
  loading.value = true
  try {
    await confirmExecution(props.executionId, {
      action,
      accept_rules: acceptRules.value,
      tool_calls: toolCalls.value,
    })
    message.success(action === 'approve' ? '已通过，任务继续' : action === 'reject' ? '已拒绝' : '已中断')
    emit('resolved', action)
  } catch (e: any) {
    message.error(`操作失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="less">
.hitl-confirm-panel {
  border: 1px solid var(--accent-soft);
  border-radius: 12px;
  background: var(--bg-surface);
  padding: 14px 16px;
  margin: 6px 0;
}
.hcp-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.hcp-badge { font-weight: 600; color: var(--fg); display: inline-flex; align-items: center; gap: 6px; }
.hcp-timeout { font-size: 12px; color: var(--fg-secondary); }
.hcp-tools { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.hcp-tool { border: 1px solid var(--border-soft); border-radius: 8px; padding: 8px 10px; background: var(--bg-subtle); }
.hcp-tool-name { font-size: 13px; color: var(--fg); margin-bottom: 4px; }
.hcp-tool-id { margin-left: 6px; color: var(--fg-secondary); font-size: 12px; }
.hcp-tool-input {
  margin: 0; font-size: 12px; white-space: pre-wrap; word-break: break-all;
  max-height: 160px; overflow: auto; color: var(--fg-secondary);
}
.hcp-rules { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
.hcp-accept { margin-bottom: 10px; }
.hcp-actions { display: flex; gap: 8px; }
</style>
