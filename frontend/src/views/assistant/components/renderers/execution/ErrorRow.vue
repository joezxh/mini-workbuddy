<template>
  <div class="error-row">
    <div class="error-row-header" @click="expanded = !expanded">
      <XCircle :size="14" class="error-icon" />
      <span class="error-label">{{ error.message || '执行错误' }}</span>
      <ChevronRight v-if="error.traceback" :size="14" class="error-chevron" :class="{ open: expanded }" />
    </div>
    <transition name="expand">
      <pre v-if="expanded && error.traceback" class="error-traceback">{{ error.traceback }}</pre>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { XCircle, ChevronRight } from '@lucide/vue'

defineProps<{ error: { message: string; traceback?: string; recovered?: boolean } }>()
const expanded = ref(false)
</script>

<style scoped lang="less">
.error-row { font-size: 13px; }
.error-row-header {
  display: flex; align-items: center; gap: 6px; padding: 6px 10px;
  cursor: pointer; color: var(--err); &:hover { background: var(--err-soft); }
}
.error-icon { flex-shrink: 0; }
.error-label { flex: 1; font-weight: 500; }
.error-chevron { transition: transform 0.2s; color: var(--fg-muted); &.open { transform: rotate(90deg); } }
.error-traceback {
  margin: 0 10px 8px 30px; padding: 8px; background: var(--err-soft); border: 1px solid #ffccc7;
  border-radius: 4px; font-size: 11px; color: var(--err); overflow-x: auto; white-space: pre-wrap;
}
.expand-enter-active, .expand-leave-active { transition: all 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; }
.expand-enter-to, .expand-leave-from { opacity: 1; max-height: 300px; }
</style>
