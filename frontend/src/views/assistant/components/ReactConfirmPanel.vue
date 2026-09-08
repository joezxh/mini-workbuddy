<template>
  <div class="react-confirm-panel">
    <div class="rcp-question">{{ question }}</div>
    <a-radio-group v-if="options?.length" v-model:value="selectedValue" class="rcp-options">
      <a-radio v-for="opt in options" :key="opt.value" :value="opt.value" class="rcp-option">
        <span class="rcp-option-label">{{ opt.label }}</span>
        <span v-if="opt.description" class="rcp-option-desc">{{ opt.description }}</span>
      </a-radio>
    </a-radio-group>
    <a-textarea
      v-if="allowCustom"
      v-model:value="customInput"
      placeholder="或输入自定义回答..."
      :auto-size="{ minRows: 2, maxRows: 4 }"
      class="rcp-custom-input"
    />
    <div class="rcp-actions">
      <a-button type="primary" size="small" @click="handleConfirm">
        <CheckOutlined /> {{ $t('react.confirm_approve') }}
      </a-button>
      <a-button size="small" @click="$emit('skip')">
        <ForwardOutlined /> {{ $t('react.confirm_skip') }}
      </a-button>
      <a-button size="small" danger @click="$emit('cancel')">
        <CloseOutlined /> {{ $t('react.confirm_cancel') }}
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { CheckOutlined, ForwardOutlined, CloseOutlined } from '@ant-design/icons-vue'

defineProps<{
  question: string
  options?: Array<{ label: string; value: string; description?: string }>
  allowCustom?: boolean
}>()

const emit = defineEmits<{
  (e: 'confirm', value: string, action: string): void
  (e: 'skip'): void
  (e: 'cancel'): void
}>()

const selectedValue = ref('')
const customInput = ref('')

function handleConfirm() {
  const value = customInput.value || selectedValue.value || ''
  emit('confirm', value, 'confirm')
}
</script>

<style scoped lang="less">
.react-confirm-panel {
  border: 1px solid var(--accent-soft); border-radius: 10px;
  background: var(--bg-surface); padding: 12px 16px; margin: 4px 0;
}
.rcp-question {
  font-size: 14px; font-weight: 600; color: var(--fg);
  margin-bottom: 10px; line-height: 1.5;
}
.rcp-options { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.rcp-option { align-items: flex-start; }
.rcp-option-label { font-size: 13px; color: var(--fg); }
.rcp-option-desc { display: block; font-size: 12px; color: var(--fg-secondary); margin-top: 2px; }
.rcp-custom-input { margin-bottom: 10px; }
.rcp-actions { display: flex; gap: 8px; }
</style>
